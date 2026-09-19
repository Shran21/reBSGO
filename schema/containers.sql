-- github.com/Shran21
CREATE TABLE IF NOT EXISTS container_slots
(
    kind INTEGER NOT NULL,
    player_id         INTEGER NOT NULL,
    PRIMARY KEY (kind, player_id),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);

CREATE TABLE IF NOT EXISTS installed_systems
(
    player_id    INTEGER NOT NULL,
    container_id INTEGER NOT NULL,
    server_id     INTEGER NOT NULL,
    guid          INTEGER NOT NULL,
    durability    REAL    NOT NULL,
    PRIMARY KEY (player_id, container_id, server_id, guid),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id),
    FOREIGN KEY (container_id)
        REFERENCES container_slots (id)
);

CREATE TABLE IF NOT EXISTS stacks
(
    player_id    INTEGER NOT NULL,
    container_id INTEGER NOT NULL,
    server_id     INTEGER NOT NULL,
    guid          INTEGER NOT NULL,
    count         INTEGER NOT NULL,
    PRIMARY KEY (player_id, container_id, server_id, guid),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id),
    FOREIGN KEY (container_id)
        REFERENCES container_slots (id)
);