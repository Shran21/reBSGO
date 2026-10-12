[github.com/Shran21](https://github.com/Shran21)

# Your own ship, targets, ammunition

## Your own ship

    ship.invulnerable <true|false>   → invulnerability (GodMode); the
                                       client's god_mode button sends this
                                       too
                                       e.g. ship.invulnerable true
    ship.buff <type>                 → self-buff on your ship (the
                                       self_buff button)
                                       e.g. ship.buff heal
                                       (types: speed, heal, dmg, range,
                                       cooldown, dispell)
    ship.max-gear <name>             → sets the named pilot's ship to
                                       maximum gear
                                       e.g. ship.max-gear Vega
    ship.speed <value>               → speed adjustment for testing
                                       e.g. ship.speed 150
    ship.teleport <name> <distance>  → teleport to the named pilot at a
                                       given distance
                                       e.g. ship.teleport Vega 500
    ship.teleport-centre             → teleport to the centre of the sector
    ship.visibility <true|false> <reason>
                                     → your ship's visibility switch
                                       e.g. ship.visibility false Default
                                       (reason: Default, Jump, Death, Anchor)

## Target operations (mark a target in the game first)

    target.report                    → the target's full data sheet
    target.kill                      → destroys the target instantly
                                       (kill_target button)
    target.loot                      → scatters the target's loot
                                       (loot_target button)
    target.scan-all                  → scans every asteroid and planetoid
                                       in your sector; no target is needed
                                       for it, only that you are in space.
                                       Afterwards you see for each one
                                       which resource it holds, and for
                                       the planetoids also whether they
                                       can still be mined
    target.scan-all-for <name>       → the same for the named pilot, in
                                       their sector
                                       e.g. target.scan-all-for Vega
    object.mark <0|1>                → highlight marker on the target
                                       e.g. object.mark 1

## Ammunition and consumables

    ammo.weapons <name> <count>      → weapon ammunition for the named pilot
                                       e.g. ammo.weapons Vega 50
    ammo.hull <name> <count>         → hull repair items for the named pilot
                                       e.g. ammo.hull Vega 10
    ammo.computer <name> <count>     → computer consumables for the named pilot
                                       e.g. ammo.computer Vega 10
    ammo.engine <name> <count>       → engine consumables for the named pilot
                                       e.g. ammo.engine Vega 10
    ammo.all <name> <count>          → every consumable for the named pilot
                                       e.g. ammo.all Vega 20

## Other

    augment.try                      → augment test
    skill_learn / skill_unlearn      → the button names of pilot.train /
                                       pilot.untrain
                                       e.g. skill_learn 0
