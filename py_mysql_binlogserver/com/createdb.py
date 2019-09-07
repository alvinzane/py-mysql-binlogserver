# coding=utf-8

from py_mysql_binlogserver.lib import Flags
from py_mysql_binlogserver.lib.packet import Packet
from py_mysql_binlogserver.lib.proto import Proto

class Createdb(Packet):
    __slots__ = ('schema',) + Packet.__slots__

    def __init__(self):
        super(Createdb, self).__init__()
        self.schema = ''

    def getPayload(self):
        payload = bytearray()

        payload.extend(Proto.build_byte(Flags.COM_CREATE_DB))
        payload.extend(Proto.build_eop_str(self.schema))

        return payload

    @staticmethod
    def loadFromPacket(packet):
        obj = Createdb()
        proto = Proto(packet, 3)

        obj.sequenceId = proto.get_fixed_int(1)
        proto.get_filler(1)
        obj.schema = proto.get_eop_str()

        return obj
