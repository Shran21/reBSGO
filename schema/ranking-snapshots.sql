-- github.com/Shran21
-- A havi ranglistához kell egy fogódzó: ahhoz, hogy "ebben a hónapban"
-- értelmes legyen, tudni kell, hol állt a számláló a hónap elején. A
-- pillanatkép ezt őrzi, számlálónként és pilótánként, és a havi érték
-- egyszerűen a mostani állás mínusz ez.
--
-- Egy időszakból egy sor van pilótánként és számlálónként; a régebbi
-- időszakok bent maradnak, mert a torna múlt szezonjai ugyanezen a
-- táblán állnak.
CREATE TABLE IF NOT EXISTS ranking_snapshots
(
    period_key TEXT    NOT NULL,
    player_id  INTEGER NOT NULL,
    guid       INTEGER NOT NULL,
    value      REAL    NOT NULL,

    PRIMARY KEY (period_key, player_id, guid)
);

CREATE INDEX IF NOT EXISTS ranking_snapshots_period
    ON ranking_snapshots (period_key);
