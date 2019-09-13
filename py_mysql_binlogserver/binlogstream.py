# -*- coding: utf-8 -*-
import os
import socket
import struct

from mysql_piper.com.query import Query
from py_mysql_binlogserver.packet.dump_gtid import DumpGtid
from py_mysql_binlogserver.packet.dump_pos import DumpPos
from py_mysql_binlogserver.packet.semiack import SemiAck
from py_mysql_binlogserver.packet.slave import Slave
from py_mysql_binlogserver.packet.challenge import Challenge
from py_mysql_binlogserver.packet.response import Response
from py_mysql_binlogserver.protocol import Flags
from py_mysql_binlogserver.protocol.Flags import header_name
from py_mysql_binlogserver.protocol.err import ERR
from py_mysql_binlogserver.protocol.packet import read_server_packet, getSequenceId, getType, getSize
from py_mysql_binlogserver.protocol.proto import scramble_native_password, byte2int


class BinLogStreamReader(object):
    """Connect to replication stream and read event
    """
    report_slave = None

    def __init__(self, connection_settings, log_file=None, log_pos=None, auto_position=None):
        self.__connected_stream = None
        self.__connection_settings = connection_settings
        self.__log_file = log_file
        self.__log_pos = log_pos
        self.__auto_position = auto_position
        self.__has_register_slave = False
        if connection_settings["semi_sync"]:
            self.__binlog_header_fix_length = 7  # 4 + 1 + 2, packet header + command + semi sycn magic number
        else:
            self.__binlog_header_fix_length = 5  # 4 + 1, packet header + command

    def _read_packet(self):
        """
        Reads a packet from a socket
        """
        socket_in = self.__connected_stream
        # Read the size of the packet
        psize = bytearray(3)
        socket_in.recv_into(psize, 3)

        size = getSize(psize) + 1

        # Read the rest of the packet
        packet_payload = bytearray(size)
        socket_in.recv_into(packet_payload, size)

        # Combine the chunks
        psize.extend(packet_payload)
        BinLogStreamReader.dump_packet(psize)
        return psize

    def _send_packet(self, buff):
        skt = self.__connected_stream
        skt.sendall(buff)
        BinLogStreamReader.dump_packet(buff)

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

        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host = self.__connection_settings["host"]
        port = self.__connection_settings["port"]
        user = self.__connection_settings["user"]
        password = self.__connection_settings["password"]
        schema = ""
        conn.connect((host, port))
        self.__connected_stream = conn

        packet = self._read_packet()
        # print("== Greeting ==")
        # print(BinLogStreamReader.dump_packet(packet))

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

        packet = read_server_packet(conn)
        if __debug__:
            print(BinLogStreamReader.dump_packet(packet))

    def close(self):
        self.__connected_stream.close()

    def _register_slave(self):

        if self.__has_register_slave:
            return

        if not self.__connected_stream:
            self.get_socket()

        master_id = self.__connection_settings["master_id"]
        port = self.__connection_settings["port"]
        server_id = self.__connection_settings["server_id"]
        server_uuid = self.__connection_settings["server_uuid"]
        heartbeat_period = self.__connection_settings["heartbeat_period"]

        sql = Query()
        sql.sequenceId = 0
        sql.query = "SET @slave_uuid= '%s'" % server_uuid
        packet = sql.toPacket()
        self._send_packet(packet)
        self._read_packet()

        sql = Query()
        sql.sequenceId = 0
        sql.query = "SET @master_heartbeat_period= %d" % heartbeat_period
        packet = sql.toPacket()
        self._send_packet(packet)
        self._read_packet()

        slave = Slave("", '', '', port, master_id, server_id)
        slave.sequenceId = 0
        packet = slave.getPayload()
        self._send_packet(packet)
        self._read_packet()

        # 是否启用半同步
        if self.__connection_settings["semi_sync"]:
            sql = Query()
            sql.sequenceId = 0
            sql.query = "SET @rpl_semi_sync_slave= 1"
            packet = sql.toPacket()
            self._send_packet(packet)
            self._read_packet()

        if self.__auto_position:
            dump = DumpGtid(server_id, self.__auto_position)
        else:
            dump = DumpPos(server_id, self.__log_file, self.__log_pos)
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

            unpack = struct.unpack('<IcIIIH',
                                   packet[self.__binlog_header_fix_length:self.__binlog_header_fix_length + 19])
            # Header
            timestamp = unpack[0]
            event_type = byte2int(unpack[1])
            server_id = unpack[2]
            event_size = unpack[3]
            log_pos = unpack[4]
            flags = unpack[5]

            # 跳过HEARTBEAT_EVENT
            if event_type == 27:
                continue

            if event_type == 16:
                ack = SemiAck(self.__log_file, log_pos)
                ack.sequenceId = 0
                acp_packet = ack.toPacket()
                self._send_packet(acp_packet)

            if packetType == Flags.ERR:
                buf = ERR.loadFromPacket(packet)
                print("error:", buf.errorCode, buf.sqlState, buf.errorMessage)
                self.close()
                exit(1)
                break
            return (timestamp, event_type, event_size, log_pos), packet[self.__binlog_header_fix_length:]

    def __iter__(self):
        return iter(self.fetchone, None)
