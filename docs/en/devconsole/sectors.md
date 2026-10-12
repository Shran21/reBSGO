[github.com/Shran21](https://github.com/Shran21)

# Sector operations

Every command acts in the issuer's **own sector**, unless stated otherwise.

## Outpost

    outpost.points <colonial|cylon> <points>
                                     → readiness points ± in this sector
                                       (the scale is 0–3000; from 900 the
                                       outpost stands, from 1350 a beacon
                                       can come)
    outpost.points-max               → EVERY sector, both sides, set to 3000

Example: `outpost.points cylon 1500`

## Getting your bearings

    sector.census                    → object census of the sector
    asteroid.ore-report              → report on the ore-bearing asteroids

## Travel

    sector.jump <sector_id>          → instant jump into the given sector
                                       e.g. sector.jump 21
    sector.jump-notice <error_code> <reason>
                                     → test of a jump-refusal message
                                       e.g. sector.jump-notice 2 7

## Asteroid generation

    sector.fill <seed> <asteroid> <planetoid> <fields> <count/field> <field_size> <loops> <loop_size> <count/loop>
        → a full sector scatter with nine integers; <seed> is the
          random seed, so the same number gives the same picture.
          e.g. sector.fill 42 4 1 1 5 400 1 500 6

    asteroid.tendril <seed> <from_centre> <count> <tendrils> <angle>
        → a tendril-shaped asteroid cluster
          e.g. asteroid.tendril 7 2000 10 3 15

    asteroid.ring <seed> <from_centre> <count> <inner> <outer> <angle>
        → a ring shape between the inner and outer radius

    asteroid.unstick                 → pushes stuck (colliding) asteroids apart
    asteroid.clear                   → deletes every asteroid
    asteroid.clear-water             → deletes only the water-bearing ones

Example: `asteroid.ring 42 0 120 800 1600 15`

The generators work IN MEMORY: the result lives until the sector restarts.
If a layout is meant to be permanent, it has to be carried over into the
Sector template (GameData/templates/Sector/sector_N.json) — the `<seed>`
values are good for this, because the picture is reproducible.
