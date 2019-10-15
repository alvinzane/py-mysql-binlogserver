import socket
import struct

from py_mysql_binlogserver._tutorial.learn_packet1_greeting import get_greeting
from py_mysql_binlogserver._tutorial.learn_packet2_auth import dump_packet, get_response


def read_packet(skt):
    while True:
        _header = skt.recv(5)
        _length = struct.unpack("<I", (_header[0:3] + b"\x00"))[0]
        _sequenceId = struct.unpack("<B", _header[3:4])[0]
        _packetType = struct.unpack("<B", _header[4:])[0]

        if _packetType == 0xfe:     # EOF
            break

        _payload = skt.recv(_length - 1)
        dump_packet(_header + _payload, f"read packet [{_sequenceId}]")


def get_query(sql):
    """
    https://dev.mysql.com/doc/internals/en/com-query.html
    1              [03] COM_QUERY
    string[EOF]    the query the server shall execute
    """
    query = b''
    query += struct.pack("<B", 3)
    query += sql.encode()

    query = struct.pack('<I', len(query))[:-1] + struct.pack('<B', 0) + query
    return query


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
