[github.com/Shran21](https://github.com/Shran21)

# Keltés (spawn) parancsok

Mind a kiadó pilóta **saját szektorában** és a **saját hajója körül**
dolgozik: a `<sugár>` egy dobozt jelöl a hajó körül, ezen belül sorsolódik
minden példány helye. A sugár alsó határa 10.

## npc.spawn — NPC-hajók keltése

    npc.spawn <darab> <sugár> [típus] [élettartam_mp]

- `típus` lehet:
  - üresen hagyva: a kiadó **saját hajójának** kártyájából kelt (annak másait);
  - `random` (vagy `mix`, `all`): véletlen hajótípusok vegyesen;
  - `random_cylon` / `random_colonial`: véletlen, de csak az adott frakcióból;
  - egy **GUI-kulcs** (pl. a gui.json `key` mezője).
- `élettartam_mp`: ennyi másodperc után maguktól eltűnnek (alapérték 3600).
- A keltett NPC-k a sugár-dobozon belül járőröznek.

Példák:

    npc.spawn 10 800 random 600      → 10 véletlen NPC, 10 perc élettartammal
    npc.spawn 3 200                  → 3 másolat a saját hajóból

## drone.spawn — drónok

    drone.spawn <darab> <sugár> [típus] [élettartam_mp]
    drone.spawn 1 1 help             → kiírja a saját súgóját

- `típus`: `human` / `cylon` (kis, T1), `human_large` / `cylon_large`
  (nagy, T3), `large` (= `human_large`). Üresen: a frakciód kis drónja.
- Nevesített fajták (a kliens összes drón-azonossága, a Dev/spawn_types.json
  `droneKinds` térképéből): `strike_buffer`, `strike_cannon`,
  `strike_debuffer`, `strike_missiletank` (Ébredés-esemény drónjai),
  `training`, `target` (gyakorló), `story1_dps`, `story1_tank`,
  `story2_dps`, `story2_tank`, `tutorial_damaged`, `tutorial_static`,
  `wave_dps`, `wave_tank`, `ancient_small_dps`, `ancient_large_tank`,
  és `command` (Drónparancsnoki hálózati hajó — fegyvertelen célhajó).

Példa: `drone.spawn 5 200 human_large 600`, `drone.spawn 1 300 command`

## platform.spawn és platform.ring — fegyverplatformok

    platform.spawn <darab> <sugár> [típus]
    platform.spawn 1 1 help          → kiírja a típusneveket

- `típus`: `stationary1`–`3` (= `humanstationary1`–`3`). Üresen: ősi (ancient)
  alapplatform.
- Frakciónév (`colonial`/`cylon`) megadásakor a platform ahhoz a frakcióhoz
  tartozik majd. A típusnevek a `GameData/templates/Dev/spawn_types.json`
  fájlból jönnek — új típust oda kell felvenni.
- A `platform.ring` ugyanígy működik, csoport-keltésre; pl.
  `platform.ring 3 400 stationary1`.

Példa: `platform.spawn 3 200 stationary2`

## Objektum-keltők

    cargo.spawn                      → gyűjthető konténer (az alap fajta)

## Takarítás

    debris.clear                     → minden roncs törlése a szektorból
    planet.clear                     → minden bolygó törlése
    sector.clear                     → minden NEM-játékos objektum törlése

A keltett objektumok nem élik túl a szektor újraindítását — a WebPanel
Szektorok fülén egy Újraindítás mindent alaphelyzetbe tesz.
