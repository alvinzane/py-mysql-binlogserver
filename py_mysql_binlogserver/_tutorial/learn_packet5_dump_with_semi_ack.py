import struct

from py_mysql_binlogserver._tutorial.learn_packet2_auth import dump_packet
from py_mysql_binlogserver._tutorial.learn_packet3_query import read_packet, get_conn
from py_mysql_binlogserver._tutorial.learn_packet4_dump import get_dump_pos, query
from py_mysql_binlogserver._tutorial.learn_packet4_dump2 import fetch_events

XID_EVENT = 16
QUERY_EVENT = 2
event_map = {27: 'HEARTBEAT_LOG_EVENT', 0: 'UNKNOWN_EVENT', 1: 'START_EVENT_V3', 2: 'QUERY_EVENT', 3: 'STOP_EVENT', 4: 'ROTATE_EVENT', 5: 'INTVAR_EVENT', 6: 'LOAD_EVENT', 7: 'SLAVE_EVENT', 8: 'CREATE_FILE_EVENT', 9: 'APPEND_BLOCK_EVENT', 10: 'EXEC_LOAD_EVENT', 11: 'DELETE_FILE_EVENT', 12: 'NEW_LOAD_EVENT', 13: 'RAND_EVENT', 14: 'USER_VAR_EVENT', 15: 'FORMAT_DESCRIPTION_EVENT', 16: 'XID_EVENT', 17: 'BEGIN_LOAD_QUERY_EVENT', 18: 'EXECUTE_LOAD_QUERY_EVENT', 19: 'TABLE_MAP_EVENT', 20: 'PRE_GA_WRITE_ROWS_EVENT', 21: 'PRE_GA_UPDATE_ROWS_EVENT', 22: 'PRE_GA_DELETE_ROWS_EVENT', 26: 'INCIDENT_EVENT', 28: 'IGNORABLE_LOG_EVENT', 29: 'ROWS_QUERY_LOG_EVENT', 30: 'WRITE_ROWS_EVENT', 31: 'UPDATE_ROWS_EVENT', 32: 'DELETE_ROWS_EVENT', 33: 'GTID_LOG_EVENT', 34: 'ANONYMOUS_GTID_LOG_EVENT', 35: 'PREVIOUS_GTIDS_LOG_EVENT'}


def get_semi_ack(log_file, log_pos):
    # 1 0xef kPacketMagicNum
    # 8 log_pos
    # n binlog_filename

    buff = b'\xef'
    buff += struct.pack("<Q", log_pos)
    buff += log_file.encode("utf8")

    return struct.pack("<I", len(buff)) + buff


if __name__ == "__main__":
    conn = get_conn("192.168.1.100", 3306, "repl", "repl1234")
    # query(conn, "select @@version_comment")
    # 启用增强半同步
    query(conn, "SET @rpl_semi_sync_slave=1")

    log_file = "mysql-bin.000016"
    log_pos = 4

    dump = get_dump_pos(log_file, log_pos, 3306100)
    dump_packet(dump, "Dump Binlog Event:")
    conn.send(dump)

    for event in fetch_events(conn):

        timestamp, event_type, server_id, event_size, log_pos, flags = struct.unpack('<IBIIIH', event[2:21])
        print("Binlog Event[%s]: [%s] %s %s" % (timestamp,
                                                event_type,
                                                event_map.get(event_type), log_pos))
        dump_packet(event[2:], f"Read event packet:")

        if event_type in (XID_EVENT, QUERY_EVENT):
            # TODO  从ROTATE_EVENT中解析当前的binlog文件名
            semi_ack = get_semi_ack(log_file, log_pos)
            dump_packet(semi_ack,  "Send semi ack:")
            conn.sendall(semi_ack)
