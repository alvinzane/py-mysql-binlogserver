# -*- coding: utf-8 -*-
import os
import socket
import struct

from py_mysql_binlogserver.auth.dump_gtid import DumpGtid
from py_mysql_binlogserver.auth.semiack import SemiAck
from py_mysql_binlogserver.auth.slave import Slave
from py_mysql_binlogserver.com.query import Query
from pymysql.util import byte2int

from py_mysql_binlogserver.auth.challenge import Challenge
from py_mysql_binlogserver.auth.response import Response
from py_mysql_binlogserver.lib import Flags
from py_mysql_binlogserver.lib.Flags import header_name
from py_mysql_binlogserver.lib.err import ERR
from py_mysql_binlogserver.lib.packet import read_server_packet, getSequenceId, getType, getSize
from py_mysql_binlogserver.lib.proto import scramble_native_password


class BinLogStreamReader(object):
    """Connect to replication stream and read event
    """
    report_slave = None

    def __init__(self, connection_settings, server_id):
        self.__connected_stream = None
        self.__connection_settings = connection_settings
        self.server_id = server_id

        pass

    def _read_packet(self):
        skt = self.__connected_stream
        while True:
            packet = read_server_packet(skt)
            # sequenceId = getSequenceId(packet)
            packetType = getType(packet)

            if packetType == Flags.ERR:
                buf = ERR.loadFromPacket(packet)
                print("error:", buf.errorCode, buf.sqlState, buf.errorMessage)
                skt.close()
                exit(1)
                break

            if packetType == Flags.EOF or packetType == Flags.OK:
                break

            return packet

    def _send_packet(self, buff):
        skt = self.__connected_stream
        skt.sendall(buff)

    @staticmethod
    def dump_packet(packet):
        """
        Dumps a packet to the string
        """
        offset = 0
        try:
            header = getType(packet)
        except:
            header = 0
        dump = 'Length: %s, SequenceId: %s, Header: %s=%s \n' % (
            getSize(packet), getSequenceId(packet), header_name(header), header,)

        while offset < len(packet):
            dump += hex(offset)[2:].zfill(8).upper()
            dump += '  '

            for x in range(16):
                if offset + x >= len(packet):
                    dump += '   '
                else:
                    dump += hex(packet[offset + x])[2:].upper().zfill(2)
                    dump += ' '
                    if x == 7:
                        dump += ' '

            dump += '  '

            for x in range(16):
                if offset + x >= len(packet):
                    break
                c = chr(packet[offset + x])
                if (len(c) > 1
                        or packet[offset + x] < 32
                        or packet[offset + x] == 255):
                    dump += '.'
                else:
                    dump += c

                if x == 7:
                    dump += ' '

            dump += '\n'
            offset += 16

        return dump

    def get_socket(self):

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host = self.__connection_settings["host"]
        port = self.__connection_settings["port"]
        user = self.__connection_settings["user"]
        password = self.__connection_settings["password"]
        schema = ""
        s.connect((host, port))

        packet = read_server_packet(s)

        challenge = Challenge.loadFromPacket(packet)

        challenge1 = challenge.challenge1
        challenge2 = challenge.challenge2

        scramble_password = scramble_native_password(password, challenge1 + challenge2)
        response = Response()
        response.sequenceId = 1
        response.capabilityFlags = 33531397
        response.characterSet = 33
        response.maxPacketSize = 16777216
        response.clientAttributes["_client_name"] = 'pymysql'
        response.clientAttributes["_pid"] = str(os.getpid())
        response.clientAttributes["_client_version"] = '5.7'
        response.clientAttributes["program_name"] = 'mysql'
        response.pluginName = 'mysql_native_password'
        response.username = user
        response.schema = schema
        response.authResponse = scramble_password
        response.removeCapabilityFlag(Flags.CLIENT_COMPRESS)
        response.removeCapabilityFlag(Flags.CLIENT_SSL)
        response.removeCapabilityFlag(Flags.CLIENT_LOCAL_FILES)

        packet = response.toPacket()
        self._send_packet(packet)

        packet = read_server_packet(s)
        if __debug__:
            print(dump_packet(packet))

        self.__connected_stream = s

        return s

    def close(self):
        self.__connected_stream.close()

    def _register_slave(self):

        if self.__has_register_slave:
            return

        if not self.__connected_stream:
            self.get_socket()

        sql = Query()
        sql.sequenceId = 0
        sql.query = "SET @slave_uuid= '8efa8f0a-d128-11e9-952d-0800275ae9e8'"
        packet = sql.toPacket()
        self._send_packet(packet)
        self._read_packet()

        # 不用hearbeat会从第一个event开始传送
        sql = Query()
        sql.sequenceId = 0
        sql.query = "SET @master_heartbeat_period= 30000001024"
        packet = sql.toPacket()
        self._send_packet(packet)
        self._read_packet()

        slave = Slave("", '', '', 3306, 3306100, 3306202)
        slave.sequenceId = 0
        packet = slave.getPayload()
        self._send_packet(packet)
        self._read_packet()

        # 使用增强半同步后，binlog的packet格式会产生变化
        sql = Query()
        sql.sequenceId = 0
        sql.query = "SET @rpl_semi_sync_slave= 1"
        packet = sql.toPacket()
        self._send_packet(packet)
        self._read_packet()

        # dump = DumpPos(3306100, "mysql-bin.000007", 3122)
        dump = DumpGtid(3306202, "f0ea18e0-3cff-11e9-9488-0800275ae9e7:1-5")
        dump.sequenceId = 0
        packet = dump.getPayload()
        self._send_packet(packet)
        self._read_packet()

        self.__has_register_slave = True

    def __connect_to_stream(self):
        pass

    def fetchone(self):
        while True:

            self._register_slave()
            packet = self._read_packet()
            sequenceId = getSequenceId(packet)
            packetType = getType(packet)

            # OK value
            # timestamp
            # event_type
            # server_id
            # log_pos
            # flags
            unpack = struct.unpack('<cIcIIIH', packet[6:26])

            # Header
            timestamp = unpack[1]
            event_type = byte2int(unpack[2])
            server_id = unpack[3]
            event_size = unpack[4]
            # position of the next event
            log_pos = unpack[5]
            flags = unpack[6]

            if event_type == 16:
                ack = SemiAck("mysql-bin.000001", log_pos)
                ack.sequenceId = 0
                acp_packet = ack.toPacket()
                self._send_packet(acp_packet)

            if packetType == Flags.ERR:
                buf = ERR.loadFromPacket(packet)
                print("error:", buf.errorCode, buf.sqlState, buf.errorMessage)
                self.close()
                exit(1)
                break

            if packetType == Flags.EOF or packetType == Flags.OK:
                break

            return packet

    def __iter__(self):
        return iter(self.fetchone, None)
