# github.com/Shran21

from __future__ import annotations

from enum import Enum
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.reply_base import ReplyBase
import logging


class ControlKind(Enum):
    TargetEnemy = 19
    TargetAlly = 20
    ThrottleBar = 21
    Boosters = 22
    Camera = 23
    SystemMap = 24
    MatchSpeed = 25
    Follow = 26
    Turn = 27
    Strafe = 28
    Roll = 29
    Tournament = 51
    Weapon1 = 101
    Weapon2 = 102
    Weapon3 = 103
    Weapon4 = 104
    Weapon5 = 105
    Weapon6 = 106
    Weapon7 = 107
    Weapon8 = 108
    Weapon9 = 109
    Weapon10 = 110
    Weapon11 = 111
    Weapon12 = 112
    WEAPON_MAX = 113
    Ability1 = 114
    Ability2 = 115
    Ability3 = 116
    Ability4 = 117
    Ability5 = 118
    Ability6 = 119
    Ability7 = 120
    Ability8 = 121
    Ability9 = 122
    Ability10 = 123
    ABILITY_MAX = 126
    HpGuiSlot = 130

    @property
    def wire_code(self) -> int:
        return self.value - 256 if self.value >= 128 else self.value

    @staticmethod
    def from_code(value: int):
        return _control_kind_BY_VALUE.get(value & 0xFF)
_control_kind_BY_VALUE = {member.value: member for member in ControlKind}


class ServerMessage(Enum):
    BannerBox = 1
    MessageBox = 2
    HelpBox = 3
    Mark = 4
    MissionLog = 5
    SelectTarget = 6
    HighlightControl = 7
    Progress = 8
    HighlightObject = 9
    CloseMessageBoxes = 10
    CloseMissionLog = 11
    PlayCutscene = 12
    SimplifyTutorialUi = 13
    AddSkipButton = 14
    EnableTargeting = 15
    StartLookAtTriggerClientCheck = 16
    EnableMissileTutorial = 17
    ShowOnScreenNotification = 18
    EnableGear = 19
    AskContinue = 20

    @property
    def short_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "ServerMessage | None":
        return _server_message_BY_VALUE.get(value)
_server_message_BY_VALUE = {member.value: member for member in ServerMessage}


class StoryReplies(ReplyBase):
    UZENETEK = {
        "message_box": (
            ServerMessage.MessageBox.short_value,
            [("boolean", "show_ok"), ("guid", "gui_card"), ("string", "main_text"),
             ("string", "advice"), ("string", "image_path")]),
        "mission_log": (
            ServerMessage.MissionLog.short_value,
            [("string", "objective_text_key"), ("boolean", False)]),
        "select_target": (
            ServerMessage.SelectTarget.short_value,
            [("uint32", "object_id")]),
        "highlight_object": (
            ServerMessage.HighlightObject.short_value,
            [("uint32", "object_id"), ("boolean", "is_highlighted")]),
        "play_cutscene": (
            ServerMessage.PlayCutscene.short_value,
            [("string", "s")]),
        "show_on_screen_notification": (
            ServerMessage.ShowOnScreenNotification.short_value,
            [("string", "text")]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Story)

    def banner_box(self, zaszlo_guid: int):
        bw = self.new_message()
        bw.write_msg_type(ServerMessage.BannerBox.short_value)
        bw.write_guid(zaszlo_guid)
        return bw

    def help_box(self, help_screen_id: int):
        bw = self.new_message()
        bw.write_msg_type(ServerMessage.HelpBox.short_value)
        bw.write_uint32(help_screen_id)
        return bw


log = logging.getLogger(__name__)


class _ClientMessage(Enum):
    TriggerControl = 1
    MessageBoxOk = 2
    Skip = 3
    Abandon = 4
    Continue = 5
    Decline = 6
    CutsceneFinished = 7
    LookingAtTrigger = 8

    @staticmethod
    def from_code(value: int):
        return _CM_BY_VALUE.get(value)
_CM_BY_VALUE = {member.value: member for member in _ClientMessage}


class StoryProtocol(BgoProtocol):
    def __init__(self, ctx):
        super().__init__(ProtocolID.Story, ctx)
        self._writer = StoryReplies()

    @property
    def replies(self) -> StoryReplies:
        return self._writer

    def read_message(self, msg_type: int, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        if client_message == _ClientMessage.TriggerControl:
            control_type = ControlKind.from_code(br.read_byte())
            log.warning('%sstory: trigger control %s', self.user().user_log(), control_type)
        elif client_message == _ClientMessage.MessageBoxOk:
            log.warning('%sstory: message acknowledged', self.user().user_log())
        elif client_message == _ClientMessage.Skip:
            log.info('%sstory: skipped', self.user().user_log())
        elif client_message == _ClientMessage.Abandon:
            log.warning('%sstory: abandoned', self.user().user_log())
        elif client_message == _ClientMessage.Continue:
            log.warning('%sstory: continuing', self.user().user_log())
        elif client_message == _ClientMessage.Decline:
            log.warning('%sstory: declined', self.user().user_log())
        elif client_message == _ClientMessage.CutsceneFinished:
            log.info('%sstory: cutscene over', self.user().user_log())
        elif client_message == _ClientMessage.LookingAtTrigger:
            log.warning('%sstory: eyeing a trigger', self.user().user_log())
        else:
            log.error('%sstory: reply kind nothing handles: %s message kind: %s',
                      self.user().user_log(), client_message, msg_type)
