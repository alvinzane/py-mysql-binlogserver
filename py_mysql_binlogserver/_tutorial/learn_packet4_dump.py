import struct

from py_mysql_binlogserver._tutorial.learn_packet2_auth import dump_packet
from py_mysql_binlogserver._tutorial.learn_packet3_query import get_query, read_packet, get_conn


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


def query(s, sql):
    query = get_query(sql)
    dump_packet(query, f"query packet:{sql}")
    s.send(query)

    return read_packet(s)


if __name__ == "__main__":

    conn = get_conn("192.168.1.100", 3306, "repl", "repl1234")
    # query(conn, "select @@version_comment")

    log_file = "mysql-bin.000015"
    log_pos = 4
    dump = get_dump_pos(log_file, log_pos, 3306100)
    conn.send(dump)

    print("=== Dump Binlog Event ===")
    while True:
        _header = conn.recv(5)
        _length = struct.unpack("<I", (_header[0:3] + b"\x00"))[0]
        _sequenceId = struct.unpack("<B", _header[3:4])[0]
        _packetType = struct.unpack("<B", _header[4:])[0]

        if _packetType == 0xfe:  # EOF
            break

        _payload = conn.recv(_length - 1)
        dump_packet(_header + _payload, f"read packet [{_sequenceId}]")
