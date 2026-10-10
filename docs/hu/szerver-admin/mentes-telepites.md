[github.com/Shran21](https://github.com/Shran21)

# Mentés, hordozható csomag, telepítés

## Gyors mentés

- **WebPanel** → Eszközök → „Teljes mentés most": tar.gz a
  `/opt/bsgo-backups` mappába (naplók és venv nélkül), a lista elemei
  letölthetők. Egyszerre egy mentés futhat.
- A célmappa a panel `PANEL_BACKUP_DIR` beállításával áthelyezhető.

## Egyszerű telepítés — egy paranccsal

    curl -fsSL https://raw.githubusercontent.com/Shran21/reBSGO/main/install-basic.sh | sudo sh

Ahol nincs `curl`, ugyanez `wget -qO- …`-val. Az `install-basic.sh` letölti a repót a
GitHubról, egy átmeneti mappában kibontja, onnan elindítja a telepítőt
(lásd lent), végül az átmeneti mappát törli. Két dolgot kérdez: a
célmappát (Enter = `/opt/rebsgo`, root nélkül `~/rebsgo`), és a telepítőn
keresztül az első admin fiókot. Kapcsolók az `sh -s --` után:

    … | sudo sh -s -- --dir /srv/rebsgo     → célmappa, kérdés nélkül
    … | sudo sh -s -- --ref <ág vagy tag>    → nem a main ágról
    … | sudo sh -s -- --no-systemd           → szolgáltatások nélkül

**Frissítés:** ugyanez a parancs, ugyanarra a célmappára. A kód lecserélődik,
a `.env`, a világállapot (`sqlite/`) és a helyi beállítások maradnak, admin
fiókot nem kérdez újra. Ha a szolgáltatások már futottak, a telepítő a végén
kiírja az újraindító parancsot (`systemctl restart bsgo rebsgo-panel`); ezt
magától nem futtatja, mert a bsgo leállása kilépteti a játékosokat.

Terminál nélkül, például automatizálva, nem kérdez semmit: a célmappa az
alapértelmezett vagy a `--dir`, az admin fiókot utólag kell létrehozni
(`fiokok.md`).

## Telepítés — klónból vagy csomagból

    sh install.sh

A telepítő először megkérdezi, **hova kerüljön a szerver** (Enter = marad,
ahol a fa van); más útvonalra átmásolja a fát, és onnan folytatja. Kérdés
nélkül: `--dir /a/hova/akarod`, vagy `--here` (helyben). Csomagból:

    tar xzf reBSGO-portable-*.tar.gz -C /a/hova/akarod
    cd /a/hova/akarod/reBSGO-server && sh install.sh

Az `sh` előtag miatt a telepítő akkor is elindul, ha a fájl futtatási joga
útközben elveszett (például Windowsról feltöltve); a többi szkriptnek a
telepítő maga adja vissza.

A telepítő hálózat nélkül dolgozik:

1. kibontja a **hozott Python 3.13-at** a `runtime/python` alá (ha nincs,
   a rendszer python3-at használja — 3.13 kell a natív gyorsítómodulhoz);
2. létrehozza a mappákat, futtathatóvá teszi a szkripteket (`install.sh`,
   `WebPanel/run.sh`, `tools/*.py`), és ha nincs `.env`, generál egyet friss
   panel-tokennel — ezt csak a tulajdonosa olvashatja;
3. ellenőrzi, hogy a szerverkód betölt-e, és hogy a **natív gyorsítómodul**
   (`native/lib`, a fában szállítva) aktív-e;
4. felépíti a panel venv-jét a `WebPanel/vendor/wheels` készletből, és
   megírja a `WebPanel/panel.env`-et: a panel csak a saját gépéről nyílik
   (`PANEL_HOST=127.0.0.1`), a fájlt csak a tulajdonosa olvashatja;
5. ha még nincs Developer szerepű fiók, bekéri az **első admin fiókot**
   (név, majd kétszer a jelszó; Enter = kihagyás). Ez Developer és Console
   szerepet kap, ezzel lehet belépni a WebPanelbe. Terminál nélkül csak
   kiírja a pótló parancsot (`fiokok.md`);
6. root-ként felteszi, engedélyezi és **elindítja** a systemd unitokat
   (`bsgo`, `rebsgo-panel`) a `deploy/` sablonból, az új helyre mutatva.

A játékosok launchere a `launcher/rebsgo-launcher.exe` — ezt kell nekik
odaadni; a beléptető ajtó címét a launcher beállításában adják meg.

Kapcsolók: `--check` (csak jelent, nem változtat), `--no-systemd`, `--dir`,
`--here`. A telepítő **újrafuttatható**: meglévő telepítést kiegészít, nem
ront el; meglévő telepítésre másolva a kód frissül, a `.env`, a világállapot
(`sqlite/`) és a helyi beállítások megmaradnak. Az admin fiókot csak akkor
kérdezi, ha még nincs Developer szerepű fiók.

Indítás utána:

    systemctl start bsgo rebsgo-panel

vagy kézzel:

    PYTHONPATH=src ./runtime/python/bin/python3 -m rebsgo.main
    ./WebPanel/run.sh

## Ellenőrzött tulajdonságok

- Tiszta Debian-konténerben (Python nélkül) a csomag kicsomagolás +
  telepítő után natívan elindult: játékszerver ÉS panel.
- A telepítő második futása semmit nem rontott el (idempotens).
- A `deploy/bsgo.service.template` szóról szóra az éles unit mása
  (szabályos SIGTERM-leállással, ami kilépéskor menti a pilótákat).
