# coding=utf-8


from py_mysql_binlogserver.lib.packet import Packet
from py_mysql_binlogserver.lib.proto import Proto


class Prepare_Ok(Packet):

    def getPayload(self):
        payload = bytearray()

        return payload

    @staticmethod
    def loadFromPacket(packet):
        obj = Prepare_Ok()
        proto = Proto(packet, 3)

        obj.sequenceId = proto.get_fixed_int(1)

        return obj
