[github.com/Shran21](https://github.com/Shran21)

# Mentés, hordozható csomag, telepítés

## Gyors mentés

- **WebPanel** → Eszközök → „Teljes mentés most": tar.gz a
  `/opt/bsgo-backups` mappába (naplók és venv nélkül), a lista elemei
  letölthetők. Egyszerre egy mentés futhat.
- A célmappa a panel `PANEL_BACKUP_DIR` beállításával áthelyezhető.

## Telepítés — klónból vagy csomagból

    ./install.sh

A telepítő először megkérdezi, **hova kerüljön a szerver** (Enter = marad,
ahol a fa van); más útvonalra átmásolja a fát, és onnan folytatja. Kérdés
nélkül: `--dir /a/hova/akarod`, vagy `--here` (helyben). Csomagból:

    tar xzf reBSGO-portable-*.tar.gz -C /a/hova/akarod
    cd /a/hova/akarod/reBSGO-server && ./install.sh

A telepítő hálózat nélkül dolgozik:

1. kibontja a **hozott Python 3.13-at** a `runtime/python` alá (ha nincs,
   a rendszer python3-at használja — 3.13 kell a natív gyorsítómodulhoz);
2. létrehozza a mappákat, és ha nincs `.env`, generál egyet friss
   panel-tokennel;
3. ellenőrzi, hogy a szerverkód betölt-e, és hogy a **natív gyorsítómodul**
   (`native/lib`, a fában szállítva) aktív-e;
4. felépíti a panel venv-jét a `WebPanel/vendor/wheels` készletből;
5. root-ként felteszi, engedélyezi és **elindítja** a systemd unitokat
   (`bsgo`, `rebsgo-panel`) a `deploy/` sablonból, az új helyre mutatva.

A játékosok launchere a `launcher/rebsgo-launcher.exe` — ezt kell nekik
odaadni; a beléptető ajtó címét a launcher beállításában adják meg.

Kapcsolók: `--check` (csak jelent, nem változtat), `--no-systemd`, `--dir`,
`--here`. A telepítő **újrafuttatható**: meglévő telepítést kiegészít, nem
ront el; meglévő telepítésre másolva a kód frissül, a `.env`, a világállapot
(`sqlite/`) és a helyi beállítások megmaradnak.

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
