[github.com/Shran21](https://github.com/Shran21)

# Server administration — overview

Day-to-day operation has two routes.

**WebPanel** (`http://<the machine's address>:27055`) — the browser handles
user and role management, bans, resources, sectors, the console, the logs,
configuration, monitoring, backups and the scheduled restart. Signing in uses
the in-game name and password, with the Developer or Console role. It has its
own write-up: `docs/en/webpanel/`.

**Command line** — systemd, the scripts under `tools/`, and the installer.

| File | Topic |
|---|---|
| `operations.md` | starting, stopping, logs, changes while running |
| `accounts.md` | accounts, passwords, roles, bans |
| `backup-install.md` | backup, portable package, install on a new machine |

The developer console's commands are in `docs/en/devconsole/`, and the
tab-by-tab write-up of the WebPanel is in `docs/en/webpanel/`.
