#!/usr/bin/env python
# coding=utf-8


from py_mysql_binlogserver.protocol.packet import Packet
from py_mysql_binlogserver.protocol.proto import Proto


class SemiAck(Packet):
    __slots__ = ('binlog_filename', 'binlog_pos') + Packet.__slots__

    def __init__(self, binlog_filename, binlog_pos):
        super(SemiAck, self).__init__()
        self.binlog_filename = binlog_filename
        self.binlog_pos = binlog_pos

    def getPayload(self):

        # 1 0xef kPacketMagicNum
        # 8 log_pos
        # n binlog_filename

        payload = bytearray()
        payload.extend(Proto.build_byte(0xef))
        payload.extend(Proto.build_fixed_int(8, self.binlog_pos))
        payload.extend(Proto.build_eop_str(self.binlog_filename))

        return payload

    @staticmethod
    def loadFromPacket(packet):
        return None
