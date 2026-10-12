#!/bin/sh
# github.com/Shran21

set -u
HERE=$(cd "$(dirname "$0")" && pwd)
CHECK=0
SYSTEMD=1
RESTART=1
INPLACE=0
TARGET=""
while [ $# -gt 0 ]; do
    case "$1" in
        --check) CHECK=1 ;;
        --no-systemd) SYSTEMD=0 ;;
        --no-restart) RESTART=0 ;;
        --here) INPLACE=1 ;;
        --dir) shift; TARGET=${1:-}; [ -n "$TARGET" ] || { echo "--dir: missing path"; exit 2; } ;;
        --dir=*) TARGET=${1#--dir=} ;;
        *) echo "unknown flag: $1"; exit 2 ;;
    esac
    shift
done

case "${REBSGO_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in
    hu*|HU*|magyar*|Hungarian*) NYELV=hu ;;
    *) NYELV=en ;;
esac
t() {
    if [ "$NYELV" = hu ]; then printf '%s' "$1"; else printf '%s' "$2"; fi
}

if [ -t 1 ] || [ "${INSTALL_SZINES:-0}" = 1 ]; then
    ZOLD=$(printf '\033[1;32m'); CIAN=$(printf '\033[1;36m')
    PIROS=$(printf '\033[1;31m'); SARGA=$(printf '\033[1;33m')
    VASTAG=$(printf '\033[1m'); VEGE=$(printf '\033[0m')
else
    ZOLD=; CIAN=; PIROS=; SARGA=; VASTAG=; VEGE=
fi

OSSZES_FAZIS=9
FAZIS=0

fazis() {
    FAZIS=$((FAZIS + 1))
    printf '\n%s[%s/%s] %s%s\n' "$CIAN" "$FAZIS" "$OSSZES_FAZIS" "$1" "$VEGE"
}
kesz()  { printf '  %s✔ %s%s\n' "$ZOLD" "$*" "$VEGE"; }
mond()  { printf '    %s\n' "$*"; }
figyel(){ printf '  %s! %s%s\n' "$SARGA" "$*" "$VEGE"; }
fail()  { printf '\n%s✘ %s: %s%s\n' "$PIROS" "$(t 'HIBA' 'ERROR')" "$*" "$VEGE" >&2; exit 1; }

kibonto() {
    _osszes=$(tar tzf "$1" | wc -l)
    mkdir -p "$2"
    tar xzvf "$1" -C "$2" 2>&1 | awk -v ossz="$_osszes" -v zold="$ZOLD" -v vege="$VEGE" '
        BEGIN { split("5 10 20 30 40 50 60 70 80 90 100", hatar, " "); i = 1 }
        {
            n++
            szazalek = int(n * 100 / ossz)
            while (i <= 11 && szazalek >= hatar[i]) {
                sav = ""
                tele = int(hatar[i] / 5)
                for (j = 1; j <= 20; j++) sav = sav (j <= tele ? "#" : ".")
                printf "    [%s] %s%3d%%%s\n", sav, zold, hatar[i], vege
                i++
            }
        }
        END {
            while (i <= 11) {
                printf "    [####################] %s%3d%%%s\n", zold, hatar[i], vege
                i++
            }
        }'
}

printf '%s' "$CIAN"
cat <<'FELIRAT'
              ____  ____   ____  ___
    _ __ ___ | __ )/ ___| / ___|/ _ \
   | '__/ _ \|  _ \\___ \| |  _| | | |
   | | |  __/| |_) |___) | |_| | |_| |
   |_|  \___||____/|____/ \____|\___/
FELIRAT
printf '%s' "$VEGE"
printf '            %s@ S H R A N 2 1%s\n' "$SARGA" "$VEGE"
printf '            %sgithub.com/Shran21%s\n' "$CIAN" "$VEGE"
printf '   %s%s%s — %s\n' "$VASTAG" "$(t 'telepítő' 'installer')" "$VEGE" "$HERE"
if [ "$CHECK" = 1 ]; then
    figyel "$(t 'ellenőrző mód: semmi nem változik' 'check mode: nothing is changed')"
elif [ "$INPLACE" = 0 ]; then
    sleep 5
fi

fazis "$(t 'Célmappa — hova kerüljön a szerver?' 'Target directory — where should the server live?')"
if [ "$INPLACE" = 1 ]; then
    TARGET="$HERE"
elif [ -z "$TARGET" ]; then
    if [ -t 0 ]; then
        mond "$(t 'Enter = marad itt:' 'Enter = stays here:') $HERE"
        printf '    %s: ' "$(t 'célmappa' 'target directory')"
        read -r VALASZ || VALASZ=""
        TARGET=${VALASZ:-$HERE}
    else
        TARGET="$HERE"
        mond "$(t 'nincs terminál, nem kérdezek: marad itt' 'no terminal, no question asked: it stays here')"
    fi
fi
case "$TARGET" in
    "~") TARGET="$HOME" ;;
    "~/"*) TARGET="$HOME/${TARGET#\~/}" ;;
esac
case "$TARGET" in /*) : ;; *) TARGET="$PWD/$TARGET" ;; esac
if [ "$CHECK" = 0 ]; then
    mkdir -p "$TARGET" || fail "$(t 'a célmappa nem hozható létre:' 'the target directory cannot be created:') $TARGET"
fi
[ -d "$TARGET" ] && TARGET=$(cd "$TARGET" && pwd)
if [ "$TARGET" = "$HERE" ]; then
    kesz "$(t 'helyben marad:' 'staying in place:') $HERE"
elif [ "$CHECK" = 1 ]; then
    mond "$(t '(átmásolná ide, és onnan folytatná:' '(it would copy the tree here and carry on from there:') $TARGET)"
else
    mond "$(t 'másolás:' 'copying:') $HERE -> $TARGET"
    KIHAGY="--exclude=./runtime --exclude=./WebPanel/venv --exclude=./logs"
    KIHAGY="$KIHAGY --exclude=./WebPanel/logs --exclude=./cache --exclude=./.git --exclude=__pycache__"
    for ALLAPOT in .env sqlite GameData/local WebPanel/panel.env; do
        [ -e "$TARGET/$ALLAPOT" ] && KIHAGY="$KIHAGY --exclude=./$ALLAPOT"
    done
    # shellcheck disable=SC2086
    ( cd "$HERE" && tar $KIHAGY -cf - . ) | tar -xf - -C "$TARGET" \
        || fail "$(t 'a másolás elakadt' 'the copy failed')"
    kesz "$(t 'átmásolva; a telepítés az új helyről folytatódik' 'copied; the installation carries on from the new place')"
    TOVABB="--here"
    [ "$SYSTEMD" = 0 ] && TOVABB="$TOVABB --no-systemd"
    [ "$RESTART" = 0 ] && TOVABB="$TOVABB --no-restart"
    # shellcheck disable=SC2086
    exec sh "$TARGET/install.sh" $TOVABB
fi
ROOT="$TARGET"

fazis "$(t 'Python — az értelmező' 'Python — the interpreter')"
GEP=$(uname -m)
# A Python 3.11 or newer that really starts here: one built for another
# processor (the bundled x86_64 one on an ARM machine) is executable on paper
# and fails on every call.
fut() { "$1" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; }
PYTHON="$ROOT/runtime/python/bin/python3"
TARBALL=$(ls "$ROOT"/vendor/python/cpython-*.tar.gz 2>/dev/null | head -1)
if fut "$PYTHON"; then
    kesz "$(t 'már ki van bontva:' 'already unpacked:') $("$PYTHON" -V 2>&1)"
elif [ -n "$TARBALL" ] && case "$(basename "$TARBALL")" in *"-$GEP-"*) true ;; *) false ;; esac; then
    mond "$(t 'kibontás:' 'unpacking:') $(basename "$TARBALL")"
    if [ "$CHECK" = 0 ]; then
        rm -rf "$ROOT/runtime/python"
        kibonto "$TARBALL" "$ROOT/runtime"
        fut "$PYTHON" || fail "$(t 'a kibontott értelmező nem indul' 'the unpacked interpreter does not start')"
        kesz "$(t 'kész:' 'done:') $("$PYTHON" -V 2>&1)"
    else
        mond "$(t '(kibontaná ide: runtime/)' '(it would unpack into runtime/)')"
    fi
else
    if [ -n "$TARBALL" ]; then
        figyel "$(t "a csomagolt értelmező másik processzorra készült, ez a gép $GEP - a rendszer python3-at használom" "the bundled interpreter was built for another processor, this machine is $GEP - using the system python3")"
    else
        figyel "$(t 'nincs csomagolt értelmező; a rendszer python3-ra váltok' 'no bundled interpreter; falling back to the system python3')"
    fi
    if [ -e "$ROOT/runtime/python" ] && [ "$CHECK" = 0 ]; then
        rm -rf "$ROOT/runtime/python"
        mond "$(t 'egy korábbi futás itt nem induló értelmezője törölve: runtime/python' "an earlier run's interpreter that does not start here was removed: runtime/python")"
    fi
    PYTHON=$(command -v python3) \
        || fail "$(t 'ezen a gépen nincs python3 - telepítsd: apt install python3 python3-venv' 'this machine has no python3 - install it: apt install python3 python3-venv')"
    fut "$PYTHON" \
        || fail "$(t "3.11 vagy újabb Python kell, ez: $("$PYTHON" -V 2>&1)" "Python 3.11 or newer is needed, this one is: $("$PYTHON" -V 2>&1)")"
    kesz "$(t 'rendszer-értelmező:' 'system interpreter:') $PYTHON, $("$PYTHON" -V 2>&1)"
fi
NATIV_ITT=0
ls "$ROOT"/native/lib/rebsgo_native*"-$GEP-"*.so >/dev/null 2>&1 && NATIV_ITT=1
if [ "$NATIV_ITT" = 1 ] && fut "$PYTHON"; then
    case "$("$PYTHON" -V 2>&1)" in
        *" 3.13."*) : ;;
        *) figyel "$(t 'a natív modul cp313-ra épült; más verzióval a gyorsítás kimarad' 'the native module was built for cp313; another version leaves the acceleration out')" ;;
    esac
fi

fazis "$(t 'Szerverfa és mappák' 'The server tree and its directories')"
[ -d "$ROOT/src/rebsgo" ] || fail "$(t 'src/rebsgo hiányzik - ez nem egy szerverfa?' 'src/rebsgo is missing - is this a server tree?')"
if [ "$NATIV_ITT" = 1 ]; then
    kesz "$(t 'natív gyorsítómodul: megvan (native/lib)' 'native accelerator module: present (native/lib)')"
elif ls "$ROOT"/native/lib/rebsgo_native*.so >/dev/null 2>&1; then
    figyel "$(t "a natív modul másik processzorra készült ($GEP-re nincs) - tiszta-python tartalékon fut (lassabb, de teljes)" "the native module was built for another processor (none for $GEP) - running on the pure-python fallback (slower, but complete)")"
else
    figyel "$(t 'natív modul nincs - tiszta-python tartalékon fut (lassabb, de teljes)' 'no native module - running on the pure-python fallback (slower, but complete)')"
fi
if [ "$CHECK" = 0 ]; then
    mkdir -p "$ROOT/logs" "$ROOT/sqlite" "$ROOT/WebPanel/logs"
fi
kesz "$(t 'mappák: logs/ sqlite/ WebPanel/logs/' 'directories: logs/ sqlite/ WebPanel/logs/')"
# GitHub's upload page and a Windows checkout both drop the execute bit, and
# systemd will not start WebPanel/run.sh without it.
if [ "$CHECK" = 0 ]; then
    chmod +x "$ROOT/install.sh" "$ROOT/uninstall.sh" "$ROOT/WebPanel/run.sh" "$ROOT"/tools/*.py 2>/dev/null
    kesz "$(t 'futtatható: install.sh, uninstall.sh, WebPanel/run.sh, tools/*.py' 'executable: install.sh, uninstall.sh, WebPanel/run.sh, tools/*.py')"
else
    mond "$(t '(futtathatóvá tenné: install.sh, uninstall.sh, WebPanel/run.sh, tools/*.py)' '(it would make these executable: install.sh, uninstall.sh, WebPanel/run.sh, tools/*.py)')"
fi

fazis "$(t 'Beállítások (.env)' 'Settings (.env)')"
if [ ! -f "$ROOT/.env" ]; then
    mond "$(t 'nincs .env - készítem a .env.example-ből, friss panel-tokennel' 'no .env - writing one from .env.example, with a fresh panel token')"
    if [ "$CHECK" = 0 ]; then
        TOKEN=$("$PYTHON" -c "import secrets; print(secrets.token_urlsafe(32))")
        [ -n "$TOKEN" ] || fail "$(t 'nem sikerült panel-tokent készíteni' 'could not make a panel token')"
        cp "$ROOT/.env.example" "$ROOT/.env" 2>/dev/null || touch "$ROOT/.env"
        printf '\nREBSGO_PANEL_TOKEN=%s\nREBSGO_NET_PANEL_DOOR_PORT=27053\n' "$TOKEN" >> "$ROOT/.env"
        chmod 600 "$ROOT/.env"
        kesz "$(t '.env elkészült, a panel-token friss; csak a tulajdonosa olvashatja' '.env written, with a fresh panel token; readable by its owner only')"
    else
        mond "$(t '(elkészítené)' '(it would write one)')"
    fi
# An interrupted earlier run can leave .env with an empty token, and the
# panel door does not open without one.
elif [ -z "$(sed -n 's/^REBSGO_PANEL_TOKEN=//p' "$ROOT/.env" | tail -1)" ]; then
    if [ "$CHECK" = 0 ]; then
        TOKEN=$("$PYTHON" -c "import secrets; print(secrets.token_urlsafe(32))")
        [ -n "$TOKEN" ] || fail "$(t 'nem sikerült panel-tokent készíteni' 'could not make a panel token')"
        printf '\nREBSGO_PANEL_TOKEN=%s\n' "$TOKEN" >> "$ROOT/.env"
        kesz "$(t '.env már van, de panel-token nélkül - friss tokent írtam bele' '.env is there, but without a panel token - a fresh one is written into it')"
    else
        mond "$(t '(a .env-ből hiányzik a panel-token - pótolná)' '(.env has no panel token - it would add one)')"
    fi
else
    kesz "$(t '.env már van - nem nyúlok hozzá' '.env is already there - left untouched')"
fi
# At the server's own default every sector simulates at full speed even with
# nobody in it, and a small machine cannot keep up with that. A setting the
# operator made, either way, stays as it is.
if grep -qE '^(REBSGO_SECTOR_GATING_MODE|REBSGO_SECTOR_EMPTY_GATING)=.' "$ROOT/.env" 2>/dev/null; then
    kesz "$(t 'szektor-altatás: a .env saját beállítása marad' 'sector gating: the setting in .env stays')"
elif [ "$CHECK" = 1 ]; then
    mond "$(t '(bekapcsolná a szektor-altatást: REBSGO_SECTOR_GATING_MODE=idle)' '(it would switch sector gating on: REBSGO_SECTOR_GATING_MODE=idle)')"
else
    printf '\n# %s\nREBSGO_SECTOR_GATING_MODE=idle\n' \
        "empty sectors sleep, a player arriving wakes them; off = every sector simulates all the time" >> "$ROOT/.env"
    kesz "$(t 'szektor-altatás bekapcsolva: az üres szektorok alszanak (REBSGO_SECTOR_GATING_MODE=idle)' 'sector gating switched on: empty sectors sleep (REBSGO_SECTOR_GATING_MODE=idle)')"
    mond "$(t 'kikapcsolás: REBSGO_SECTOR_GATING_MODE=off a .env-ben, majd a bsgo újraindítása' 'to switch it off: REBSGO_SECTOR_GATING_MODE=off in .env, then restart bsgo')"
fi

fazis "$(t 'Gyorspróba — betölt-e a szerverkód, él-e a natív gyorsítás' 'Quick check — does the server code load, is the native acceleration live')"
if [ "$CHECK" = 1 ]; then
    mond "$(t '(lefuttatná)' '(it would run this)')"
else
    ( cd "$ROOT" && PYTHONPATH="$ROOT/src" "$PYTHON" -c '
import rebsgo.main  # import binds no ports; a broken tree fails right here
from rebsgo.native import hotpath
raise SystemExit(0 if hotpath._native is not None else 3)
' )
    RC=$?
    case "$RC" in
        0) kesz "$(t 'a szerver kódja betölt; a natív gyorsítómodul aktív' 'the server code loads; the native accelerator module is active')" ;;
        3) kesz "$(t 'a szerver kódja betölt' 'the server code loads')"
           figyel "$(t 'a natív modul nem töltődött be - tiszta-python tartalékon fut' 'the native module did not load - running on the pure-python fallback')" ;;
        *) fail "$(t 'a szerver kódja nem tölt be - hiányos vagy sérült fa?' 'the server code does not load - an incomplete or damaged tree?')" ;;
    esac
fi

fazis "$(t 'Launcher — az exe és a fájllista útvonalai' 'Launcher — the exe and the file-list paths')"
if [ -f "$ROOT/launcher/rebsgo-launcher.exe" ]; then
    kesz "$(t 'launcher/rebsgo-launcher.exe - ezt kapják a játékosok' 'launcher/rebsgo-launcher.exe - this is what the players get')"
else
    figyel "$(t 'nincs launcher/rebsgo-launcher.exe ebben a fában' 'there is no launcher/rebsgo-launcher.exe in this tree')"
fi
kulcs() { sed -n "s/^$1=//p" "$ROOT/.env" 2>/dev/null | tail -1; }
for NEV in REBSGO_LAUNCHER_MANIFEST_DIR REBSGO_LAUNCHER_CLIENT_DIR; do
    ERTEK=$(kulcs "$NEV")
    [ -n "$ERTEK" ] || continue
    case "$ERTEK" in /*) UT="$ERTEK" ;; *) UT="$ROOT/$ERTEK" ;; esac
    if [ -d "$UT" ]; then
        kesz "$NEV: $(t 'megvan' 'present')"
    else
        figyel "$(t "$NEV a .env-ben erre mutat, de nincs meg:" "$NEV in .env points here, but it does not exist:") $ERTEK"
        figyel "$(t '  (generálás: tools/gen_launcher_manifests.py; kulcs nélkül nincs fájllista)' '  (generate it with tools/gen_launcher_manifests.py; without the keys there is no file list)')"
    fi
done

fazis "$(t 'Webpanel — venv a csomagolt wheel-ekből' 'WebPanel — a venv from the bundled wheels')"
VENV="$ROOT/WebPanel/venv"
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
    kesz "$(t 'a venv már fel van építve' 'the venv is already built')"
elif [ "$CHECK" = 0 ]; then
    rm -rf "$VENV"
    DARAB=$(ls "$ROOT"/WebPanel/vendor/wheels/*.whl 2>/dev/null | wc -l)
    mond "$(t "venv létrehozása, majd a panel csomagjai: elsőként a hozott $DARAB wheel, hálózat nélkül" "creating the venv, then the panel's packages: the $DARAB bundled wheels first, with no network")"
    "$PYTHON" -m venv "$VENV" \
        || fail "$(t 'a venv létrehozása nem sikerült (Debianon, Ubuntun: apt install python3-venv)' 'the venv could not be created (on Debian, Ubuntu: apt install python3-venv)')"
    # The bundled wheels are built for x86_64 and Python 3.13. Anywhere else,
    # whatever does not fit comes from PyPI.
    if "$VENV/bin/pip" install --quiet --disable-pip-version-check --no-index \
            --find-links "$ROOT/WebPanel/vendor/wheels" \
            -r "$ROOT/WebPanel/requirements.txt" 2>/dev/null; then
        kesz "$(t 'a panel venv-je kész' "the panel's venv is ready")"
    else
        figyel "$(t "a hozott wheel-ek nem mind illenek ehhez a géphez ($GEP) - a többit a PyPI-ról töltöm le" "not all bundled wheels fit this machine ($GEP) - fetching the rest from PyPI")"
        "$VENV/bin/pip" install --quiet --disable-pip-version-check \
            --find-links "$ROOT/WebPanel/vendor/wheels" \
            -r "$ROOT/WebPanel/requirements.txt" \
            || fail "$(t 'a wheel-telepítés elakadt - van hálózat?' 'the wheel install failed - is there a network?')"
        kesz "$(t 'a panel venv-je kész' "the panel's venv is ready")"
    fi
else
    mond "$(t '(felépítené a WebPanel/vendor/wheels tartalmából)' '(it would build one from WebPanel/vendor/wheels)')"
fi
# Left to the panel, panel.env is written on its first start - after run.sh has
# already read it, found nothing, and bound to every address until a restart.
PANEL_ENV="$ROOT/WebPanel/panel.env"
if [ -f "$PANEL_ENV" ]; then
    kesz "$(t 'WebPanel/panel.env már van - nem nyúlok hozzá' 'WebPanel/panel.env is already there - left untouched')"
elif [ "$CHECK" = 1 ]; then
    mond "$(t '(elkészítené a WebPanel/panel.env-et: a panel csak erről a gépről nyílna)' '(it would write WebPanel/panel.env: the panel would open from this machine only)')"
elif ( cd "$ROOT/WebPanel" && REBSGO_LANG="$NYELV" "$VENV/bin/python" -c 'from panel import settings; settings.raw()' ) \
        && [ -f "$PANEL_ENV" ]; then
    chmod 600 "$PANEL_ENV"
    kesz "$(t 'WebPanel/panel.env elkészült: a panel csak erről a gépről nyílik (PANEL_HOST=127.0.0.1)' 'WebPanel/panel.env written: the panel opens from this machine only (PANEL_HOST=127.0.0.1)')"
else
    figyel "$(t 'a WebPanel/panel.env nem készült el - az első indításkor minden címen figyel majd' 'WebPanel/panel.env was not written - on its first start the panel will listen on every address')"
fi

fazis "$(t 'Első admin fiók — a WebPanelhez és a fejlesztői jogokhoz' 'The first admin account — for the WebPanel and the developer rights')"
PILOTAK="$ROOT/tools/pilots.py"
POTLAS="\"$PYTHON\" \"$PILOTAK\" create <$(t 'név' 'name')> --grant Developer,Console"
if [ "$CHECK" = 1 ]; then
    ADMIN="$(t '(ellenőrző módban nem néztem meg)' '(not looked at in check mode)')"
    mond "$(t '(ha még nincs Developer szerepű fiók, felajánlaná, hogy most létrehozza)' '(if no account has the Developer role yet, it would offer to make one now)')"
elif "$PYTHON" "$PILOTAK" admins >/dev/null 2>&1; then
    ADMIN="$(t 'már van - a listájuk:' 'already there - to list them:') \"$PYTHON\" \"$PILOTAK\" admins"
    kesz "$(t 'van már Developer szerepű fiók - nem kérdezek' 'an account with the Developer role is already there - no question asked')"
elif [ -t 0 ]; then
    ADMIN="$(t 'még nincs - később:' 'none yet - later:') $POTLAS"
    mond "$(t 'A WebPanelbe csak Developer vagy Console szereppel lehet belépni, fiókot pedig csak' 'Only a Developer or a Console gets into the WebPanel, and only a Developer can make')"
    mond "$(t 'Developer hozhat létre. Ez az első fiók mindkettőt megkapja, és a játékba is ezzel' 'accounts there. This first account gets both, and it signs in to the game as well.')"
    mond "$(t 'lehet belépni. A jelszó legalább 5 karakter. Enter = kihagyás.' 'The password is at least 5 characters. Enter = skip.')"
    PROBA=0
    LETREJOTT=0
    while [ "$PROBA" -lt 3 ]; do
        printf '    %s: ' "$(t 'pilótanév' 'pilot name')"
        read -r NEV || NEV=""
        [ -n "$NEV" ] || break
        if "$PYTHON" "$PILOTAK" create "$NEV" --grant Developer,Console; then
            ADMIN="$NEV (Developer, Console)"
            LETREJOTT=1
            kesz "$(t "kész: $NEV - ezzel lehet belépni a WebPanelbe és a játékba" "done: $NEV - this one signs in to the WebPanel and the game")"
            break
        fi
        PROBA=$((PROBA + 1))
    done
    [ "$LETREJOTT" = 1 ] || figyel "$(t 'nem készült admin fiók - később:' 'no admin account was made - later:') $POTLAS"
else
    ADMIN="$(t 'még nincs - később:' 'none yet - later:') $POTLAS"
    figyel "$(t 'nincs admin fiók, és terminál sincs, hogy megkérdezzem' 'there is no admin account, and no terminal to ask about one')"
    mond "$(t 'később:' 'later:') $POTLAS"
fi

fazis "$(t 'Szolgáltatások — telepítés és indítás' 'Services — installing and starting')"
if [ "$SYSTEMD" = 0 ]; then
    figyel "$(t 'kihagyva kérésre (--no-systemd)' 'skipped on request (--no-systemd)')"
    mond "$(t 'kézi indítás:' 'start by hand:')  cd $ROOT && PYTHONPATH=src $PYTHON -m rebsgo.main"
    mond "$(t 'panel kézzel:' 'panel by hand:')  $ROOT/WebPanel/run.sh"
elif ! command -v systemctl >/dev/null 2>&1; then
    figyel "$(t 'ezen a gépen nincs systemctl - kihagyva' 'this machine has no systemctl - skipped')"
    mond "$(t 'kézi indítás:' 'start by hand:')  cd $ROOT && PYTHONPATH=src $PYTHON -m rebsgo.main"
elif [ "$(id -u)" != 0 ]; then
    figyel "$(t 'nem rootként fut - a szolgáltatás-telepítés kimaradt' 'not running as root - the service installation was skipped')"
    mond "$(t 'rootként újrafuttatva a bsgo és a rebsgo-panel is felkerül és elindul' 'run again as root and both bsgo and rebsgo-panel are installed and started')"
elif [ "$CHECK" = 1 ]; then
    mond "$(t '(telepítené, engedélyezné és elindítaná: bsgo, rebsgo-panel)' '(it would install, enable and start: bsgo, rebsgo-panel)')"
else
    sed -e "s|__ROOT__|$ROOT|g" -e "s|__PYTHON__|$PYTHON|g" -e "s|__LANG__|$NYELV|g" \
        "$ROOT/deploy/bsgo.service.template" > /etc/systemd/system/bsgo.service
    sed -e "s|__PANEL_DIR__|$ROOT/WebPanel|g" -e "s|__LANG__|$NYELV|g" \
        "$ROOT/WebPanel/deploy/rebsgo-panel.service" > /etc/systemd/system/rebsgo-panel.service
    systemctl daemon-reload
    systemctl enable bsgo rebsgo-panel >/dev/null 2>&1
    kesz "$(t 'unitok a helyükön, mindkettő engedélyezve (újraindulás után is felállnak)' 'both units are in place and enabled (they come up after a reboot too)')"
    MAR_FUTOTT=""
    for SZOLGALTATAS in bsgo rebsgo-panel; do
        [ "$(systemctl is-active "$SZOLGALTATAS")" = active ] && MAR_FUTOTT="$MAR_FUTOTT $SZOLGALTATAS"
    done
    # An update only takes over once the services restart; stopping bsgo
    # signs the players out, and on the way out it saves the pilots.
    if [ -n "$MAR_FUTOTT" ] && [ "$RESTART" = 1 ]; then
        mond "$(t "újraindítás, hogy a frissítés életbe lépjen:$MAR_FUTOTT (a bent lévők kilépnek, a pilóták mentődnek)..." "restarting so the update takes over:$MAR_FUTOTT (players inside are signed out, the pilots are saved)...")"
        # shellcheck disable=SC2086
        systemctl restart $MAR_FUTOTT
    else
        mond "$(t 'indítás...' 'starting...')"
    fi
    systemctl start bsgo rebsgo-panel
    sleep 3
    for SZOLGALTATAS in bsgo rebsgo-panel; do
        if [ "$(systemctl is-active "$SZOLGALTATAS")" = active ]; then
            kesz "$SZOLGALTATAS: $(t 'fut' 'running')"
        else
            figyel "$(t "$SZOLGALTATAS nem indult el - napló: journalctl -u $SZOLGALTATAS -e" "$SZOLGALTATAS did not start - log: journalctl -u $SZOLGALTATAS -e")"
        fi
    done
    if [ -n "$MAR_FUTOTT" ] && [ "$RESTART" = 0 ]; then
        figyel "$(t "már előtte is futott:$MAR_FUTOTT - kérésre nem indítottam újra (--no-restart); a frissítés az újraindítás után él" "already running before:$MAR_FUTOTT - not restarted on request (--no-restart); the update takes over after a restart")"
        mond "systemctl restart$MAR_FUTOTT"
        mond "$(t '(a bsgo leállása kilépteti a játékosokat, a pilótákat elmenti)' '(stopping bsgo signs the players out, and saves the pilots)')"
    fi
fi

printf '\n%s%s✔ %s%s\n' "$VASTAG" "$ZOLD" "$(t 'Kész.' 'Done.')" "$VEGE"
mond "$(t 'szerver:         ' 'server:          ')$ROOT"
mond "$(t 'beléptető ajtó:  http://<ez-a-gép>:27051/   (a launcher ide csatlakozik)' 'admission door:  http://<this-machine>:27051/   (the launcher connects here)')"
mond "$(t 'launcher:        ' 'launcher:        ')$ROOT/launcher/rebsgo-launcher.exe"
mond "$(t 'webpanel:        http://<ez-a-gép>:27055/   (hálózati eléréshez a WebPanel/panel.env' 'webpanel:        http://<this-machine>:27055/   (for network access set')"
mond "$(t '                 fájlban PANEL_HOST=0.0.0.0, vagy TLS-proxy mögé)' '                 PANEL_HOST=0.0.0.0 in WebPanel/panel.env, or put it behind a TLS proxy)')"
mond "$(t 'beállítások:     ' 'settings:        ')$ROOT/.env"
mond "$(t 'admin fiók:      ' 'admin account:   ')$ADMIN"
mond "$(t 'eltávolítás:     ' 'uninstall:       ')sh $ROOT/uninstall.sh"
exit 0
