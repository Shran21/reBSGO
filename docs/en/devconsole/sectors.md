[github.com/Shran21](https://github.com/Shran21)

# Sector operations

Every command acts in the issuer's **own sector**, unless stated otherwise.

## Event and outpost

    sector.event                     → ARMS the freighter event here. A
                                       marker and a zone appear; it starts
                                       when a pilot flies into the zone. In
                                       an empty sector the request fades
                                       away.
    outpost.points <colonial|cylon> <points>
                                     → readiness points ± in this sector
                                       (the scale is 0–3000; from 900 the
                                       outpost stands, from 1350 a beacon
                                       can come)
    outpost.points-max               → EVERY sector, both sides, set to 3000

Example: `outpost.points cylon 1500`

## Getting your bearings

    sector.census                    → object census of the sector
    sector.zones                     → zone information (★ Developer)
    asteroid.ore-report              → report on the ore-bearing asteroids
    sector.template                  → prints the sector's template data

## Travel

    sector.jump <sector_id>          → instant jump into the given sector
    sector.jump-notice <error_code> <reason>
                                     → test of a jump-refusal message

## Asteroid generation

    sector.fill <seed> <asteroid> <planetoid> <fields> <count/field> <field_size> <loops> <loop_size> <count/loop>
        → a full sector scatter with nine integers; <seed> is the
          random seed, so the same number gives the same picture.

    asteroid.tendril <seed> <from_centre> <count> <tendrils> <angle>
        → a tendril-shaped asteroid cluster

    asteroid.ring <seed> <from_centre> <count> <inner> <outer> <angle>
        → a ring shape between the inner and outer radius

    asteroid.unstick                 → pushes stuck (colliding) asteroids apart
    asteroid.clear                   → deletes every asteroid
    asteroid.clear-water             → deletes only the water-bearing ones
    planet.mining-rig                → test of the mining rig on the planetoid

Example: `asteroid.ring 42 0 120 800 1600 15`

The generators work IN MEMORY: the result lives until the sector restarts.
If a layout is meant to be permanent, it has to be carried over into the
Sector template (GameData/templates/Sector/sector_N.json) — the `<seed>`
values are good for this, because the picture is reproducible.
