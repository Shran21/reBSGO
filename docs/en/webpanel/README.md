[github.com/Shran21](https://github.com/Shran21)

# WebPanel — overview

The WebPanel is the server's web admin interface: everything that used to
need a command line can be done from a browser — accounts, sectors, the
database, logs, settings, backups, the console.

**Address:** `http://<the machine's address>:27055`. After a fresh install the
panel opens on its own machine; `PANEL_HOST=0.0.0.0` opens it to the network,
and public reach belongs behind a TLS proxy (`settings.md`).

## Signing in

The same **pilot name and password** as in the game — there is no separate
panel account. The panel asks the game server's own password store, so a
password change takes effect in both places at once.

Signing in needs either the **Developer (16)** or the **Console (32)** role.
Anyone with neither gets the very same sentence as somebody who typed the
wrong password — deliberately, so that accounts cannot be mapped out from
outside.

- A login lasts **12 hours**, and renews itself automatically during use.
- **Ten attempts a minute** are allowed per address.
- Every sign-in, refusal and write goes into the panel's audit
  (`WebPanel/logs/panel-audit.log`, the **Audit** tab in the interface).

The interface runs in **Hungarian and English**; the language switch is at
the bottom of the left sidebar, and the choice is kept in a cookie.

## Who may do what — roles

| Role | What it grants on the panel |
|---|---|
| **Developer (16)** | everything: database writes, saving settings, creating and deleting accounts, sector operations, backups, restarts |
| **Console (32)** | signing in, reading, the Console tab, kicking, broadcasts |
| **Ban (4)** | changing passwords and banning |
| **Edit (2)** | editing a pilot's resources |

The Mod (2048) bit **disables the console**, even with the Console role
beside it — that is the game's rule, and the panel follows it.

Two recurring limits:

- **The data of a pilot who is in the game cannot be edited** (roles,
  resources, deleting the account, its database rows). While somebody is
  playing, the server holds their data in memory and writes it back every
  two minutes — a value written from the panel would be lost. The panel
  states this: the pilot has to leave the game first.
- **Every write is CSRF-protected**, and every write goes into the audit.

## Conveniences

- **Theme:** the interface follows the system's light/dark setting; the
  button at the bottom of the sidebar pins light or dark, and the choice
  stays in the browser.
- **Search (Ctrl+K):** one box jumps to a pilot, a sector or a card — the
  arrows move, Enter opens.
- **Live updates:** the overview, the users, the sectors and the star map
  receive changes over a single event stream and only reload when something
  happened; the page header shows when it last refreshed. Where the stream
  cannot be held, the page falls back to timed refreshes on its own.
- **Overview:** fresh errors, the last backup, free disk, maintenance, the
  curve of players online over the last hour, the busiest sectors and quick
  actions.
- **Users:** filter by name, sort by column, online pilots first by default.
- **Logs:** every line carries its date; the error tab shows real errors
  only by default (a switch brings the warnings in), and the overview counts
  errors, not file bytes; the loaded lines can be filtered in place, the view
  copied or downloaded; while following, the page refreshes when the file
  changes.
- **Monitor:** one hour or 24 hours of history, which survives a panel
  restart.
- **Confirmation:** the dangerous buttons (restart, delete, ban) open a
  dialog that says what will happen and whom it touches.

On a released server the panel reads the cards and templates the same way the
game does, but the game data itself is read-only: the **Game tuning** tab and
the sector policy cannot be saved, and the panel says so.

## Files

| File | Topic |
|---|---|
| `tabs.md` | tab by tab: what each one does and which role it needs |
| `settings.md` | configuration, the panel's own settings, backup scheduling, game tuning |
| `internals.md` | structure, the panel door, files, troubleshooting |

The command-line side of day-to-day operations lives in
`docs/en/server-admin/`, and the console commands in `docs/en/devconsole/`.
