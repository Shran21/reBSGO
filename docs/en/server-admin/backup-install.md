[github.com/Shran21](https://github.com/Shran21)

# Backup, portable package, installation

## Quick backup

- **WebPanel** → Tools → "Full backup now": a tar.gz into the
  `/opt/bsgo-backups` folder (without logs and venv); the entries in the
  list can be downloaded. Only one backup can run at a time.
- The target folder can be moved with the panel's `PANEL_BACKUP_DIR`
  setting.

## Installing — from a clone or from the package

    ./install.sh

The installer first asks **where the server should live** (Enter = where
the tree already is); for another path it copies the tree there and carries
on from the new place. Without a question: `--dir /where/you/want`, or
`--here` (in place). From the package:

    tar xzf reBSGO-portable-*.tar.gz -C /where/you/want
    cd /where/you/want/reBSGO-server && ./install.sh

The installer works without a network:

1. it unpacks the **Python 3.13 it brought along** under `runtime/python`
   (if that is missing, it uses the system python3 — 3.13 is needed for
   the native accelerator module);
2. it creates the folders, and if there is no `.env`, it generates one
   with a fresh panel token;
3. it checks that the server code loads and that the **native accelerator
   module** (`native/lib`, shipped in the tree) is active;
4. it builds the panel's venv from the `WebPanel/vendor/wheels` set;
5. as root it installs, enables and **starts** the systemd units (`bsgo`,
   `rebsgo-panel`) from the `deploy/` template, pointed at the new place.

The players' launcher is `launcher/rebsgo-launcher.exe` — that is what to
hand them; they enter the door's address in the launcher's settings.

Switches: `--check` (report only, change nothing), `--no-systemd`, `--dir`,
`--here`. The installer is **re-runnable**: it completes an existing
installation and breaks nothing; copied onto an existing installation it
refreshes the code and keeps `.env`, the world state (`sqlite/`) and the
local settings.

Starting afterwards:

    systemctl start bsgo rebsgo-panel

or by hand:

    PYTHONPATH=src ./runtime/python/bin/python3 -m rebsgo.main
    ./WebPanel/run.sh

## Verified properties

- In a bare Debian container (without Python) the package started
  natively after unpacking plus the installer: the game server AND the
  panel.
- A second run of the installer broke nothing (idempotent).
- `deploy/bsgo.service.template` is a word-for-word copy of the live unit
  (with the graceful SIGTERM stop that saves the pilots on the way out).
