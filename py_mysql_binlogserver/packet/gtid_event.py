import binascii
import struct

from py_mysql_binlogserver.protocol.packet import Packet
from py_mysql_binlogserver.protocol.proto import Proto, byte2int


class GitdEvent(Packet):
    __slots__ = ('commit_flag', 'sid', 'gno', 'gtid') + Packet.__slots__

    def __init__(self, commit_flag=None, sid=None, gno=None, gtid=None):
        super(GitdEvent, self).__init__()
        self.commit_flag = commit_flag
        self.sid = sid
        self.gno = gno
        self.gtid = gtid

    def getPayload(self):
        payload = bytearray()
        # TODO

        return payload

    @staticmethod
    def loadFromPacket(packet):

        obj = GitdEvent()
        proto = Proto(packet, 19)

        obj.commit_flag = byte2int(proto.get_fixed_int(1)) == 1
        obj.sid = proto.read(16)
        obj.gno = struct.unpack('<Q', proto.read(8))[0]

        nibbles = binascii.hexlify(obj.sid).decode('ascii')
        obj.gtid = '%s-%s-%s-%s-%s:%d' % (
            nibbles[:8], nibbles[8:12], nibbles[12:16], nibbles[16:20], nibbles[20:], obj.gno
        )

        return obj
