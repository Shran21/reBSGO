[github.com/Shran21](https://github.com/Shran21)

# Accounts, passwords, roles

## Creating an account

- **WebPanel** → Users → "+ New account": name + faction (or "picks a
  faction in the game") + password. The account is born bare; on first
  entry the game walks it through faction choice and avatar creation, and
  hands out the starter ship.
- **From the launcher** a player can sign up on their own: the admission
  door (port 27051 by default) takes `POST /register` with a `name` and a
  `password`, and answers with an `ok <id>` line. It applies the game's own
  name rules and creates the same bare account.
  `REBSGO_ADMISSION_REGISTRATION_OPEN=false` in `.env` closes it.
- There is no separate creator on the command line — the panel is the way
  to go.

## Password

- **WebPanel** → the pilot's page → "Set password" (at least 6 characters).
- From the command line (in the server's directory; where there is no system
  Python, use the bundled one: `./runtime/python/bin/python3 tools/pilots.py …`):

      tools/pilots.py list                     → who has a password
      tools/pilots.py password Tuser           → prompts for it, hidden
      tools/pilots.py password Tuser --password titok
                                               → (avoid: shell history!)

## Roles

- **WebPanel** → the pilot's page → Roles (explanation under every checkbox).
- From the command line:

      tools/pilots.py roles Tuser                       → print them
      tools/pilots.py roles Tuser --grant Developer,Console
      tools/pilots.py roles Tuser --revoke GodMode

| Role | Bit | What it gives |
|---|---|---|
| View | 1 | the game does not use it; read rights in the panel |
| Edit | 2 | panel: writing the database and the hold |
| Ban | 4 | panel: password change, ban |
| CommunityManager | 8 | sandbox sector + staff shop |
| Developer | 16 | dev console commands + panel administration |
| Console | 32 | the precondition for the in-game console |
| GodMode | 1024 | invulnerability |
| Mod | 2048 | sandbox — but it DISABLES the console |

You can sign in to the panel with the Developer or Console role.

## Bans and kicks

- **Kick**: the pilot's page → "Kick from the game" (the player sees the
  normal sign-out screen), or `pilot.kick <id>` from the console.
- **Timed ban**: the pilot's page → the Ban card (1 hour … forever, with a
  reason). Until it expires, the gate answers every login with the date
  and the reason; if they were inside, it kicks them at once. Lifting it
  happens in the same place.
- The bans live in the `panel_bans` table (they show on the Database tab
  too).

## Other pilot operations

    tools/pilots.py place teszt3 44   → where they turn up next time
    tools/pilots.py remove Tuser      → deletes the pilot's PASSWORD

Erasing an account FOR GOOD (from every table) is on the pilot's page in
the panel, on the Danger zone card — there is no undo.
