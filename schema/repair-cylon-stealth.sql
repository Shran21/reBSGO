-- github.com/Shran21
DELETE FROM slot_state
WHERE EXISTS (
    SELECT 1
    FROM owned_ships h
    WHERE h.player_id = slot_state.player_id
      AND h.server_id = slot_state.ship_id
      AND h.guid = 10000030
);

INSERT OR REPLACE INTO slot_state(player_id, ship_id, server_id, guid, durability)
SELECT player_id, server_id, 0, 20003122, 999999.0 FROM owned_ships WHERE guid = 10000030;
INSERT OR REPLACE INTO slot_state(player_id, ship_id, server_id, guid, durability)
SELECT player_id, server_id, 2, 20000397, 999999.0 FROM owned_ships WHERE guid = 10000030;
INSERT OR REPLACE INTO slot_state(player_id, ship_id, server_id, guid, durability)
SELECT player_id, server_id, 4, 20001173, 999999.0 FROM owned_ships WHERE guid = 10000030;
INSERT OR REPLACE INTO slot_state(player_id, ship_id, server_id, guid, durability)
SELECT player_id, server_id, 6, 20000334, 999999.0 FROM owned_ships WHERE guid = 10000030;
INSERT OR REPLACE INTO slot_state(player_id, ship_id, server_id, guid, durability)
SELECT player_id, server_id, 7, 20001193, 999999.0 FROM owned_ships WHERE guid = 10000030;
INSERT OR REPLACE INTO slot_state(player_id, ship_id, server_id, guid, durability)
SELECT player_id, server_id, 8, 20003282, 999999.0 FROM owned_ships WHERE guid = 10000030;
INSERT OR REPLACE INTO slot_state(player_id, ship_id, server_id, guid, durability)
SELECT player_id, server_id, 10, 20000148, 999999.0 FROM owned_ships WHERE guid = 10000030;
INSERT OR REPLACE INTO slot_state(player_id, ship_id, server_id, guid, durability)
SELECT player_id, server_id, 13, 10001412, 999999.0 FROM owned_ships WHERE guid = 10000030;
INSERT OR REPLACE INTO slot_state(player_id, ship_id, server_id, guid, durability)
SELECT player_id, server_id, 16, 20002200, 999999.0 FROM owned_ships WHERE guid = 10000030;
INSERT OR REPLACE INTO slot_state(player_id, ship_id, server_id, guid, durability)
SELECT player_id, server_id, 17, 20000791, 999999.0 FROM owned_ships WHERE guid = 10000030;

UPDATE owned_ships
SET guid = 10000131
WHERE guid = 10000030;
