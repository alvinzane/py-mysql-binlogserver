# coding=utf-8
from py_mysql_binlogserver.protocol import Flags
from py_mysql_binlogserver.protocol.packet import Packet
from py_mysql_binlogserver.protocol.proto import Proto


class EventHeader(Packet):
    '''
    4              timestamp
    1              event type
    4              server-id
    4              event-size
    4              log pos
    2              flags
    '''
    __slots__ = ('timestamp','event_type','server_id','event_size','log_pos','flags') + Packet.__slots__

    def __init__(self, timestamp, event_type, server_id):
        super(EventHeader, self).__init__()
        self.timestamp = timestamp
        self.event_type = event_type
        self.server_id = server_id
        self.log_pos = 0
        self.flags = 0

    def getEventBody(self):
        """
        Return the event body as a bytearray
        """
        raise NotImplementedError('getEventBody')

    def getPayload(self):
        payload = bytearray()

        payload.extend(b'\x00')     # OK
        payload.extend(Proto.build_fixed_int(4, self.timestamp))
        payload.extend(Proto.build_fixed_int(1, self.event_type))
        payload.extend(Proto.build_fixed_int(4, self.server_id))
        payload.extend(Proto.build_fixed_int(4, len(self.getEventBody())))
        payload.extend(Proto.build_fixed_int(4, self.log_pos))
        payload.extend(Proto.build_fixed_int(2, self.flags))
        payload.extend(self.getEventBody())

        return payload

    @staticmethod
    def loadFromPacket(packet):
        return b''
