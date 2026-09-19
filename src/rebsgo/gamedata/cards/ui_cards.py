# github.com/Shran21

from __future__ import annotations

from rebsgo.gamedata import json_helper as jh
from rebsgo.gamedata.cards.card_base import write_layout, Card
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.vocabulary.sorszamos_enum import SorszamosEnum


class AvatarCatalogueCard(Card):
    def __init__(self, card_guid: int, avatar_indexes):
        super().__init__(card_guid, CardView.AvatarCatalogue)
        self.avatar_indexes = avatar_indexes

    @classmethod
    def from_json(cls, obj: dict) -> "AvatarCatalogueCard":
        nyers = obj.get("avatarIndexes")
        indexes = None if nyers is None else [AvatarCatalogueCard.AvatarChoice.from_json(a) for a in nyers]
        return cls(jh.as_long(obj, "cardGUID"), indexes)

    _HUZALREND = (
        ('desc_array', 'avatar_indexes'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, AvatarCatalogueCard._HUZALREND)

    class AvatarChoice:
        def __init__(self, race: str, sex: str, items: dict, textures: dict, materials: dict):
            self.race = race
            self.sex = sex
            self.items = items
            self.textures = textures
            self.materials = materials

        @classmethod
        def from_json(cls, obj: dict) -> "AvatarCatalogueCard.AvatarChoice":
            return cls(
                jh.as_text(obj, "race"),
                jh.as_text(obj, "sex"),
                obj.get("items") or {},
                obj.get("textures") or {},
                obj.get("materials") or {},
            )

        def to_wire(self, bw) -> None:
            bw.write_string(self.sex)
            bw.write_string(self.race)

            bw.write_uint16(len(self.items))
            for key, ertek in self.items.items():
                bw.write_string(key)
                bw.write_length(len(ertek))
                for s in ertek:
                    bw.write_string(s)

            bw.write_uint16(len(self.materials))
            for key, ertek in self.materials.items():
                bw.write_string(key)
                bw.write_length(len(ertek))
                for key2, value2 in ertek.items():
                    bw.write_string(key2)
                    bw.write_length(len(value2))
                    for s in value2:
                        bw.write_string(s)

            bw.write_length(len(self.textures))
            for key, ertek in self.textures.items():
                bw.write_string(key)
                bw.write_length(len(ertek))
                for s in ertek:
                    bw.write_string(s)


class BannerCard(Card):
    def __init__(self, card_guid: int, artwork_path: str, description: str, footer_text: str, title: str):
        super().__init__(card_guid, CardView.Banner)
        self.artwork_path = artwork_path
        self.description = description
        self.footer_text = footer_text
        self.title = title

    @classmethod
    def from_json(cls, obj: dict) -> "BannerCard":
        return cls(jh.as_long(obj, "cardGUID"), jh.as_text(obj, "artworkPath"),
                   jh.as_text(obj, "description"), jh.as_text(obj, "footerText"), jh.as_text(obj, "title"))

    _HUZALREND = (
        ('string', 'artwork_path'),
        ('string', 'description'),
        ('string', 'footer_text'),
        ('string', 'title'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, BannerCard._HUZALREND)


class GuiCard(Card):
    def __init__(self, card_guid: int, key: str, level: int, gui_atlas_texture_path: str,
                 frame_index: int, gui_icon: str, gui_avatar_slot_texture_path: str,
                 gui_texture_path: str, args):
        super().__init__(card_guid, CardView.GUI)
        self.key = key
        self.level = level
        self.gui_atlas_texture_path = gui_atlas_texture_path
        self.frame_index = frame_index
        self.gui_icon = gui_icon
        self.gui_avatar_slot_texture_path = gui_avatar_slot_texture_path
        self.gui_texture_path = gui_texture_path
        self.args = [] if args is None else args

    @classmethod
    def from_json(cls, obj: dict) -> "GuiCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_text(obj, "key"),
            jh.as_short(obj, "level"),
            jh.as_text(obj, "guiAtlasTexturePath"),
            jh.as_int(obj, "frameIndex"),
            jh.as_text(obj, "guiIcon"),
            jh.as_text(obj, "guiAvatarSlotTexturePath"),
            jh.as_text(obj, "guiTexturePath"),
            jh.as_text_list(obj, "args"),
        )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_string(self.key)
        bw.write_byte(self.level & 0xFF)
        bw.write_string(self.gui_atlas_texture_path)
        bw.write_uint16(self.frame_index)
        bw.write_string(self.gui_icon)
        bw.write_string(self.gui_avatar_slot_texture_path)
        bw.write_string(self.gui_texture_path)
        bw.write_string_array([] if self.args is None else self.args)


class MailTemplateCard(Card):
    def __init__(self, card_guid: int, colonial_face_guid: int, cylon_face_guid: int,
                 expire: int, body_colonial: str, body_cylon: str, mail_limit: int, mail_type, bonus_guid: int):
        super().__init__(card_guid, CardView.MailTemplate)
        self.sender_colonial_gui_card_guid = colonial_face_guid
        self.sender_cylon_gui_card_guid = cylon_face_guid
        self.expire = expire
        self.body_colonial = body_colonial
        self.body_cylon = body_cylon
        self.mail_limit = mail_limit
        self.type = mail_type
        self.bonus_guid = bonus_guid

    @classmethod
    def from_json(cls, obj: dict) -> "MailTemplateCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_long(obj, "senderColonialGuiCardGuid"),
            jh.as_long(obj, "senderCylonGuiCardGuid"),
            jh.as_int(obj, "expire"),
            jh.as_text(obj, "bodyColonial"),
            jh.as_text(obj, "bodyCylon"),
            jh.as_int(obj, "mailLimit"),
            jh.as_enum_by_name(obj, "type", MailTemplateCard.MailKind),
            jh.as_long(obj, "bonusGuid"),
        )

    _HUZALREND = (
        ('guid', 'sender_colonial_gui_card_guid'),
        ('guid', 'sender_cylon_gui_card_guid'),
        ('uint16', 'expire'),
        ('string', 'body_colonial'),
        ('string', 'body_cylon'),
        ('uint16', 'mail_limit'),
        ('byte', 'type', 'value'),
        ('guid', 'bonus_guid'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, MailTemplateCard._HUZALREND)

    class MailKind(SorszamosEnum):
        Mail = 0
        TgbPopupMail = 1


class StickerListCard(Card):
    def __init__(self, card_guid: int, view: CardView, stickers_cylon, stickers_colonial):
        super().__init__(card_guid, view)
        self.stickers_cylon = stickers_cylon
        self.stickers_colonial = stickers_colonial

    @classmethod
    def from_json(cls, obj: dict) -> "StickerListCard":
        raw_cylon = obj.get("StickersCylon")
        cylon = None if raw_cylon is None else [StickerListCard.Sticker.from_json(s) for s in raw_cylon]
        raw_colonial = obj.get("StickersColonial")
        colonial = None if raw_colonial is None else [StickerListCard.Sticker.from_json(s) for s in raw_colonial]
        view = CardView.from_code(jh.as_int(obj, "cardView"))
        return cls(jh.as_long(obj, "cardGUID"), view, cylon, colonial)

    _HUZALREND = (
        ('desc_array', 'stickers_colonial'),
        ('desc_array', 'stickers_cylon'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, StickerListCard._HUZALREND)

    class Sticker:
        def __init__(self, id: int, texture: str):
            self.id = id
            self.texture = texture

        @classmethod
        def from_json(cls, obj: dict) -> "StickerListCard.Sticker":
            return cls(jh.as_int(obj, "ID"), jh.as_text(obj, "Texture"))

        _HUZALREND = (
            ('uint16', 'id'),
            ('string', 'texture'),
        )

        def to_wire(self, bw) -> None:
            write_layout(self, bw, StickerListCard.Sticker._HUZALREND)


class TitleCard(Card):
    def __init__(self, card_guid: int, level: int, static_buff, multiply_buff):
        super().__init__(card_guid, CardView.Title)
        self.level = level
        self.static_buff = static_buff
        self.multiply_buff = multiply_buff

    @classmethod
    def from_json(cls, obj: dict) -> "TitleCard":
        return cls(jh.as_long(obj, "cardGUID"), jh.as_byte(obj, "Level"),
                   jh.as_object_stats(obj, "StaticBuff"), jh.as_object_stats(obj, "MultiplyBuff"))

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_byte(self.level)
        bw.write_string("")
        bw.write_desc(self.static_buff)
        bw.write_desc(self.multiply_buff)
