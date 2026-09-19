-- github.com/Shran21
-- Who a pilot counts as a friend.
--
-- One row per direction rather than one per pair: that is how the two pilots
-- hold it in memory, and it is what lets a list be read back with a single
-- lookup on player_id. The two directions are written together whenever a
-- friendship is made or broken, so they stay in step.
CREATE TABLE IF NOT EXISTS friends
(
    player_id INTEGER NOT NULL,
    friend_id INTEGER NOT NULL,
    PRIMARY KEY (player_id, friend_id),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);
