# github.com/Shran21

from __future__ import annotations

from rebsgo.gamedata import json_helper as jh
from rebsgo.gamedata.cards.card_base import write_layout, Card
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.reading import AbilityActionKind, AugmentActionKind, ConsumableEffectKind, ObjectStats, ShipAbilityAffect, ShipAbilityLaunch, ShipAbilityTargetTier, ShipConsumableOption, ShipImmutableSlot, ShipRole, ShipSlotType, ShipSystemClass, StatView
from rebsgo.vocabulary.pilot import Faction, OldShipRole


class ShipAbilityCard(Card):
    def __init__(self, card_guid: int, view: CardView, level: int, ship_ability_launch, ship_ability_affect,
                 ability_group_id: int, target_tiers, consumable_type: int, consumable_tier: int,
                 ship_consumable_option, ability_action_type, overwrite_action_type, gui_buff_atlas: str,
                 gui_buff_index: int, item_buff_add, item_buff_multiply, remote_buff_add, remote_buff_multiply,
                 toggle_system_add, toggle_system_multiply, on_by_default: bool,
                 tiltott_hatasok, kepesseg_fajtak):
        super().__init__(card_guid, view)
        self.level = level
        self.ship_ability_launch = ship_ability_launch
        self.ship_ability_affect = ship_ability_affect
        self._ability_group_id = ability_group_id
        self.target_tiers = target_tiers
        self._consumable_type = consumable_type
        self.consumable_tier = consumable_tier
        self.ship_consumable_option = ship_consumable_option
        self._ability_action_type = ability_action_type
        self.overwrite_action_type = overwrite_action_type
        self.gui_buff_atlas = gui_buff_atlas
        self.gui_buff_index = gui_buff_index
        self._item_buff_add = item_buff_add
        self.item_buff_multiply = item_buff_multiply
        self.remote_buff_add = remote_buff_add
        self.remote_buff_multiply = remote_buff_multiply
        self.toggle_system_add = toggle_system_add
        self.toggle_system_multiply = toggle_system_multiply
        self.on_by_default = on_by_default
        self.consumable_effect_types_blacklist = tiltott_hatasok
        self.ability_action_types = kepesseg_fajtak

    @property
    def ability_action_type(self):
        return self._ability_action_type

    @property
    def ability_group_id(self) -> int:
        return self._ability_group_id

    @property
    def consumable_type(self) -> int:
        return self._consumable_type

    @property
    def item_buff_add(self):
        return self._item_buff_add

    def ability_affect_of(self):
        return self.ship_ability_affect

    def consumable_option_of(self):
        return self.ship_consumable_option

    @classmethod
    def from_json(cls, obj: dict) -> "ShipAbilityCard":
        view = CardView.from_code(jh.as_int(obj, "cardView"))
        target_tiers = set(jh.as_enum_list(obj, "TargetTiers", ShipAbilityTargetTier) or [])
        blacklist = jh.as_enum_list(obj, "effectTypeBlacklist", ConsumableEffectKind) or []
        affected = set(jh.as_enum_list(obj, "AffectedAbilityTypes", AbilityActionKind) or [])
        return cls(
            jh.as_long(obj, "cardGUID"), view,
            jh.as_short(obj, "Level"),
            jh.as_enum_by_name(obj, "Launch", ShipAbilityLaunch),
            jh.as_enum_by_name(obj, "Affect", ShipAbilityAffect),
            jh.as_long(obj, "AbilityGroupId"),
            target_tiers,
            jh.as_int(obj, "ConsumableType"),
            jh.as_long(obj, "ConsumableTier"),
            jh.as_enum_by_name(obj, "ConsumableOption", ShipConsumableOption),
            jh.as_enum_by_name(obj, "ActionType", AbilityActionKind),
            jh.as_enum_by_name(obj, "OverwriteActionType", AbilityActionKind),
            jh.as_text(obj, "GUIBuffAtlas"),
            jh.as_int(obj, "GUIBuffIndex"),
            jh.as_object_stats(obj, "ItemBuffAdd"),
            jh.as_object_stats(obj, "ItemBuffMultiply"),
            jh.as_object_stats(obj, "RemoteBuffAdd"),
            jh.as_object_stats(obj, "RemoteBuffMultiply"),
            jh.as_object_stats(obj, "ToggleSystemAdd"),
            jh.as_object_stats(obj, "ToggleSystemMultiply"),
            jh.as_flag(obj, "OnByDefault"),
            blacklist,
            affected,
        )

    def tier_of(self, tier: int):
        eredmeny = 1 << (tier - 1)
        return ShipAbilityTargetTier.from_code(eredmeny)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_byte(self.level & 0xFF)
        bw.write_byte(self.ship_ability_launch.value)
        bw.write_byte(self.ship_ability_affect.value)
        bw.write_uint32(self._ability_group_id)

        to_write = 0
        for tetel in self.target_tiers:
            to_write |= tetel.value
        bw.write_uint16(to_write)

        bw.write_uint16(self._consumable_type)
        bw.write_uint32(self.consumable_tier)
        bw.write_byte(self.ship_consumable_option.value)
        wire_action_type = (AbilityActionKind.None_ if self._ability_action_type == AbilityActionKind.DropMine
                            else self._ability_action_type)
        bw.write_byte(wire_action_type.value)
        bw.write_byte(self.overwrite_action_type.value)
        bw.write_string(self.gui_buff_atlas)
        bw.write_uint16(self.gui_buff_index)
        bw.write_desc(self._item_buff_add)
        bw.write_desc(self.item_buff_multiply)
        bw.write_desc(self.remote_buff_add)
        bw.write_desc(self.remote_buff_multiply)
        bw.write_desc(self.toggle_system_add)
        bw.write_desc(self.toggle_system_multiply)
        bw.write_boolean(self.on_by_default)

        blacklist = self.consumable_effect_types_blacklist
        bw.write_uint16(len(blacklist))
        for effect in blacklist:
            bw.write_byte(effect.value)

        bw.write_uint16(len(self.ability_action_types))
        for type_ in self.ability_action_types:
            bw.write_byte(type_.value)


class ShipCard(Card):
    def __init__(self, card_guid: int, ship_object_key: int, level: int, hangar_id: int, max_level: int,
                 level_requirement: int, durability: float, tier: int, ship_roles, ship_role_deprecated,
                 paperdoll_ui_layoutfile: str, rekesz_kartyak, cubit_only_repair: bool, variant_hangar_ids,
                 parent_hangar_id: int, stats, faction, immutable_slots, kovetkezo_hajo_guid: int):
        super().__init__(card_guid, CardView.Ship)
        self.ship_object_key = ship_object_key
        self.level = level
        self.hangar_id = hangar_id
        self.max_level = max_level
        self.level_requirement = level_requirement
        self.durability = durability
        self.tier = tier
        self.ship_roles = ship_roles
        self.ship_role_deprecated = ship_role_deprecated
        self.paperdoll_ui_layoutfile = paperdoll_ui_layoutfile
        self.ship_slot_cards = rekesz_kartyak
        self.cubit_only_repair = cubit_only_repair
        self.variant_hangar_ids = variant_hangar_ids
        self.parent_hangar_id = parent_hangar_id
        self.stats = stats
        self._faction = faction
        self.immutable_slots = immutable_slots
        self.next_ship_card_guid = kovetkezo_hajo_guid

    @classmethod
    def from_json(cls, obj: dict) -> "ShipCard":
        raw_slots = obj.get("Slots")
        rekeszek = None if raw_slots is None else [ShipSlotCard.from_json(s) for s in raw_slots]
        raw_imm = obj.get("ImmutableSlots")
        imm = None if raw_imm is None else [ShipImmutableSlot.from_json(s) for s in raw_imm]
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_long(obj, "ShipObjectKey"),
            jh.as_byte(obj, "Level"),
            jh.as_byte(obj, "HangarID"),
            jh.as_byte(obj, "MaxLevel"),
            jh.as_short(obj, "LevelRequirement"),
            jh.as_float(obj, "Durability"),
            jh.as_byte(obj, "Tier"),
            jh.as_enum_list(obj, "ShipRoles", ShipRole),
            jh.as_enum_by_name(obj, "ShipRoleDeprecated", OldShipRole),
            jh.as_text(obj, "PaperdollUiLayoutfile"),
            rekeszek,
            jh.as_flag(obj, "CubitOnlyRepair"),
            jh.as_long_list(obj, "VariantHangarIDs"),
            jh.as_int(obj, "ParentHangarID"),
            jh.as_object_stats(obj, "Stats"),
            jh.as_enum_by_name(obj, "Faction", Faction),
            imm,
            jh.as_long(obj, "nextShipCardGuid"),
        )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_guid(self.ship_object_key)
        bw.write_byte(self.level)
        bw.write_byte(self.max_level)
        bw.write_byte(self.level_requirement & 0xFF)
        bw.write_byte(self.hangar_id)
        bw.write_guid(self.next_ship_card_guid)
        bw.write_single(self.durability)
        bw.write_byte(self.tier)

        if self.ship_roles is None:
            bw.write_length(0)
        else:
            non_null = [r for r in self.ship_roles if r is not None]
            bw.write_length(len(non_null))
            for role in non_null:
                bw.write_byte(role.value)

        deprecated_role = OldShipRole.None_ if self.ship_role_deprecated is None else self.ship_role_deprecated
        bw.write_byte(deprecated_role.value)
        bw.write_string(self.paperdoll_ui_layoutfile)
        bw.write_desc_array(self.ship_slot_cards)
        bw.write_boolean(self.cubit_only_repair)
        bw.write_uint32_collection(self.variant_hangar_ids if self.variant_hangar_ids is not None else [])
        bw.write_int32(self.parent_hangar_id)
        bw.write_desc(self.stats)
        safe_faction = Faction.Neutral if self._faction is None else self._faction
        bw.write_byte(safe_faction.value)
        bw.write_desc_array(self.immutable_slots)
        bw.write_guid(0)

    def ship_slot_card(self, slot_id: int):
        if self.ship_slot_cards is None:
            return None
        for slot_card in self.ship_slot_cards:
            if slot_card.slot_id == slot_id:
                return slot_card
        return None

    @property
    def cubits_only_repair(self) -> bool:
        return self.cubit_only_repair

    @property
    def faction(self) -> Faction:
        return Faction.Neutral if self._faction is None else self._faction

    @property
    def stats_of(self):
        return self.stats


class ShipCardBrief(Card):
    def __init__(self, card_guid: int, ship_object_key: int, tier: int, ship_roles, ship_role_deprecated):
        super().__init__(card_guid, CardView.ShipLight)
        self.ship_object_key = ship_object_key
        self.tier = tier
        self.ship_roles = ship_roles
        self.ship_role_deprecated = ship_role_deprecated

    @classmethod
    def from_json(cls, obj: dict) -> "ShipCardBrief":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_long(obj, "ShipObjectKey"),
            jh.as_byte(obj, "Tier"),
            jh.as_enum_list(obj, "ShipRoles", ShipRole),
            jh.as_enum_by_name(obj, "ShipRoleDeprecated", OldShipRole),
        )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_guid(self.ship_object_key)
        bw.write_byte(self.tier)
        safe_roles = [] if self.ship_roles is None else self.ship_roles
        bw.write_length(len(safe_roles))
        for role in safe_roles:
            if role is None:
                continue
            bw.write_byte(role.value)
        deprecated = OldShipRole.None_ if self.ship_role_deprecated is None else self.ship_role_deprecated
        bw.write_byte(deprecated.value)


class ShipConsumableCard(Card):
    def __init__(self, card_guid: int, consumable_type: int, tier: int, item_buff_multiply, item_buff_add,
                 augment_action_type, is_augment: bool, auto_consume: bool, trashable: bool, buy_count: int,
                 fogyoeszkoz_jegyek, effect_type):
        super().__init__(card_guid, CardView.ShipConsumable)
        self._consumable_type = consumable_type
        self.tier = tier
        self.item_buff_multiply = item_buff_multiply
        self._item_buff_add = item_buff_add
        self.augment_action_type = augment_action_type
        self.is_augment_ = is_augment
        self.auto_consume = auto_consume
        self.trashable = trashable
        self.buy_count = buy_count
        self.consumable_attributes = fogyoeszkoz_jegyek
        self._effect_type = effect_type

    @classmethod
    def from_json(cls, obj: dict) -> "ShipConsumableCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_int(obj, "ConsumableType"),
            jh.as_byte(obj, "Tier"),
            jh.as_object_stats(obj, "ItemBuffMultiply"),
            jh.as_object_stats(obj, "ItemBuffAdd"),
            jh.as_enum_by_name(obj, "Action", AugmentActionKind),
            jh.as_flag(obj, "IsAugment"),
            jh.as_flag(obj, "AutoConsume"),
            jh.as_flag(obj, "Trashable"),
            jh.as_int(obj, "buyCount"),
            jh.as_text_list(obj, "consumableAttributes"),
            jh.as_enum_by_name(obj, "effectType", ConsumableEffectKind),
        )

    _HUZALREND = (
        ('uint16', '_consumable_type'),
        ('byte', 'tier'),
        ('desc', 'item_buff_multiply'),
        ('desc', '_item_buff_add'),
        ('byte', 'augment_action_type', 'value'),
        ('boolean', 'is_augment_'),
        ('boolean', 'auto_consume'),
        ('boolean', 'trashable'),
        ('uint16', 'buy_count'),
        ('string_array', 'consumable_attributes'),
        ('byte', '_effect_type', 'value'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, ShipConsumableCard._HUZALREND)

    @property
    def is_augment(self) -> bool:
        return self.is_augment_

    @property
    def is_auto_consume(self) -> bool:
        return self.auto_consume

    @property
    def may_discard(self) -> bool:
        return self.trashable

    @property
    def consumable_type(self) -> int:
        return self._consumable_type

    @property
    def item_buff_add(self):
        return self._item_buff_add

    @property
    def effect_type(self):
        return self._effect_type


class ShipListCard(Card):
    def __init__(self, card_guid: int, hull_card_guids, upgrade_hull_guids):
        super().__init__(card_guid, CardView.ShipList)
        self.ship_card_guids = hull_card_guids
        self.upgrade_ship_card_guids = upgrade_hull_guids

    @classmethod
    def from_json(cls, obj: dict) -> "ShipListCard":
        return cls(jh.as_long(obj, "cardGUID"),
                   jh.as_long_list(obj, "shipCardGuids") or [],
                   jh.as_long_list(obj, "upgradeShipCardGuids") or [])

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        hossz = len(self.ship_card_guids)
        bw.write_length(hossz)
        for i in range(hossz):
            bw.write_guid(self.ship_card_guids[i])
            bw.write_guid(self.upgrade_ship_card_guids[i])


class ShipSaleCard(Card):
    def __init__(self, card_guid: int, colonial_jutalmak, reward_cards_cylon):
        super().__init__(card_guid, CardView.ShipSale)
        self.reward_cards_colonial = colonial_jutalmak
        self.reward_cards_cylon = reward_cards_cylon

    @classmethod
    def from_json(cls, obj: dict) -> "ShipSaleCard":
        return cls(jh.as_long(obj, "cardGUID"),
                   jh.as_long_list(obj, "rewardCardsColonial") or [],
                   jh.as_long_list(obj, "getRewardCardsCylon") or [])

    _HUZALREND = (
        ('uint32_collection', 'reward_cards_colonial'),
        ('uint32_collection', 'reward_cards_cylon'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, ShipSaleCard._HUZALREND)


class ShipSlotCard:
    def __init__(self, slot_id: int, object_point: str, object_point_server_hash: int,
                 ship_slot_type, level: int):
        self.slot_id = slot_id
        self.object_point = object_point
        self.object_point_server_hash = object_point_server_hash
        self.ship_slot_type = ship_slot_type
        self.level = level

    @classmethod
    def from_json(cls, obj: dict) -> "ShipSlotCard":
        return cls(
            jh.as_int(obj, "SlotId"),
            jh.as_text(obj, "ObjectPoint"),
            jh.as_int(obj, "ObjectPointServerHash"),
            jh.as_enum_by_name(obj, "SystemType", ShipSlotType),
            jh.as_byte(obj, "Level"),
        )

    _HUZALREND = (
        ('uint16', 'slot_id'),
        ('string', 'object_point'),
        ('uint16', 'object_point_server_hash'),
        ('byte', 'ship_slot_type', 'value'),
        ('byte', 'level'),
    )

    def to_wire(self, bw) -> None:
        write_layout(self, bw, ShipSlotCard._HUZALREND)


class ShipSystemCard(Card):
    def __init__(self, card_guid: int, level: int, max_level: int, upgrade_target_guid: int, ship_slot_type, tier: int,
                 ship_object_key_restrictions, ship_role_restrictions, skill_hashes, kepesseg_kartyak,
                 static_buffs, multiply_buffs, durability: float, ship_system_class, stat_nezetek, unique: bool,
                 replaceable_only: bool, user_upgradeable: bool, trashable: bool, indestructible: bool,
                 max_count_per_ship: int):
        super().__init__(card_guid, CardView.ShipSystem)
        self.level = level
        self.max_level = max_level
        self.next_card_guid = upgrade_target_guid
        self.ship_slot_type = ship_slot_type
        self.tier = tier
        self.ship_object_key_restrictions = ship_object_key_restrictions
        self.ship_role_restrictions = ship_role_restrictions
        self.skill_hashes = skill_hashes
        self.ship_ability_cards = kepesseg_kartyak
        self.static_buffs = static_buffs
        self.multiply_buffs = multiply_buffs
        self.durability = durability
        self.ship_system_class = ship_system_class
        self.stat_views = stat_nezetek
        self.unique = unique
        self.replaceable_only = replaceable_only
        self.user_upgradeable = user_upgradeable
        self.trashable = trashable
        self.indestructible = indestructible
        self.max_count_per_ship = max_count_per_ship

    @classmethod
    def from_json(cls, obj: dict) -> "ShipSystemCard":
        raw_restr = obj.get("ShipObjectKeyRestrictions")
        restrictions = set() if raw_restr is None else set(int(x) for x in raw_restr)
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_byte(obj, "Level"),
            jh.as_byte(obj, "MaxLevel"),
            jh.as_long(obj, "nextShipSystemCardGuid"),
            jh.as_enum_by_name(obj, "SlotType", ShipSlotType),
            jh.as_byte(obj, "Tier"),
            restrictions,
            jh.as_enum_list(obj, "ShipRoleRestrictions", ShipRole),
            jh.as_long_list(obj, "SkillHashes"),
            jh.as_long_list(obj, "shipAbilityCards"),
            jh.as_object_stats(obj, "StaticBuffs"),
            jh.as_object_stats(obj, "MultiplyBuffs"),
            jh.as_float(obj, "Durability"),
            jh.as_enum_by_name(obj, "Class", ShipSystemClass),
            jh.as_enum_list(obj, "Views", StatView),
            jh.as_flag(obj, "Unique"),
            jh.as_flag(obj, "ReplaceableOnly"),
            jh.as_flag(obj, "UserUpgradeable"),
            jh.as_flag(obj, "Trashable"),
            jh.as_flag(obj, "Indestructible"),
            jh.as_short(obj, "MaxCountPerShip"),
        )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_byte(self.level)
        bw.write_byte(self.max_level)
        bw.write_guid(self.next_card_guid)
        safe_slot_type = self.ship_slot_type if self.ship_slot_type is not None else ShipSlotType.undefined
        bw.write_byte(safe_slot_type.value)
        bw.write_byte(self.tier)

        bw.write_uint32_collection(self.ship_object_key_restrictions if self.ship_object_key_restrictions is not None else set())

        safe_roles = self.ship_role_restrictions if self.ship_role_restrictions is not None else []
        bw.write_uint16(len(safe_roles))
        for role in safe_roles:
            bw.write_byte(role.value)

        bw.write_uint32_array(self.skill_hashes if self.skill_hashes is not None else [])
        bw.write_uint32_array(self.ship_ability_cards if self.ship_ability_cards is not None else [])

        bw.write_desc(self.static_buffs if self.static_buffs is not None else ObjectStats())
        bw.write_desc(self.multiply_buffs if self.multiply_buffs is not None else ObjectStats())
        bw.write_single(self.durability)
        safe_class = self.ship_system_class if self.ship_system_class is not None else ShipSystemClass.Standart
        bw.write_byte(safe_class.value)

        safe_stat_views = self.stat_views if self.stat_views is not None else []
        bw.write_uint16(len(safe_stat_views))
        for stat_view in safe_stat_views:
            bw.write_byte(stat_view.value)

        bw.write_boolean(self.unique)
        bw.write_boolean(self.replaceable_only)
        bw.write_boolean(self.user_upgradeable)
        bw.write_boolean(self.trashable)
        bw.write_boolean(self.indestructible)
        bw.write_byte(self.max_count_per_ship & 0xFF)

    def object_key_barred(self, ship_object_key: int) -> bool:
        return len(self.ship_object_key_restrictions) > 0 and ship_object_key not in self.ship_object_key_restrictions

    @property
    def single_copy(self) -> bool:
        return self.unique

    @property
    def replace_only(self) -> bool:
        return self.replaceable_only

    @property
    def player_may_upgrade(self) -> bool:
        return self.user_upgradeable

    @property
    def may_discard(self) -> bool:
        return self.trashable

    @property
    def cannot_break(self) -> bool:
        return self.indestructible


class ShipSystemPaintCard(Card):
    def __init__(self, card_guid: int, prefab_name: str, paint_texture: str = "", hull_card_guid: int = 0):
        super().__init__(card_guid, CardView.ShipPaint)
        self.prefab_name = prefab_name
        self.paint_texture = paint_texture
        self.ship_card_guid = hull_card_guid

    @classmethod
    def from_json(cls, obj: dict) -> "ShipSystemPaintCard":
        return cls(jh.as_long(obj, "cardGUID"), jh.as_text(obj, "model"),
                   jh.as_text(obj, "paintTexture"), jh.as_long(obj, "shipCardGuid"))

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_string(self.paint_texture)
        bw.write_string(self.prefab_name)
        bw.write_length(0)
        bw.write_guid(self.ship_card_guid)

    @property
    def uses_default_model(self) -> bool:
        return self.prefab_name == "default"
