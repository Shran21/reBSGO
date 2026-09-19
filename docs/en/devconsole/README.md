[github.com/Shran21](https://github.com/Shran21)

# Devconsole — overview

The developer console is reachable from the client (Enter → console
prompt) and from the WebPanel's **Console** tab as well — both drive the
same server-side machinery, with the same permissions.

## Permissions

- Using the console requires the **Console (32)** role, and the **Mod (2048)
  bit disables it** — even if Console is set alongside it.
- Commands marked with ★ in the files under `docs/en/devconsole/` live in
  the **developer layer**: they also require the **Developer (16)** role.
- Roles can be set on the WebPanel's Users page or with the `pilot.role`
  command (the latter is only available to accounts 1 and 2).

## General rules

- Command arguments are separated by spaces; text of more than one word
  has to be quoted: `notice.all "Maintenance incoming"`.
- Most sector-bound commands (spawn, asteroid, event) act **in the sector**
  where the issuer happens to be flying — from the WebPanel console these
  only work if the pilot logged into the panel is in the game.
- The client also sends 16 hard-wired button command names (e.g.
  `consumable`, `god_mode`, `spawn_comet`) — these are aliases of the
  matching exact commands, and the files mention them under their proper
  names.
- You can add your own aliases in `GameData/local/console_aliases.json`
  (a per-machine file; the installer never overwrites an existing one).

## Files

| File | Topic |
|---|---|
| `spawning.md` | spawning NPCs, drones, platforms and objects |
| `sectors.md` | sector operations, asteroids, outpost readiness |
| `pilots.md` | pilot administration, XP, resources, mail, boosts |
| `ships.md` | your own ship, target operations, ammunition |
| `server.md` | server-level commands, notices, tallies |
