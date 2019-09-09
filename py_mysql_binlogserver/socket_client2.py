# coding=utf-8
import socket
import os
import struct

from pymysql.util import byte2int

from py_mysql_binlogserver.auth.dump_gtid import DumpGtid
from py_mysql_binlogserver.auth.dump_pos import DumpPos
from py_mysql_binlogserver.auth.slave import Slave
from py_mysql_binlogserver.lib.err import ERR
from py_mysql_binlogserver.lib.packet import dump_my_packet, send_client_socket, getSequenceId, getType
from py_mysql_binlogserver.auth.challenge import Challenge
from py_mysql_binlogserver.auth.response import Response
from py_mysql_binlogserver.com.initdb import Initdb
from py_mysql_binlogserver.com.query import Query
from py_mysql_binlogserver.lib import Flags
from py_mysql_binlogserver.lib.packet import read_server_packet
from py_mysql_binlogserver.lib.proto import scramble_native_password


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
        unpack = struct.unpack('<cIcIIIH', packet[4:24])

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
    s = get_socket(host="192.168.1.101", user="admin", password="aaaaaa", schema="mysql")

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

    slave = Slave("", '', '', 3306, 3306100, 3306201)
    slave.sequenceId = 0
    packet = slave.getPayload()
    send_socket(s, packet)
    read_packet(s)

    # # 使用增强半同步后，binlog的packet格式会产生变化
    # sql = Query()
    # sql.sequenceId = 0
    # sql.query = "SET @rpl_semi_sync_slave= 1"
    # packet = sql.toPacket()
    # print("query 1:")
    # dump_my_packet(packet)
    # send_socket(s, packet)
    # read_packet(s)

    # dump = DumpPos(3306100, "mysql-bin.000007", 3122)
    dump = DumpGtid(3306201, "ba66414c-d10d-11e9-b4b0-0800275ae9e7:1-14,f0ea18e0-3cff-11e9-9488-0800275ae9e7:1-24")
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
    timestamp event_type server_id event_size log_pos
    1567897996 33 3306101 61 9863 
    GTID_LOG_EVENT
    Length: 62, SequenceId: 25, Header: OK=0 
    00000000  3E 00 00 19 00 8C 39 74  5D 21 75 72 32 00 3D 00   >....9t ]!ur2.=.
    00000010  00 00 87 26 00 00 00 00  00 BA 66 41 4C D1 0D 11   ..&.... .ºfALÑ..
    00000020  E9 B4 B0 08 00 27 5A E9  E7 13 00 00 00 00 00 00   é´°..'Zé ç.......
    00000030  00 02 2A 00 00 00 00 00  00 00 2B 00 00 00 00 00   ..*..... ..+.....
    00000040  00 00                                             ..
    
    1567897996 2 3306101 67 9930
    Length: 68, SequenceId: 26, Header: OK=0 
    QUERY_EVENT
    00000000  44 00 00 1A 00 8C 39 74  5D 02 75 72 32 00 43 00   D....9t ].ur2.C.
    00000010  00 00 CA 26 00 00 08 00  1F 02 00 00 00 00 00 00   ..Ê&.... ........
    00000020  03 00 00 1A 00 00 00 00  00 00 01 00 00 20 40 00   ........ ..... @.
    00000030  00 00 00 06 03 73 74 64  04 E0 00 E0 00 E0 00 64   .....std .à.à.à.d
    00000040  62 31 00 42 45 47 49 4E                            b1.BEGIN 
    
    1567897996 19 3306101 43 9973
    Length: 44, SequenceId: 27, Header: OK=0 
    TABLE_MAP_EVENT
    00000000  2C 00 00 1B 00 8C 39 74  5D 13 75 72 32 00 2B 00   ,....9t ].ur2.+.
    00000010  00 00 F5 26 00 00 00 00  0D 01 00 00 00 00 01 00   ..õ&.... ........
    00000020  03 64 62 31 00 02 74 31  00 02 03 0F 02 28 00 02   .db1..t1 .....(..
    
    1567897996 30 3306101 41 10014
    Length: 42, SequenceId: 28, Header: OK=0 
    WRITE_ROWS_EVENT_V2
    00000000  2A 00 00 1C 00 8C 39 74  5D 1E 75 72 32 00 29 00   *....9t ].ur2.).
    00000010  00 00 1E 27 00 00 00 00  0D 01 00 00 00 00 01 00   ...'.... ........
    00000020  02 00 02 FF FC 23 00 00  00 04 32 33 33 33         ....ü#.. ..2333
    
    1567897996 16 3306101 27 10041
    XID_EVENT
    Length: 28, SequenceId: 29, Header: OK=0 
    00000000  1C 00 00 1D 00 8C 39 74  5D 10 75 72 32 00 1B 00   .....9t ].ur2...
    00000010  00 00 39 27 00 00 00 00  AE 26 00 00 00 00 00 00   ..9'.... ®&......
    '''

    s.close()
