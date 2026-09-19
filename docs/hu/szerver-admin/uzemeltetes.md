[github.com/Shran21](https://github.com/Shran21)

# Üzemeltetés

## Indítás és leállítás (systemd)

    systemctl start bsgo             → játékszerver indítása
    systemctl stop bsgo              → szabályos leállítás (SIGTERM: kilépéskor
                                       MENTI a bent lévő pilótákat)
    systemctl restart bsgo           → újraindítás (beállítás-változásokhoz)
    systemctl status bsgo            → fut-e, mióta
    journalctl -u bsgo -f            → élő napló a journald-ból

    systemctl restart rebsgo-panel   → a WebPanel újraindítása
    systemctl status rebsgo-panel

A WebPanelről is lehet: Áttekintés → „Szerver újraindítása" (azonnali),
vagy Eszközök → „Ütemezett újraindítás" (kihirdetéssel, lefújhatóan).

## Kézi futtatás (fejlesztéshez)

    cd <a szerver mappája> && PYTHONPATH=src ./runtime/python/bin/python3 -m rebsgo.main
                                     → közvetlen indítás előtérben

## A kimenet nyelve

A telepítő és a szállított eszközök a gép nyelvét követik: magyar
rendszeren magyarul, minden máson angolul beszélnek (`REBSGO_LANG=hu|en`
felülírja). A naplók sorai szándékosan angolok, hogy kereshetők és
megoszthatók legyenek; a fejléc szava követi a rendszer nyelvét.

## Naplók — öt csatorna a logs/ mappában

| Fájl | Mit tartalmaz |
|---|---|
| `server.log`  | minden, KIVÉVE a szektor-zajt; indításkor félretéve |
| `sector.log`  | a szektorok árama (a leghangosabb, saját rotációval) |
| `login.log`   | belépések és pilóta-események, hónapokra visszamenőleg |
| `error.log`   | minden figyelmeztetés és hiba egy helyen |
| `audit.log`   | ki mit csinált ranggal (konzolparancsok, szerep-váltások) |

A WebPanel Naplók füle mindet olvassa és keresi; a Naplók menüponton piros
pont jelzi, ha új hiba érkezett. A panel saját auditja a
`WebPanel/logs/panel-audit.log`.

## Futás közben állítható

- **Naplószint**: WebPanel → Naplók → „Naplószint futás közben" (összesítve
  vagy területenként; újraindításig érvényes, a tartós beállítás az `.env`-ben van).
- **Karbantartó mód**: WebPanel → Eszközök (új belépés csak stábnak).
- **Szektor-szabályzat** (tiltás, játékos-limit): WebPanel → Szektorok →
  Szabályzat mentése — élőben újratölt, kliensnek újra-belépés kell a
  térképi változáshoz.
- **Szektor-újraindítás**: WebPanel → Szektorok → Újraindítás (ha vannak bent
  játékosok, előbb figyelmeztet, majd kirúgja őket).

## Konfiguráció (.env)

A tartós beállítások a gyökér `.env` fájlban vannak; a teljes katalógus
magyarázatokkal az `.env.example`-ben. A WebPanel Konfiguráció füle
űrlapként szerkeszti (a kommentek megmaradnak, az előző változat
`.env.panel-bak` néven), a legtöbb érték a következő újraindításkor él.
