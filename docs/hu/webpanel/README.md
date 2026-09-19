[github.com/Shran21](https://github.com/Shran21)

# WebPanel — áttekintés

A WebPanel a szerver webes adminfelülete: böngészőből intézhető minden, amihez
eddig parancssor kellett — fiókok, szektorok, adatbázis, naplók, beállítások,
mentések, konzol.

**Cím:** `http://<a gép címe>:27055`. Friss telepítés után a panel a saját
gépéről nyílik; a hálózat felé a `PANEL_HOST=0.0.0.0` beállítás nyitja meg,
nyilvános eléréshez TLS-proxy ajánlott (`beallitasok.md`).

## Belépés

Ugyanaz a **pilótanév és jelszó**, mint a játékban — nincs külön panel-fiók.
A panel a játékszerver saját jelszótárát kérdezi, tehát a jelszóváltás
mindkét helyen egyszerre érvényes.

Belépni csak **Developer (16)** vagy **Console (32)** szereppel lehet. Aki
egyikkel sem rendelkezik, ugyanazt a mondatot kapja, mint aki rossz jelszót
írt — szándékosan, hogy kívülről ne lehessen fiókokat feltérképezni.

- A belépés **12 óráig** érvényes, és használat közben automatikusan megújul.
- Címenként **percenként 10** próbálkozás engedett.
- Minden belépés, elutasítás és írás bekerül a panel auditjába
  (`WebPanel/logs/panel-audit.log`, a felületen az **Audit** fül).

A felület **magyarul és angolul** érhető el; a nyelvváltó a bal oldalsáv
alján van, a választás sütiben marad.

## Mit mi enged — szerepek

| Szerep | Mire jogosít a panelen |
|---|---|
| **Developer (16)** | mindenre: adatbázis-írás, beállítás-mentés, fiók-létrehozás és -törlés, szektor-műveletek, mentések, újraindítás |
| **Console (32)** | belépés, olvasás, a Konzol fül, kirúgás, közlemény |
| **Ban (4)** | jelszó-változtatás és kitiltás |
| **Edit (2)** | pilóta-nyersanyagok szerkesztése |

A Mod (2048) bit **letiltja a konzolt**, akkor is, ha Console szerep van
mellette — ez a játék szabálya, a panel is ezt követi.

Két visszatérő korlát:

- **Bent lévő pilóta adatai nem szerkeszthetők** (szerep, nyersanyag, fiók
  törlése, adatbázis-sorai). Amíg valaki játszik, az adatait a szerver tartja
  a memóriában, és két percenként visszaírja — a panelből írt érték elveszne.
  A panel ilyenkor jelzi, hogy a pilótának előbb ki kell lépnie a játékból.
- **Minden írás CSRF-védett**, és minden írás auditba kerül.

## Kényelmi funkciók

- **Téma:** a felület a rendszer világos/sötét beállítását követi; a bal
  oldalsáv alján lévő gombbal rögzíthető a világos vagy a sötét, a választás
  a böngészőben marad.
- **Keresés (Ctrl+K):** egyetlen mezőből ugrás pilótára, szektorra vagy
  kártyára — a nyilak léptetnek, az Enter megnyit.
- **Élő frissítés:** az áttekintés, a felhasználók, a szektorok és a
  csillagtérkép egyetlen eseménycsatornán kapja a változást, és csak akkor
  tölt újra, ha történt valami; a lap fejlécében látszik, mikor frissült.
  Ahol a csatorna nem tartható, a lap időzített frissítésre vált.
- **Áttekintés:** friss hibák, utolsó mentés, szabad lemez, karbantartás,
  a bent lévők görbéje az elmúlt órából, a legforgalmasabb szektorok és
  gyorsgombok.
- **Felhasználók:** név szerinti szűrés, rendezés oszlop szerint, alapból
  a bent lévők elöl.
- **Napló:** minden sor dátummal; az error-fül alapból csak a valódi hibákat
  mutatja (a figyelmeztetéseket egy kapcsoló hozza be), az áttekintés is
  hibákat számol, nem fájlméretet; a betöltött sorok helyben szűrhetők, a
  nézet másolható vagy letölthető; követés közben a fájl változásakor frissül.
- **Monitor:** egy órás vagy 24 órás előzmény, ami a panel újraindítását is
  túléli.
- **Megerősítés:** a veszélyes gombok (újraindítás, törlés, kitiltás) előtt
  párbeszédablak mondja ki, mi történik és kiket érint.

Kiadott szerveren a panel ugyanúgy olvassa a kártyákat és a sablonokat, mint
a játék, a játékadat viszont csak olvasható: a **Játék-beállítások** fül és a
szektor-szabályzat ilyenkor nem menthető, és a panel ezt ki is írja.

## Fájlok

| Fájl | Témakör |
|---|---|
| `fulek.md` | fülről fülre: mit tud és mihez kell szerep |
| `beallitasok.md` | konfiguráció, panel saját beállításai, mentés-ütemezés, játék-hangolás |
| `muszaki.md` | felépítés, panel-ajtó, fájlok, hibakeresés |

A napi üzemeltetés parancssori oldala a `docs/hu/szerver-admin/`, a konzolparancsok
a `docs/hu/devconsole/` mappában vannak.
