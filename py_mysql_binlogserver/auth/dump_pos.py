#!/usr/bin/env python
# coding=utf-8

import struct

from pymysql.constants.COMMAND import COM_BINLOG_DUMP_GTID, COM_BINLOG_DUMP
from pymysql.util import int2byte

from py_mysql_binlogserver.lib.gtid import GtidSet
from py_mysql_binlogserver.lib.packet import Packet


class DumpPos(Packet):
    __slots__ = ('server_id', 'log_file', 'log_pos') + Packet.__slots__

    def __init__(self, server_id, log_file ,log_pos):
        super(DumpPos, self).__init__()
        self.server_id = server_id
        self.log_file = log_file
        self.log_pos = log_pos

    def getPayload(self):
        # # only when log_file and log_pos both provided, the position info is
        # # valid, if not, get the current position from master
        # if self.log_file is None or self.log_pos is None:
        #     cur = self._stream_connection.cursor()
        #     cur.execute("SHOW MASTER STATUS")
        #     master_status = cur.fetchone()
        #     if master_status is None:
        #         raise BinLogNotEnabled()
        #     self.log_file, self.log_pos = master_status[:2]
        #     cur.close()

        prelude = struct.pack('<i', len(self.log_file) + 11) \
                  + int2byte(COM_BINLOG_DUMP)

        prelude += struct.pack('<I', self.log_pos)

        flags = 0
        # if not self.__blocking:
        #     flags |= 0x01  # BINLOG_DUMP_NON_BLOCK
        prelude += struct.pack('<H', flags)

        prelude += struct.pack('<I', self.server_id)
        prelude += self.log_file.encode()

        return prelude

    @staticmethod
    def loadFromPacket(packet):
        return None
