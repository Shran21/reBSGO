# github.com/Shran21

from __future__ import annotations

import logging
import threading

from rebsgo.protocol.login import LoginProtocolClientMessage
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.journal import hivasi_lanc

log = logging.getLogger(__name__)


class IncomingLoop:
    BELEPES_UTANI_TURELEM_MS = 3 * 60 * 1000

    LEALLITO_HIBAK = (
        (OSError, 'the reader thread could not read: '),
        (RuntimeError, 'the reader thread wound up in a bad state: '),
    )

    def __init__(self, connection, protocol_desk):
        self._connection = connection
        self._protocol_desk = protocol_desk
        self._is_hello_send = True
        self._login_writer = replies_for(ProtocolID.Login)
        self._is_init_received = False

    def run(self) -> None:
        threading.current_thread().name = f'bejovo {self._connection.remote_socket_address()}'
        try:
            self._olvaso_kor()
        except Exception as hiba:
            self._szal_vege(hiba)

    __call__ = run

    def _olvaso_kor(self) -> None:
        while not self._connection.is_closed():
            if self._is_hello_send:
                self._connection.send(self._login_writer.hello())
                self._is_hello_send = False
            if not self._egy_uzenet():
                return

    def _egy_uzenet(self) -> bool:
        uzenet = self._connection.next_message()
        protokoll_kod = uzenet.read()
        protokoll = ProtocolID.from_code(protokoll_kod)
        if protokoll is None:
            self._connection.close_connection(f"no protocol answers to code {protokoll_kod}")
            return False

        fajta = uzenet.read_uint16()
        if not self._is_init_received and not self._elso_uzenet_rendben(protokoll, fajta):
            return False
        return self._tovabbadas(protokoll, fajta, uzenet)

    def _elso_uzenet_rendben(self, protokoll: ProtocolID, fajta: int) -> bool:
        if protokoll != ProtocolID.Login or fajta != LoginProtocolClientMessage.Init.value:
            self._connection.close_connection(
                "opening message was not a login ({}/{}) from {}".format(
                    protokoll, fajta, self._connection.remote_socket_address()))
            return False
        self._connection.link_timeout(self.BELEPES_UTANI_TURELEM_MS)
        self._is_init_received = True
        return True

    def _tovabbadas(self, protokoll: ProtocolID, fajta: int, uzenet) -> bool:
        try:
            self._protocol_desk.protocol_of(protokoll).read_message(fajta, uzenet)
        except KeyError as nincs_ilyen:
            log.info(str(nincs_ilyen))
            return False
        except RuntimeError as allapot_hiba:
            self._connection.close_connection(f"the message handler stalled: {allapot_hiba}")
        except OSError as io_hiba:
            self._connection.close_connection('read fell over mid-message: '
                                              + hivasi_lanc(io_hiba))
            return False
        return True

    def _szal_vege(self, hiba: BaseException) -> None:
        for fajta, ok in self.LEALLITO_HIBAK:
            if isinstance(hiba, fajta):
                self._connection.close_connection(ok + str(hiba))
                return
        lanc = hivasi_lanc(hiba)
        log.error('reader thread hit something unplanned ({}): {}\n{}'.format(
            self._connection.remote_socket_address(), hiba, lanc))
        self._connection.close_connection('inbound handling hit something unplanned ' + lanc)
