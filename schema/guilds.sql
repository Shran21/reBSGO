-- github.com/Shran21
CREATE TABLE IF NOT EXISTS guilds
(
    id   INTEGER NOT NULL PRIMARY KEY,
    name TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS guild_ranks
(
    guild_id    INTEGER NOT NULL,
    role_id     INTEGER NOT NULL, -- a rank, small enough for one byte
    rank_name   TEXT    NOT NULL,
    permissions INTEGER NOT NULL,
    PRIMARY KEY (guild_id, role_id),
    FOREIGN KEY (guild_id)
        REFERENCES guilds (id)
);

CREATE TABLE IF NOT EXISTS guild_members
(
    guild_id       INTEGER NOT NULL,
    player_id     INTEGER NOT NULL,
    role INTEGER NOT NULL, -- a rank, small enough for one byte
    PRIMARY KEY (guild_id, player_id, role)
);