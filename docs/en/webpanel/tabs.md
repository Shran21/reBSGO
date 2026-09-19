[github.com/Shran21](https://github.com/Shran21)

# The panel's tabs

In the order of the left sidebar. On a phone the sidebar hides behind the
hamburger button in the header, and wide tables break up into cards.

## Overview

The front page: whether the game server is running, since when, how many
pilots are in and in which sector, the curve of players online over the last
hour, the **Health** card (fresh errors, last backup, free disk, maintenance,
pilot count), the busiest sectors and the quick actions. The chip of anyone
online opens that pilot's page with a single click. It refreshes itself when
something changes (a live stream; the header shows when). The Developer role
also finds the immediate **Restart server** button here (with no
announcement, though the confirmation names whoever is online — the gentle
route is the scheduled restart on the Tools tab).

## Users

**List:** every account, with an online badge (and the sector's name), the
date of the last login; filter by name, sort by column, online pilots first
by default. The whole row is clickable.

**Pilot page:** everything about one pilot on a single page.

| Action | Needs | Note |
|---|---|---|
| ticking roles | Developer | refused while the pilot is in the game |
| changing the password | Developer / Ban | safe at any time, the game never writes the password table |
| setting resources | Developer / Edit | refused while the pilot is in the game; the mail is never harmed |
| banning with an expiry and a reason | Developer / Ban | a pilot who is in the game is kicked at once as well |
| kicking | Console | uses the game's own kick message: the client gets a proper exit screen |
| creating an account | Developer | a bare account; the character is created in the game at the first login |
| deleting an account | Developer | from every table, friend lists included; irreversible |

At the bottom of the page comes the pilot's **dossier**: tallies (kills,
missions, mining), the most recent logins from the log, and the stacks.

## Sectors

A live table of every sector: how many are inside (by name), NPC, asteroid
and object counts, outpost points and outpost health, beacons. Click a
column header to sort. It refreshes itself when something changes.

Per-row actions (Developer):

- **Event** — arms a sector event. It cannot be started in an empty sector,
  and arming is not an immediate start: a player has to fly into the zone.
- **Restart** — rebuilds the sector. If anyone is inside it warns first and
  lists them; once confirmed it kicks them, then starts.
- **OP** — sets outpost points per faction (± or maximum). It is offered
  only for the factions the star allows.
- **Limit** and **Closed** — the per-sector player cap and closure. The
  "Save policy" button reloads it live: a closed sector vanishes from the
  galaxy map and cannot be jumped to. Clients already in the game only see
  the map change after re-entering.

## Map

The galaxy drawn from its own card, in the game's own orientation. The size
and colour of a star show how many pilots are inside, with the outpost marks
(K/C) beside it, the beacon anchor, and a closed sector in red. A click
jumps to the matching row of the Sectors table.

## Database

A browser for every table: tiles for the tables with their row counts, and
inside one a search across all columns, header-click sorting, paging, and an
editor when you click a row. A new row can be added and a row deleted (with
a confirmation; the old row goes into the audit). Only Developer can write;
everyone who signs in can read.

The **database backup** card lives here too: a snapshot by hand (safe even
while the game runs), the list of earlier backups, with downloads. The
automatic schedule is set on the Configuration tab — see `settings.md`.

## Console

The game's developer console from a browser, with the same rights and the
same commands. Commands always run **in the name of the signed-in pilot** —
there is no way to issue a command as somebody else. The ↑ key brings back
the history, typing offers completions, and next to it sits the curated
command handbook as a filterable table. Sector-bound commands only bite
while the signed-in pilot is actually in the game.

## Logs

All five server channels (`server`, `sector`, `login`, `error`, `audit`) and
the panel's own audit, with a search, read from the end of the file; every
line carries its date. The `error` channel shows real errors only by default,
with their tracebacks, and a switch brings the warnings in; the loaded lines
can be filtered in place, and the view copied or downloaded. A **red dot** on
the menu entry marks a real error arriving since you last looked.
The **log level can also be changed while the server runs**, as a whole or
per area (that lasts until the next restart; the permanent setting lives in
`.env`).

## Configuration

The server's `.env` file as a form, explained by the game's own catalogue,
and the panel's own settings can be edited here as well. In detail:
`settings.md`.

## Game tuning

Chosen GameData templates on a field-by-field form: Revenant haunt, command
drone swarm, sector events, mines, carrier docking. In detail: `settings.md`.

## Monitoring

Processor, memory, disk, the load of the server process and the number of
pilots inside, refreshed every five seconds, with an hour or 24 hours of
history that survives a panel restart (in
small charts).

## Rankings

A live view of the in-game leaderboards from the tallies, next to the
monthly saved standings. The Developer role gets a **Recalculate now**
button that starts the server's own leaderboard and tournament run.

## Economy

Totals per pilot and per resource: how much of it there is in the world
altogether, who is richest, and the full matrix. It shows five resources —
cubits, tylium, titanium, water, merit. (The side items — tuning kits, tech
analysis, uranium, plutonium — are deliberately left out; their holdings can
be looked up on the Database tab in the `stacks` table.)

## Tools

- **Broadcast to everyone** — a message to everyone in the game.
- **Scheduled restart** — with an announcement (when armed, and 5 and 1
  minutes before), a countdown, and can be called off at any time.
- **Maintenance mode** — new entries for staff only, with a message of your
  own.
- **Full backup** — the whole server tree into a tar.gz, with a download.
- The **Accounts on one address** report.
- **GameData search** — read-only, over the card data.

## Audit

Two logs on one page: the game's audit channel (who did what with their
rank) and the panel's own audit (who wrote what from the interface). Every
entry shows who, when, what, and what came of it.
