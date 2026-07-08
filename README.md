# reBSGO Python Server

**Coming soon:** this repository contains a Python-based reimplementation of a **Battlestar Galactica Online** game server. The goal is to provide a server-side system that can communicate with the original Unity client and run the core multiplayer gameplay: login, galaxy navigation, sectors, movement, combat, NPCs, ships, inventory, shop, community systems and data-driven game content.

This repository is being prepared for public release. It contains the server code and server-side data files only. The original client, client assets and third-party game files are not included.

### Technology

- **Python 3.11+** is the main implementation language. The server is structured around Python packages for protocols, gameplay systems, sector simulation, persistence, templates and networking.
- **SQLite** is used for persistent server state: player records, hangars, containers, guilds, missions, selected equipment and other account/gameplay data that must survive restarts.
- **Custom TCP protocol layer** mirrors the original client protocol families. The project implements read/write protocol handling for login, game, player, universe, scene, shop, community, notification, ranking, arena and other client-facing systems.
- **GameData JSON/template system** is the content backbone. Ships, weapons, modules, paints, NPCs, sectors, colliders, loot tables, missions, shop entries, carrier settings, outpost data and other gameplay content are loaded from data files instead of being hardcoded wherever possible.
- **Threaded sector simulation** drives the real-time game world. Each active sector processes movement, collision, combat, NPC logic, timers, object visibility, state/property updates and outgoing broadcasts.
- **Spatial indexing and hotpath optimization** are used for high-object-count sectors. Uniform grid / spatial hash based candidate filtering reduces full object scans in collision, NPC targeting, missiles, mines, damage areas and ability effects.
- **Rust/PyO3 native hotpath** accelerates CPU-heavy operations such as radius filtering, distance checks, spatial candidate generation, future position calculations and packet-oriented helper paths.
- **Performance guardrails and diagnostics** provide switchable logging for slow ticks, sender queues, player input latency, GameData loading, database operations and sector hotpath summaries.

### Implemented Highlights

- **Login, sessions and player state:** account/session flow, player profile data, hangar state, inventory/container handling, resources, selected consumables and persistent save/load paths.
- **Galaxy and sector flow:** galaxy map state, sector entry, scene transitions, jump handling, group jumps, beacon jumps, carrier transponders and sector object synchronization.
- **Real-time movement:** speed and gear handling, WASD/QWEASD-style movement commands, movement frame updates, out-of-sector checks, position broadcasts and player input prioritization.
- **Combat and abilities:** cannon fire, missiles, mines, flares, AoE effects, buffs/debuffs, stealth, fortify, slide, shrapnel, toggle systems, target updates and deterministic damage application.
- **NPC systems:** static and dynamic NPC spawning, target selection, AI timers, combat participation, loot/drop generation and cleanup logic.
- **Mining and resources:** mining actions, resource scanning, asteroid and planetoid resource spawning, mining ship behavior and related NPC interactions.
- **Outposts and sector control:** outpost spawning, readiness/decrease logic, beacons, platforms, HP bonuses and sector-level state updates.
- **Carrier and capital ship support:** carrier/base mode, anchoring, unanchoring, launch strikes, T1 docking/anchoring behavior, carrier transponder logic and capital ship map/visibility support.
- **Shop, catalogue and ship content:** catalogue delivery, shop filtering, paints, ship upgrades, stealth ships, capital ship data and GameData-driven content expansion.
- **Community and progression systems:** party, guild, friends/community, chat integration, rankings, arena, WOF, dialog, story, notifications and mission-related flows.
- **Debug and operations:** admin/debug commands, test helpers, configurable diagnostics and performance guardrail logs for investigating high-load gameplay issues.

### Client Compatibility

The server is designed around the original BSGO client protocol and asset expectations. In the current state, most core gameplay paths are implemented and usable server-side.

Rough functional estimate: **around 75-85% of the main client-facing gameplay features** are currently connected. This is not an exact asset-count metric; it is a practical gameplay estimate. The remaining work is mostly around rarer, legacy, event-specific or partially implemented client systems, such as some market/battlespace/tournament-style flows and edge cases.

### Status

The project is under active development and is NOT an official BSGO server. It is not affiliated with the original rights holders.

---

**Hamarosan:** ez a repository a **Battlestar Galactica Online** játékszerver Python-alapú újraimplementációját tartalmazza. A cél egy olyan szerveroldali rendszer, amely képes kommunikálni az eredeti Unity klienssel, és futtatni a fő multiplayer játékmenetet: belépés, galaxisnavigáció, szektorok, mozgás, harc, NPC-k, hajók, inventory, shop, közösségi rendszerek és adatvezérelt játéktartalom.

A repository jelenleg publikus megjelenésre készül. Csak a szerverkódot és a szerveroldali adatfájlokat tartalmazza. Az eredeti kliens, kliens assetek és harmadik féltől származó játékfájlok nem részei a projektnek.

### Technológia

- **Python 3.11+** a fő implementációs nyelv. A szerver Python csomagokra épül protokollokhoz, gameplay rendszerekhez, szektor-szimulációhoz, perzisztenciához, template-kezeléshez és hálózati kommunikációhoz.
- **SQLite** tárolja a perzisztens szerverállapotot: játékosadatokat, hangart, containereket, guildeket, mission állapotokat, kiválasztott felszereléseket és egyéb restart után is megmaradó gameplay adatokat.
- **Saját TCP protokollréteg** igazodik az eredeti kliens protokollcsaládjaihoz. A projekt kezel login, game, player, universe, scene, shop, community, notification, ranking, arena és több más kliensoldali protokollágat.
- **GameData JSON/template rendszer** adja a tartalmi alapot. Hajók, fegyverek, modulok, festések, NPC-k, szektorok, colliderek, loot táblák, missionök, shop elemek, carrier beállítások, outpost adatok és egyéb gameplay tartalmak adatfájlokból töltődnek be, ahol csak lehet hardcode helyett.
- **Threadelt szektor-szimuláció** futtatja a valós idejű játékteret. Az aktív szektorok mozgást, collisiont, harcot, NPC logikát, timereket, objektum-láthatóságot, state/property frissítéseket és kimenő broadcastokat dolgoznak fel.
- **Spatial index és hotpath optimalizáció** segíti a sok objektumot tartalmazó szektorokat. Uniform grid / spatial hash alapú candidate szűrés csökkenti a teljes objektumlista-végigjárásokat collision, NPC target keresés, rakéták, aknák, damage area és ability effektek esetén.
- **Rust/PyO3 native hotpath** gyorsítja a CPU-igényes részeket, például radius szűrést, távolságellenőrzést, spatial candidate generálást, jövőbeli pozíciószámítást és packet-közeli segédútvonalakat.
- **Teljesítmény guardrail és diagnosztika** kapcsolható logolást ad lassú tickekhez, sender queue-khoz, player input késéshez, GameData betöltéshez, adatbázis műveletekhez és szektor hotpath összegzésekhez.

### Megvalósított főbb elemek

- **Login, session és játékosállapot:** account/session folyamatok, játékosprofil, hangar állapot, inventory/container kezelés, erőforrások, kiválasztott consumable állapotok és perzisztens mentési/betöltési útvonalak.
- **Galaxy és szektorfolyamatok:** galaxy map állapot, szektorbelépés, scene váltás, jump kezelés, group jump, beacon jump, carrier transponder és szektorobjektum-szinkronizáció.
- **Valós idejű mozgás:** speed és gear kezelés, WASD/QWEASD jellegű movement parancsok, movement frame frissítések, out-of-sector ellenőrzések, pozíció broadcast és player input prioritás.
- **Harc és ability-k:** cannon lövés, rakéták, aknák, flare, AoE effektek, buff/debuff, stealth, fortify, slide, shrapnel, toggle rendszerek, target update-ek és determinisztikus damage alkalmazás.
- **NPC rendszerek:** statikus és dinamikus NPC spawn, célválasztás, AI timerek, combat részvétel, loot/drop generálás és cleanup logika.
- **Bányászat és erőforrások:** mining actionök, resource scan, asteroid és planetoid resource spawn, mining ship működés és kapcsolódó NPC interakciók.
- **Outpost és szektorkontroll:** outpost spawn, readiness/decrease logika, beaconök, platformok, HP bonuszok és szintű szektorállapot-frissítések.
- **Carrier és capital ship támogatás:** carrier/base mode, anchor, unanchor, launch strikes, T1 dock/anchor viselkedés, carrier transponder logika és capital ship map/láthatósági támogatás.
- **Shop, catalogue és hajótartalom:** catalogue kiszolgálás, shop szűrés, festések, hajófejlesztés, stealth hajók, capital ship adatok és GameData-alapú tartalombővítés.
- **Közösségi és progression rendszerek:** party, guild, friend/community, chat integráció, ranking, arena, WOF, dialog, story, notification és mission jellegű folyamatok.
- **Debug és üzemeltetés:** admin/debug parancsok, tesztelési segédek, kapcsolható diagnosztika és teljesítmény guardrail logok nagy terhelésű gameplay helyzetek vizsgálatához.

### Kliens-kompatibilitás

A szerver az eredeti BSGO kliens protokolljaihoz és asset-elvárásaihoz igazodik. A jelenlegi állapotban a fő játékmeneti utak többsége szerveroldalon megvalósított és használható.

Gyakorlati becslés szerint a fő kliensoldali gameplay funkciók **kb. 75-85%-a** jelenleg be van kötve. Ez nem pontos asset-darabszám, hanem funkcionális becslés; a maradék főleg ritkább, legacy, event-jellegű vagy részben megvalósított kliensrendszerekhez kötődik, például egyes market/battlespace/tournament jellegű folyamatokhoz és edge case-ekhez.

### Állapot

A projekt aktív fejlesztés alatt áll, és NEM hivatalos BSGO szerver. Nem áll kapcsolatban az eredeti jogtulajdonosokkal.
