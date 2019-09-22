# coding=utf-8
import logging
import os
import socketserver
import struct
import threading
from _md5 import md5
from io import BytesIO

from py_mysql_binlogserver.constants.COMMAND import com_type_name
from py_mysql_binlogserver.constants.EVENT_TYPE import event_type_name, GTID_LOG_EVENT
from py_mysql_binlogserver.packet.binlog_event import BinlogEvent
from py_mysql_binlogserver.packet.challenge import Challenge
from py_mysql_binlogserver.packet.gtid_event import GitdEvent
from py_mysql_binlogserver.packet.query import Query
from py_mysql_binlogserver.packet.response import Response
from py_mysql_binlogserver.protocol import Flags
from py_mysql_binlogserver.protocol.err import ERR
from py_mysql_binlogserver.protocol.gtid import GtidSet
from py_mysql_binlogserver.protocol.ok import OK
from py_mysql_binlogserver.protocol.packet import getSize, getType, dump_my_packet, file2packet
from py_mysql_binlogserver.protocol.proto import scramble_native_password

SocketServer = socketserver
connection_counter = 0
logger = logging.getLogger()


class BinlogGTIDReader(object):

    _start_log_file = None
    _start_log_pos = 4
    _binlog_dir = os.path.dirname(__file__) + '/binlogs/'

    def __init__(self, connection_settings):
        if "binlog_dir" in connection_settings.keys() and connection_settings["binlog_dir"]:
            self._binlog_dir = connection_settings["binlog_dir"]
        if not os.path.isdir(self._binlog_dir):
            # TODO rise a error
            pass
        self._binlog_name = connection_settings["binlog_name"]
        self.eventmap = event_type_name()

    def find_log_pos_by_gtid(self, gtid_set):
        gtid_index_file = "%s/%s.gtid.index" % (self._binlog_dir, self._binlog_name)
        gtid, gno = gtid_set.split(":")
        if "-" in gno:
            gno = gno.split("-")[1]
        _log_file_name = None
        with open(gtid_index_file, "r") as fr:
            for line in fr.readlines():
                if gtid in line:
                    _file_name, _gtid, _gno = line.split(":")
                    if int(_gno) >= int(gno):
                        _log_file_name = _file_name
                        break
        if _log_file_name is None:
            logger.info("%s has not found in %s" % (gtid_set, gtid_index_file))
            return False

        logger.info("%s has found in %s" % (gtid_set, _log_file_name))
        with open(self._binlog_dir + "/" + _log_file_name, mode="rb") as fr:
            _file_header = fr.read(4)
            if _file_header != bytes.fromhex("fe62696e"):
                logger.error("It is not a binlog file.")
                exit()

            '''
            4              timestamp
            1              event type
            4              server-id
            4              event-size
            4              log pos
            2              flags
            '''
            while True:
                event_header = fr.read(19)
                if len(event_header) == 0:
                    break
                timestamp, event_type, server_id, event_size, log_pos, flags = struct.unpack('<IBIIIH', event_header)
                logger.debug("Binlog Event[%s]: [%s] %s %s" % (timestamp,
                                                               event_type,
                                                               self.eventmap.get(event_type), log_pos))
                event_body = fr.read(event_size - 19)
                if event_type == GTID_LOG_EVENT:
                    gtid_event = GitdEvent.loadFromPacket(event_body)
                    logger.debug("%s %s" % (gtid_event.gtid, log_pos))
                    if gtid_set == gtid_event.gtid:
                        self._start_log_file = _log_file_name
                        self._start_log_pos = log_pos
                        return _log_file_name, log_pos

    def fetch_binlog_events(self):
        if self._start_log_file is None:
            return None
        with open("%s/%s.index" % (self._binlog_dir, self._binlog_name), "r") as fr:
            _start_send = False
            for line in fr.readlines():
                if self._start_log_file in line:
                    _start_send = True
                if _start_send is False:
                    continue
                _log_file = line[:-1]
                print(_log_file)
                with open("%s/%s" % (self._binlog_dir, _log_file), "rb") as _fr:
                    if _log_file == self._start_log_file:
                        _fr.read(self._start_log_pos)
                    else:
                        _fr.read(4)
                    while True:
                        event_header = _fr.read(19)
                        if len(event_header) == 0:
                            break
                        event_size = struct.unpack('<I', event_header[9:13])[0]
                        event_body = _fr.read(event_size - 19)
                        yield event_header + event_body


class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):
    connection_id = 0
    timeout = 5
    user_id = 0
    logger = logging.getLogger('server')
    server_id = 0
    dir_name = os.path.dirname(__file__)

    def setup(self):
        global connection_counter
        connection_counter += 1
        self.connection_id = connection_counter
        pass

    def send_packet(self, packet):
        self.request.sendall(packet)

    def read_packet(self):
        """
        Reads a packet from a socket
        """
        # Read the size of the packet
        socket_in = self.request
        psize = bytearray(3)
        socket_in.recv_into(psize, 3)

        size = getSize(psize) + 1

        # Read the rest of the packet
        packet_payload = bytearray(size)
        socket_in.recv_into(packet_payload, size)

        # Combine the chunks
        psize.extend(packet_payload)

        return psize

    def handle(self):

        # 认证
        challenge1 = '12345678'
        challenge2 = '123456789012'
        challenge = self.create_challenge(challenge1, challenge2)
        self.send_packet(challenge.toPacket())

        packet = self.read_packet()
        response = Response()
        response = response.loadFromPacket(packet)

        username = response.username
        self.logger.info("login user:" + username)

        password = 'repl1234'
        self.user_id = 'repl'

        # 验证密码
        native_password = scramble_native_password(password, challenge1 + challenge2)

        if response.authResponse.encode("iso-8859-1") != native_password:
            err = ERR(9001, '28000', '[%s] Access denied.' % username)
            buff = err.toPacket()
            self.send_packet(buff)
            self.finish()
            return

        buff = file2packet("auth_result.cap")
        self.send_packet(buff)
        # self.send_packet(bytes.fromhex("07 00 00 02 00 00 00 02 00 00 00"))

        # 查询
        while True:

            packet = self.read_packet()
            if len(packet) < 4:
                continue
            packet_type = getType(packet)

            # dump_my_packet(packet)
            print('packet_type', packet_type, com_type_name(packet_type))

            if packet_type == Flags.COM_QUIT:
                self.finish()
            elif packet_type == Flags.COM_REGISTER_SLAVE:
                logger.info("Received COM_REGISTER_SLAVE")
                self.send_packet(OK().toPacket())

            elif packet_type == Flags.COM_BINLOG_DUMP_GTID:
                logger.info("Received COM_BINLOG_DUMP_GTID")

                payload = packet[27:]
                gtid_set = GtidSet.decode(BytesIO(payload))

                self.dump_binlog_gtid(gtid_set)

            elif packet_type == Flags.COM_QUERY:
                self.handle_query(packet)

    def dump_binlog_gtid(self, gtid_set):
        logger.info("Begin dump gtid binlog from %s " % (gtid_set,))
        reader = BinlogGTIDReader({"binlog_name": "mysql-bin"})

        for gtid in str(gtid_set).split(","):
            reader.find_log_pos_by_gtid(gtid)
            for event in reader.fetch_binlog_events():
                self.send_packet(BinlogEvent(event).toPacket())

    def create_challenge(self, challenge1, challenge2):
        # 认证
        challenge = Challenge()
        challenge.protocolVersion = 10
        challenge.serverVersion = '5.7.20-log'
        challenge.connectionId = self.connection_id
        challenge.challenge1 = challenge1
        challenge.challenge2 = challenge2
        challenge.capabilityFlags = 4160717151
        challenge.characterSet = 224
        challenge.statusFlags = 2
        challenge.authPluginDataLength = 21
        challenge.authPluginName = 'mysql_native_password'
        challenge.sequenceId = 0
        return challenge

    def dispatch_packet(self, qp):
        """
        从缓存从读取回包，没有就响应错误
        """
        dir_name = self.dir_name + "/cap/" + md5(qp.query.encode()).hexdigest()

        if not os.path.isdir(dir_name):
            dir_name = self.dir_name + "/cap/" + '0000_base'

        # 缓存包内含有一个sql txt文件
        for idx in range(0, len(os.listdir(dir_name)) - 1):
            cap_file = dir_name + "/" + str(idx) + ".cap"
            with open(cap_file, "rb") as rf:
                buff = rf.read(10240)
            self.send_packet(buff)

    def handle_query(self, packet):
        qp = Query.loadFromPacket(packet)
        logger.info("query: " + qp.query)
        self.dispatch_packet(qp)


class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass


class BinlogServer(object):

    def __init__(self, host="0.0.0.0", port=3306):
        self.host = host
        self.port = port

    def run(self):

        server = ThreadedTCPServer((self.host, self.port), ThreadedTCPRequestHandler)
        ip, port = server.server_address

        logging.basicConfig(format="%(asctime)s %(message)s")
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        server_thread = threading.Thread(target=server.serve_forever)

        server_thread.start()
        logger.info("BinlogServer running in thread: %s %s %s" % (server_thread.name, self.host, self.port))


def test_binlog_parse():
    FORMAT = "%(asctime)s %(message)s"
    logging.basicConfig(format=FORMAT)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    reader = BinlogGTIDReader({"binlog_name": "mysql-bin"})
    reader.find_log_pos_by_gtid("f0ea18e0-3cff-11e9-9488-0800275ae9e7:30")
    for binlog_event in reader.fetch_binlog_events():
        timestamp, event_type, server_id, event_size, log_pos, flags = struct.unpack('<IBIIIH', binlog_event[:19])
        logger.debug("Binlog Event[%s]: [%s] %s %s" % (timestamp,
                                                       event_type,
                                                       event_type, log_pos))


if __name__ == "__main__":
    '''
    CHANGE MASTER TO
      MASTER_HOST='192.168.1.1',
      MASTER_USER='repl',
      MASTER_PASSWORD='repl1234',
      MASTER_PORT=6066,
      MASTER_AUTO_POSITION=1;
    '''
    server = BinlogServer(port=3308)
    server.run()

    # test_binlog_parse()
