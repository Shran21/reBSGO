-- github.com/Shran21
-- What a pilot's password is checked against.
--
-- The launcher sends a password at admission; this is what it is weighed
-- against. The password itself is not here - only a digest derived from it,
-- which even together with the salt cannot be turned back into the original.
-- It can only be re-derived and compared.
--
-- Salt and digest sit in columns of their own, as raw bytes, rather than in
-- one joined string. That leaves no format to parse, and no way to lie about
-- the digest length by placing a separator well.
--
-- `algorithm` records how hard the derivation was worked. When it is time to
-- work it harder, the older rows stay checkable: each one carries the recipe
-- it was made with.

CREATE TABLE pilot_passwords
(
    player_id  INTEGER NOT NULL,
    algorithm  TEXT    NOT NULL,
    salt       BLOB    NOT NULL,
    secret     BLOB    NOT NULL,
    changed_at TEXT    NOT NULL,

    PRIMARY KEY (player_id),
    FOREIGN KEY (player_id)
        REFERENCES pilots (id)
);
