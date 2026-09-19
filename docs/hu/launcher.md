[github.com/Shran21](https://github.com/Shran21)

# Launcher — játékosnak és üzemeltetőnek

A `launcher/rebsgo-launcher.exe` a játék indítója: regisztráció, belépés,
fájl-ellenőrzés, indítás — egyetlen fájl, telepítő és függőségek nélkül,
Windowson.

## A játékos oldala

1. **Első indításkor a beállítás-lap fogad.** Két dolog kell: a **szerver
   címe** (a gép neve vagy IP-je, port nélkül — a beléptető ajtó portját a
   launcher maga keresi meg) és a **játék mappája** (a telepítés gyökerére is
   mutathat, a `bsgo.exe`-t három szint mélyen megtalálja). A mappa útvonalában
   **ne legyen szóköz**: a kliens a saját parancssorát szóközöknél vágja.
2. **Regisztráció és belépés** ugyanazon a lapon: név 3–20 karakter, ékezet és
   szóköz nélkül; jelszó legalább 6 karakter. A jelszó a beléptető ajtóhoz megy,
   a játék felé egy **belépőjegy** utazik — a kliens sosem látja a jelszót.
3. **Fájl-ellenőrzés** (ha az üzemeltető bekapcsolta): a szervertől kért lista
   alapján a launcher minden fájlt méret és ellenőrzőösszeg szerint összevet, a
   hiányzót vagy eltérőt letölti. **Sosem töröl** — ami nincs a listán, marad.
4. A **JÁTÉK** gomb indítja a klienst a szerver címével és a jeggyel.

A felület nyelve követi a rendszerét (magyar vagy angol, a többi angol), és a
játék is ezt a nyelvet kapja. A beállítások a `%APPDATA%\reBSGO\launcher.ini`
fájlban, a napló a `%APPDATA%\reBSGO\launcher.log` fájlban van; hibakereséshez ez
utóbbi a legjobb kiindulás.

## Az üzemeltető oldala

| Mi kell | Hol |
|---|---|
| a launcher fájl | `launcher/rebsgo-launcher.exe`, a játékosoknak szánt program |
| elérhető portok | 27051 (beléptető ajtó), 27050 (játék), 27052 (chat) |
| fájllista (opcionális) | `REBSGO_LAUNCHER_MANIFEST_DIR` és `REBSGO_LAUNCHER_CLIENT_DIR` a `.env`-ben |

A fájllistát a `tools/gen_launcher_manifests.py` írja a saját, tiszta
kliensből (`--client …/client/live --out <listamappa> --skip-suspect`); az ajtó
ugyanebből a mappából szolgálja ki a fájlokat. Kulcsok nélkül az ajtó üres
listát ad, a launcher kihagyja az ellenőrzést, és azt indítja, ami a
játékosnál van — így a kliens-build egyezése a játékos dolga marad.

Az alsó sáv két hivatkozása a projektoldalra
(<https://github.com/Shran21/reBSGO>) és a fejlesztő Discordjára
(<https://discord.com/users/469848422732660767>) visz.

A launcher az ajtót a **manifest** alakjáról ismeri fel (portkeresésnél is),
tehát csak reBSGO-szerverhez kapcsolódik. A játék indítási argumentumai a
kliens szabványos kapcsolói (`+gameServer`, `+cdn`, `+userID`, `+session`,
`+language`).
