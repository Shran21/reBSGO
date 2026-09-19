[github.com/Shran21](https://github.com/Shran21)

# Pilóta-adminisztráció

## Kapcsolat és fegyelem

    pilot.kick <id>                  → kirúgás azonosító szerint (a játékos
                                       rendes kijelentkező képernyőt lát)
    pilot.kick-for <név>             → ugyanez név szerint
    pilot.mute <név> <óra>           → chat-némítás órákra
    pilot.list                       → bent lévők száma frakciónként
    pilot.address                    → azonos hálózati címen ülő fiókok
    pilot.save                       → minden bent lévő azonnali mentése

## Szerepek (★ Developer réteg)

    pilot.role <id> <bitek>      ★   → szerep-bitek beállítása (CSAK az 1-es
                                       és 2-es fiók adhatja ki)
    pilot.role-for <név> <bitek> ★   → ugyanez név szerint

Bitek: View 1 · Edit 2 · Ban 4 · CommunityManager 8 · Developer 16 ·
Console 32 · GodMode 1024 · Mod 2048. Összeadva: pl. Developer+Console = 48.
Ugyanez a WebPanel Felhasználók lapján is beállítható.

## Tapasztalat és nyersanyag

    pilot.xp <mennyi>                → XP magadnak
    pilot.xp-for <név> <mennyi>      → XP hozzáadása másnak
    pilot.xp-set <név> <mennyi>      → XP beállítása pontos értékre
    pilot.resource <típus> <mennyi>  → nyersanyag magadnak
    pilot.resource-for <név> <típus> <mennyi>
                                     → nyersanyag másnak

A `<típus>` a kliens gomb-neveivel egyezik (pl. cubits, tylium, titanium,
water, token). Ugyanez a WebPanel Felhasználók lapján is elvégezhető.

## Frakció és külsőségek

    pilot.faction <név> <cubittal?> <ár>
                                     → frakcióváltás; a 2. arg dönti el,
                                       cubitból megy-e a díj, a 3. az ár
    paint.drop-all <név>             → a pilóta ÖSSZES festékének elvétele
    pilot.station <szoba>            → átküldés adott állomás-szobába
    pilot.settings                   → a kliens-beállítások kiírása
    pilot.squad-refresh <0|1>        → kötelék-jelzés frissítése

## Képzettségek

    pilot.train <skill_id>           → képzettség megtanítása
    pilot.untrain <skill_id>         → képzettség elvétele

## Posta

    mail.send <név>                  → próba-rendszerlevél
    mail.send-to <név> <cubit> <tylium> <titán> <token>
                                     → levél nyersanyag-melléklettel

Példa: `mail.send-to Tuser 1000 50000 20000 5`

## Boostok (★ Developer réteg a loot/di-hez)

    boost.loot <név> <szorzó> <óra> ★ → zsákmány-szorzó időre
    boost.di <név> <szorzó> <óra>   ★ → DI-szorzó időre
    boost.report                     → a saját szorzóid kiírása
    boost.clear                      → a saját szorzóid törlése

## Küldetések (★ Developer réteg)

    assignment.clear             ★   → a napi küldetéseid törlése
    assignment.clear-for <név>   ★   → küldetés-törlés másnak
    assignment.repair <név>      ★   → beragadt küldetések helyrerakása
    assignment.report                → küldetés-napló próbaüzenete
