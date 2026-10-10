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

**Updating:** the same command, onto the same target directory. The code is
replaced, while `.env`, the world state (`sqlite/`) and the local settings
stay, and no admin account is asked for again. If the services were already
running, the installer prints the restart command at the end (`systemctl
restart bsgo rebsgo-panel`); it does not run it on its own, because stopping
bsgo signs the players out.

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

1. it unpacks the **Python 3.13 it brought along** under `runtime/python`
   (if that is missing, it uses the system python3 — 3.13 is needed for
   the native accelerator module);
2. it creates the folders, makes the scripts executable (`install.sh`,
   `WebPanel/run.sh`, `tools/*.py`), and if there is no `.env`, it
   generates one with a fresh panel token — readable by its owner only;
3. it checks that the server code loads and that the **native accelerator
   module** (`native/lib`, shipped in the tree) is active;
4. it builds the panel's venv from the `WebPanel/vendor/wheels` set, and
   writes `WebPanel/panel.env`: the panel opens on its own machine only
   (`PANEL_HOST=127.0.0.1`), and only the file's owner can read it;
5. if no account has the Developer role yet, it asks for the **first admin
   account** (a name, then the password twice; Enter = skip). It gets the
   Developer and Console roles, and it is the one that signs in to the
   WebPanel. Without a terminal it only prints the command that makes one
   later (`accounts.md`);
6. as root it installs, enables and **starts** the systemd units (`bsgo`,
   `rebsgo-panel`) from the `deploy/` template, pointed at the new place.

The players' launcher is `launcher/rebsgo-launcher.exe` — that is what to
hand them; they enter the door's address in the launcher's settings.

Switches: `--check` (report only, change nothing), `--no-systemd`, `--dir`,
`--here`. The installer is **re-runnable**: it completes an existing
installation and breaks nothing; copied onto an existing installation it
refreshes the code and keeps `.env`, the world state (`sqlite/`) and the
local settings. It only asks for an admin account while no account has the
Developer role.

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
