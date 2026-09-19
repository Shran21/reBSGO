[github.com/Shran21](https://github.com/Shran21)

# Your own ship, targets, ammunition

## Your own ship

    ship.invulnerable <0|1>          → invulnerability (GodMode); the
                                       client's god_mode button sends this
                                       too
    ship.buff <type>                 → self-buff on your ship (the
                                       self_buff button)
    ship.max-gear <name>             → sets the named pilot's ship to
                                       maximum gear
    ship.speed <value>               → speed adjustment for testing
    ship.teleport <name> <distance>  → teleport to the named pilot at a
                                       given distance
    ship.teleport-centre             → teleport to the centre of the sector
    ship.visibility <0|1> [reason]   → your ship's visibility switch
    ship.fly <guid>                  → move into the given ship card
    ship.fly-for <name> <guid>       → moves another pilot into one

## Target operations (mark a target in the game first)

    target.report                    → the target's full data sheet
    target.kill                      → destroys the target instantly
                                       (kill_target button)
    target.loot                      → scatters the target's loot
                                       (loot_target button)
    target.scan-all                  → reveals every object to you
    target.scan-all-for <name>       → the same for the named pilot
    object.mark <0|1>                → highlight marker on the target
    object.report <name> <guid> <level>
                                     → item report from the named pilot's
                                       storage
    object.report-guid <name> <guid> → item report by guid

## Ammunition and consumables (the client's consumable button is ammo.give)

    ammo.give <name> <guid> <count>  → gives a certain consumable
    ammo.weapons                     → refills your weapon ammunition
    ammo.hull                        → refills the hull repair items
    ammo.computer                    → refills the computer consumables
    ammo.engine                      → refills the engine consumables
    ammo.all                         → refills all of your consumables

## Other

    augment.try                      → augment test
    refund.all <lvl1_guid>           → refund of an upgrade chain
    skill_learn / skill_unlearn      → the button names of pilot.train /
                                       pilot.untrain
