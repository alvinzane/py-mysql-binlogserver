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

        _payload = skt.recv(_length - 1)
        dump_packet(_header + _payload, f"read packet [{_sequenceId}]")

        if _packetType in (0xfe, 0x00):     # EOF
            break


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


def get_conn(host, port, user, pwd):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))

    greeting = get_greeting(s)
    username = user
    password = pwd
    response = get_response(s, username, password, greeting["challenge1"], greeting["challenge2"])
    s.send(response)
    result = s.recv(1024)
    return s


if __name__ == "__main__":

    conn = get_conn("192.168.1.100", 3306, "repl", "repl1234")
    sql = "select @@version_comment"
    query = get_query(sql)
    dump_packet(query, f"query packet:{sql}")
    conn.send(query)

    read_packet(conn)
