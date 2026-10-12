[github.com/Shran21](https://github.com/Shran21)

# Server-level commands

## Status

    server.online                    → number of players online, by faction
    server.report                    → statistics summary
                                       (stats_debug_dump button)
    server.hull-census           ★   → census by hull type
    server.hull-keys             ★   → counts of the four big ship pairs
    sector.census                    → the objects in your own sector

## Shutdown and restart

Use the WebPanel for this: Tools → Scheduled restart (it announces the
restart, warns at 5 and 1 minutes, restarts, and can be called off).

## Notices

    notice.all "<text>"              → pop-up message for everyone online
                                       e.g. notice.all "Maintenance in 10 minutes"
    notice.restart                   → built-in "restart incoming" message
    notice.me                        → test message for yourself

## Setting switches (★ Developer layer)

    server.gear-level            ★   → NPC gear level switch
    server.gear-by-faction       ★   → the same per faction

## Reward tests

    reward.try                       → reward window test (100 cubits)
