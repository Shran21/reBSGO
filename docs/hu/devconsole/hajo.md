[github.com/Shran21](https://github.com/Shran21)

# Saját hajó, célpont, lőszer

## Saját hajó

    ship.invulnerable <true|false>   → sebezhetetlenség (GodMode); a kliens
                                       god_mode gombja is ezt küldi
                                       pl. ship.invulnerable true
    ship.buff <típus>                → buff a saját hajóra (self_buff gomb)
                                       pl. ship.buff heal
                                       (típusok: speed, heal, dmg, range,
                                       cooldown, dispell)
    ship.max-gear <név>              → a megnevezett pilóta hajója max
                                       felszereltségre
                                       pl. ship.max-gear Vega
    ship.speed <érték>               → sebesség-állítás próbához
                                       pl. ship.speed 150
    ship.teleport <név> <táv>        → teleport a megnevezetthez adott
                                       távolságra
                                       pl. ship.teleport Vega 500
    ship.teleport-centre             → teleport a szektor közepére
    ship.visibility <true|false> <ok>
                                     → a saját hajó láthatóság-kapcsolója
                                       pl. ship.visibility false Default
                                       (ok: Default, Jump, Death, Anchor)

## Célpont-műveletek (előbb jelölj célt a játékban)

    target.report                    → a célpont teljes adatlapja
    target.kill                      → a célpont azonnali elpusztítása
                                       (kill_target gomb)
    target.loot                      → a célpont zsákmányának kiszórása
                                       (loot_target gomb)
    target.scan-all                  → a szektorod összes aszteroidájának és
                                       kisbolygójának beszkennelése; ehhez
                                       nem kell célpont, csak űrben kell
                                       lenned. Utána mindegyiknél látod,
                                       milyen nyersanyag van benne, a
                                       kisbolygóknál azt is, hogy
                                       bányászható-e még
    target.scan-all-for <név>        → ugyanez a megnevezett pilótának, az
                                       ő szektorában
                                       pl. target.scan-all-for Vega
    object.mark <0|1>                → a célpont kiemelés-jelölése
                                       pl. object.mark 1

## Lőszer és fogyóeszköz

    ammo.weapons <név> <darab>       → fegyver-lőszer a megnevezettnek
                                       pl. ammo.weapons Vega 50
    ammo.hull <név> <darab>          → burkolat-javító a megnevezettnek
                                       pl. ammo.hull Vega 10
    ammo.computer <név> <darab>      → számítógép-fogyó a megnevezettnek
                                       pl. ammo.computer Vega 10
    ammo.engine <név> <darab>        → hajtómű-fogyó a megnevezettnek
                                       pl. ammo.engine Vega 10
    ammo.all <név> <darab>           → minden fogyóeszköz a megnevezettnek
                                       pl. ammo.all Vega 20

## Egyéb

    augment.try                      → augment-próba
    skill_learn / skill_unlearn      → a pilot.train / pilot.untrain gomb-nevei
                                       pl. skill_learn 0
