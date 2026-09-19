-- github.com/Shran21
-- Rank names that are still the enum's English defaults become empty, so
-- the client shows its own localized role words instead. A name a leader
-- actually typed in stays exactly as typed.
UPDATE guild_ranks SET rank_name = ''
 WHERE rank_name IN ('None_', 'Recruit', 'Pilot', 'SeniorPilot',
                     'FlightLeader', 'GroupLeader', 'Leader');
