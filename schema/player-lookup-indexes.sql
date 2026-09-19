-- github.com/Shran21
CREATE INDEX IF NOT EXISTS idx_players_name
    ON pilots(name);

CREATE INDEX IF NOT EXISTS idx_players_name_nocase
    ON pilots(name COLLATE NOCASE);
