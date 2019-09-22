# coding=utf-8
from py_mysql_binlogserver.protocol import Flags
from py_mysql_binlogserver.protocol.packet import Packet
from py_mysql_binlogserver.protocol.proto import Proto


class BinlogEvent(Packet):

    def __init__(self, event):
        super(BinlogEvent, self).__init__()
        self.event = event

    def getPayload(self):
        payload = bytearray()

        payload.extend(bytes.fromhex("00ef00"))
        payload.extend(self.event)

        return payload

    @staticmethod
    def loadFromPacket(packet):
        pass
