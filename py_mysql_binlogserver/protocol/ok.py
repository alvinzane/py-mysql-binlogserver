#!/usr/bin/env python
# coding=utf-8

from py_mysql_binlogserver.protocol.packet import Packet, hex_ba


class OK(Packet):
    __slots__ = ('errorCode', 'sqlState', 'errorMessage') + Packet.__slots__

    def __init__(self):
        super().__init__()
        self.sequenceId = 1

    def getPayload(self):
        payload = bytearray()

        payload.extend(hex_ba('07 00 00 02 00 00 00 02  00 00 00'))

        return payload


if __name__ == "__main__":
    import doctest
    doctest.testmod()
