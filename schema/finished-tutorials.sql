-- github.com/Shran21
-- Dismissed help screens / completed tutorials (UserSetting.CompletedTutorials).
-- This is a list of HelpScreenType ids per player, so it cannot live in the single-value
-- client_options table and gets its own table.
CREATE TABLE IF NOT EXISTS tutorials_done
(
    player_id     INTEGER NOT NULL,
    help_screen_id INTEGER NOT NULL,
    PRIMARY KEY (player_id, help_screen_id),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);
