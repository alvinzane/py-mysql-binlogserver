# coding=utf-8
from py_mysql_binlogserver.protocol import Flags
from py_mysql_binlogserver.protocol.packet import Packet, dump_my_packet
from py_mysql_binlogserver.protocol.proto import Proto
from py_mysql_binlogserver.packet.event_header import EventHeader
import time


class FormatDescriptionEvent(EventHeader):
    '''
    https://dev.mysql.com/doc/internals/en/format-description-event.html
    2                binlog-version
    string[50]       mysql-server version
    4                create timestamp
    1                event header length
    string[p]        event type header lengths
    '''
    __slots__ = ('binlog_version','mysql_server_version', 'timestamp', 'header_length', 'event_type_header_length') + Packet.__slots__

    def __init__(self,  timestamp, event_type, server_id):
        super(FormatDescriptionEvent, self).__init__(timestamp, event_type, server_id)
        self.sequenceId = 1
        self.binlog_version = 4
        self.mysql_server_version = '5.7.25-log'
        self.timestamp = timestamp or int(time.time())
        self.header_length = 19
        self.event_type_header_length = bytes.fromhex("38 0D 00 08 00 12 00  04 04 04 04 12 00 00 5F 00 04 1A 08 00 00 00 08  08 08 02 00 00 00 0A 0A 0A 2A 2A 00 12 34 00 00 FF 77 B6 DC")
        

    def getEventBody(self):
        payload = bytearray()

        payload.extend(Proto.build_fixed_int(2, self.binlog_version))
        payload.extend(Proto.build_fixed_str(50, self.mysql_server_version))
        payload.extend(Proto.build_fixed_int(4, self.timestamp))
        payload.extend(Proto.build_fixed_int(1, self.header_length))
        payload.extend(self.event_type_header_length)

        return payload

    @staticmethod
    def loadFromPacket(packet):
        return b''

if __name__ == "__main__":
    event = FormatDescriptionEvent(0, 0x0f, 3306101)
    dump_my_packet(event.toPacket())
