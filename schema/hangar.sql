-- github.com/Shran21
CREATE TABLE IF NOT EXISTS hangar_state
(
    player_id   INTEGER NOT NULL,
    active_index INTEGER NOT NULL,

    PRIMARY KEY (player_id),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);

CREATE TABLE IF NOT EXISTS owned_ships
(
    player_id INTEGER NOT NULL,
    server_id  INTEGER NOT NULL,
    guid       INTEGER NOT NULL,
    durability REAL    NOT NULL,
    name       TEXT    NOT NULL,

    PRIMARY KEY (player_id, server_id, guid),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);


CREATE TABLE IF NOT EXISTS slot_state
(
    player_id INTEGER NOT NULL,
    ship_id    INTEGER NOT NULL,
    server_id  INTEGER NOT NULL,
    guid       INTEGER NOT NULL,
    durability REAL    NOT NULL,
    PRIMARY KEY (player_id, server_id, ship_id),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);