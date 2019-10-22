# coding=utf-8
import configparser
import logging
import os
import socket
import socketserver
import struct
import sys
import threading

from py_mysql_binlogserver.packet.challenge import Challenge
from py_mysql_binlogserver.packet.query import Query
from py_mysql_binlogserver.packet.response import Response
from py_mysql_binlogserver.protocol import Flags
from py_mysql_binlogserver.protocol.err import ERR
from py_mysql_binlogserver.protocol.packet import getSize, getType, file2packet, \
    dump
from py_mysql_binlogserver.protocol.proto import scramble_native_password

SocketServer = socketserver
connection_counter = 0
logger = logging.getLogger()


class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):
    connection_id = 0
    timeout = 5
    user_id = 0
    logger = logging.getLogger('server')
    server_id = 0
    dir_name = os.path.dirname(__file__)
    upstream = None

    def setup(self):
        global connection_counter
        connection_counter += 1
        self.connection_id = connection_counter

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

    def init_upstream(self):
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host = self.server.settings["server_host"]
        port = self.server.settings.getint("server_port")
        user = self.server.settings["server_user"]
        password = self.server.settings["server_password"]

        schema = ""
        conn.connect((host, port))
        self.upstream = conn

        challenge = Challenge.loadFromPacket(self.upstream.recv(10240))

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

        self.upstream.send(response.toPacket())

        _packet = self.upstream.recv(10240)
        packetType = getType(_packet)

        if packetType == Flags.ERR:
            buf = ERR.loadFromPacket(_packet)
            logger.error("Upstream error:", buf.errorCode, buf.sqlState, buf.errorMessage)
            self.upstream.close()
            self.finish()
            exit(1)

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

        password = self.server.settings["proxy_password"]
        self.user_id = username

        # 验证密码
        native_password = scramble_native_password(password, challenge1 + challenge2)

        if self.server.settings["proxy_user"] != username or response.authResponse.encode("iso-8859-1") != native_password:
            err = ERR(9001, '28000', '[%s] Access denied.' % username)
            buff = err.toPacket()
            self.send_packet(buff)
            self.finish()
            return

        buff = file2packet("auth_result.cap")
        self.send_packet(buff)

        # 初始化后端服务器
        self.init_upstream()

        # 查询
        while True:

            packet = self.read_packet()
            if len(packet) < 4:
                continue
            packet_type = getType(packet)

            if packet_type == Flags.COM_QUIT:
                self.upstream.close()
                self.finish()

            elif packet_type == Flags.COM_QUERY:
                self.handle_query(packet)
            else:
                self.dispatch_packet(packet)

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

    def dispatch_packet(self, packet):
        self.upstream.send(packet)

        dump(packet)
        while True:
            _header = self.upstream.recv(5)
            _length = struct.unpack("<I", (_header[0:3] + b"\x00"))[0]
            _sequenceId = struct.unpack("<B", _header[3:4])[0]
            _packetType = struct.unpack("<B", _header[4:])[0]

            _payload = self.upstream.recv(_length - 1)
            dump(_header + _payload)
            self.send_packet(_header + _payload)

            if _packetType == Flags.EOF or _packetType == Flags.OK:
                return

    def handle_query(self, packet):
        qp = Query.loadFromPacket(packet)
        logger.info("query: " + qp.query)
        self.dispatch_packet(packet)


class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass


class MyProxy(object):

    def __init__(self, server_settings):
        self.host = server_settings["proxy_host"]
        self.port = server_settings.getint("proxy_port")
        self.settings = server_settings

    def run(self):
        server = ThreadedTCPServer((self.host, self.port), ThreadedTCPRequestHandler)
        server.settings = self.settings
        server_thread = threading.Thread(target=server.serve_forever)

        server_thread.start()
        logger.info("BinlogServer running in thread: %s %s %s" % (server_thread.name, self.host, self.port))


if __name__ == "__main__":

    config = configparser.ConfigParser()
    conf_file = len(sys.argv) > 1 and sys.argv[1] or os.path.dirname(__file__)+"/example.conf"
    config.read(conf_file)

    logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger()
    logger.setLevel(config["Logging"].getint("level"))

    server_settings = config["Proxy"]

    proxy = MyProxy(server_settings)
    proxy.settings = server_settings
    proxy.run()
