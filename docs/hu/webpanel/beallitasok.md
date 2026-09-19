[github.com/Shran21](https://github.com/Shran21)

# Beállítások a panelről

Három, egymástól független beállítás-csoport van, más-más helyen tárolva:

| Mit | Hol | Mikor lép életbe |
|---|---|---|
| a szerver futása (portok, naplózás, gyorsítótár, teljesítmény) | Konfiguráció fül → `.env` | a játékszerver újraindításakor |
| a panel maga (port, ki léphet be, mentés-ütemezés) | Konfiguráció fül → panel-szekció → `panel.env` | a panel újraindításakor (a mentés-ütemezés azonnal) |
| a játék viselkedése (események, aknák, hordozó) | Játék-beállítások fül → GameData-sablonok | a játékszerver újraindításakor |

## Konfiguráció fül — a szerver `.env`-je

A fül az **éles értékeket** mutatja: a mezőkben az van, ami a `.env`-ben áll.
A kulcslistát, a magyarázatokat és az alapértékeket a játék saját katalógusa
(`.env.example`) adja hozzá, így a lista nem térhet el a kódtól.

**Üres mező azt jelenti: nincs felülbírálva, az alapérték érvényes.** A feloldás
három rétegű, ebben a sorrendben:

1. a folyamat környezeti változói,
2. a `.env` fájl,
3. a beépített alapértékek (a kódban rögzített katalógus; ugyanezeket mutatja a `.env.example`).

A mentés a `.env`-et **helyben szerkeszti**: a kézzel írt kommentek és a
sorrend megmaradnak, az előző változat pedig `.env.panel-bak` néven marad meg.
Minden mentés auditba kerül, régi és új értékkel.

Két jelölés a felületen:

- **„óvatosan"** — ez a kulcs a panel saját hídját is kizárhatja
  (`REBSGO_PANEL_TOKEN`, a panel-ajtó portja).
- **„a katalóguson kívüli sorok"** — amit a `.env` tartalmaz, de a katalógus
  nem ismer. Ide kerül például a `GAME_CHAT_ADDRESS`: örökség-név, de él —
  ugyanazt a beállítást tölti, ami a katalógusban `REBSGO_NET_CHAT_ADDRESS`
  néven szerepel.

Az adatbázis útvonala (`REBSGO_DB`) is innen állítható. Áthelyezés esetén
**a panel `PANEL_DB` beállítását is ugyanoda kell irányítani** — különben a
panel egy másik adatbázist mutatna, mint amit a játék használ.

## Konfiguráció fül — a panel saját beállításai

A lap alján külön szekció szerkeszti a `panel.env`-et. A mentett érték a
**panel újraindításakor** él; a gomb ott van mellette.

| Kulcs | Mit állít |
|---|---|
| `PANEL_HOST` | melyik címen figyel: alapból `127.0.0.1` (csak ez a gép); `0.0.0.0` = minden hálózaton — nyilvános elérésre inkább TLS-proxy elé |
| `PANEL_PORT` | a panel portja (alapból 27055) |
| `PANEL_DB` | a játék-adatbázis útvonala a panel szemével |
| `PANEL_LOGIN_ROLES` | mely játékbeli szerepekkel lehet belépni |
| `PANEL_SESSION_HOURS` | meddig él egy belépés |
| `PANEL_BRIDGE_URL` | a játékszerver panel-ajtajának címe |
| `PANEL_DEFAULT_LANG` | a felület alapnyelve (`hu`/`en`) |
| `PANEL_BACKUP_DIR` | hová kerüljenek a mentések |
| `PANEL_BACKUP_AT` | napi automata mentés ideje `ÓÓ:PP` alakban; üresen kikapcsolva |
| `PANEL_BACKUP_KEEP` | hány automata mentés maradjon meg fajtánként |
| `PANEL_BACKUP_KIND` | `db` = adatbázis-pillanatkép, `full` = teljes tar.gz |

A panel titkos kulcsa (`PANEL_SECRET`) szándékosan **nem** szerkeszthető
innen: a cseréje mindenkit kiléptet, egy félbehagyott érték pedig magát ezt az
oldalt zárná ki. Cserélni csak a `panel.env` fájlban lehet.

## Mentések

Kétféle mentés van, és mindkettő ugyanabba a mappába dolgozik:

- **Adatbázis-pillanatkép** (`db`) — csak a játék-adatbázisról, tömörítve.
  Az SQLite saját mentő-eljárásával készül, ezért **játék közben is
  biztonságos**: nem szakad félbe attól, hogy a szerver közben ír.
  Kézzel az Adatbázis fülön indítható, letölteni is onnan lehet.
- **Teljes mentés** (`full`) — az egész szervermappa tar.gz-be (a naplók, a
  gyorsítótár és a virtuális környezetek nélkül). Kézzel az Eszközök fülön.

Az automata ütemezéshez elég a `PANEL_BACKUP_AT` időpontot beírni — **ez
azonnal érvényes, panel-újraindítás nélkül**. A panel félpercenként nézi az
órát, naponta egyszer fut le (akkor is, ha időközben újraindult), és a
`PANEL_BACKUP_KEEP` fölötti régi mentéseket automatikusan törli.

## Játék-beállítások fül

Kurált sablonok, mezőnkénti űrlapon, típus- és határellenőrzéssel. Ami itt
átírható:

| Sablon | Mit lehet állítani |
|---|---|
| Revenant-kísértés | be/ki, egyszerre hány szektorban, tiltott szektorok, felszerelés-szint, élettartam, újraindulási várakozás, járőr-sugár |
| Parancsnoki drónraj | be/ki, hullám mérete (min/max), új hullám késleltetése, keltés- és járőr-sugár, felszerelés-szint |
| Szektor-események | be/ki, kizárt szektorok, gyakoriság és szórás, egyidejű NPC-k, támadó-arány, időtartam, hullám-szünet |
| Aknák | élesedési sugár, robbanás-sugár, tartalék élettartam |
| Hordozó-dokkolás | dokkolási távolság, csak-párt kapcsolók, erődítés-követelmény, javítás |

Amit **nem** lehet innen elrontani: a funkciók azonosságát hordozó mezők
(kártya-GUID-ok, hajófajta-listák, robbanófej-táblák) szürkén, zárolva
látszanak; ezek csak a sablonfájlban módosíthatók.

Ha egy érték kilóg a megengedett tartományból, a mentés **nem ír semmit**, és
a panel megnevezi a hibás mezőt. Minden sikeres mentés auditba kerül, régi és új értékkel.

**Fontos:** ezeket a sablonokat a játék indításkor olvassa — a mentés után
**szerver-újraindítás** kell hozzá. A gomb ott van az oldal tetején.
