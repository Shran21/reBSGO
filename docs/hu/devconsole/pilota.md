[github.com/Shran21](https://github.com/Shran21)

# Pilóta-adminisztráció

## Kapcsolat és fegyelem

    pilot.kick <id>                  → kirúgás azonosító szerint (a játékos
                                       rendes kijelentkező képernyőt lát)
                                       pl. pilot.kick 7
    pilot.kick-for <név>             → ugyanez név szerint
                                       pl. pilot.kick-for Vega
    pilot.mute <név> <óra>           → chat-némítás órákra
                                       pl. pilot.mute Vega 2
    pilot.list                       → bent lévők száma frakciónként
    pilot.address                    → azonos hálózati címen ülő fiókok
    pilot.save                       → minden bent lévő azonnali mentése

## Szerepek (★ Developer réteg)

    pilot.role <id> <bitek>      ★   → szerep-bitek beállítása (CSAK az 1-es
                                       és 2-es fiók adhatja ki)
                                       pl. pilot.role 7 48
    pilot.role-for <név> <bitek> ★   → ugyanez név szerint
                                       pl. pilot.role-for Vega 48

Bitek: View 1 · Edit 2 · Ban 4 · CommunityManager 8 · Developer 16 ·
Console 32 · GodMode 1024 · Mod 2048. Összeadva: pl. Developer+Console = 48.
Ugyanez a WebPanel Felhasználók lapján is beállítható.

## Tapasztalat és nyersanyag

    pilot.xp <mennyi>                → XP magadnak
                                       pl. pilot.xp 50000
    pilot.xp-for <név> <mennyi>      → XP hozzáadása másnak
                                       pl. pilot.xp-for Vega 50000
    pilot.xp-set <név> <mennyi>      → XP beállítása pontos értékre
                                       pl. pilot.xp-set Vega 9801000
    pilot.resource <típus> <mennyi>  → nyersanyag magadnak
                                       pl. pilot.resource resource_cubits 100000
    pilot.resource-for <név> <típus> <mennyi>
                                     → nyersanyag másnak
                                       pl. pilot.resource-for Vega resource_tylium 5000

A `<típus>` lehet: `resource_cubits`, `resource_tylium`, `resource_titanium`,
`resource_water`, `resource_token`. Ugyanez a WebPanel Felhasználók lapján
is elvégezhető.

## Frakció és külsőségek

    pilot.faction <név> <cubittal?> <ár>
                                     → frakcióváltás; a 2. arg dönti el,
                                       cubitból megy-e a díj, a 3. az ár
                                       pl. pilot.faction Vega false 0
    paint.drop-all <név>             → a pilóta ÖSSZES festékének elvétele
                                       pl. paint.drop-all Vega
    pilot.station <szoba>            → átküldés adott állomás-szobába
                                       pl. pilot.station cic x
                                       (a második szó kötelező, de nem számít)
    pilot.settings                   → a kliens-beállítások kiírása
    pilot.squad-refresh <0|1>        → kötelék-jelzés frissítése
                                       pl. pilot.squad-refresh 1

## Képzettségek

    pilot.train <skill_id>           → képzettség megtanítása
                                       pl. pilot.train 0
    pilot.untrain <skill_id>         → képzettség elvétele
                                       pl. pilot.untrain 0

## Boostok (★ Developer réteg a loot/di-hez)

    boost.loot <név> <szorzó> <óra> ★ → zsákmány-szorzó időre
                                       pl. boost.loot Vega 1 24
    boost.di <név> <szorzó> <óra>   ★ → DI-szorzó időre
                                       pl. boost.di Vega 1 24
    boost.report                     → a saját szorzóid kiírása
    boost.clear                      → a saját szorzóid törlése

## Küldetések (★ Developer réteg)

    assignment.clear             ★   → a napi küldetéseid törlése
    assignment.clear-for <név>   ★   → küldetés-törlés másnak
                                       pl. assignment.clear-for Vega
