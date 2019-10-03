# coding=utf-8
from py_mysql_binlogserver.protocol import Flags
from py_mysql_binlogserver.protocol.packet import Packet
from py_mysql_binlogserver.protocol.proto import Proto


class BinlogEvent(Packet):

    def __init__(self, event):
        super(BinlogEvent, self).__init__()
        self.event = event
        self.sequenceId = 0

    def getPayload(self):
        payload = b''

        # payload += bytes.fromhex("00ef00")
        payload += bytes.fromhex("00")
        payload += self.event

        return payload

    @staticmethod
    def loadFromPacket(packet):
        pass
