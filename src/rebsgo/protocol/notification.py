# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass

from enum import Enum
from rebsgo.gamedata.ship_parts.parts import ShipItemBody
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.reply_base import ReplyBase
from rebsgo.vocabulary.client import JumpRefusal, JumpRefusalLevel
from rebsgo.vocabulary.combat import SpecialMove
from rebsgo.wire.bytes.outgoing import Outgoing


class MinerAlarm(Enum):
    ShipUnderAttackSimple = 1
    ShipUnderAttack = 2
    ShipDamaged = 3
    ShipDrivenOff = 4


class OutpostAlarm(Enum):
    OutpostUnderAttack = 2
    OutpostHeavyDamage = 3
    OutpostDied = 4


class EventPhase(Enum):
    Inactive = 0
    Active = 1
    Success = 2
    Failed = 3

    def to_wire(self, bw) -> None:
        bw.write_byte(self._value_)


class EventGoalDetail(Enum):
    FREIGHTER = 1
    DRONE_INSURGENT = 2

    def to_wire(self, bw) -> None:
        bw.write_byte(self._value_)


@dataclass(slots=True, eq=False)
class ProtectGoal(Outgoing):
    index: int
    sector_event_task_type: object
    sector_event_task_sub_type: object
    sector_event_state: object
    vip_object_id: int
    end_time: object

    def to_wire(self, bw) -> None:
        (bw
         .write_byte(self.index)
         .write_desc(self.sector_event_state)
         .write_desc(self.sector_event_task_type)
         .write_desc(self.sector_event_task_sub_type)
         .write_uint32(self.vip_object_id)
         .write_date_time(self.end_time))


class ServerMessage(Enum):
    Message = 1
    MiningShipUnderAttack = 2
    OutpostAttacked = 5
    HeavyFight = 6
    Experience = 7
    DutyUpdated = 8
    OreMined = 9
    Reward = 10
    MissionCompleted = 11
    DailyLoginBonus = 12
    SystemUpgradeResult = 13
    EmergencyMessage = 14
    AugmentItem = 15
    DeathPaymentBonus = 16
    JumpBeaconAttacked = 19
    MonthlyShipSale = 20
    SectorEventReward = 21
    EventPhase = 22
    SectorEventTasks = 23
    FtlMissionsOff = 24
    ErrorMessage = 25
    SectorFortificationLevel = 26
    LootMessage = 27
    InboxMailLimit = 28
    JumpNotification = 29
    ConversionCampaignOffer = 30

    @property
    def short_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "ServerMessage | None":
        return _BY_VALUE.get(value)


_BY_VALUE = {tag.value: tag for tag in ServerMessage}


class NotificationReplies(ReplyBase):
    UZENETEK = {
        "mission_completed": (
            ServerMessage.MissionCompleted.short_value,
            [("uint16", "mission_id")]),
        "ftl_mission_off": (ServerMessage.FtlMissionsOff.short_value, []),
        "emergency_message": (
            ServerMessage.EmergencyMessage.short_value,
            [("string", "message"), ("uint16", 0), ("single", "time_in_seconds")]),
        "daily_login_bonus": (
            ServerMessage.DailyLoginBonus.short_value,
            [("uint32", "bonus_level"), ("uint32_collection", "rewar_guids")]),
        "experience_gained": (
            ServerMessage.Experience.short_value,
            [("byte", 0), ("int32", "exp")]),
        "sector_event_task": (
            ServerMessage.SectorEventTasks.short_value,
            [("uint32", "event_object_id"), ("desc_collection", "sector_event_tasks")]),
        "heavy_fight": (
            ServerMessage.HeavyFight.short_value,
            [("guid", "sector_guid")]),
        "debug_message": (
            ServerMessage.Message.short_value,
            [("string", "message")]),
        "system_upgrade_result": (
            ServerMessage.SystemUpgradeResult.short_value,
            [("boolean", "upgrade_successful")]),
        "sector_event_state": (ServerMessage.EventPhase.short_value, [('uint32', 'event_object_id'), ('byte', 'faction.value'), ('byte', 'state_value'), ('vector3', 'position'), ('single', 'radius')]),
        "jump_notification": (ServerMessage.JumpNotification.value, [('byte', 'jump_error_severity.value'), ('byte', 'jump_error_reason.value')]),
        "sector_fortification": (ServerMessage.SectorFortificationLevel.short_value, [('byte', 'faction.value'), ('guid', 'sector_guid'), ('byte', 'level'), ('byte', 'sector_fortification_change_type.value')]),
        "outpost_attacked": (ServerMessage.OutpostAttacked.short_value, [('byte', 'faction.value'), ('guid', 'sector_guid'), ('byte', 'outpost_attacked_type.value')]),
        "mining_ship_under_attack": (ServerMessage.MiningShipUnderAttack.short_value, [('guid', 'sector_guid'), ('byte', 'mining_ship_attack_type.value'), ('boolean', 'is_your_mining_ship')]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Notification)

    def mission_reward(self, gui_card: int, targyak):
        bw = self.new_message()
        bw.write_msg_type(ServerMessage.Reward.short_value)
        bw.write_guid(gui_card)
        ShipItemBody.to_wire(bw, targyak)
        return bw

    def augment_item(self, item_list):
        bw = self.new_message()
        bw.write_msg_type(ServerMessage.AugmentItem.short_value)
        ShipItemBody.to_wire(bw, item_list)
        return bw

    def loot_message_deprecated(self, keszletek):
        bw = self.new_message()
        bw.write_msg_type(ServerMessage.LootMessage.short_value)
        bw.write_length(len(keszletek))
        for item_countable in keszletek:
            ShipItemBody.to_wire(bw, item_countable)
            bw.write_length(0)
        bw.write_length(0)
        return bw

    def loot_message(self, items, kulon_gombok):
        bw = self.new_message()
        bw.write_msg_type(ServerMessage.LootMessage.short_value)
        bw.write_length(len(items))
        for tetel in items:
            ShipItemBody.to_wire(bw, tetel.item_countable)
            loot_bonus_map = tetel.loot_bonus_type_long_map
            bw.write_length(len(loot_bonus_map))
            for loot_bonus_type, value in loot_bonus_map.items():
                bw.write_uint16(loot_bonus_type.value)
                bw.write_uint32(value)
        if len(kulon_gombok) == 1 and kulon_gombok[0] == SpecialMove.None_:
            bw.write_length(0)
        else:
            bw.write_desc_collection(kulon_gombok)
        bw.write_boolean(False)
        return bw

    def ore_taken_out(self, item_countable):
        bw = self.new_message()
        bw.write_msg_type(ServerMessage.OreMined.short_value)
        ShipItemBody.to_wire(bw, item_countable)
        return bw

    def sector_event_reward(self, event_object_id: int, sector_event_guid: int, ranking_value: int, targyak):
        bw = self.new_message()
        bw.write_msg_type(ServerMessage.SectorEventReward.short_value)
        bw.write_uint32(event_object_id)
        bw.write_guid(sector_event_guid)
        bw.write_byte(ranking_value)
        ShipItemBody.to_wire(bw, list(targyak))
        return bw


class NotificationProtocol(BgoProtocol):
    def __init__(self, ctx):
        super().__init__(ProtocolID.Notification, ctx)
        self._notification_protocol_write_only = NotificationReplies()

    @property
    def replies(self) -> NotificationReplies:
        return self._notification_protocol_write_only

    def read_message(self, msg_type: int, br) -> None:
        pass

    def hand_out_augments(self, item_list) -> None:
        self.user().send(self.replies.augment_item(item_list))

        locker = self.user().pilot_of().locker
        from rebsgo.pilots.state.holdings.walks.locker_walk import LockerWalk
        utvonal = LockerWalk(self.user(), None)
        for ship_item in item_list:
            utvonal.add_ship_item(ship_item, locker)

    def refuse_jump(self) -> None:
        bw = self.replies.jump_notification(JumpRefusalLevel.Error, JumpRefusal.Closed)
        self.user().send(bw)
