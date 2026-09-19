-- github.com/Shran21
CREATE TABLE IF NOT EXISTS pilots
(
    id               INTEGER NOT NULL,
    name             TEXT    NOT NULL,
    faction       INTEGER NOT NULL,
    roles_bits       INTEGER NOT NULL, -- one bit per role, not an id
    last_logout_date TEXT    NOT NULL,
    last_wof_date    TEXT    NOT NULL,

    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS avatar_parts
(
    player_id INTEGER NOT NULL,
    item_id    INTEGER NOT NULL,
    value      TEXT    NOT NULL,

    PRIMARY KEY (player_id, item_id)
        FOREIGN KEY (player_id)
        REFERENCES pilots(id)
);

CREATE TABLE IF NOT EXISTS limits
(
    player_id    INTEGER NOT NULL,
    guid          INTEGER NOT NULL,
    value         INTEGER NOT NULL,
    last_cap_date TEXT    NOT NULL,


    PRIMARY KEY (player_id, guid),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);

CREATE TABLE IF NOT EXISTS tallies
(
    player_id INTEGER NOT NULL,
    guid       INTEGER NOT NULL,
    value      REAL    NOT NULL,

    PRIMARY KEY (player_id, guid),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);

CREATE TABLE IF NOT EXISTS boosts
(
    id               INTEGER NOT NULL,
    player_id       INTEGER NOT NULL,
    factor_source_id INTEGER NOT NULL,
    factor_type_id   INTEGER NOT NULL,
    value            REAL    NOT NULL,
    end_time         TEXT    NOT NULL,

    PRIMARY KEY (player_id, id),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);

CREATE TABLE IF NOT EXISTS mail
(
    mail_id            INTEGER NOT NULL,
    player_id         INTEGER NOT NULL,
    mail_template_guid INTEGER NOT NULL,
    received_timestamp TEXT    NOT NULL,
    parameters         TEXT    NOT NULL,
    PRIMARY KEY (player_id, mail_id),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);

CREATE TABLE IF NOT EXISTS mission_logs
(
    player_id                     INTEGER NOT NULL PRIMARY KEY,
    last_time_missions_fetch_date TEXT    NOT NULL,
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);

CREATE TABLE IF NOT EXISTS pilot_missions
(
    player_id              INTEGER NOT NULL,
    mission_id             INTEGER NOT NULL,
    mission_guid           INTEGER NOT NULL,
    associated_sector_guid INTEGER NOT NULL,
    counter_guid           INTEGER NOT NULL,
    current_count          INTEGER NOT NULL,
    need_count             INTEGER NOT NULL,
    PRIMARY KEY (player_id, mission_id, mission_guid, counter_guid),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);