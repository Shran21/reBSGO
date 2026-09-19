[github.com/Shran21](https://github.com/Shran21)

# A panel fülei

A bal oldalsáv sorrendjében. Mobilon az oldalsáv a fejléc hamburger menüjébe
kerül, a széles táblák pedig kártya-nézetre váltanak.

## Áttekintés

A kezdőlap: fut-e a játékszerver, mióta, hányan vannak bent és melyik
szektorban, a bent lévők görbéje az elmúlt órából, az **Állapot** kártya
(friss hibák, utolsó mentés, szabad lemez, karbantartás, pilóták száma), a
legforgalmasabb szektorok és a gyorsgombok. A bent lévő pilóta nevére
kattintva megnyílik az adatlapja. A lap változáskor automatikusan frissül,
és a fejléc mutatja a frissítés idejét. Developer szerepnek itt van az
azonnali **szerver-újraindítás** gombja is (kihirdetés nélkül, de a
megerősítés felsorolja a bent lévőket; kihirdetéssel az Eszközök fül
ütemezett újraindítása jár).

## Felhasználók

**Lista:** minden fiók, online-jelvénnyel (és a szektor nevével), utolsó
belépés dátumával; név szerint szűrhető, oszlop szerint rendezhető, alapból a
bent lévők elöl. A teljes sor kattintható.

**Adatlap:** egy pilóta mindene egy oldalon.

| Művelet | Kell hozzá | Megjegyzés |
|---|---|---|
| szerepek pipálása | Developer | bent lévőnél tiltva |
| jelszó cseréje | Developer / Ban | bármikor biztonságos, a játék sosem írja a jelszótáblát |
| nyersanyagok állítása | Developer / Edit | bent lévőnél tiltva; a posta soha nem sérül |
| kitiltás lejárattal és indokkal | Developer / Ban | bent lévőt azonnal ki is rúg |
| kirúgás | Console | a játék saját kirúgó üzenetével: a kliens szabályos kilépő-képernyőt kap |
| fiók létrehozása | Developer | üres fiók; a karakter az első belépéskor jön létre a játékban |
| fiók törlése | Developer | minden táblából, a barátlistákról is; visszavonhatatlan |

Az adatlap alján a **dossziéja**: számlálók (ölések, küldetések, bányászat),
a legutóbbi belépések naplóból, és a készletek.

## Szektorok

Élő tábla minden szektorról: hányan vannak bent (névvel), NPC, aszteroida és
objektumszám, támaszpont-pontok és -életerő, jeladók. Az oszlopfejlécekre
kattintva rendezhető, és változáskor automatikusan frissül.

Műveletek soronként (Developer):

- **Esemény** — szektor-esemény élesítése. Üres szektorban nem indítható, és
  az élesítés nem azonnali indulás: a játékosnak a zónába kell repülnie.
- **Újraindítás** — a szektor újjáépítése. Ha vannak bent, előbb figyelmeztet
  és felsorolja őket; a jóváhagyás után előbb kirúgja őket, aztán indít.
- **OP** — támaszpont-pontok állítása frakciónként (±, illetve maximum).
  Csak azokra a frakciókra kínálja, amelyeknek a csillag engedi.
- **Limit** és **Tiltva** — szektoronkénti játékos-korlát és lezárás. A
  „Szabályzat mentése" gomb élőben tölti újra: a tiltott szektor eltűnik a
  galaxistérképről és nem ugorható. A már bent lévő kliensek a térkép-változást
  csak újra-belépés után látják.

## Térkép

A galaxis rajza a saját kártyájából, a játékbeli tájolásban. A csillag mérete
és színe a bent lévők számát mutatja, mellette a támaszpont-jelek (K/C), a
jeladó-horgony, a tiltott szektor pedig pirosan. Kattintásra a Szektorok
tábla megfelelő sorára ugrik.

## Adatbázis

Az adatbázis böngészője: a táblák csempéken, sorszámmal, táblán belül keresés
az összes oszlopban, fejléc-kattintós rendezés, lapozás, sor-kattintásra
szerkesztő. Új sor felvehető, sor törölhető (megerősítéssel, a régi sor
auditba kerül). Írni csak Developer tud, olvasni minden belépő.

Itt van az **adatbázis-mentés** kártyája is: kézi pillanatkép (biztonságos
játék közben is), a korábbi mentések listája, letöltéssel. Az automata
ütemezés a Konfiguráció fülön áll — lásd `beallitasok.md`.

## Konzol

A játék fejlesztői konzolja böngészőből, ugyanazokkal a jogokkal és
parancsokkal. A parancsok **mindig a belépett pilóta nevében** futnak — más
nevében nem lehet parancsot kiadni. A ↑ billentyű előhozza az előzményeket,
gépelés közben kiegészít, és mellette ott a kurált parancs-kézikönyv szűrhető
táblázatban. A szektor-kötött parancsok csak akkor hatnak, ha a belépett
pilóta éppen bent van a játékban.

## Naplók

Mind az öt szerver-csatorna (`server`, `sector`, `login`, `error`, `audit`)
és a panel saját auditja, kereséssel, a fájl végéről olvasva; minden sor
dátummal. Az `error` csatorna alapból csak a valódi hibákat mutatja a hívási
láncukkal, a figyelmeztetéseket egy kapcsoló hozza be; a betöltött sorok
helyben szűrhetők, a nézet másolható vagy letölthető. A menüponton **piros
pont** jelzi, ha az utolsó megtekintés óta valódi hiba érkezett.
Itt állítható a **naplószint futás közben** is, összesítve vagy területenként
(ez újraindításig él; a tartós beállítás az `.env`-ben van).

## Konfiguráció

A szerver `.env` fájlja űrlapként, a játék saját katalógusa szerint
magyarázva, és itt szerkeszthetők a panel saját beállításai is. Részletesen:
`beallitasok.md`.

## Játék-beállítások

Kiválasztott GameData-sablonok mezőnkénti űrlapon: Revenant-kísértés,
parancsnoki drónraj, szektor-események, aknák, hordozó-dokkolás. Részletesen:
`beallitasok.md`.

## Monitoring

Processzor, memória, lemez, a szerver folyamatának terhelése és a bent lévők
száma, öt másodpercenként frissülve, egyórás vagy 24 órás visszatekintéssel
és kis grafikonokkal; az előzmény a panel újraindítását is túléli.

## Ranglisták

A játékbeli ranglisták élő nézete a számlálókból, mellette a havi mentett
állások. Developer szerepnek van egy **újraszámolás** gombja, ami a szerver
saját ranglista- és torna-futtatását indítja.

## Gazdaság

Összesítők pilótánként és nyersanyagonként: mennyi van összesen a világban,
ki a leggazdagabb, és a teljes mátrix. Öt nyersanyagot mutat — cubit, tílium,
titán, víz, jelvény. (A mellékes tételek — hangolókészlet, tech-analízis,
urán, plutónium — szándékosan nincsenek benne; a készletük az Adatbázis fülön
a `stacks` táblában megnézhető.)

## Eszközök

- **Közlemény** — üzenet minden bent lévőnek.
- **Ütemezett újraindítás** — kihirdetéssel (indításkor, 5 és 1 perccel
  előtte), visszaszámlálóval, bármikor lefújható.
- **Karbantartó mód** — új belépés csak stábnak, saját üzenettel.
- **Teljes mentés** — az egész szervermappa tar.gz-be, letöltéssel.
- **Azonos gépről belépők** kimutatása.
- **GameData-kereső** — olvasásra a kártyaadatban.

## Audit

Két napló egy lapon: a játék audit-csatornája (ki mit csinált ranggal) és a
panel saját auditja (ki mit írt a felületről). Minden bejegyzés mutatja, ki,
mikor, mit és mi lett az eredménye.
