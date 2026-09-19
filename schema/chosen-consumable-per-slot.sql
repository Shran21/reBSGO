-- github.com/Shran21
ALTER TABLE slot_state
    ADD COLUMN current_consumable_guid INTEGER NOT NULL DEFAULT 0;
