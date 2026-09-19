# github.com/Shran21

from __future__ import annotations

from rebsgo.gamedata.reading import ObjectStat
from rebsgo.helpers.floats import fdiv
from rebsgo.protocol.notification import MinerAlarm, OutpostAlarm
from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.vocabulary.world import ObjectKind


class NoticeKey:
    def __init__(self, space_object, outpost_alarm=None, mining_attack_kind=None):
        self._space_object = space_object
        self._outpost_attacked_type = outpost_alarm
        self._mining_ship_attacked_type = mining_attack_kind

    @property
    def space_object(self):
        return self._space_object

    @property
    def outpost_attacked_type(self):
        return self._outpost_attacked_type

    def mining_attack_kind(self):
        return self._mining_ship_attacked_type

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, NoticeKey):
            return False
        return (self._space_object == other._space_object
                and self._outpost_attacked_type == other._outpost_attacked_type
                and self._mining_ship_attacked_type == other._mining_ship_attacked_type)

    def __hash__(self) -> int:
        return hash((self._space_object, self._outpost_attacked_type, self._mining_ship_attacked_type))

    def __repr__(self) -> str:
        milyen = self._outpost_attacked_type or self._mining_ship_attacked_type
        return f'<alarm on {self._space_object}: {milyen}>' 


class Announcer:
    def __init__(self, pilot_roster):
        self._pilot_roster = pilot_roster
        self._notification_protocol_write_only = replies_for(ProtocolID.Notification)

    def cry_attack(self, ertesites_kulcs, star_guid: int) -> None:
        space_object = ertesites_kulcs.space_object
        entity_type = space_object.space_entity_type
        if entity_type == ObjectKind.Outpost:
            self._notify_outpost_attack_type(space_object, star_guid, ertesites_kulcs.outpost_attacked_type)
        elif entity_type == ObjectKind.MiningShip:
            self.cry_mining_attack(space_object, star_guid, ertesites_kulcs.mining_attack_kind())

    def notification_key(self, space_object) -> NoticeKey:
        entity_type = space_object.space_entity_type
        if entity_type == ObjectKind.Outpost:
            outpost_attacked_type = self._out_post_attack_type(space_object)
            return NoticeKey(space_object, outpost_alarm=outpost_attacked_type)
        if entity_type == ObjectKind.MiningShip:
            mining_attack_kind = self.mining_attack_kind(space_object)
            return NoticeKey(space_object, mining_attack_kind=mining_attack_kind)
        raise ValueError(f'no implementation covers this object kind {entity_type}')

    def _out_post_attack_type(self, outpost):
        current_hp = outpost.space_subscribe_info().hp
        max_hp = outpost.space_subscribe_info().stat(ObjectStat.MaxHullPoints)

        is_above50_percent = fdiv(current_hp, max_hp) > 0.5
        is_dead = outpost.is_removed()

        if not is_above50_percent and not is_dead:
            return OutpostAlarm.OutpostHeavyDamage
        if is_dead:
            return OutpostAlarm.OutpostDied
        return OutpostAlarm.OutpostUnderAttack

    def _notify_outpost_attack_type(self, outpost, star_guid: int, tamadas_fajta) -> None:
        outpost_faction = outpost.faction
        bw_outpost_attacked = self._notification_protocol_write_only.outpost_attacked(
            outpost_faction, star_guid, tamadas_fajta)
        self.announce_to_faction(outpost_faction, bw_outpost_attacked)

    def mining_attack_kind(self, mining_ship):
        current_hp = mining_ship.space_subscribe_info().hp
        max_hp = mining_ship.space_subscribe_info().stat(ObjectStat.MaxHullPoints)

        is_above50_percent = fdiv(current_hp, max_hp) > 0.5
        is_dead = mining_ship.is_removed()

        if not is_above50_percent and not is_dead:
            return MinerAlarm.ShipDamaged
        if is_dead:
            return MinerAlarm.ShipDrivenOff
        return MinerAlarm.ShipUnderAttack

    def cry_mining_attack(self, mining_ship, star_guid: int, mining_attack_kind) -> None:
        owner = mining_ship.owner
        party = owner.pilot_of().party()
        users_of_interest = []
        if party is not None:
            users_of_interest.extend(party.members())
        else:
            users_of_interest.append(owner)

        for user in users_of_interest:
            bw = self._notification_protocol_write_only.mining_ship_under_attack(
                star_guid, mining_attack_kind, owner == user)
            user.send(bw)

    def announce_to_faction(self, faction, bw) -> None:
        users_to_send_to = self._pilot_roster.user_list(
            lambda user: user.is_connected() and user.pilot_of().faction == faction)
        self.tell_sector(users_to_send_to, bw)

    def tell_sector(self, pilotak, bw) -> None:
        for user in pilotak:
            user.send(bw)
