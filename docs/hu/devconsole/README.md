[github.com/Shran21](https://github.com/Shran21)

# Devconsole — áttekintés

A fejlesztői konzol a kliensből érhető el (Enter → konzolsor), illetve a
WebPanel **Konzol** füléről is — mindkettő ugyanazt a szerver-oldali
gépezetet hajtja, ugyanazokkal a jogokkal.

## Jogosultság

- A konzol használatához **Console (32)** szerep kell, és a **Mod (2048) bit
  letiltja** — hiába van Console mellette.
- A `docs/hu/devconsole/` fájljaiban ★-gal jelölt parancsok a **fejlesztői
  rétegben** élnek: hozzájuk **Developer (16)** szerep is kell.
- A szerepeket a WebPanel Felhasználók lapján vagy a `pilot.role` paranccsal
  lehet állítani (utóbbi csak az 1-es és 2-es fióknak jár).

## Általános szabályok

- A parancsok argumentumai szóközzel válnak el; a több szavas szöveget
  idézőjelbe kell tenni: `notice.all "Karbantartás jön"`.
- A legtöbb szektor-kötött parancs (spawn, aszteroida, esemény) **abban a
  szektorban** hat, ahol a kiadója éppen repül — a WebPanel konzoljából ezek
  csak akkor mennek, ha a panelbe belépett pilóta bent van a játékban.
- A kliens 16 beégetett gomb-parancsnevet is küld (pl. `consumable`,
  `god_mode`, `spawn_comet`) — ezek a megfelelő pontos parancsok álnevei,
  a fájlokban a rendes nevüknél említjük őket.
- Saját álneveket a `GameData/local/console_aliases.json` fájlban lehet
  felvenni (gépenkénti fájl; a telepítő a meglévőt nem írja felül).

## Fájlok

| Fájl | Témakör |
|---|---|
| `spawn.md` | NPC-, drón-, platform- és objektum-keltés |
| `szektor.md` | szektor-műveletek, aszteroidák, támaszpont-készültség |
| `pilota.md` | pilóta-adminisztráció, XP, nyersanyag, posta, boostok |
| `hajo.md` | saját hajó, célpont-műveletek, lőszer |
| `szerver.md` | szerver-szintű parancsok, közlemények, számlálók |
