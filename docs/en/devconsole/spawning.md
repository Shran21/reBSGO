[github.com/Shran21](https://github.com/Shran21)

# Spawn commands

All of them work in the issuing pilot's **own sector** and **around their
own ship**: `<radius>` marks out a box around your ship, and every instance
is placed at a random spot inside it. The lower bound of the radius is 10.

## npc.spawn — spawning NPC ships

    npc.spawn <count> <radius> [type] [lifetime_sec]

- `type` can be:
  - left empty: spawns from **your own ship's** card (copies of your ship);
  - `colonial` or `cylon`: an NPC ship of that faction;
  - `random` (or `mix`, `all`): a mixture of random ship types;
  - `random_cylon` / `random_colonial`: random, but only from that faction;
  - a **ship guid** or **GUI key** (e.g. the `key` field of gui.json).
- `lifetime_sec`: they disappear on their own after this many seconds
  (default 3600).
- The spawned NPCs patrol inside the radius box.

Examples:

    npc.spawn 5 300 cylon            → 5 cylon NPCs within a radius of 300
    npc.spawn 10 800 random 600      → 10 random NPCs, 10-minute lifetime
    npc.spawn 3 200                  → 3 copies of your own ship
    npc.spawn 1 150 124779515        → 1 ship of the given guid

## drone.spawn — drones

    drone.spawn <count> <radius> [type] [lifetime_sec]
    drone.spawn 1 1 help             → prints its own help

- `type`: `human` / `cylon` (small, T1), `human_large` / `cylon_large`
  (large, T3), `small` / `large` (your own faction's default), or a guid
  directly. Empty: your faction's small drone.
- Named kinds (every drone identity the client has, from the `droneKinds`
  map of Dev/spawn_types.json): `strike_buffer`, `strike_cannon`,
  `strike_debuffer`, `strike_missiletank` (drones of the Awakening event),
  `training`, `target` (practice), `story1_dps`, `story1_tank`,
  `story2_dps`, `story2_tank`, `tutorial_damaged`, `tutorial_static`,
  `wave_dps`, `wave_tank`, `ancient_small_dps`, `ancient_large_tank`,
  and `command` (Drone Command network ship — an unarmed target ship).

Example: `drone.spawn 5 200 human_large 600`, `drone.spawn 1 300 command`

## platform.spawn and platform.ring — weapon platforms

    platform.spawn <count> <radius> [type]
    platform.spawn 1 1 help          → prints the type names

- `type`: `stationary1`–`6` (= `humanstationary1`–`6`, colonial),
  `cylonstationary1`–`6`, or a guid. Empty: the ancient base platform.
- If a faction name (`colonial`/`cylon`) is given, the platform will belong
  to that faction. The type names come from the file
  `GameData/templates/Dev/spawn_types.json` — a new type has to be added
  there.
- `platform.ring` works the same way, for spawning groups.

Example: `platform.spawn 3 200 stationary2`

## Object spawners (★ Developer is needed for comet.spawn)

    comet.spawn                      → comet at the centre of the sector (★)
    comet.spawn-guid <guid>          → comet from a given card
    nebula.spawn                     → spawns a debris nebula (debris 16)
    cargo.spawn [guid]               → collectable container; empty gives the
                                       default container (50000113)
    debris.spawn <guid> <y>          → debris field at a given height (x=z=0)
    planet.spawn <guid> <x> <y> <z> <rx> <ry> <rz>
                                     → planet at a given position and angle

## Cleanup

    debris.clear                     → deletes all debris from the sector
    planet.clear                     → deletes all planets
    sector.clear                     → deletes every NON-player object

Spawned objects do not survive a sector restart — a Restart on the
WebPanel's Sectors tab puts everything back to its initial state.
