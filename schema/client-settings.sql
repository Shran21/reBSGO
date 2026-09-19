-- github.com/Shran21
-- One row per setting. The value column holds whatever the setting's
-- own type says it is, written out as text and read back by that type.
CREATE TABLE IF NOT EXISTS client_options
(
    player_id      INTEGER NOT NULL,
    user_setting_id INTEGER NOT NULL,
    value           REAL    NOT NULL,
    PRIMARY KEY (player_id, user_setting_id),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);

CREATE TABLE IF NOT EXISTS key_bindings
(
    player_id          INTEGER NOT NULL,
    action_id           INTEGER NOT NULL,
    device_trigger_code INTEGER NOT NULL,
    device_mod_code     INTEGER NOT NULL,
    device              INTEGER NOT NULL,
    flags               INTEGER NOT NULL,
    profile_number      INTEGER NOT NULL,

    PRIMARY KEY (player_id, action_id),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);