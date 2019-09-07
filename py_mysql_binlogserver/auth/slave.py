#!/usr/bin/env python
# coding=utf-8

from py_mysql_binlogserver.lib import Flags
from py_mysql_binlogserver.lib.packet import Packet
from pymysql.constants.COMMAND import COM_BINLOG_DUMP, COM_REGISTER_SLAVE
from pymysql.util import int2byte

import collections
import struct


class Slave(Packet):
    __slots__ = ('hostname', 'username', 'password',
                 'port', 'master_id', 'server_id') + Packet.__slots__

    def __init__(self, hostname, username, password, port, master_id, server_id):
        super(Slave, self).__init__()
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.master_id = master_id
        self.server_id = server_id

    def getPayload(self):
        """
           server_id: the slave server-id
           master_id: usually 0. Appears as "master id" in SHOW SLAVE HOSTS
                      on the master. Unknown what else it impacts.
           """

        # 1              [15] COM_REGISTER_SLAVE
        # 4              server-id
        # 1              slaves hostname length
        # string[$len]   slaves hostname
        # 1              slaves user len
        # string[$len]   slaves user
        # 1              slaves password len
        # string[$len]   slaves password
        # 2              slaves mysql-port
        # 4              replication rank
        # 4              master-id

        lhostname = len(self.hostname.encode())
        lusername = len(self.username.encode())
        lpassword = len(self.password.encode())

        packet_len = (1 +  # command
                      4 +  # server-id
                      1 +  # hostname length
                      lhostname +
                      1 +  # username length
                      lusername +
                      1 +  # password length
                      lpassword +
                      2 +  # slave mysql port
                      4 +  # replication rank
                      4)  # master-id

        MAX_STRING_LEN = 257  # one byte for length + 256 chars

        payload = (struct.pack('<i', packet_len) +
                   int2byte(COM_REGISTER_SLAVE) +
                   struct.pack('<L', self.server_id) +
                   struct.pack('<%dp' % min(MAX_STRING_LEN, lhostname + 1),
                               self.hostname.encode()) +
                   struct.pack('<%dp' % min(MAX_STRING_LEN, lusername + 1),
                               self.username.encode()) +
                   struct.pack('<%dp' % min(MAX_STRING_LEN, lpassword + 1),
                               self.password.encode()) +
                   struct.pack('<H', self.port) +
                   struct.pack('<l', 0) +
                   struct.pack('<l', self.master_id))
        return payload

    @staticmethod
    def loadFromPacket(packet):
        return None
