[github.com/Shran21](https://github.com/Shran21)

# Operations

## Starting and stopping (systemd)

    systemctl start bsgo             → start the game server
    systemctl stop bsgo              → graceful stop (SIGTERM: on the way
                                       out it SAVES the pilots inside)
    systemctl restart bsgo           → restart (for settings changes)
    systemctl status bsgo            → whether it is running, and since when
    journalctl -u bsgo -f            → live journal from journald

    systemctl restart rebsgo-panel   → restart the WebPanel
    systemctl status rebsgo-panel

The WebPanel can do it too: Overview → "Restart server" (at once), or
Tools → "Scheduled restart" (announced, and can be called off).

## Running it by hand (for development)

    cd <the server's directory> && PYTHONPATH=src ./runtime/python/bin/python3 -m rebsgo.main
                                     → start it directly in the foreground

## The language of the output

The installer and the shipped tools follow the machine's language: Hungarian
on a Hungarian locale, English everywhere else (`REBSGO_LANG=hu|en`
overrides it). The log lines themselves are deliberately English, so that a
log stays searchable and shareable; only the header's word follows the
locale.

## Logs — five channels in the logs/ folder

| File | What is in it |
|---|---|
| `server.log`  | everything EXCEPT the sector noise; rotated aside at startup |
| `sector.log`  | the running traffic of the sectors (the loudest, own rotation) |
| `login.log`   | logins and pilot events, going back months |
| `error.log`   | every warning and error in one place |
| `audit.log`   | who did what with rank (console commands, role changes) |

The WebPanel's Logs tab reads and searches all of them; a red dot on the
Logs menu item marks a new error. The panel's own audit is
`WebPanel/logs/panel-audit.log`.

## Changeable while running

- **Log level**: WebPanel → Logs → "Journal volume at runtime" (all at
  once or per area; it lives until the next restart, the lasting word
  stays in `.env`).
- **Maintenance mode**: WebPanel → Tools (new entries for staff only).
- **Sector policy** (closing, player limit): WebPanel → Sectors → Save
  policy — it reloads live; the client has to re-enter for the map to
  change.
- **Sector restart**: WebPanel → Sectors → Restart (at an inhabited
  sector it warns you, and it kicks whoever is inside).

## Configuration (.env)

The lasting settings live in the `.env` file at the root; the full
catalogue, with explanations, is in `.env.example`. The WebPanel's
Configuration tab edits it as a form (your comments survive, and the
previous version stays as `.env.panel-bak`); most values speak at the
next restart.
