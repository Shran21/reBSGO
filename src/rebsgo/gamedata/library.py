# github.com/Shran21

from __future__ import annotations

from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.cards.ship_cards import ShipCard, ShipListCard
from rebsgo.gamedata.cards.world_cards import WorldCard
from rebsgo.gamedata.reading import ObjectStats
from rebsgo.vocabulary.world import WellKnownCard
import logging


class AssignmentCardRow:
    def __init__(self, mission_card, reward_card):
        self._mission_card = mission_card
        self._reward_card = reward_card

    @staticmethod
    def void_frame() -> "AssignmentCardRow":
        return AssignmentCardRow(None, None)

    @property
    def mission_card(self):
        return self._mission_card

    @property
    def reward_card(self):
        return self._reward_card

    @property
    def usable(self) -> bool:
        return self._mission_card is not None and self._reward_card is not None


class LiveCard:
    def __init__(self, *kartya_nezetek):
        if len(kartya_nezetek) == 1 and isinstance(kartya_nezetek[0], (set, frozenset)):
            self._initial_requested_views = set(kartya_nezetek[0])
        else:
            self._initial_requested_views = set(kartya_nezetek)
        self._card_map: dict[CardView, object] = {}
        self._all_cards_available = False

    def file_card(self, card) -> None:
        self._card_map[card.card_view] = card

    def _is_all_cards_available(self) -> bool:
        if self._all_cards_available:
            return True
        initial_matches = self._check_initial_views_match_current
        if initial_matches:
            self._all_cards_available = True
        return initial_matches

    @property
    def _check_initial_views_match_current(self) -> bool:
        return set(self._card_map.keys()) == self._initial_requested_views

    def card(self, view: CardView):
        if not self._is_all_cards_available():
            raise ValueError('that card view is unavailable')
        return self._card_map.get(view)


class SystemPrices:
    def __init__(self, ship_system_card, shop_item_card):
        self._ship_system_card = ship_system_card
        self._shop_item_card = shop_item_card

    @staticmethod
    def void_frame() -> "SystemPrices":
        return SystemPrices(None, None)

    @property
    def ship_system_card(self):
        return self._ship_system_card

    @property
    def shop_item_card(self):
        return self._shop_item_card

    @property
    def usable(self) -> bool:
        return self._ship_system_card is not None and self._shop_item_card is not None


class OwnedWorldCard:
    def __init__(self, world_card, owner_card):
        if world_card is None:
            raise TypeError("a world_card is required")
        if owner_card is None:
            raise TypeError("an owner_card is required")
        self._world_card = world_card
        self._owner_card = owner_card

    def world_card(self):
        return self._world_card

    @property
    def owner_card(self):
        return self._owner_card


log = logging.getLogger(__name__)
def _guid_of(kartya) -> int:
    return kartya.value if isinstance(kartya, WellKnownCard) else kartya


class Catalogue:
    def __init__(self, card_shelf):
        self._card_shelf = card_shelf
        self._card_map: dict[int, object] = {}
        self._mission_cards_map: dict[int, object] = {}
        self._card_writers: dict[int, object] = {}
        self._cards_by_view: dict[CardView, list] = {}
        self._ship_cards_by_object_key: dict[int, list] = {}
        self._skill_cards: list = []
        self.load_cards()

    @property
    def map_card(self):
        return self.card_or_none(WellKnownCard.GalaxyMap, CardView.GalaxyMap)

    @property
    def world_card(self):
        return self.card_or_none(WellKnownCard.GlobalCard, CardView.Global)

    def load_cards(self) -> None:
        kartyak = self._card_shelf.fetch_all_cards_2()
        self._add_cards(kartyak)
        self._straighten_map_icons()
        self._straighten_drone_cards()
        self._ensure_minimal_static_cards()

        self._skill_cards.extend(self.all_cards_of_view(CardView.Skill))

        for mission_card in self.all_cards_of_view(CardView.Assignment):
            self._mission_cards_map[mission_card.card_guid_of()] = mission_card

        free_card_guids = self.free_card_guids(100)
        log.info('card guids still available: %s', free_card_guids)

    def _ensure_minimal_static_cards(self) -> None:
        if self.card_of(WellKnownCard.ShipListCardColonial.value, CardView.ShipList) is None:
            log.warning('colonial ship-list card absent; an empty list keeps the client handshake alive')
            self.take_card(ShipListCard(WellKnownCard.ShipListCardColonial.value, [], []))
        if self.card_of(WellKnownCard.ShipListCardCylon.value, CardView.ShipList) is None:
            log.warning('cylon ship-list card absent; an empty list keeps the client handshake alive')
            self.take_card(ShipListCard(WellKnownCard.ShipListCardCylon.value, [], []))

    _TERKEPEN_MUTATANDO = ("t1", "t2", "t3", "t4", "t5", "stationary", "drone")

    _TERKEP_TEXTURA = "GUI/Map/map_objects"

    @property
    def all_asteroid_world_cards(self) -> list:
        return [c for c in self._card_map.values()
                if c.card_view == CardView.World and "asteroid" in c.prefab_name
                and "field" not in c.prefab_name]

    def all_cards_of_view(self, card_view: CardView) -> list:
        return list(self._cards_by_view.get(card_view, ()))

    def all_mission_cards(self) -> dict:
        from types import MappingProxyType

        return MappingProxyType(self._mission_cards_map)

    def all_skil_cards_of_level(self, level: int) -> list:
        return [s for s in self._skill_cards if s.level == level]

    def all_world_cards_of_prefab_start_with(self, prefab_start: str) -> list:
        return [c for c in self._card_map.values()
                if c.card_view == CardView.World and c.prefab_name.startswith(prefab_start)]

    def card_of(self, kartya, card_view: CardView):
        card_guid = _guid_of(kartya)
        if card_guid == 0:
            return None
        return self._card_map.get(self.key_for(card_guid, card_view))

    def card_or_none(self, kartya, card_view: CardView):
        kulcs = self.key_for(_guid_of(kartya), card_view)
        return self._card_map.get(kulcs)

    def cards_of(self, guid: int, *kartya_nezetek) -> LiveCard:
        wrapper = LiveCard(*kartya_nezetek)
        for card_view in kartya_nezetek:
            kartya = self.card_of(guid, card_view)
            if kartya is None:
                break
            wrapper.file_card(kartya)
        return wrapper

    def forget_writer(self, card_guid: int, view: CardView) -> None:
        self._card_writers.pop(self.key_for(card_guid, view), None)

    def free_card_guids(self, count: int) -> list:
        free_card_guids = []
        views = list(CardView)
        l = 1
        korlat = 0xFFFFFFFF * 2
        while l < korlat:
            exists = False
            for card_view in views:
                if self.key_for(l, card_view) in self._card_map:
                    exists = True
                    break
            if not exists:
                free_card_guids.append(l)
                if len(free_card_guids) >= count:
                    break
            l += 1
        return free_card_guids

    @staticmethod
    def key_for(card_guid: int, card_view: CardView) -> int:
        szam = card_view.value
        szam <<= 32
        return szam + card_guid

    def mission_cards(self, assignment_guid: int) -> AssignmentCardRow:
        mission_card = self.card_of(assignment_guid, CardView.Assignment)
        if mission_card is None:
            log.warning('catalogue lookup failed for assignment %s', assignment_guid)
            return AssignmentCardRow.void_frame()
        reward_card = self.card_of(mission_card.reward_card_guid, CardView.Reward)
        if reward_card is None:
            log.warning('catalogue lookup failed for assignment reward %s', mission_card.reward_card_guid)
            return AssignmentCardRow.void_frame()
        return AssignmentCardRow(mission_card, reward_card)

    def price_cards(self, card_guid: int) -> SystemPrices:
        ship_system_card = self.card_of(card_guid, CardView.ShipSystem)
        if ship_system_card is None:
            log.warning('catalogue lookup failed for system %s', card_guid)
            return SystemPrices.void_frame()
        shop_item_card = self.card_of(card_guid, CardView.Price)
        if shop_item_card is None:
            log.warning('catalogue lookup failed for a system price %s', card_guid)
            return SystemPrices.void_frame()
        return SystemPrices(ship_system_card, shop_item_card)

    def register_writer(self, card_guid: int, view: CardView, bw) -> None:
        self._card_writers[self.key_for(card_guid, view)] = bw

    def replies(self, card_guid: int, view: CardView):
        return self._card_writers.get(self.key_for(card_guid, view))

    def sector_card_by_id(self, id: int):
        gui_card = None
        for kartya in self._card_map.values():
            if kartya.card_view == CardView.GUI and kartya.key == f'sector{id}':
                gui_card = kartya
                break
        if gui_card is None:
            return None
        return self.card_of(gui_card.card_guid_of(), CardView.Sector)

    def ship_cards_by_object_key(self, ship_object_key: int) -> list:
        return list(self._ship_cards_by_object_key.get(ship_object_key, ()))

    def swap_card(self, card) -> None:
        self._put_card(card, log_duplicate=False)

    def system_cards(self, guid: int) -> dict:
        eredmeny: dict = {}
        init_card = self.card_of(guid, CardView.ShipSystem)
        if init_card is None:
            raise ValueError('that guid does not parse')
        eredmeny[init_card.level] = init_card
        mostani = init_card
        while mostani.next_card_guid != 0:
            next_card = self.card_of(mostani.next_card_guid, CardView.ShipSystem)
            if next_card is None:
                break
            mostani = next_card
            eredmeny[next_card.level] = next_card
        return eredmeny

    def take_card(self, card) -> None:
        self._put_card(card, log_duplicate=True)

    def world_owner_cards(self, guid: int) -> OwnedWorldCard:
        world_card = self.card_of(guid, CardView.World)
        owner_card = self.card_of(guid, CardView.Owner)
        if owner_card is None:
            raise ValueError(f'owner card absent for guid {guid}')
        if world_card is None:
            raise ValueError(f'world card absent for guid {guid}')
        return OwnedWorldCard(world_card, owner_card)

    def _add_card_to_indexes(self, card) -> None:
        view = card.card_view
        self._cards_by_view.setdefault(view, []).append(card)
        if isinstance(card, ShipCard):
            self._ship_cards_by_object_key.setdefault(card.ship_object_key, []).append(card)

    def _add_cards(self, cards) -> None:
        if cards is not None:
            for kartya in cards:
                if kartya is not None:
                    self.take_card(kartya)

    def _put_card(self, card, log_duplicate: bool) -> None:
        if card is None:
            log.error('catalogue met an empty card row and stepped over it')
            return
        if card.card_view is None:
            log.error('card %s has no view on it, so it is skipped', card.card_guid_of())
            return
        kulcs = self.key_for(card.card_guid_of(), card.card_view)
        eredmeny = self._card_map.get(kulcs)
        if eredmeny is not None:
            self._remove_card_from_indexes(eredmeny)
        self._card_map[kulcs] = card
        self._add_card_to_indexes(card)
        self._card_writers.pop(kulcs, None)
        if log_duplicate and eredmeny is not None:
            log.error("DOUBLE CARD; current: %s before: %s", card, eredmeny)

    def _remove_card_from_indexes(self, card) -> None:
        self._remove_from_index_list(self._cards_by_view, card.card_view, card)
        if isinstance(card, ShipCard):
            self._remove_from_index_list(self._ship_cards_by_object_key, card.ship_object_key, card)

    @staticmethod
    def _remove_from_index_list(index: dict, key, card) -> None:
        bejegyzesek = index.get(key)
        if not bejegyzesek:
            return
        for idx, existing in enumerate(bejegyzesek):
            if existing is card:
                del bejegyzesek[idx]
                break
        else:
            try:
                bejegyzesek.remove(card)
            except ValueError:
                return
        if not bejegyzesek:
            index.pop(key, None)

    def _straighten_drone_cards(self) -> None:
        from rebsgo.gamedata.from_json.template_readers import drone_hull_keys
        kulcsok = drone_hull_keys()
        updated = 0
        for kartya in self.all_cards_of_view(CardView.Ship):
            if not isinstance(kartya, ShipCard) or kartya.ship_object_key not in kulcsok:
                continue
            if kartya.stats_of is not None:
                continue
            mutatok = ObjectStats() if kartya.stats_of is None else kartya.stats_of
            fixed = ShipCard(
                kartya.card_guid_of(),
                kartya.ship_object_key,
                kartya.level,
                kartya.hangar_id,
                kartya.max_level,
                kartya.level_requirement & 0xFF,
                kartya.durability,
                kartya.tier,
                kartya.ship_roles,
                kartya.ship_role_deprecated,
                kartya.paperdoll_ui_layoutfile,
                kartya.ship_slot_cards,
                kartya.cubits_only_repair,
                kartya.variant_hangar_ids,
                kartya.parent_hangar_id,
                mutatok,
                kartya.faction,
                kartya.immutable_slots,
                kartya.next_ship_card_guid,
            )
            self.swap_card(fixed)
            updated += 1
        if updated > 0:
            log.info('straightened out %d drone hull cards', updated)

    def _straighten_map_icons(self) -> None:
        atfestettek = 0
        for world_card in self.all_cards_of_view(CardView.World):
            nev = world_card.prefab_name or ""
            mutassa = any(jel in nev.lower() for jel in Catalogue._TERKEPEN_MUTATANDO)
            rendben = (nev.strip() == ""
                       or (world_card.system_map_textures == Catalogue._TERKEP_TEXTURA
                           and (world_card.always_on_map or not mutassa)))
            if not rendben:
                self.swap_card(Catalogue._terkepre_igazitva(world_card, mutassa))
                atfestettek += 1
        if atfestettek:
            log.info('straightened out %d world-card map entries (texture and visibility)', atfestettek)

    @staticmethod
    def _terkepre_igazitva(world_card, mutassa: bool) -> WorldCard:
        return WorldCard(
            world_card.card_guid_of(),
            world_card.prefab_name,
            world_card.lod_count,
            world_card.radius_of(),
            world_card.spots,
            Catalogue._TERKEP_TEXTURA,
            world_card.frame_index,
            world_card.secondary_frame_index,
            world_card.is_target_able,
            world_card.brackets_within_range,
            mutassa or world_card.always_on_map,
        )


def fogyoeszkoz_kartya(fogyoeszkoz):
    from rebsgo.services import Services
    from rebsgo.gamedata.cards.card_view import CardView

    katalogus = Services.get(Catalogue)
    return katalogus.card_or_none(fogyoeszkoz.card_guid_of(), CardView.ShipConsumable)
