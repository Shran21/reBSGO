[github.com/Shran21](https://github.com/Shran21)

# A panel felépítése és hibakeresése

## Két folyamat, egy titok

A panel **külön folyamat** a játékszervertől (`rebsgo-panel` systemd-szolgáltatás,
a `WebPanel/` mappában). Így a panel újraindítása nem érinti a játékot, és a
játék összeomlása sem viszi magával a panelt.

A kettő két csatornán beszél:

1. **Adatbázis** — a panel közvetlenül olvassa a játék SQLite-fájlját.
2. **Panel-ajtó** — a játékszerverben futó kis HTTP-kiszolgáló a
   `127.0.0.1:27053` címen (kizárólag a gépen belülről érhető el). Minden
   kérés a `.env`-ben tárolt közös kulcsot viszi `X-Panel-Key` fejlécben;
   kulcs nélkül az ajtó ki sem nyílik.

Az ajtó végpontjai: `/status`, `/save`, `/console`, `/console/commands`,
`/log`, `/sectors`, `/sector-event`, `/sector-op`, `/sector-restart`,
`/policy-reload`, `/maintenance`, `/rankings-recalc`.

**Miért nem ír a panel közvetlenül mindent az adatbázisba:** amíg egy pilóta
bent van, az adatai a szerver memóriájában élnek, és két percenként
felülíródik a soruk. Ezért megy minden élő állapot az ajtón át, és ezért
tiltja a panel a bent lévők adatainak szerkesztését.

## Fájlok

    WebPanel/
      panel/
        app.py           a webalkalmazás, a belépési kapu, a közös oldal-váz
        auth.py          jelszó-ellenőrzés, jegyek, CSRF, próbálkozás-korlát
        settings.py      a panel beállításai (panel.env + környezet)
        db.py            adatbázis-olvasás és -írás
        bridge.py        a panel-ajtó kliense
        backups.py       mentések (kézi és ütemezett) + a mentés-óra szála
        envfile.py       a .env és a panel.env helyben szerkesztése
        auditlog.py      a panel saját auditja
        i18n.py          magyar és angol feliratok
        logfiles.py      a napló-csatornák
        sectors.py       szektornevek a GameData-ból
        gamedata.py      a kártyaadat keresője
        restarter.py     ütemezett újraindítás
        policy.py        szektor-szabályzat
        routes/          fülönként egy-egy modul
        templates/       oldalsablonok
        static/          stíluslap, betűtípusok
      panel.env          a panel saját beállításai (nem része a csomagnak)
      logs/panel-audit.log

## Indítás és leállítás

    systemctl restart rebsgo-panel     újraindítás
    systemctl status rebsgo-panel      fut-e
    journalctl -u rebsgo-panel -n 50   a panel naplója

A panel a Konfiguráció fülről is újraindítható (a gomb elengedi magát, ezért
a válasz még megérkezik).


## Biztonsági fejlécek, egyszeri üzenet, élő csatorna

Minden válasz `Content-Security-Policy`-t visel: script csak a panel saját
fájljából és a kérésenként sorsolt nonce-szal jelölt beágyazott blokkokból
futhat, a keretbe ágyazás tiltott (`frame-ancestors 'none'`), mellette
`X-Content-Type-Options`, `X-Frame-Options` és `Referrer-Policy`. A sütik TLS
mögött (`https`, vagy `X-Forwarded-Proto: https` egy proxytól) `Secure`
jelzőt kapnak.

Az átirányítások üzenete (`?notice=…`, `?error=…`) az ajtóban egy egyszeri
`panel_flash` sütibe költözik, a cím tisztán marad; a következő oldal
megmutatja, aztán törli.

Az élő lapok a `/events` eseménycsatornát tartják (SSE): a panel három
másodpercenként nézi a játék állapotát és a naplófájlok méretét, és csak
változáskor küld `change` vagy `logs` eseményt, húsz másodpercenként pedig
`tick`-et. A monitor a `/monitor/events` csatornán öt másodpercenként kap
teljes pillanatképet. Ha a csatorna nem tartható, a böngésző időzített
lekérésre vált.

A játékadatot a panel a szerver saját adatrétegén át olvassa
(`rebsgo.gamedata.vfs`): mappás fában a JSON-t, kiadott fában a csomagolt
játékadatot. A szektornevek, a kártyakereső, a csillagtérkép és a
játék-beállítások mindkettőből mennek; írni csak a mappásba lehet.

## Ha valami nem működik

**„A játékszerver nem elérhető" mindenütt.** Az ajtó nem válaszol. Ellenőrizd,
hogy fut-e a játék (`systemctl status bsgo`), és hogy a `.env`-ben van-e
`REBSGO_PANEL_TOKEN` — ha nincs, az ajtó el sem indul. A token változása után
mindkét szolgáltatást újra kell indítani.

**Belépés után azonnal visszadob a belépő oldalra.** A jegy sütije nem
érkezik vissza; leggyakrabban azért, mert a panel a titkos kulcsát épp
lecserélte (`panel.env` újragenerálódott). Ilyenkor mindenkinek újra kell
lépnie.

**„Ez a pilóta bent van" minden szerkesztésnél.** Ez nem hiba: a panel védi az
adatot a felülíródástól. Kérd meg a pilótát, hogy lépjen ki, vagy rúgd ki a
kirúgás gombbal.

**A felület régi kinézettel jön.** A stíluslap verziószámmal hivatkozik; ha
egy böngésző mégis a régit tartja, elég egy erős frissítés (Ctrl+F5).

**A szektor-tábla üres vagy hideg.** A számok az ajtóból jönnek — ha a játék
épp indul, néhány másodpercig nincs mit mutatni; a lap ezután frissül.
