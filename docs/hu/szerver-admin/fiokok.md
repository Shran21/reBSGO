[github.com/Shran21](https://github.com/Shran21)

# Fiókok, jelszavak, szerepek

## Fiók létrehozása

- **WebPanel** → Felhasználók → „+ Új fiók": név + frakció (vagy „választ a
  játékban") + jelszó. A fiók üresen jön létre; első belépéskor a játék
  viszi végig a frakcióválasztáson és az avatár-készítésen, és megkapja a
  kezdőhajót.
- **A launcherből** a játékos maga is regisztrálhat: a beléptető ajtó
  (alapból a 27051-es port) `POST /register` címe `name` és `password`
  mezőt vár, és `ok <azonosító>` sorral felel. Ugyanazokkal a névszabályokkal
  dolgozik, mint a játék, és ugyanilyen üres fiókot készít.
  Az `.env`-ben a `REBSGO_ADMISSION_REGISTRATION_OPEN=false` bezárja.
- **Parancssorból** ugyanilyen üres fiók készül, a launcher névszabályaival
  és jelszó-minimumával (5 karakter); a regisztráció lezárása erre nem hat:

      tools/pilots.py create Tuser             → jelszó bekérése rejtve
      tools/pilots.py create Tuser --grant Developer,Console
                                               → szerepekkel együtt

## Az első admin fiók

A panelbe csak Developer vagy Console szereppel lehet belépni, fiókot ott
pedig csak Developer hozhat létre, így friss szerveren az első admin fiók
nem a panelből jön. A telepítő gondoskodik róla: ha még nincs Developer
szerepű fiók, bekéri az elsőt, és Developer + Console szerepet ad neki.
Ha ez kimaradt (Enterrel kihagyva, vagy terminál nélkül futott a telepítő),
utólag parancssorból:

    tools/pilots.py create Admin --grant Developer,Console
    tools/pilots.py admins                   → kinek van Developer szerepe és jelszava

Meglévő fióknak, például egy launcherből regisztráltnak, a `roles` parancs
adja meg a szerepet (lásd lent).

## Jelszó

- **WebPanel** → a pilóta adatlapja → „Jelszó beállítása" (min. 6 karakter).
- Parancssorból. A `tools/pilots.py` bárhonnan indítható, mindig a szerver
  saját adatbázisán dolgozik (a `.env`-beli `REBSGO_DB`, vagy a
  `sqlite/bgo_server.db`); ahol nincs rendszer-Python, a szerver mappájából a
  csomagolt értelmezővel: `./runtime/python/bin/python3 tools/pilots.py …`:

      tools/pilots.py list                     → kinek van jelszava
      tools/pilots.py password Tuser           → jelszó bekérése rejtve
      tools/pilots.py password Tuser --password titok
                                               → (kerülendő: shell-history!)

## Szerepek

- **WebPanel** → adatlap → Szerepek (minden pipa alatt magyarázat).
- Parancssorból:

      tools/pilots.py roles Tuser                       → kiírás
      tools/pilots.py roles Tuser --grant Developer,Console
      tools/pilots.py roles Tuser --revoke GodMode

| Szerep | Bit | Mit ad |
|---|---|---|
| View | 1 | a játék nem használja; paneles olvasó-jog |
| Edit | 2 | panel: adatbázis- és készlet-írás |
| Ban | 4 | panel: jelszóváltás, kitiltás |
| CommunityManager | 8 | homokozó-szektor + stáb-bolt |
| Developer | 16 | dev-konzolparancsok + panel-adminisztráció |
| Console | 32 | a játékbeli konzol előfeltétele |
| GodMode | 1024 | sebezhetetlenség |
| Mod | 2048 | homokozó — de a konzolt LETILTJA |

A panelbe belépni Developer vagy Console szereppel lehet.

## Kitiltás és kirúgás

- **Kirúgás**: adatlap → „Kirúgás a játékból" (a játékos rendes kijelentkező
  képernyőt lát), vagy konzolból `pilot.kick <id>`.
- **Időzített kitiltás**: adatlap → Kitiltás kártya (1 óra … végleg, indokkal).
  A kapu a lejáratig minden belépésre a dátummal és az indokkal válaszol; ha
  bent volt, azonnal ki is rúgja. Feloldás ugyanott.
- A kitiltások a `panel_bans` táblában tárolódnak (az Adatbázis fülön is látszanak).

## Egyéb pilóta-műveletek

    tools/pilots.py place teszt3 44   → hol jelenjen meg legközelebb
    tools/pilots.py remove Tuser      → a pilóta JELSZAVÁNAK törlése

A fiók VÉGLEGES törlése (minden táblából) a panel adatlapján, a
Veszélyzóna kártyán van — nem visszavonható.
