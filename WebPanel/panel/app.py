# github.com/Shran21

from __future__ import annotations

import base64
import logging
import secrets
import shutil
import time
import urllib.parse

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from panel.auth import COOKIE_NAME, Gatekeeper, LoginRefused, Session
from panel.auditlog import record
from panel.bridge import Bridge, uptime_seconds
from panel.db import Database
from panel.i18n import COOKIE as LANG_COOKIE
from panel.i18n import JS_KEYS, LANGS, pick_lang, translator
from panel.settings import ROOT, Settings
from panel.version import VERSION

log = logging.getLogger(__name__)

settings = Settings.load()
gatekeeper = Gatekeeper(settings)
database = Database(settings.db_path)
bridge = Bridge(settings.bridge_url, settings.bridge_token)

app = FastAPI(title="reBSGO Panel", docs_url=None, redoc_url=None, openapi_url=None)
record("panel", "start", outcome="github.com/Shran21")
app.mount("/static", StaticFiles(directory=ROOT / "panel" / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "panel" / "templates")

ASSET_VERSION = "22"

_OPEN_PATHS = ("/login", "/static/", "/favicon.ico", "/lang/")

_FLASH_COOKIE = "panel_flash"
_FLASH_KEYS = ("notice", "error", "detail")


def _session_of(request: Request) -> Session | None:
    ticket = request.cookies.get(COOKIE_NAME)
    return None if ticket is None else gatekeeper.read_ticket(ticket)


def _lang_of(request: Request) -> str:
    return pick_lang(request.cookies.get(LANG_COOKIE), settings.default_lang)


def _over_tls(request: Request) -> bool:
    return (request.url.scheme == "https"
            or request.headers.get("x-forwarded-proto", "").lower() == "https")


def set_cookie(request: Request, response: Response, name: str, value: str, **extra) -> None:
    response.set_cookie(name, value, secure=_over_tls(request), samesite="lax", **extra)


def _flash_to_cookie(request: Request, response: Response) -> None:
    target = response.headers.get("location", "")
    if "?" not in target:
        return
    base, _, query = target.partition("?")
    params = urllib.parse.parse_qsl(query, keep_blank_values=True)
    flash = [(key, value) for key, value in params if key in _FLASH_KEYS and value]
    if not flash:
        return
    rest = [(key, value) for key, value in params if key not in _FLASH_KEYS]
    response.headers["location"] = base + ("?" + urllib.parse.urlencode(rest) if rest else "")
    packed = base64.urlsafe_b64encode(urllib.parse.urlencode(flash).encode("utf-8")).decode("ascii")
    set_cookie(request, response, _FLASH_COOKIE, packed.rstrip("="), max_age=60, httponly=True)


def _flash_of(request: Request) -> dict:
    raw = request.cookies.get(_FLASH_COOKIE)
    if not raw:
        return {}
    try:
        text = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return {}
    return {key: value for key, value in urllib.parse.parse_qsl(text) if key in _FLASH_KEYS}


def _armour(request: Request, response: Response) -> Response:
    nonce = getattr(request.state, "nonce", "")
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "frame-ancestors 'none'; form-action 'self'; base-uri 'self'; object-src 'none'")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if 300 <= response.status_code < 400:
        _flash_to_cookie(request, response)
    return response


@app.middleware("http")
async def _door(request: Request, call_next):
    path = request.url.path
    request.state.lang = _lang_of(request)
    request.state.nonce = secrets.token_urlsafe(12)
    if any(path == open_path or path.startswith(open_path) for open_path in _OPEN_PATHS):
        return _armour(request, await call_next(request))
    session = _session_of(request)
    if session is None:
        return _armour(request, RedirectResponse("/login", status_code=303))
    request.state.session = session
    response = await call_next(request)
    if session.expires - time.time() < settings.session_seconds / 2:
        fresh = Session(session.pilot_id, session.name, session.role_bits,
                        int(time.time()) + settings.session_seconds)
        set_cookie(request, response, COOKIE_NAME, gatekeeper.write_ticket(fresh),
                   max_age=settings.session_seconds, httponly=True)
    return _armour(request, response)


def _errors_new(request: Request) -> int:
    from panel.live import error_state
    try:
        seen = int(request.cookies.get("panel_errseen", "0"))
    except ValueError:
        seen = 0
    return max(0, error_state()["total"] - seen)


def _errors_pending(request: Request) -> bool:
    return _errors_new(request) > 0


def _base_context(request: Request) -> dict:
    session = getattr(request.state, "session", None)
    lang = getattr(request.state, "lang", settings.default_lang)
    t = translator(lang)
    return {
        "session": session,
        "t": t,
        "lang": lang,
        "langs": LANGS,
        "csrf": "" if session is None else gatekeeper.csrf_token(session),
        "nonce": getattr(request.state, "nonce", ""),
        "asset_v": ASSET_VERSION,
        "version": VERSION,
        "js_strings": {key: t(key) for key in JS_KEYS},
    }


def page(request: Request, template: str, **context) -> HTMLResponse:
    flash = _flash_of(request)
    for key in _FLASH_KEYS:
        if not context.get(key) and flash.get(key):
            context[key] = flash[key]
    response = templates.TemplateResponse(request, template, {
        **_base_context(request),
        "error_pending": _errors_pending(request),
        **context})
    if flash:
        response.delete_cookie(_FLASH_COOKIE)
    return response


def csrf_ok(request: Request, token: str) -> bool:
    session = getattr(request.state, "session", None)
    return session is not None and token == gatekeeper.csrf_token(session)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if _session_of(request) is not None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html",
                                      {**_base_context(request), "error": None})


@app.post("/login")
async def login_submit(request: Request, name: str = Form(""), password: str = Form("")):
    origin = request.client.host if request.client else "?"
    lang = _lang_of(request)
    try:
        session = gatekeeper.login(name, password, origin)
    except LoginRefused as refusal:
        record(name or "?", "login", outcome=f"refused ({origin})")
        return templates.TemplateResponse(
            request, "login.html",
            {**_base_context(request), "error": translator(lang)(refusal.message_key)},
            status_code=401)
    record(session.name, "login", outcome=f"ok ({origin})")
    response = RedirectResponse("/", status_code=303)
    set_cookie(request, response, COOKIE_NAME, gatekeeper.write_ticket(session),
               max_age=settings.session_seconds, httponly=True)
    return response


@app.get("/logout")
async def logout(request: Request):
    session = _session_of(request)
    if session is not None:
        record(session.name, "logout")
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/lang/{code}")
async def switch_language(request: Request, code: str):
    back = request.headers.get("referer") or "/"
    response = RedirectResponse(back, status_code=303)
    if code in LANGS:
        set_cookie(request, response, LANG_COOKIE, code, max_age=365 * 24 * 3600, httponly=True)
    return response


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(ROOT / "panel" / "static" / "favicon.svg", media_type="image/svg+xml")


def _health(request: Request) -> dict:
    from panel import backups
    try:
        usage = shutil.disk_usage(str(ROOT))
        disk_free_pct = round(usage.free / usage.total * 100)
    except OSError:
        disk_free_pct = None
    from panel.live import error_state
    last_at = error_state()["last_at"]
    newest = None
    try:
        for entry in backups.db_backups()[:1] + backups.full_backups()[:1]:
            if newest is None or entry["when"] > newest["when"]:
                newest = entry
    except OSError:
        newest = None
    return {"disk_free_pct": disk_free_pct, "errors_new": _errors_new(request),
            "error_last": time.strftime("%m.%d %H:%M", time.localtime(last_at)) if last_at else "",
            "backup": newest}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, notice: str = "", error: str = ""):
    from panel.routes.monitor import online_history
    from panel.sectors import sector_name
    from panel.spark import sparkline
    from rebsgo.vocabulary.pilot import ServerRoles
    live = bridge.status()
    if live:
        live["uptime_s"] = uptime_seconds(live)
    for pilot in (live or {}).get("online", []):
        pilot["sector_name"] = sector_name(pilot.get("sector"))
    busiest = []
    maintenance = None
    if live:
        rows = [row for row in (bridge.sectors() or {}).get("sectors", []) if row.get("players")]
        rows.sort(key=lambda row: (row.get("players", 0), row.get("total", 0)), reverse=True)
        busiest = [{"id": row["id"], "name": sector_name(row["id"]),
                    "players": row.get("players", 0), "npcs": row.get("npcs", 0)}
                   for row in rows[:3]]
        maintenance = bridge.maintenance()
    session = request.state.session
    return page(request, "home.html",
                overview=database.overview(),
                live=live,
                bridge_wired=bridge.has_token,
                may_operate=session.wears(ServerRoles.Developer),
                may_console=session.can_console,
                busiest=busiest,
                maintenance=maintenance,
                health=_health(request),
                spark=sparkline(online_history()),
                notice=notice, error=error)


from panel.routes import users as _users_routes  # noqa: E402
assert _users_routes is not None
from panel.routes import db_browser as _db_routes  # noqa: E402
assert _db_routes is not None
from panel.routes import console as _console_routes  # noqa: E402
assert _console_routes is not None
from panel.routes import logs as _logs_routes  # noqa: E402
assert _logs_routes is not None
from panel.routes import sectors as _sectors_routes  # noqa: E402
assert _sectors_routes is not None
from panel.routes import config as _config_routes  # noqa: E402
assert _config_routes is not None
from panel.routes import gametuning as _gametuning_routes  # noqa: E402
assert _gametuning_routes is not None
from panel import backups as _backups_clock  # noqa: E402
assert _backups_clock is not None
from panel.routes import monitor as _monitor_routes  # noqa: E402
assert _monitor_routes is not None
from panel.routes import tools as _tools_routes  # noqa: E402
assert _tools_routes is not None
from panel.routes import audit as _audit_routes  # noqa: E402
assert _audit_routes is not None
from panel.routes import rankings as _rankings_routes  # noqa: E402
assert _rankings_routes is not None
from panel.routes import economy as _economy_routes  # noqa: E402
assert _economy_routes is not None
from panel.routes import starmap_view as _map_routes  # noqa: E402
assert _map_routes is not None
from panel.routes import search as _search_routes  # noqa: E402
assert _search_routes is not None
from panel import live as _live_routes  # noqa: E402
assert _live_routes is not None
