[github.com/Shran21](https://github.com/Shran21)

# Keltés (spawn) parancsok

Mind a kiadó pilóta **saját szektorában** és a **saját hajója körül**
dolgozik: a `<sugár>` egy dobozt jelöl a hajó körül, ezen belül sorsolódik
minden példány helye. A sugár alsó határa 10.

## npc.spawn — NPC-hajók keltése

    npc.spawn <darab> <sugár> [típus] [élettartam_mp]

- `típus` lehet:
  - üresen hagyva: a kiadó **saját hajójának** kártyájából kelt (annak másait);
  - `colonial` vagy `cylon`: az adott frakció NPC-hajója;
  - `random` (vagy `mix`, `all`): véletlen hajótípusok vegyesen;
  - `random_cylon` / `random_colonial`: véletlen, de csak az adott frakcióból;
  - egy **hajó-guid** vagy **GUI-kulcs** (pl. a gui.json `key` mezője).
- `élettartam_mp`: ennyi másodperc után maguktól eltűnnek (alapérték 3600).
- A keltett NPC-k a sugár-dobozon belül járőröznek.

Példák:

    npc.spawn 5 300 cylon            → 5 cylon NPC 300-as körzetben
    npc.spawn 10 800 random 600      → 10 véletlen NPC, 10 perc élettartammal
    npc.spawn 3 200                  → 3 másolat a saját hajóból
    npc.spawn 1 150 124779515        → 1 db a megadott guid-ú hajóból

## drone.spawn — drónok

    drone.spawn <darab> <sugár> [típus] [élettartam_mp]
    drone.spawn 1 1 help             → kiírja a saját súgóját

- `típus`: `human` / `cylon` (kis, T1), `human_large` / `cylon_large`
  (nagy, T3), `small` / `large` (a saját frakciód alapértelmezettje),
  vagy közvetlen guid. Üresen: a frakciód kis drónja.
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

- `típus`: `stationary1`–`6` (= `humanstationary1`–`6`, kolóniai),
  `cylonstationary1`–`6`, vagy guid. Üresen: ősi (ancient) alapplatform.
- Frakciónév (`colonial`/`cylon`) megadásakor a platform ahhoz a frakcióhoz
  tartozik majd. A típusnevek a `GameData/templates/Dev/spawn_types.json`
  fájlból jönnek — új típust oda kell felvenni.
- A `platform.ring` ugyanígy működik, csoport-keltésre.

Példa: `platform.spawn 3 200 stationary2`

## Objektum-keltők (★ mindegyikhez Developer kell a comet.spawn-nál)

    comet.spawn                      → üstökös a szektor közepére (★)
    comet.spawn-guid <guid>          → üstökös adott kártyából
    nebula.spawn                     → egy roncs-köd (16-os debris) keltése
    cargo.spawn [guid]               → gyűjthető konténer; üresen az alap
                                       konténer (50000113)
    debris.spawn <guid> <y>          → roncsmező adott magasságra (x=z=0)
    planet.spawn <guid> <x> <y> <z> <rx> <ry> <rz>
                                     → bolygó adott helyre és szögbe

## Takarítás

    debris.clear                     → minden roncs törlése a szektorból
    planet.clear                     → minden bolygó törlése
    sector.clear                     → minden NEM-játékos objektum törlése

A keltett objektumok nem élik túl a szektor újraindítását — a WebPanel
Szektorok fülén egy Újraindítás mindent alaphelyzetbe tesz.
