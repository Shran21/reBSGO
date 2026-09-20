[github.com/Shran21](https://github.com/Shran21)

# reBSGO

Magyar · [English](#english)

**Battlestar Galactica Online** játékszerver Pythonban, az eredeti Unity-klienshez: a teljes szerveroldal, egy webes adminfelület és a játék indítója egy csomagban.

Nem hivatalos projekt, és nem áll kapcsolatban az eredeti jogtulajdonosokkal. A kliens és a kliens fájljai nem részei a repónak.

## Telepítés

    ./install.sh

A telepítő megkérdezi a célmappát, a többit magától elvégzi: kibontja a csomagolt Python 3.13-at (rendszer-Python nem kell hozzá), ellenőrzi a natív gyorsítómodult, felépíti a panel környezetét, elkészíti a `.env`-et, végül telepíti és elindítja a `bsgo` és a `rebsgo-panel` szolgáltatást. Hálózati kapcsolat nélkül is végigfut.

| Szolgáltatás | Cím |
|---|---|
| beléptető ajtó, ide csatlakozik a launcher | `http://<a gép címe>:27051` |
| játék, chat | 27050, 27052 |
| WebPanel | `http://<a gép címe>:27055`, hálózati eléréshez `PANEL_HOST=0.0.0.0` |
| beállítások | `.env`, a kulcsok katalógusa a `.env.example` |

Bővebben: [telepítés és mentés](docs/hu/szerver-admin/mentes-telepites.md).

## A repó tartalma

| Mappa | Tartalom |
|---|---|
| `src/rebsgo/` | a szerver: protokollok, szektor-szimuláció, játékmenet, adattárolás |
| `GameData/` | a játék adatai |
| `WebPanel/` | a webes adminfelület |
| `launcher/` | a játék indítója |
| `docs/` | a dokumentációk |
| `tools/` | fiókkezelés és a launcher fájllistájának elkészítése |
| `schema/`, `native/`, `vendor/` | adatbázis-séma, natív gyorsítómodul, csomagolt Python |

## Launcher

A `launcher/rebsgo-launcher.exe` egyetlen fájl, telepítés nélkül fut Windowson. Első indításkor a szerver címét és a játék mappáját kéri, a portot és a `bsgo.exe`-t magától megtalálja; regisztrálni és belépni is ezen keresztül lehet. A jelszó nem jut el a klienshez, az csak egy belépőjegyet kap. Ha az üzemeltető beállította a fájllistát, a launcher indítás előtt a szerverén lévő klienshez igazítja a játékosét: a hiányzót és az eltérőt letölti, törölni sosem töröl.

Részletek: [a launcher leírása](docs/hu/launcher.md).

## Dokumentáció

A [`docs/`](docs/README.md) mappában, magyarul és angolul, ugyanazokkal az oldalakkal.

| Témakör | Hol |
|---|---|
| üzemeltetés: indítás, naplók, fiókok, mentés, telepítés | [`szerver-admin/`](docs/hu/szerver-admin/README.md) |
| WebPanel: belépés, fülek, beállítások, felépítés | [`webpanel/`](docs/hu/webpanel/README.md) |
| a fejlesztői konzol parancsai | [`devconsole/`](docs/hu/devconsole/README.md) |
| a játék indítója | [`launcher.md`](docs/hu/launcher.md) |

## Technológia

Python 3.13, a csomag hozza magával; a szerver a standard könyvtárra épül. Az adatok SQLite-ban laknak, a forró útvonalakon Rust/PyO3 natív modul gyorsít, lefordítva a fában. A WebPanel FastAPI-ra épül. A játéktartalom JSON-sablonokból jön, nem a kódból. A viselkedést a fejlesztés során pytest-készletek fedik: protokoll, játékszabályok, teljesítmény.

## Kapcsolat

- Projektoldal: <https://github.com/Shran21/reBSGO>
- E-mail: [shranit.dev@gmail.com](mailto:shranit.dev@gmail.com)

A launcher alsó sávjának **WEBOLDAL** és **KAPCSOLAT** hivatkozása ugyanide visz.

## Licenc

A szerver az **AGPL-3.0-or-later** feltételei szerint használható; a teljes szöveg a [LICENSE](LICENSE) fájlban. Ez hálózati szolgáltatásra is kiterjed: aki a szervert üzemelteti és módosítja, a módosított forrást elérhetővé kell tegye a játékosainak. A csomagban utazó idegen komponensek (Python, wheel-ek, betűtípusok, natív modul, launcher) saját licencüket viszik — a felsorolás a [NOTICE](NOTICE) fájlban.

## Állapot

Aktív fejlesztés alatt. Működik a belépés és a fiókkezelés, a galaxis és a szektorok, a mozgás, a harc és a képességek, az NPC-k, a bányászat, a támaszpontok, a hordozók és a capital hajók, a bolt, a közösségi rendszerek (párt, kötelék, chat), a ranglisták, az aréna, a küldetések és a napi bónusz. Hátravan néhány ritkább, esemény-jellegű kliensrendszer.

---

## English

English · [Magyar](#rebsgo)

A **Battlestar Galactica Online** game server in Python for the original Unity client: the full server side, a web admin interface and the game's launcher in one package.

An unofficial project, not affiliated with the original rights holders. The client and its files are not part of the repository.

### Installation

    ./install.sh

The installer asks for the target directory and does the rest on its own: it unpacks the bundled Python 3.13 (no system Python needed), checks the native accelerator module, builds the panel's environment, writes `.env`, then installs and starts the `bsgo` and `rebsgo-panel` services. It runs through without a network connection.

| Service | Address |
|---|---|
| admission door, where the launcher connects | `http://<the machine's address>:27051` |
| game, chat | 27050, 27052 |
| WebPanel | `http://<the machine's address>:27055`, set `PANEL_HOST=0.0.0.0` for network access |
| settings | `.env`, with every key catalogued in `.env.example` |

More on this: [installation and backups](docs/en/server-admin/backup-install.md).

### What the repository holds

| Directory | Contents |
|---|---|
| `src/rebsgo/` | the server: protocols, sector simulation, gameplay, storage |
| `GameData/` | the game's data |
| `WebPanel/` | the web admin interface |
| `launcher/` | the game's launcher |
| `docs/` | the documentation |
| `tools/` | account management and building the launcher's file list |
| `schema/`, `native/`, `vendor/` | database schema, native accelerator module, bundled Python |

### Launcher

`launcher/rebsgo-launcher.exe` is a single file that runs on Windows without installation. On the first start it asks for the server's address and the game folder, finding the port and `bsgo.exe` by itself; registration and sign-in go through it as well. The password never reaches the client, which receives a ticket instead. When the operator has set up the file list, the launcher aligns the player's client with the one on the server before starting: it downloads what is missing or different, and never deletes.

Details: [the launcher's write-up](docs/en/launcher.md).

### Documentation

In the [`docs/`](docs/README.md) directory, in English and Hungarian, with the same pages in both.

| Subject | Where |
|---|---|
| operations: starting, logs, accounts, backups, installation | [`server-admin/`](docs/en/server-admin/README.md) |
| WebPanel: signing in, tabs, settings, internals | [`webpanel/`](docs/en/webpanel/README.md) |
| the developer console's commands | [`devconsole/`](docs/en/devconsole/README.md) |
| the game's launcher | [`launcher.md`](docs/en/launcher.md) |

### Technology

Python 3.13, bundled with the package; the server is built on the standard library. Data lives in SQLite, and a Rust/PyO3 native module speeds up the hot paths, prebuilt in the tree. The WebPanel is built on FastAPI. Game content comes from JSON templates rather than from code. Behaviour is covered by pytest suites during development: protocol, game rules, performance.

### Contact

- Project page: <https://github.com/Shran21/reBSGO>
- Email: [shranit.dev@gmail.com](mailto:shranit.dev@gmail.com)

The **WEBOLDAL** and **KAPCSOLAT** links along the bottom of the launcher lead to the same two places.

### Licence

The server is available under the terms of **AGPL-3.0-or-later**; the full text is in [LICENSE](LICENSE). It covers network use as well: whoever runs a modified server has to offer the modified source to its players. The third-party components that travel in the package (Python, the wheels, the typefaces, the native module, the launcher) keep their own licences, listed in [NOTICE](NOTICE).

### Status

Under active development. Working: sign-in and account management, the galaxy and its sectors, movement, combat and abilities, NPCs, mining, outposts, carriers and capital ships, the shop, the community systems (party, guild, chat), rankings, the arena, missions and the daily bonus. What remains is mostly the rarer, event-style client systems.
