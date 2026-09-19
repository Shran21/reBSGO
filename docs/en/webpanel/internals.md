[github.com/Shran21](https://github.com/Shran21)

# How the panel is built, and how to debug it

## Two processes, one secret

The panel is a **separate process** from the game server (the
`rebsgo-panel` systemd service, in the `WebPanel/` directory). So restarting
the panel does not touch the game, and a crash of the game does not take the
panel with it.

The two talk over two channels:

1. **Database** — the panel reads the game's SQLite file directly.
2. **Panel door** — a small HTTP server running inside the game server at
   `127.0.0.1:27053` (reachable only from the machine itself). Every
   request carries the shared key kept in `.env` in the `X-Panel-Key`
   header; without the key the door does not even open.

The door's endpoints: `/status`, `/save`, `/console`, `/console/commands`,
`/log`, `/sectors`, `/sector-event`, `/sector-op`, `/sector-restart`,
`/policy-reload`, `/maintenance`, `/rankings-recalc`.

**Why the panel does not write everything straight into the database:**
while a pilot is in the game, their data lives in the server's memory and
their row is overwritten every two minutes. That is why all live state goes
through the door, and why the panel refuses to edit the data of anyone who
is in the game.

## Files

    WebPanel/
      panel/
        app.py           the web application, the login gate, the shared page frame
        auth.py          password checking, tickets, CSRF, attempt limiting
        settings.py      the panel's settings (panel.env + environment)
        db.py            database reads and writes
        bridge.py        the panel door's client
        backups.py       backups (by hand and scheduled) + the backup clock thread
        envfile.py       in-place editing of .env and panel.env
        auditlog.py      the panel's own audit
        i18n.py          Hungarian and English labels
        logfiles.py      the log channels
        sectors.py       sector names from GameData
        gamedata.py      the card data search
        restarter.py     scheduled restart
        policy.py        sector policy
        routes/          one module per tab
        templates/       page templates
        static/          stylesheet, fonts
      panel.env          the panel's own settings (not part of the package)
      logs/panel-audit.log

## Starting and stopping

    systemctl restart rebsgo-panel     restart
    systemctl status rebsgo-panel      is it running
    journalctl -u rebsgo-panel -n 50   the panel's log

The panel can also be restarted from the Configuration tab (the button lets
go of the request first, so the reply still arrives).


## Security headers, one-shot notices, the live channel

Every answer wears a `Content-Security-Policy`: script may only run from the
panel's own files and from the inline blocks marked with the nonce drawn for
that request, framing is forbidden (`frame-ancestors 'none'`), and
`X-Content-Type-Options`, `X-Frame-Options` and `Referrer-Policy` ride along.
Behind TLS (`https`, or `X-Forwarded-Proto: https` from a proxy) the cookies
are marked `Secure`.

A redirect's notice (`?notice=…`, `?error=…`) moves into a one-shot
`panel_flash` cookie at the door and the address stays clean; the next page
shows it, then deletes it.

Live pages hold the `/events` stream (SSE): every three seconds the panel
looks at the game's state and the log files' sizes and sends a `change` or
`logs` event only when something moved, plus a `tick` every twenty seconds.
The monitor receives a full snapshot every five seconds over
`/monitor/events`. Where the stream cannot be held, the browser falls back
to timed fetches.

The game data is read through the server's own data layer
(`rebsgo.gamedata.vfs`): the JSON in a folder tree, the packaged game data in
a shipped one. Sector names, the card search, the star map and the game
tuning work from either; only the folder can be written.

## If something is not working

**"The game server is unreachable" everywhere.** The door is not answering.
Check that the game is running (`systemctl status bsgo`), and that `.env`
holds `REBSGO_PANEL_TOKEN` — without it the door never starts at all. After
the token changes, both services have to be restarted.

**It throws you straight back to the sign-in page after signing in.** The
ticket cookie is not coming back; most often because the panel has just
replaced its secret key (`panel.env` was regenerated). Everyone has to sign
in again in that case.

**"This pilot is in the game" on every edit.** This is not a fault: the
panel is protecting the data from being overwritten. Ask the pilot to leave,
or kick them with the kick button.

**The interface comes up with the old look.** The stylesheet is referenced
with a version number; if a browser still holds on to the old one, a hard
refresh (Ctrl+F5) is enough.

**The sector table is empty or cold.** The numbers come from the door — if
the game is just starting there is nothing to show for a few seconds; the
page refreshes itself.
