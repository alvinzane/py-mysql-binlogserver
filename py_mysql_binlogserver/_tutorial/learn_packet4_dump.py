import socket
import struct

from py_mysql_binlogserver._tutorial.learn_packet1_greeting import get_greeting
from py_mysql_binlogserver._tutorial.learn_packet2_auth import dump_packet, get_response
from py_mysql_binlogserver._tutorial.learn_packet3_query import get_query, read_packet


def get_dump_pos(log_file, log_pos, server_id):
    """
    https://dev.mysql.com/doc/internals/en/com-binlog-dump.html
    1              [12] COM_BINLOG_DUMP
    4              binlog-pos
    2              flags
    4              server-id
    string[EOF]    binlog-filename
    """
    COM_BINLOG_DUMP = 0x12
    buffer = struct.pack('<i', len(log_file) + 11) \
             + struct.pack('<B', COM_BINLOG_DUMP)

    buffer += struct.pack('<I', log_pos)

    flags = 0
    buffer += struct.pack('<H', flags)
    buffer += struct.pack('<I', server_id)
    buffer += log_file.encode()

    return buffer


if __name__ == "__main__":
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("192.168.1.100", 3306))

    greeting = get_greeting(s)
    username = 'repl'
    password = 'repl1234'
    response = get_response(s, username, password, greeting["challenge1"], greeting["challenge2"])
    s.send(response)
    result = s.recv(1024)

    sql = "select @@version_comment"
    query = get_query(sql)
    dump_packet(query, f"query packet:{sql}")
    s.send(query)

    read_packet(s)

    log_file = "mysql-bin.000010"
    log_pos = 4
    dump = get_dump_pos(log_file, log_pos, 3306100)
    s.send(dump)

    read_packet(s)
