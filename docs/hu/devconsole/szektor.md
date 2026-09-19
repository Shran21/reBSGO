[github.com/Shran21](https://github.com/Shran21)

# Szektor-műveletek

Minden parancs a kiadó **saját szektorában** hat, ha másképp nincs jelezve.

## Esemény és támaszpont

    sector.event                     → teherhajós esemény ÉLESÍTÉSE itt.
                                       Jelölő + zóna jelenik meg; akkor indul
                                       be, ha egy pilóta a zónába repül.
                                       Üres szektorban a kérés nem indít
                                       eseményt.
    outpost.points <colonial|cylon> <pont>
                                     → készültség-pont ± ebben a szektorban
                                       (0–3000 a skála; 900-tól áll a
                                       támaszpont, 1350-től jöhet jeladó)
    outpost.points-max               → MINDEN szektor mindkét oldala 3000-re

Példa: `outpost.points cylon 1500`

## Tájékozódás

    sector.census                    → objektum-összeírás a szektorról
    sector.zones                     → zóna-információk (★ Developer)
    asteroid.ore-report              → érc-tartalmú aszteroidák jelentése
    sector.template                  → a szektor sablon-adatainak kiírása

## Utazás

    sector.jump <szektor_id>         → azonnali átugrás a megadott szektorba
    sector.jump-notice <hibakód> <indok>
                                     → ugrás-elutasító üzenet próbája

## Aszteroida-generálás

    sector.fill <mag> <aszteroida> <planetoid> <mezők> <db/mező> <mezőméret> <hurok> <hurokméret> <db/hurok>
        → teljes szektor-szórás kilenc egész számmal; a <mag> a
          véletlen-mag, így ugyanaz a szám ugyanazt a képet adja.

    asteroid.tendril <mag> <középtől> <db> <csápok> <szög>
        → csáp-alakzatú aszteroidafürt

    asteroid.ring <mag> <középtől> <db> <belső> <külső> <szög>
        → gyűrű alakzat a belső–külső sugár között

    asteroid.unstick                 → beragadt (ütköző) aszteroidák szétlökése
    asteroid.clear                   → minden aszteroida törlése
    asteroid.clear-water             → csak a víz-tartalmúak törlése
    planet.mining-rig                → bányász-fúró próbája a planetoidon

Példa: `asteroid.ring 42 0 120 800 1600 15`

A generálók MEMÓRIÁBAN dolgoznak: az eredmény a szektor újraindulásáig él.
Ha egy elrendezés végleges kell, a Sector-sablonba (GameData/templates/
Sector/sector_N.json) kell átvezetni — ehhez jók a `<mag>` értékek, mert
reprodukálható a kép.
