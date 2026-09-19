-- github.com/Shran21
-- Timed bans issued from the web panel. The admission gate reads this on
-- every login; a row past its until date simply stops mattering.
CREATE TABLE IF NOT EXISTS panel_bans
(
    player_id  INTEGER NOT NULL PRIMARY KEY,
    until_utc  TEXT    NOT NULL,
    reason     TEXT    NOT NULL DEFAULT '',
    banned_by  TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL DEFAULT ''
);
