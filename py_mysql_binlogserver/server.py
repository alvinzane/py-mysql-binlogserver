import os
import socket
import struct
from os.path import isfile

from py_mysql_binlogserver.constants.EVENT_TYPE import HEARTBEAT_EVENT, XID_EVENT, ROTATE_EVENT
from py_mysql_binlogserver.packet.challenge import Challenge
from py_mysql_binlogserver.packet.dump_gtid import DumpGtid
from py_mysql_binlogserver.packet.dump_pos import DumpPos
from py_mysql_binlogserver.packet.query import Query
from py_mysql_binlogserver.packet.response import Response
from py_mysql_binlogserver.packet.semiack import SemiAck
from py_mysql_binlogserver.packet.slave import Slave
from py_mysql_binlogserver.protocol import Flags
from py_mysql_binlogserver.protocol.err import ERR
from py_mysql_binlogserver.protocol.packet import getSize, getType, getSequenceId, dump_my_packet
from py_mysql_binlogserver.protocol.proto import scramble_native_password, byte2int


class BaseStream(object):
    """
    dump binlog into file from master
    """

    def __init__(self, connection_settings):
        self._connection = None
        self._connection_settings = connection_settings
        self.get_conn()

    def _read_packet(self):
        """
        Reads a packet from a socket
        """
        socket_in = self._connection
        # Read the size of the packet
        psize = bytearray(3)
        socket_in.recv_into(psize, 3)

        size = getSize(psize) + 1

        # Read the rest of the packet
        packet_payload = bytearray(size)
        socket_in.recv_into(packet_payload, size)

        # Combine the chunks
        psize.extend(packet_payload)
        packetType = getType(psize)

        if packetType == Flags.ERR:
            buf = ERR.loadFromPacket(psize)
            print("error:", buf.errorCode, buf.sqlState, buf.errorMessage)
            self.close()
            exit(1)

        return psize

    def _send_packet(self, buff):
        skt = self._connection
        skt.sendall(buff)

    def get_conn(self):
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host = self._connection_settings["host"]
        port = self._connection_settings["port"]
        user = self._connection_settings["user"]
        password = self._connection_settings["password"]
        schema = ""
        conn.connect((host, port))
        self._connection = conn

        challenge = Challenge.loadFromPacket(self._read_packet())

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

        self._send_packet(response.toPacket())

        _packet = self._read_packet()
        packetType = getType(_packet)

        if packetType == Flags.ERR:
            buf = ERR.loadFromPacket(_packet)
            print("error:", buf.errorCode, buf.sqlState, buf.errorMessage)
            self.close()
            exit(1)

    def close(self):
        self._connection.close()


class BinLogReaderStream(BaseStream):
    """Connect to replication stream and read event
    """
    report_slave = None

    def __init__(self, connection_settings, log_file=None, log_pos=None, auto_position=None):
        super().__init__(connection_settings)
        self.__log_file = log_file
        self.__log_pos = log_pos
        self.__auto_position = auto_position
        self.__has_register_slave = False
        if self._connection_settings["semi_sync"]:
            self.__binlog_header_fix_length = 7  # 4 + 1 + 2, packet header + command + semi sycn magic number
        else:
            self._binlog_header_fix_length = 5  # 4 + 1, packet header + command

    def _register_slave(self):

        if self.__has_register_slave:
            return

        master_id = self._connection_settings["master_id"]
        port = self._connection_settings["port"]
        server_id = self._connection_settings["server_id"]
        server_uuid = self._connection_settings["server_uuid"]
        heartbeat_period = self._connection_settings["heartbeat_period"]

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
        if self._connection_settings["semi_sync"]:
            sql = Query()
            sql.sequenceId = 0
            sql.query = "SET @rpl_semi_sync_slave= 1"
            packet = sql.toPacket()
            self._send_packet(packet)
            self._read_packet()

        if self.__auto_position:
            dump = DumpGtid(server_id, self.__auto_position)
        else:
            print("Dump binlog from %s at %d" % (self.__log_file, self.__log_pos))
            dump = DumpPos(server_id, self.__log_file, self.__log_pos)
        dump.sequenceId = 0
        packet = dump.getPayload()
        self._send_packet(packet)
        self._read_packet()

        self.__has_register_slave = True

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
            if event_type == HEARTBEAT_EVENT:
                continue

            # Send SemiAck after xid event
            if self._connection_settings["semi_sync"]:
                if event_type == XID_EVENT:
                    ack = SemiAck(self.__log_file, log_pos)
                    ack.sequenceId = 0
                    acp_packet = ack.toPacket()
                    self._send_packet(acp_packet)

            if packetType == Flags.ERR:
                buf = ERR.loadFromPacket(packet)
                print("error:", buf.errorCode, buf.sqlState, buf.errorMessage)
                self.close()
                exit(1)

            return (timestamp, event_type, event_size, log_pos), packet[self.__binlog_header_fix_length:]

    def __iter__(self):
        return iter(self.fetchone, None)


class BinlogServer(BaseStream):
    """
    dump binlog into file from master
    """

    _log_file = None
    _log_pos = 4

    def __init__(self, connection_settings):
        super().__init__(connection_settings)
        if "binlog_dir" in connection_settings.keys() and connection_settings["binlog_dir"]:
            self._binlog_dir = connection_settings["binlog_dir"]
        else:
            self._binlog_dir = os.path.dirname(__file__) + '/binlogs/'
        if not os.path.isdir(self._binlog_dir):
            os.makedirs(self._binlog_dir)

        self._last_logfile_path = self._binlog_dir + "_last_logfile"

        self._set_last_logfile()
        self._set_last_logpos()

    def _set_last_logfile(self):
        if os.path.isfile(self._last_logfile_path):
            with open(self._last_logfile_path, "r", ) as f:
                self._log_file = f.readline()
        else:
            self._log_file = "mysql-bin.000001"

    def _save_last_logfile(self, logfile):

        with open(self._last_logfile_path, "w",) as f:
            f.write(logfile)

    def _set_last_logpos(self):
        """
        https://dev.mysql.com/doc/internals/en/event-structure.html
        +=====================================+
        | event  | timestamp         0 : 4    |
        | header +----------------------------+
        |        | type_code         4 : 1    |
        |        +----------------------------+
        |        | server_id         5 : 4    |
        |        +----------------------------+
        |        | event_length      9 : 4    |
        |        +----------------------------+
        |        | next_position    13 : 4    |
        |        +----------------------------+
        |        | flags            17 : 2    |
        |        +----------------------------+
        |        | extra_headers    19 : x-19 |
        +=====================================+
        | event  | fixed part        x : y    |
        | data   +----------------------------+
        |        | variable part              |
        +=====================================+
        """
        if not isfile(self._get_cur_binlog_file()):
            self._log_pos = 4
        else:
            with open(self._get_cur_binlog_file(), "rb", ) as f:
                f.read(4)       # file header
                while True:
                    if len(f.read(4 + 1 + 4)) == 0:
                        if next_position > 0:
                            self._log_pos = next_position
                        break
                    event_length = struct.unpack("<I", f.read(4))[0]
                    next_position = struct.unpack("<I", f.read(4))[0]
                    f.read(2)
                    f.read(event_length - 19)
                    # print("next_position:", next_position)

    def _get_cur_binlog_file(self):
        return self._binlog_dir + "/" + self._log_file

    def _get_rotate_log_file(self, packet):

        """
        0 4 43 0
        Length: 0, SequenceId: 0, Header: =4
        00000000  00 00 00 00 04 74 72 32  00 2B 00 00 00 00 00 00   .....tr2 .+......
        00000010  00 20 00 04 00 00 00 00  00 00 00 6D 79 73 71 6C   . ...... ...mysql
        00000020  2D 62 69 6E 2E 30 30 30  30 30 32                  -bin.000 002
        """

        value = ""
        for i in range(27, len(packet)):
            if packet[i] == 0x00:
                break
            value += chr(packet[i])
        self._log_file = value

        return value

    def _init_binlog_file(self, log_file=None):
        if log_file:
            self._log_file = log_file
        if not isfile(self._get_cur_binlog_file()):
            fw = open(self._get_cur_binlog_file(), 'wb')
            fw.write(bytes.fromhex('fe62696e'))
        else:
            fw = open(self._get_cur_binlog_file(), 'ab')
        return fw

    def run(self):

        fw = self._init_binlog_file()
        binlog_reader = BinLogReaderStream(connection_settings,
                                           log_file=self._log_file,
                                           log_pos=self._log_pos
                                           )
        for (timestamp, event_type, event_size, log_pos), packet in binlog_reader:
            print(timestamp, event_type, event_size, log_pos)
            dump_my_packet(packet)
            fw.write(packet)
            fw.flush()
            if event_type == ROTATE_EVENT:
                self._save_last_logfile(self._log_file)
                fw.close()
                new_log_file = self._get_rotate_log_file(packet)
                print(new_log_file)
                fw = self._init_binlog_file(log_file=new_log_file)
                ## TODO flush logs后，增强半同步会中断

            # if log_pos > 2200:
            #     break


if __name__ == "__main__":
    connection_settings = {
        "host": "192.168.1.100",
        "port": 3306,
        "user": "repl",
        "password": "repl1234",
        "master_id": 3306101,
        "server_id": 3306202,
        "semi_sync": True,
        "server_uuid": "a721031c-d2c1-11e9-897c-080027adb7d7",
        "heartbeat_period": 30000001024
    }

    server = BinlogServer(connection_settings)
    server.run()
