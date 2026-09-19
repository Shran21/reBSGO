[github.com/Shran21](https://github.com/Shran21)

# Server-level commands

## Status

    server.online                    → number of players online, by faction
    server.report                    → statistics summary
                                       (stats_debug_dump button)
    server.hull-census           ★   → census by hull type
    server.hull-keys             ★   → counts of the four big ship pairs
    sector.census                    → the objects in your own sector

## Shutdown (careful!)

    server.stop                  ★   → stops the game server immediately
    server.stop-now <minutes>        → timed shutdown, in minutes

The gentler route is the WebPanel: Tools → Scheduled restart (it
announces the restart, warns at 5 and 1 minutes, restarts, and can be
called off).

## Notices

    notice.all "<text>"              → pop-up message for everyone online
    notice.restart                   → built-in "restart incoming" message
    notice.banner                    → banner box test for yourself
    notice.me                        → test message for yourself

## Tallies (★ Developer layer) — the basis of the leaderboards

    tally.set <name> <tally_guid> <star_guid> <value> ★
    tally.add <name> <tally_guid> <star_guid> <amount> ★

You can see the names of the tally guids on the WebPanel's Leaderboards
tab; star_guid is 0 for the global rows.

## Setting switches (★ Developer layer)

    pilot.multi-login            ★   → toggles the multiple-login permission
    server.gear-level            ★   → NPC gear level switch
    server.gear-by-faction       ★   → the same per faction

## Reward tests

    reward.try                       → reward window test (100 cubits)
