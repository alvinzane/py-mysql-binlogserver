#!/usr/bin/env python
# coding=utf-8

import struct

from py_mysql_binlogserver.lib.packet import Packet


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

        lbinlog_filename = len(self.binlog_filename.encode())

        packet_len = (1 +  # kPacketMagicNum
                      8 +  # log_pos
                      lbinlog_filename  # binlog_filename length
                      )

        # payload = (struct.pack('<i', packet_len) +
        #            b'0xef' +
        #            struct.pack('<Q', self.binlog_pos) +
        #            struct.pack('<%dp' % (lbinlog_filename + 1), self.binlog_filename.encode())
        #            )

        payload = (struct.pack('<B', 239) +
                   struct.pack('<Q', self.binlog_pos) +
                   struct.pack('<%dp' % (lbinlog_filename + 1), self.binlog_filename.encode())
                   )
        return payload

    @staticmethod
    def loadFromPacket(packet):
        return None
