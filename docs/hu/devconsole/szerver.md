[github.com/Shran21](https://github.com/Shran21)

# Szerver-szintű parancsok

## Állapot

    server.online                    → bent lévők száma frakcióbontásban
    server.report                    → statisztika-összefoglaló
                                       (stats_debug_dump gomb)
    server.hull-census           ★   → hajótípusonkénti összeírás
    server.hull-keys             ★   → a négy nagy hajópár darabszáma
    sector.census                    → a saját szektor objektumai

## Leállítás (óvatosan!)

    server.stop                  ★   → a játékszerver azonnali leállítása
    server.stop-now <perc>           → leállítás időzítve, percekben

Kíméletesebb út a WebPanel: Eszközök → Ütemezett újraindítás (kihirdet,
figyelmeztet 5 és 1 percnél, újraindít, lefújható).

## Közlemények

    notice.all "<szöveg>"            → felugró üzenet minden bent lévőnek
    notice.restart                   → beépített "újraindítás jön" üzenet
    notice.banner                    → banner-doboz próbája magadnak
    notice.me                        → próbaüzenet magadnak

## Számlálók (★ Developer réteg) — ranglisták alapja

    tally.set <név> <számláló_guid> <csillag_guid> <érték> ★
    tally.add <név> <számláló_guid> <csillag_guid> <mennyi> ★

A számláló-guidok neveit a WebPanel Ranglisták fülén látod; a csillag_guid
0 a globális sorokhoz.

## Beállítás-kapcsolók (★ Developer réteg)

    pilot.multi-login            ★   → többes belépés engedélyének váltása
    server.gear-level            ★   → NPC-felszereltség szint-kapcsoló
    server.gear-by-faction       ★   → ugyanez frakciónként

## Jutalom-próbák

    reward.try                       → jutalom-ablak próbája (100 cubit)
