[github.com/Shran21](https://github.com/Shran21)

# Launcher — for players and operators

`launcher/rebsgo-launcher.exe` starts the game: registration, sign-in, file
check, launch — a single file with no installer and no dependencies, on
Windows.

## The player's side

1. **The settings page comes first on the first start.** Two things are
   needed: the **server's address** (the machine's name or IP, no port — the
   launcher finds the admission door's port itself) and the **game folder**
   (the root of the installation will do; `bsgo.exe` is found up to three
   levels down). The folder's path must **contain no spaces**: the client
   splits its own command line on them.
2. **Registration and sign-in** on the same page: a name of 3–20 characters
   without accents or spaces; a password of at least 6 characters. The password
   goes to the admission door; the game receives a **ticket** — the client
   never sees the password.
3. **File check** (when the operator has switched it on): from the list the
   server hands out, the launcher compares every file by size and checksum and
   downloads what is missing or different. **It never deletes** — whatever is
   not on the list stays.
4. The **PLAY** button starts the client with the server's address and the
   ticket.

The interface follows the system language (Hungarian or English, anything
else falls back to English), and the game gets the same language. Settings
live in `%APPDATA%\reBSGO\launcher.ini`, the log in
`%APPDATA%\reBSGO\launcher.log`, which is the first place to look when
something goes wrong.

## The operator's side

| What is needed | Where |
|---|---|
| the launcher file | `launcher/rebsgo-launcher.exe`, the program the players get |
| reachable ports | 27051 (admission door), 27050 (game), 27052 (chat) |
| file list (optional) | `REBSGO_LAUNCHER_MANIFEST_DIR` and `REBSGO_LAUNCHER_CLIENT_DIR` in `.env` |

The file list is written by `tools/gen_launcher_manifests.py` from your own,
clean client (`--client …/client/live --out <list folder> --skip-suspect`); the
door serves the files from that same folder. Without the keys the door hands
out an empty list, the launcher skips the check and starts whatever the player
has — so matching the client build stays the player's business.

The two links along the bottom lead to the project page
(<https://github.com/Shran21/reBSGO>) and to the developer's Discord
(<https://discord.com/users/469848422732660767>).

The launcher recognises the door by the shape of its **manifest** (during the
port scan too), so it only ever connects to a reBSGO server. The game is
started with the client's standard switches (`+gameServer`, `+cdn`, `+userID`,
`+session`, `+language`).
