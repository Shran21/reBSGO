-- github.com/Shran21
CREATE TABLE IF NOT EXISTS skill_books
(
    player_id INTEGER NOT NULL PRIMARY KEY,
    xp        INTEGER NOT NULL,
    spent_xp          NOT NULL,
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);

CREATE TABLE IF NOT EXISTS pilot_skills
(
    player_id INTEGER NOT NULL,
    card_guid INTEGER NOT NULL,
    server_id INTEGER NOT NULL,
    PRIMARY KEY (player_id, server_id)
);