#!/usr/bin/env python
# coding=utf-8

from packet import Packet
from proto import Proto
import Flags as Flags


class EOF(Packet):
    __slots__ = ('statusFlags', 'warnings') + Packet.__slots__

    def __init__(self):
        self.statusFlags = 0
        self.warnings = 0

    def setStatusFlag(self, flag):
        self.statusFlags |= flag

    def removeStatusFlag(self, flag):
        self.statusFlags &= ~flag

    def toggleStatusFlag(self, flag):
        self.statusFlags ^= flag

    def hasStatusFlag(self, flag):
        return ((self.statusFlags & flag) == flag)

    def getPayload(self):
        payload = bytearray()

        payload.extend(Proto.build_byte(Flags.EOF))
        payload.extend(Proto.build_fixed_int(2, self.warnings))
        payload.extend(Proto.build_fixed_int(2, self.statusFlags))

        return payload

    @staticmethod
    def loadFromPacket(packet):
        obj = EOF()
        proto = Proto(packet, 3)

        obj.sequenceId = proto.get_fixed_int(1)
        proto.get_filler(1)
        obj.statusFlags = proto.get_fixed_int(2)
        obj.warnings = proto.get_fixed_int(2)

        return obj

if __name__ == "__main__":
    import doctest
    doctest.testmod()
