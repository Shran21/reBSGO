[github.com/Shran21](https://github.com/Shran21)

# Pilot administration

## Connection and discipline

    pilot.kick <id>                  → kick by id (the player sees the
                                       normal logout screen)
    pilot.kick-for <name>            → the same by name
    pilot.mute <name> <hours>        → chat mute for a number of hours
    pilot.list                       → number of players online, by faction
    pilot.address                    → accounts on the same network address
    pilot.save                       → immediate save of everyone online

## Roles (★ Developer layer)

    pilot.role <id> <bits>       ★   → sets the role bits (ONLY accounts 1
                                       and 2 may issue it)
    pilot.role-for <name> <bits> ★   → the same by name

Bits: View 1 · Edit 2 · Ban 4 · CommunityManager 8 · Developer 16 ·
Console 32 · GodMode 1024 · Mod 2048. Added up: e.g. Developer+Console = 48.
It is easier to tick them on the WebPanel's Users page.

## Experience and resources

    pilot.xp <amount>                → XP for yourself
    pilot.xp-for <name> <amount>     → adds XP to someone else
    pilot.xp-set <name> <amount>     → sets XP to an exact value
    pilot.resource <type> <amount>   → resources for yourself
    pilot.resource-for <name> <type> <amount>
                                     → resources for someone else

`<type>` matches the client's button names (e.g. cubits, tylium, titanium,
water, token). The same thing is easier from the WebPanel's Users page.

## Faction and appearance

    pilot.faction <name> <with_cubits?> <price>
                                     → faction change; arg 2 says whether
                                       the fee is in cubits, arg 3 is the
                                       price
    paint.drop-all <name>            → takes ALL of the pilot's paints away
    pilot.station <room>             → sends them to a given station room
    pilot.settings                   → prints the client settings
    pilot.squad-refresh <0|1>        → refreshes the squad indicator

## Skills

    pilot.train <skill_id>           → teaches a skill
    pilot.untrain <skill_id>         → takes a skill away

## Mail

    mail.send <name>                 → test system letter
    mail.send-to <name> <cubit> <tylium> <titanium> <token>
                                     → letter with a resource attachment

Example: `mail.send-to Tuser 1000 50000 20000 5`

## Boosts (★ Developer layer for loot/di)

    boost.loot <name> <multiplier> <hours> ★ → loot multiplier for a time
    boost.di <name> <multiplier> <hours>   ★ → DI multiplier for a time
    boost.report                             → prints your own multipliers
    boost.clear                              → clears your own multipliers

## Assignments (★ Developer layer)

    assignment.clear             ★   → clears your daily assignments
    assignment.clear-for <name>  ★   → clears assignments for someone else
    assignment.repair <name>     ★   → puts stuck assignments back in order
    assignment.report                → test message of the assignment log
