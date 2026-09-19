# github.com/Shran21

from __future__ import annotations

from rebsgo.wire.bytes.wire_out import WireOut
from rebsgo.protocol.protocol_id import ProtocolID


class ReplyBase:
    UZENETEK: dict[str, tuple[object, list[tuple[str, object]]]] = {}

    def __init__(self, protocol_id: ProtocolID):
        self.protocol_id = protocol_id

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        for nev, (uzenet, mezok) in cls.__dict__.get("UZENETEK", {}).items():
            if nev in cls.__dict__:
                raise TypeError(f"{cls.__name__}.{nev} exists both in the table and as a handwritten method")
            setattr(cls, nev, _keszits(nev, uzenet, mezok))

    def new_message(self) -> WireOut:
        bw = WireOut()
        bw.write_byte(self.protocol_id.value)
        return bw

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self.protocol_id == other.protocol_id

    def __hash__(self) -> int:
        return hash((ProtocolID, self.protocol_id))

    def protocol_id_of(self) -> ProtocolID:
        return self.protocol_id


def _keszits(nev: str, uzenet, mezok: list[tuple[str, object]]):
    def _bont(forras):
        if not isinstance(forras, str):
            return None, ()
        parameter, _, lanc = forras.partition(".")
        return parameter, tuple(lanc.split(".")) if lanc else ()

    parameterek = []
    for _, forras in mezok:
        parameter, _lanc = _bont(forras)
        if parameter is not None and parameter not in parameterek:
            parameterek.append(parameter)
    lepesek = [(f"write_{tipus}", *_bont(forras), forras) for tipus, forras in mezok]

    def ir(self, *ertekek, **nevesitett):
        if len(ertekek) > len(parameterek):
            raise TypeError(f"{nev}() takes at most {len(parameterek)} values")
        adott = dict(zip(parameterek, ertekek))
        for kulcs, ertek in nevesitett.items():
            if kulcs not in parameterek:
                raise TypeError(f"{nev}() takes no parameter named {kulcs}")
            if kulcs in adott:
                raise TypeError(f"{nev}() received twice: {kulcs}")
            adott[kulcs] = ertek
        hianyzik = [p for p in parameterek if p not in adott]
        if hianyzik:
            raise TypeError(f"{nev}() still needs: {', '.join(hianyzik)}")

        bw = self.new_message()
        bw.write_msg_type(uzenet)
        for iro, parameter, lanc, forras in lepesek:
            if parameter is None:
                getattr(bw, iro)(forras)
                continue
            ertek = adott[parameter]
            for tag in lanc:
                ertek = getattr(ertek, tag)
            getattr(bw, iro)(ertek)
        return bw

    ir.__name__ = nev
    ir.__qualname__ = nev
    ir.__doc__ = f"Serialize message {uzenet}; fields: {', '.join(parameterek) or 'none'}."
    return ir
