# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.gamedata.cards.card_deserializer import deserialize_card
from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo.helpers.rolling_latency_stats import (
    ENABLED as GUARDRAILS_ENABLED,
    GAMEDATA_FILE_WARN_MS,
    GAMEDATA_TOTAL_WARN_MS,
    elapsed_ms,
    now_ms,
    should_warn,
    warn_if_slow,
)
from rebsgo import paths

log = logging.getLogger(__name__)


class CardLoader(GameDataLoader):
    def __init__(self, path=None):
        if path is None:
            path = paths.JATEKADAT / "cards"
        super().__init__(path)

    def fetch_all_cards_2(self) -> list:
        total_started_ms = now_ms() if GUARDRAILS_ENABLED else 0.0
        file_paths = self.file_paths()
        cards = []
        element_count = 0
        for utvonal in file_paths:
            file_started_ms = now_ms() if GUARDRAILS_ENABLED else 0.0
            parsed = self.read_json(utvonal)
            if parsed is None:
                continue
            for element in parsed:
                cards.append(deserialize_card(element))
                element_count += 1
            if GUARDRAILS_ENABLED:
                warn_if_slow(
                    log,
                    elapsed_ms(file_started_ms),
                    GAMEDATA_FILE_WARN_MS,
                    "Slow card file parse path=%s entries=%s",
                    utvonal,
                    len(parsed),
                )
        if GUARDRAILS_ENABLED:
            total_elapsed = elapsed_ms(total_started_ms)
            if should_warn(total_elapsed, GAMEDATA_TOTAL_WARN_MS):
                log.warning(
                    "CardLoader loaded cards slowly files=%s entries=%s cards=%s elapsed_ms=%.1f threshold_ms=%.1f",
                    len(file_paths), element_count, len(cards), total_elapsed, GAMEDATA_TOTAL_WARN_MS)
            else:
                log.info("CardLoader loaded cards files=%s entries=%s cards=%s elapsed_ms=%.1f",
                         len(file_paths), element_count, len(cards), total_elapsed)
        return cards
