[github.com/Shran21](https://github.com/Shran21)

# Szerver-adminisztráció — áttekintés

A napi üzemeltetésnek két útja van.

**WebPanel** (`http://<a gép címe>:27055`) — böngészőből intézhető a
felhasználó- és szerepkezelés, a kitiltás, a nyersanyagok, a szektorok, a
konzol, a naplók, a konfiguráció, a monitoring, a mentések és az ütemezett
újraindítás. A belépés a játékbeli névvel és jelszóval megy, Developer vagy
Console szereppel. Saját leírása: `docs/hu/webpanel/`.

**Parancssor** — systemd, a `tools/` szkriptjei és a telepítő.

| Fájl | Témakör |
|---|---|
| `uzemeltetes.md` | indítás, leállítás, naplók, futás közbeni állítások |
| `fiokok.md` | fiókok, jelszavak, szerepek, kitiltás |
| `mentes-telepites.md` | mentés, hordozható csomag, telepítés új gépre |

A fejlesztői konzol parancsai a `docs/hu/devconsole/`, a WebPanel fülről fülre
haladó leírása a `docs/hu/webpanel/` mappában van.
