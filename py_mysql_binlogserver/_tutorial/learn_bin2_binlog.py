"""
解析Binlog Event
"""
import struct
from py_mysql_binlogserver.constants.EVENT_TYPE import event_type_name

event_map = event_type_name()

with open("mysql-bin.000009", mode="rb") as fr:
    _file_header = fr.read(4)
    if _file_header != bytes.fromhex("fe62696e"):
        print("It is not a binlog file.")
        exit()

    '''
    https://dev.mysql.com/doc/internals/en/binlog-event-header.html
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
        print("Binlog Event[%s]: [%s] %s %s" % (timestamp,
                                                event_type,
                                                event_map.get(event_type), log_pos))
        event_body = fr.read(event_size - 19)
