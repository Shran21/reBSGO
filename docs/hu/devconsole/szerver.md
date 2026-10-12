[github.com/Shran21](https://github.com/Shran21)

# Szerver-szintű parancsok

## Állapot

    server.online                    → bent lévők száma frakcióbontásban
    server.report                    → statisztika-összefoglaló
                                       (stats_debug_dump gomb)
    server.hull-census           ★   → hajótípusonkénti összeírás
    server.hull-keys             ★   → a négy nagy hajópár darabszáma
    sector.census                    → a saját szektor objektumai

## Leállítás és újraindítás

Erre a WebPanel való: Eszközök → Ütemezett újraindítás (kihirdet,
figyelmeztet 5 és 1 percnél, újraindít, lefújható).

## Közlemények

    notice.all "<szöveg>"            → felugró üzenet minden bent lévőnek
                                       pl. notice.all "Karbantartás 10 perc múlva"
    notice.restart                   → beépített "újraindítás jön" üzenet
    notice.me                        → próbaüzenet magadnak

## Beállítás-kapcsolók (★ Developer réteg)

    server.gear-level            ★   → NPC-felszereltség szint-kapcsoló
    server.gear-by-faction       ★   → ugyanez frakciónként

## Jutalom-próbák

    reward.try                       → jutalom-ablak próbája (100 cubit)
