# coding=utf-8
import os
import socket
import struct

from py_mysql_binlogserver.packet.challenge import Challenge
from py_mysql_binlogserver.packet.dump_gtid import DumpGtid
from py_mysql_binlogserver.packet.query import Query
from py_mysql_binlogserver.packet.response import Response
from py_mysql_binlogserver.packet.semiack import SemiAck
from py_mysql_binlogserver.packet.slave import Slave
from py_mysql_binlogserver.protocol import Flags
from py_mysql_binlogserver.protocol.err import ERR
from py_mysql_binlogserver.protocol.packet import dump_my_packet, send_client_socket, getSequenceId, getType
from py_mysql_binlogserver.protocol.packet import read_server_packet
from py_mysql_binlogserver.protocol.proto import scramble_native_password
from pymysql.util import byte2int


def get_socket(host='127.0.0.1', port=3306, user="", password="", schema=""):

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))

    packet = read_server_packet(s)
    print("received 1:")
    dump_my_packet(packet)

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
    print("login 1:")
    dump_my_packet(packet)

    send_client_socket(s, packet)

    packet = read_server_packet(s)
    print("received 2:")
    dump_my_packet(packet)

    return s


def read_packet(skt):
    while True:
        packet = read_server_packet(skt)
        sequenceId = getSequenceId(packet)
        print("read packet [%s]:" % (sequenceId,))
        dump_my_packet(packet)
        packetType = getType(packet)

        if packetType == Flags.ERR:
            buf = ERR.loadFromPacket(packet)
            print("error:", buf.errorCode, buf.sqlState, buf.errorMessage)
            skt.close()
            exit(1)
            break

        if packetType == Flags.EOF or packetType == Flags.OK:
            break


def read_binlog(skt):
    while True:
        packet = read_server_packet(skt)
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

        print('timestamp', 'event_type', 'server_id', 'event_size', 'log_pos')
        print(timestamp, event_type, server_id, event_size, log_pos)
        dump_my_packet(packet)

        if event_type == 16:
            ack = SemiAck("mysql-bin.000001", log_pos)
            ack.sequenceId = 0
            packet = ack.toPacket()
            send_socket(skt, packet)

        if packetType == Flags.ERR:
            buf = ERR.loadFromPacket(packet)
            print("error:", buf.errorCode, buf.sqlState, buf.errorMessage)
            skt.close()
            exit(1)
            break

        if packetType == Flags.EOF or packetType == Flags.OK:
            break


def send_socket(skt, buff):
    print("send packet:")
    dump_my_packet(buff)
    skt.sendall(buff)


if __name__ == "__main__":
    s = get_socket(host="192.168.1.100", user="admin", password="aaaaaa", schema="mysql")

    sql = Query()
    sql.sequenceId = 0
    sql.query = "SET @slave_uuid= '8efa8f0a-d128-11e9-952d-0800275ae9e8'"
    packet = sql.toPacket()
    print("query 0:")
    dump_my_packet(packet)
    send_socket(s, packet)
    read_packet(s)

    # 不用hearbeat会从第一个event开始传送
    sql = Query()
    sql.sequenceId = 0
    sql.query = "SET @master_heartbeat_period= 30000001024"
    packet = sql.toPacket()
    print("query 1:")
    dump_my_packet(packet)
    send_socket(s, packet)
    read_packet(s)

    slave = Slave("", '', '', 3306, 3306100, 3306202)
    slave.sequenceId = 0
    packet = slave.getPayload()
    send_socket(s, packet)
    read_packet(s)

    # 使用增强半同步后，binlog的packet格式会产生变化
    sql = Query()
    sql.sequenceId = 0
    sql.query = "SET @rpl_semi_sync_slave= 1"
    packet = sql.toPacket()
    print("query 1:")
    dump_my_packet(packet)
    send_socket(s, packet)
    read_packet(s)

    # dump = DumpPos(3306100, "mysql-bin.000007", 3122)
    dump = DumpGtid(3306202, "f0ea18e0-3cff-11e9-9488-0800275ae9e7:1-5")
    dump.sequenceId = 0
    packet = dump.getPayload()
    send_socket(s, packet)
    read_packet(s)

    '''
    read packet [1]:
    Length: 38, SequenceId: 1, Header: OK=0 
    00000000  26 00 00 01 00 EF 00 00  00 00 00 1B 75 72 32 00   &....ï.. ....ur2.
    00000010  23 00 00 00 16 1B 00 00  00 00 6D 79 73 71 6C 2D   #....... ..mysql-
    00000020  62 69 6E 2E 30 30 30 30  30 39                     bin.0000 09

    '''
    # s.close()
    # exit(0)

    print("===== 每个insert 5 个 event========")

    while True:
        read_binlog(s)

    '''
    # 1 OK value
    # 4 timestamp
    # 1 event_type
    # 4 server_id
    # 4 log_pos
    # 2 flags
    
    '''

    s.close()
