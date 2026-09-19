[github.com/Shran21](https://github.com/Shran21)

# Saját hajó, célpont, lőszer

## Saját hajó

    ship.invulnerable <0|1>          → sebezhetetlenség (GodMode); a kliens
                                       god_mode gombja is ezt küldi
    ship.buff <típus>                → buff a saját hajóra (self_buff gomb)
    ship.max-gear <név>              → a megnevezett pilóta hajója max
                                       felszereltségre
    ship.speed <érték>               → sebesség-állítás próbához
    ship.teleport <név> <táv>        → teleport a megnevezetthez adott
                                       távolságra
    ship.teleport-centre             → teleport a szektor közepére
    ship.visibility <0|1> [indok]    → a saját hajó láthatóság-kapcsolója
    ship.fly <guid>                  → átülés a megadott hajókártyába
    ship.fly-for <név> <guid>        → másik pilóta átültetése

## Célpont-műveletek (előbb jelölj célt a játékban)

    target.report                    → a célpont teljes adatlapja
    target.kill                      → a célpont azonnali elpusztítása
                                       (kill_target gomb)
    target.loot                      → a célpont zsákmányának kiszórása
                                       (loot_target gomb)
    target.scan-all                  → minden objektum felfedése neked
    target.scan-all-for <név>        → ugyanez a megnevezettnek
    object.mark <0|1>                → a célpont kiemelés-jelölése
    object.report <név> <guid> <szint>
                                     → tárgy-jelentés a megnevezett
                                       raktárából
    object.report-guid <név> <guid>  → tárgy-jelentés guid szerint

## Lőszer és fogyóeszköz (a kliens consumable gombja az ammo.give)

    ammo.give <név> <guid> <darab>   → adott fogyóeszköz adása
    ammo.weapons                     → fegyver-lőszereid feltöltése
    ammo.hull                        → burkolat-javítók feltöltése
    ammo.computer                    → számítógép-fogyók feltöltése
    ammo.engine                      → hajtómű-fogyók feltöltése
    ammo.all                         → minden fogyóeszközöd feltöltése

## Egyéb

    augment.try                      → augment-próba
    refund.all <lvl1_guid>           → fejlesztési lánc visszatérítése
    skill_learn / skill_unlearn      → a pilot.train / pilot.untrain gomb-nevei
