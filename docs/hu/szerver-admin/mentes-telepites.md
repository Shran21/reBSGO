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
    … | sudo sh -s -- --no-restart           → frissítéskor nem indít újra

**Frissítés:** ugyanez a parancs, ugyanarra a célmappára. A kód lecserélődik,
a `.env`, a világállapot (`sqlite/`) és a helyi beállítások maradnak, admin
fiókot nem kérdez újra. Ha a szolgáltatások már futottak, a telepítő a végén
újraindítja őket, hogy a frissítés életbe lépjen: a bsgo kilépéskor elmenti a
pilótákat, a bent lévő játékosok kilépnek. A `--no-restart` kapcsolóval ez
elmarad, és a telepítő csak kiírja az újraindító parancsot
(`systemctl restart bsgo rebsgo-panel`), például ha egy éles szervert inkább
később indítanál újra.

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

1. kibontja a **hozott Python 3.13-at** a `runtime/python` alá. Ez
   x86_64-re készült: más processzoron (például Raspberry Pi-n, ARM-on), vagy
   ha nincs csomagolt értelmező, a rendszer python3-at használja (3.11 vagy
   újabb kell; a natív gyorsítómodulhoz x86_64 és 3.13);
2. létrehozza a mappákat, futtathatóvá teszi a szkripteket (`install.sh`,
   `WebPanel/run.sh`, `tools/*.py`), és ha nincs `.env`, generál egyet friss
   panel-tokennel — ezt csak a tulajdonosa olvashatja —, és bekapcsolja
   benne a szektor-altatást (`REBSGO_SECTOR_GATING_MODE=idle`, lásd lent),
   ha a `.env` erről még nem rendelkezik;
3. ellenőrzi, hogy a szerverkód betölt-e, és hogy a **natív gyorsítómodul**
   (`native/lib`, a fában szállítva) aktív-e;
4. felépíti a panel venv-jét a `WebPanel/vendor/wheels` készletből (ami
   ebből nem illik a géphez — ARM-on, vagy nem 3.13-as Pythonnal —, azt a
   PyPI-ról tölti le, ehhez hálózat kell), és
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

Kapcsolók: `--check` (csak jelent, nem változtat), `--no-systemd`,
`--no-restart`, `--dir`, `--here`. A telepítő **újrafuttatható**: meglévő telepítést kiegészít, nem
ront el; meglévő telepítésre másolva a kód frissül, a `.env`, a világállapot
(`sqlite/`) és a helyi beállítások megmaradnak. Az admin fiókot csak akkor
kérdezi, ha még nincs Developer szerepű fiók. Egy félbeszakadt korábbi
futás nyomait is rendbe teszi: a gépen nem induló értelmezőt törli, az üres
panel-tokent pótolja, a félkész venv-et újraépíti.

**Raspberry Pi (ARM):** 64 bites Raspberry Pi OS ajánlott. A telepítő a
rendszer Pythonját használja (ha a venv nem jön létre:
`apt install python3-venv`), a panel csomagjait a hálózatról tölti le, a
szerver pedig a natív gyorsítómodul nélkül, tiszta Pythonon fut.

**Szektor-altatás.** A szerver magától minden szektort teljes sebességgel
szimulál, azokat is, ahol senki sincs; ezt egy kisebb gép nem bírja. Ezért a
telepítő a `.env`-be beírja a `REBSGO_SECTOR_GATING_MODE=idle` sort: az üres
szektor nem szimulál, 2 perc után az időzítői is lassabban járnak, 10 perc
után mélyalvásba kerül, és ha egy játékos beugrik, legfeljebb egy
másodpercen belül felébred. Egy
x86-os gépen mérve a szerver terhelése játékos nélkül így 57%-ról 20% körülire,
10 perc után 2%-ra esik (100% = egy processzormag). Az üres szektorokban zajló
dolgok (NPC-k mozgása, újraéledés, időzített események) közben lassulnak vagy
szünetelnek. A többi mód: `empty` (csak a szimuláció marad ki), `adaptive`
(mélyalvás csak nagy gépterhelésnél), `off` (mindig minden szimulál).
Átállítás a `.env`-ben, utána `systemctl restart bsgo`. A telepítő a már
meglévő beállításhoz nem nyúl, frissítéskor is csak akkor írja be, ha nincs.

Indítás utána:

    systemctl start bsgo rebsgo-panel

vagy kézzel:

    PYTHONPATH=src ./runtime/python/bin/python3 -m rebsgo.main
    ./WebPanel/run.sh

## Eltávolítás

    sudo sh /opt/rebsgo/uninstall.sh

Az `uninstall.sh` a telepítés mappájában van. Leállítja a szolgáltatásokat (a
`bsgo` kilépéskor elmenti a pilótákat), eltávolítja a `bsgo` és a
`rebsgo-panel` unitot, és ha a szerver vagy a panel kézzel fut ebből a
mappából, azt is szabályosan leállítja. Utána megkérdezi, mi maradjon:

1. **az adatok a helyükön** (ajánlott): a program törlődik, a `sqlite/`, a
   `.env`, a `WebPanel/panel.env` és a `GameData/local` marad. Egy újabb
   telepítés ugyanebbe a mappába mindent visszakap: a játékosokat, a
   beállításokat és az admin fiókot;
2. **mentés, aztán minden megy**: az adatok egy `.tar.gz`-be kerülnek
   (alapból a telepítés mellé), a mappa törlődik. Visszaállítás egy új
   telepítésbe, leállított szolgáltatásokkal: `tar xzf <mentés> -C <mappa>`;
3. **minden megy, mentés nélkül**: csak a `torles` szó begépelése után.

Kérdés nélkül: `--keep-data`, `--backup <fájl>` vagy `--purge`, mellé
`--yes`; másik telepítéshez `--dir <mappa>`. Más mappára mutató
szolgáltatáshoz nem nyúl, és a panel mentéseit (`PANEL_BACKUP_DIR`, alapból
`/opt/bsgo-backups`) sem törli.

## Ellenőrzött tulajdonságok

- Tiszta Debian-konténerben (Python nélkül) a csomag kicsomagolás +
  telepítő után natívan elindult: játékszerver ÉS panel.
- A telepítő második futása semmit nem rontott el (idempotens).
- A `deploy/bsgo.service.template` szóról szóra az éles unit mása
  (szabályos SIGTERM-leállással, ami kilépéskor menti a pilótákat).
