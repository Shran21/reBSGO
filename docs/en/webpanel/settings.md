[github.com/Shran21](https://github.com/Shran21)

# Settings from the panel

Three independent groups of settings can be changed here, each stored in a
different place:

| What | Where | When it takes effect |
|---|---|---|
| how the server runs (ports, logging, cache, performance) | Configuration tab → `.env` | at the next game server restart |
| the panel itself (port, who may sign in, backup schedule) | Configuration tab → panel section → `panel.env` | at the next panel restart (the backup schedule immediately) |
| how the game behaves (events, mines, carrier) | Game tuning tab → GameData templates | at the next game server restart |

## Configuration tab — the server's `.env`

The tab shows the **live values**: the fields hold whatever stands in
`.env`. The list of keys, the explanations and the defaults come from the
game's own catalogue (`.env.example`) — so the list can never drift away
from the code.

**An empty field means: nothing overrides it, the default applies.**
Resolution has three layers, in this order:

1. the process environment,
2. the `.env` file,
3. the built-in defaults (the catalogue fixed in code; `.env.example` shows the same values).

Saving edits `.env` **in place**: your hand-written comments and the
ordering survive, and the previous version lives on as `.env.panel-bak`.
Every save goes into the audit, with the old and the new value.

Two markings in the interface:

- **"careful"** — this key can lock out the panel's own bridge as well
  (`REBSGO_PANEL_TOKEN`, the panel door's port).
- **"Lines outside the catalogue"** — what `.env` holds but the catalogue
  does not know. `GAME_CHAT_ADDRESS` lands here, for instance: a legacy
  name, but a live one — it fills the same setting you see in the catalogue
  as `REBSGO_NET_CHAT_ADDRESS`.

The database path (`REBSGO_DB`) can be set from here too. Moved elsewhere,
**the panel's `PANEL_DB` setting has to point at the same place**
— otherwise the panel would show a different database from the one the game
uses.

## Configuration tab — the panel's own settings

A separate section at the bottom of the page edits `panel.env`. A saved
value takes effect **at the next panel restart**; the button for it is right
there.

| Key | What it sets |
|---|---|
| `PANEL_HOST` | the address it listens on: `127.0.0.1` by default (this machine only); `0.0.0.0` = every network — for public reach, put a TLS proxy in front |
| `PANEL_PORT` | the panel's port (27055 by default) |
| `PANEL_DB` | the path to the game database as the panel sees it |
| `PANEL_LOGIN_ROLES` | which in-game roles may sign in |
| `PANEL_SESSION_HOURS` | how long a login lasts |
| `PANEL_BRIDGE_URL` | the address of the game server's panel door |
| `PANEL_DEFAULT_LANG` | the interface's default language (`hu`/`en`) |
| `PANEL_BACKUP_DIR` | where backups land |
| `PANEL_BACKUP_AT` | the time of the daily automatic backup as `HH:MM`; empty is off |
| `PANEL_BACKUP_KEEP` | how many automatic backups to keep per kind |
| `PANEL_BACKUP_KIND` | `db` = database snapshot, `full` = whole-tree tar.gz |

The panel's secret key (`PANEL_SECRET`) is deliberately **not** editable
here: replacing it signs everyone out, and a half-finished value would lock
out this very page. If it has to change, edit it in the `panel.env` file.

## Backups

There are two kinds of backup, and both work into the same directory:

- **Database snapshot** (`db`) — of the game database only, compressed. It
  is taken with SQLite's own backup API, which makes it **safe even while
  the game runs**: it does not break off just because the server writes at
  the same time. It can be started by hand on the Database tab, and
  downloaded from there too.
- **Full backup** (`full`) — the whole server tree into a tar.gz (without
  the logs, the cache and the virtual environments). By hand on the Tools
  tab.

For the automatic schedule it is enough to enter a time in
`PANEL_BACKUP_AT` — **that applies immediately, with no panel restart**. The
panel looks at the clock every half minute, runs once a day (even if it
restarted in the meantime), and deletes old backups beyond
`PANEL_BACKUP_KEEP` on its own.

## Game tuning tab

Curated templates on a field-by-field form, with type and bound checks. What
can be rewritten here:

| Template | What can be set |
|---|---|
| Revenant haunt | on/off, how many sectors at once, barred sectors, gear level, lifetime, respawn delay, patrol radius |
| Command drone swarm | on/off, wave size (min/max), delay before a new wave, spawn and patrol radius, gear level |
| Sector events | on/off, excluded sectors, frequency and jitter, concurrent NPCs, attacker ratio, duration, wave gap |
| Mines | trigger radius, blast radius, fallback lifetime |
| Carrier docking | dock range, party-only switches, fortify requirement, repair |

What **cannot** be broken from here: the fields that carry a feature's
identity (card GUIDs, ship-kind lists, warhead tables) show up grey and
locked. Anyone who wants to change those edits the template file.

If a value falls outside the allowed range, the save **writes nothing** and
tells you what is wrong. Every successful save goes into the audit, with the
old and the new value.

**Important:** the game reads these templates at boot — after saving, a
**server restart** is needed. The button is at the top of the page.
