-- github.com/Shran21
-- The rising daily login reward: which day of the run the pilot stands on,
-- and the UTC date the standing was last earned. An empty date means the
-- pilot has never collected one.
ALTER TABLE pilots ADD COLUMN daily_streak_day INTEGER NOT NULL DEFAULT 0;
ALTER TABLE pilots ADD COLUMN daily_streak_date TEXT NOT NULL DEFAULT '';
