[github.com/Shran21](https://github.com/Shran21)

# Pilot administration

## Connection and discipline

    pilot.kick <id>                  → kick by id (the player sees the
                                       normal logout screen)
                                       e.g. pilot.kick 7
    pilot.kick-for <name>            → the same by name
                                       e.g. pilot.kick-for Vega
    pilot.mute <name> <hours>        → chat mute for a number of hours
                                       e.g. pilot.mute Vega 2
    pilot.list                       → number of players online, by faction
    pilot.address                    → accounts on the same network address
    pilot.save                       → immediate save of everyone online

## Roles (★ Developer layer)

    pilot.role <id> <bits>       ★   → sets the role bits (ONLY accounts 1
                                       and 2 may issue it)
                                       e.g. pilot.role 7 48
    pilot.role-for <name> <bits> ★   → the same by name
                                       e.g. pilot.role-for Vega 48

Bits: View 1 · Edit 2 · Ban 4 · CommunityManager 8 · Developer 16 ·
Console 32 · GodMode 1024 · Mod 2048. Added up: e.g. Developer+Console = 48.
It is easier to tick them on the WebPanel's Users page.

## Experience and resources

    pilot.xp <amount>                → XP for yourself
                                       e.g. pilot.xp 50000
    pilot.xp-for <name> <amount>     → adds XP to someone else
                                       e.g. pilot.xp-for Vega 50000
    pilot.xp-set <name> <amount>     → sets XP to an exact value
                                       e.g. pilot.xp-set Vega 9801000
    pilot.resource <type> <amount>   → resources for yourself
                                       e.g. pilot.resource resource_cubits 100000
    pilot.resource-for <name> <type> <amount>
                                     → resources for someone else
                                       e.g. pilot.resource-for Vega resource_tylium 5000

`<type>` can be `resource_cubits`, `resource_tylium`, `resource_titanium`,
`resource_water` or `resource_token`. The same thing is easier from the
WebPanel's Users page.

## Faction and appearance

    pilot.faction <name> <with_cubits?> <price>
                                     → faction change; arg 2 says whether
                                       the fee is in cubits, arg 3 is the
                                       price
                                       e.g. pilot.faction Vega false 0
    paint.drop-all <name>            → takes ALL of the pilot's paints away
                                       e.g. paint.drop-all Vega
    pilot.station <room>             → sends them to a given station room
                                       e.g. pilot.station cic x
                                       (the second word is required but ignored)
    pilot.settings                   → prints the client settings
    pilot.squad-refresh <0|1>        → refreshes the squad indicator
                                       e.g. pilot.squad-refresh 1

## Skills

    pilot.train <skill_id>           → teaches a skill
                                       e.g. pilot.train 0
    pilot.untrain <skill_id>         → takes a skill away
                                       e.g. pilot.untrain 0

## Boosts (★ Developer layer for loot/di)

    boost.loot <name> <multiplier> <hours> ★ → loot multiplier for a time
                                       e.g. boost.loot Vega 1 24
    boost.di <name> <multiplier> <hours>   ★ → DI multiplier for a time
                                       e.g. boost.di Vega 1 24
    boost.report                             → prints your own multipliers
    boost.clear                              → clears your own multipliers

## Assignments (★ Developer layer)

    assignment.clear             ★   → clears your daily assignments
    assignment.clear-for <name>  ★   → clears assignments for someone else
                                       e.g. assignment.clear-for Vega
