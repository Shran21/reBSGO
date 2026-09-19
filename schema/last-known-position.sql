-- github.com/Shran21
CREATE TABLE IF NOT EXISTS last_seen(
                                        player_id INTEGER NOT NULL,
                                        sector_id INTEGER NOT NULL,
                                        place INTEGER NOT NULL,
                                        previous_place INTEGER,


                                        PRIMARY KEY (player_id),
                                        FOREIGN KEY (player_id)
                                            REFERENCES pilots(id)
);

