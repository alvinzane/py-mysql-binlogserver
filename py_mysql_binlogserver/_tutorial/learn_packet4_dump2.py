import struct

from py_mysql_binlogserver._tutorial.learn_packet2_auth import dump_packet
from py_mysql_binlogserver._tutorial.learn_packet3_query import get_conn
from py_mysql_binlogserver._tutorial.learn_packet4_dump import get_dump_pos

event_map = {27: 'HEARTBEAT_LOG_EVENT', 0: 'UNKNOWN_EVENT', 1: 'START_EVENT_V3', 2: 'QUERY_EVENT', 3: 'STOP_EVENT', 4: 'ROTATE_EVENT', 5: 'INTVAR_EVENT', 6: 'LOAD_EVENT', 7: 'SLAVE_EVENT', 8: 'CREATE_FILE_EVENT', 9: 'APPEND_BLOCK_EVENT', 10: 'EXEC_LOAD_EVENT', 11: 'DELETE_FILE_EVENT', 12: 'NEW_LOAD_EVENT', 13: 'RAND_EVENT', 14: 'USER_VAR_EVENT', 15: 'FORMAT_DESCRIPTION_EVENT', 16: 'XID_EVENT', 17: 'BEGIN_LOAD_QUERY_EVENT', 18: 'EXECUTE_LOAD_QUERY_EVENT', 19: 'TABLE_MAP_EVENT', 20: 'PRE_GA_WRITE_ROWS_EVENT', 21: 'PRE_GA_UPDATE_ROWS_EVENT', 22: 'PRE_GA_DELETE_ROWS_EVENT', 26: 'INCIDENT_EVENT', 28: 'IGNORABLE_LOG_EVENT', 29: 'ROWS_QUERY_LOG_EVENT', 30: 'WRITE_ROWS_EVENT', 31: 'UPDATE_ROWS_EVENT', 32: 'DELETE_ROWS_EVENT', 33: 'GTID_LOG_EVENT', 34: 'ANONYMOUS_GTID_LOG_EVENT', 35: 'PREVIOUS_GTIDS_LOG_EVENT'}


def fetch_events(conn):
    while True:
        _header = conn.recv(5)
        _length = struct.unpack("<I", (_header[0:3] + b"\x00"))[0]
        _sequenceId = struct.unpack("<B", _header[3:4])[0]
        _packetType = struct.unpack("<B", _header[4:])[0]

        if _packetType == 0xfe:  # EOF
            break
        _payload = conn.recv(_length - 1)
        yield _payload


if __name__ == "__main__":

    conn = get_conn("192.168.1.100", 3306, "repl", "repl1234")

    log_file = "mysql-bin.000015"
    log_pos = 4
    dump = get_dump_pos(log_file, log_pos, 3306100)
    conn.send(dump)

    print("=== Dump Binlog Event ===")
    for event in fetch_events(conn):
        timestamp, event_type, server_id, event_size, log_pos, flags = struct.unpack('<IBIIIH', event[:19])
        print("Binlog Event[%s]: [%s] %s %s" % (timestamp,
                                                event_type,
                                                event_map.get(event_type), log_pos))
        dump_packet(event, f"Read event packet:")

