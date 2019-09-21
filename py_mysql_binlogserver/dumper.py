import logging
import os
import socket
import struct
from os.path import isfile

from py_mysql_binlogserver.constants.EVENT_TYPE import HEARTBEAT_EVENT, XID_EVENT, ROTATE_EVENT, event_type_name, \
    QUERY_EVENT, FORMAT_DESCRIPTION_EVENT, GTID_LOG_EVENT
from py_mysql_binlogserver.packet.challenge import Challenge
from py_mysql_binlogserver.packet.dump_gtid import DumpGtid
from py_mysql_binlogserver.packet.dump_pos import DumpPos
from py_mysql_binlogserver.packet.gtid_event import GitdEvent
from py_mysql_binlogserver.packet.query import Query
from py_mysql_binlogserver.packet.response import Response
from py_mysql_binlogserver.packet.semiack import SemiAck
from py_mysql_binlogserver.packet.slave import Slave
from py_mysql_binlogserver.protocol import Flags
from py_mysql_binlogserver.protocol.err import ERR
from py_mysql_binlogserver.protocol.packet import getSize, getType, getSequenceId, dump_my_packet, dump
from py_mysql_binlogserver.protocol.proto import scramble_native_password, byte2int

logger = logging.getLogger()


class BaseStream(object):
    """
    dump binlog into file from master
    """
    global logger

    def __init__(self, connection_settings):
        self._connection = None
        self._connection_settings = connection_settings
        self.get_conn()
        self.eventmap = event_type_name()

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
            logger.error("error:", buf.errorCode, buf.sqlState, buf.errorMessage)
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
            logger.error("error:", buf.errorCode, buf.sqlState, buf.errorMessage)
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

    def set_log_file(self, log_file):
        self.__log_file = log_file

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
            logger.info("Dump binlog from %s at %d" % (self.__log_file, self.__log_pos))
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

            # 跳过重启后的第一个 FORMAT_DESCRIPTION_EVENT
            if event_type == FORMAT_DESCRIPTION_EVENT and log_pos == 0:
                continue

            # Send SemiAck after xid event
            if self._connection_settings["semi_sync"]:
                if event_type in (XID_EVENT, QUERY_EVENT):
                    ack = SemiAck(self.__log_file, log_pos)
                    ack.sequenceId = 0
                    acp_packet = ack.toPacket()
                    self._send_packet(acp_packet)

            if packetType == Flags.ERR:
                buf = ERR.loadFromPacket(packet)
                logger.error("error:", buf.errorCode, buf.sqlState, buf.errorMessage)
                self.close()
                exit(1)

            return (timestamp, event_type, event_size, log_pos), packet[self.__binlog_header_fix_length:]

    def __iter__(self):
        return iter(self.fetchone, None)


class BinlogDumper(BaseStream):
    """
    dump binlog into file from master
    """

    _log_file = None
    _log_pos = 4
    _last_gtid = None
    _binlog_name = "mysql-bin"

    def __init__(self, connection_settings):
        super().__init__(connection_settings)
        if "binlog_dir" in connection_settings.keys() and connection_settings["binlog_dir"]:
            self._binlog_dir = connection_settings["binlog_dir"]
        else:
            self._binlog_dir = os.path.dirname(__file__) + '/binlogs/'
        if not os.path.isdir(self._binlog_dir):
            os.makedirs(self._binlog_dir)

        self._last_logfile_path = self._binlog_dir + "_last_logfile"
        self.binlog_reader = None
        self._binlog_name = connection_settings["binlog_name"]

        self._set_last_logfile()
        self._set_last_logpos()
        self._save_binlog_index()

    def _set_last_logfile(self):
        if os.path.isfile(self._last_logfile_path):
            with open(self._last_logfile_path, "r", ) as f:
                self._log_file = f.readline()
        else:
            self._log_file = self._binlog_name + ".000001"

    def _save_last_logfile(self, logfile):
        with open(self._last_logfile_path, "w", ) as f:
            f.write(logfile)

    def _save_gtid_sets(self, gtid):
        self._last_gtid = gtid

    def _reset_gtid_sets(self):
        self._last_gtid = None

    def _save_binlog_index(self):
        index_file_name = self._binlog_dir + "/" + self._log_file.split(".")[0] + ".index"
        if os.path.isfile(index_file_name):
            with open(index_file_name, "r") as fw:
                for line in fw.readlines():
                    if self._log_file in line:
                        return
        with open(index_file_name, "a") as fw:
            fw.write(self._log_file + "\n")

    def _save_gtid_index(self):
        if self._last_gtid is None:
            return
        index_file_name = self._binlog_dir + "/" + self._log_file.split(".")[0] + ".gtid.index"
        if os.path.isfile(index_file_name):
            with open(index_file_name, "r") as fw:
                for line in fw.readlines():
                    if self._log_file in line:
                        return
        with open(index_file_name, "a") as fw:
            fw.write(self._log_file + ":" + self._last_gtid + "\n")

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
            logger.debug("Parse last log pos from %s" % self._get_cur_binlog_file())
            with open(self._get_cur_binlog_file(), "rb", ) as f:
                next_position = 4
                f.read(next_position)  # file header
                while True:
                    if len(f.read(4 + 1 + 4)) < 8:
                        break
                    event_length = struct.unpack("<I", f.read(4))[0]
                    next_position = struct.unpack("<I", f.read(4))[0]
                    f.read(2)
                    f.read(event_length - 19)
                    # logger.debug("next_position: %s" % next_position)
                    self._log_pos = next_position

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
            fw = open(self._get_cur_binlog_file(), 'ab')
            fw.write(bytes.fromhex('fe62696e'))
        else:
            fw = open(self._get_cur_binlog_file(), 'ab')
        return fw

    def close(self):
        self._connection.close()
        self.binlog_reader.close()

    def run(self):

        fw = self._init_binlog_file()
        self.binlog_reader = BinLogReaderStream(self._connection_settings,
                                                log_file=self._log_file,
                                                log_pos=self._log_pos
                                                )
        for (timestamp, event_type, event_size, log_pos), packet in self.binlog_reader:
            logger.info("Received Event[%s]: [%s] %s %s %s" % (timestamp,
                                                               event_type,
                                                               self.eventmap.get(event_type), event_size, log_pos))
            dump(packet)
            fw.write(packet)
            fw.flush()
            self._log_pos = log_pos
            if event_type == GTID_LOG_EVENT:
                gitd_event = GitdEvent.loadFromPacket(packet[19:])
                self._save_gtid_sets(gitd_event.gtid)
            if event_type == ROTATE_EVENT:
                self._save_last_logfile(self._log_file)
                self._save_binlog_index()
                self._save_gtid_index()

                fw.close()
                new_log_file = self._get_rotate_log_file(packet)
                logger.info("Rotate new binlog file: %s" % new_log_file)
                fw = self._init_binlog_file(log_file=new_log_file)
                self.binlog_reader.set_log_file(new_log_file)
                self._log_file = new_log_file
                self._reset_gtid_sets()


if __name__ == "__main__":

    FORMAT = "%(asctime)s %(message)s"
    logging.basicConfig(format=FORMAT)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    connection_settings = {
        "host": "192.168.1.100",
        "port": 3306,
        "user": "repl",
        "password": "repl1234",
        "master_id": 3306101,
        "server_id": 3306202,
        "semi_sync": True,
        "server_uuid": "a721031c-d2c1-11e9-897c-080027adb7d7",
        "heartbeat_period": 30000001024,
        "binlog_name": "mysql-bin"
    }
    logger.info("Start Binlog Server from %s: %s" % (connection_settings['host'], connection_settings['port']))

    try:
        client = BinlogDumper(connection_settings)
        client.run()
    except KeyboardInterrupt:
        logger.info("Stop Binlog Server from %s: %s at %s %s" % (connection_settings['host'],
                                                                 connection_settings['port'],
                                                                 client._log_file,
                                                                 client._log_pos,
                                                                 ))
        client.close()
