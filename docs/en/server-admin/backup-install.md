[github.com/Shran21](https://github.com/Shran21)

# Backup, portable package, installation

## Quick backup

- **WebPanel** → Tools → "Full backup now": a tar.gz into the
  `/opt/bsgo-backups` folder (without logs and venv); the entries in the
  list can be downloaded. Only one backup can run at a time.
- The target folder can be moved with the panel's `PANEL_BACKUP_DIR`
  setting.

## Easy installation — one command

    curl -fsSL https://raw.githubusercontent.com/Shran21/reBSGO/main/install-basic.sh | sudo sh

Where there is no `curl`, the same with `wget -qO- …`. `install-basic.sh` downloads
the repository from GitHub, unpacks it in a temporary directory, starts the
installer from there (see below), and removes the temporary directory at the
end. It asks two things: the target directory (Enter = `/opt/rebsgo`, or
`~/rebsgo` without root), and, through the installer, the first admin
account. Switches after `sh -s --`:

    … | sudo sh -s -- --dir /srv/rebsgo     → target directory, no question
    … | sudo sh -s -- --ref <branch or tag>  → other than the main branch
    … | sudo sh -s -- --no-systemd           → without the services
    … | sudo sh -s -- --no-restart           → no restart on an update

**Updating:** the same command, onto the same target directory. The code is
replaced, while `.env`, the world state (`sqlite/`) and the local settings
stay, and no admin account is asked for again. If the services were already
running, the installer restarts them at the end so the update takes over: on
the way out bsgo saves the pilots, and the players inside are signed out.
With `--no-restart` that is left out and the installer only prints the restart
command (`systemctl restart bsgo rebsgo-panel`), for a live server you would
rather restart later, say.

Without a terminal, automated for instance, it asks nothing: the target
directory is the default or `--dir`, and the admin account has to be made
afterwards (`accounts.md`).

## Installing — from a clone or from the package

    sh install.sh

The installer first asks **where the server should live** (Enter = where
the tree already is); for another path it copies the tree there and carries
on from the new place. Without a question: `--dir /where/you/want`, or
`--here` (in place). From the package:

    tar xzf reBSGO-portable-*.tar.gz -C /where/you/want
    cd /where/you/want/reBSGO-server && sh install.sh

Started with `sh`, the installer runs even if the file lost its execute
permission on the way (uploaded from Windows, for one); the other scripts
get theirs back from the installer itself.

The installer works without a network:

1. it unpacks the **Python 3.14 it brought along** (the GIL-free,
   free-threaded build) under `runtime/python`; on an update it replaces an
   older one there. That one is built for x86_64: on another processor, or
   when no interpreter is bundled, it uses the system python3 (3.11 or
   newer is needed);
2. it creates the folders, makes the scripts executable (`install.sh`,
   `WebPanel/run.sh`, `tools/*.py`), and if there is no `.env`, it
   generates one with a fresh panel token — readable by its owner only —,
   and switches sector gating on in it (`REBSGO_SECTOR_GATING_MODE=idle`,
   see below) unless `.env` already says something about it;
3. it checks that the server code loads, and whether it runs without the
   GIL;
4. it builds the panel's venv from the `WebPanel/vendor/wheels` set
   (whatever there does not fit the machine — on another processor, or
   with a Python other than 3.14t or 3.13 — comes from PyPI, which needs a
   network; whatever PyPI has no ready package for on this machine is
   compiled here, and if `python3-dev` or `gcc` is missing for that, it
   installs them with apt-get as root; pip's log: `logs/panel-pip.log`),
   and
   writes `WebPanel/panel.env`: the panel is reachable on every network
   address (`PANEL_HOST=0.0.0.0`), and only the file's owner can read it;
5. if no account has the Developer role yet, it asks for the **first admin
   account** (a name, then the password twice; Enter = skip). It gets the
   Developer and Console roles, and it is the one that signs in to the
   WebPanel. Without a terminal it only prints the command that makes one
   later (`accounts.md`);
6. as root it installs, enables and **starts** the systemd units (`bsgo`,
   `rebsgo-panel`) from the `deploy/` template, pointed at the new place.

The players' launcher is `launcher/rebsgo-launcher.exe` — that is what to
hand them; they enter the door's address in the launcher's settings.

Switches: `--check` (report only, change nothing), `--no-systemd`,
`--no-restart`, `--dir`, `--here`. The installer is **re-runnable**: it completes an existing
installation and breaks nothing; copied onto an existing installation it
refreshes the code and keeps `.env`, the world state (`sqlite/`) and the
local settings. It only asks for an admin account while no account has the
Developer role. It also tidies up after an interrupted earlier run: it
removes an interpreter that does not start on the machine, fills in an empty
panel token, and rebuilds a half-built venv.

**Sector gating.** On its own the server simulates every sector at full
speed, the empty ones too, and a smaller machine cannot keep up with that. So
the installer writes `REBSGO_SECTOR_GATING_MODE=idle` into `.env`: an empty
sector does not simulate, after 2 minutes its timers slow down, after 10
minutes it goes into deep sleep, and a player arriving wakes it within a
second.
Measured on an x86 machine, the server's load with no players drops from 57%
to about 20% this way, and to 2% after 10 minutes (100% = one CPU core). What
goes on in empty sectors meanwhile (NPCs moving, respawns, timed events) slows
down or pauses. The other modes: `empty` (only the simulation is skipped),
`adaptive` (deep sleep only under heavy machine load), `off` (everything
simulates all the time). Change it in `.env`, then `systemctl restart bsgo`.
The installer leaves a setting that is already there alone, and on an update
it only writes the line when there is none.

Starting afterwards:

    systemctl start bsgo rebsgo-panel

or by hand:

    PYTHONPATH=src ./runtime/python/bin/python3 -m rebsgo.main
    ./WebPanel/run.sh

## Uninstalling

    sudo sh /opt/rebsgo/uninstall.sh

`uninstall.sh` sits in the installation's directory. It stops the services
(on the way out bsgo saves the pilots), removes the `bsgo` and `rebsgo-panel`
units, and if the server or the panel runs by hand from this directory, it
stops those properly too. Then it asks what should stay:

1. **the data in place** (recommended): the program goes, while `sqlite/`,
   `.env`, `WebPanel/panel.env` and `GameData/local` stay. Installing into
   the same directory again gets all of it back: the players, the settings
   and the admin account;
2. **a backup, then everything goes**: the data goes into a `.tar.gz` (next
   to the installation by default), and the directory is removed. Restoring
   into a new installation, with its services stopped:
   `tar xzf <backup> -C <directory>`;
3. **everything goes, with no backup**: only after typing the word `delete`.

With no questions: `--keep-data`, `--backup <file>` or `--purge`, with
`--yes`; for another installation `--dir <directory>`. A service pointing at
another directory is left alone, and so are the panel's backups
(`PANEL_BACKUP_DIR`, `/opt/bsgo-backups` by default).

## Verified properties

- In a bare Debian container (without Python) the package started
  natively after unpacking plus the installer: the game server AND the
  panel.
- A second run of the installer broke nothing (idempotent).
- `deploy/bsgo.service.template` is a word-for-word copy of the live unit
  (with the graceful SIGTERM stop that saves the pilots on the way out).
