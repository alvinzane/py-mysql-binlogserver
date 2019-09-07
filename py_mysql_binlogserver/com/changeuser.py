# coding=utf-8
from py_mysql_binlogserver.lib import Flags
from py_mysql_binlogserver.lib.packet import Packet
from py_mysql_binlogserver.lib.proto import Proto


class ChangeUser(Packet):
    __slots__ = ('user', 'authResponse', 'schema', 'characterSet',
                 'capabilityFlags') + Packet.__slots__

    def __init__(self):
        super(ChangeUser, self).__init__()
        self.user = ''
        self.authResponse = ''
        self.schema = ''
        self.characterSet = 0
        self.capabilityFlags = 0

    def setCapabilityFlag(self, flag):
        self.capabilityFlags |= flag

    def removeCapabilityFlag(self, flag):
        self.capabilityFlags &= ~flag

    def toggleCapabilityFlag(self, flag):
        self.capabilityFlags ^= flag

    def hasCapabilityFlag(self, flag):
        return ((self.capabilityFlags & flag) == flag)

    def getPayload(self):
        payload = bytearray()

        payload.extend(Proto.build_byte(Flags.COM_CHANGE_USER))
        payload.extend(Proto.build_null_str(self.user))
        if not self.hasCapabilityFlag(Flags.CLIENT_SECURE_CONNECTION):
            payload.extend(Proto.build_lenenc_str(self.authResponse))
        else:
            payload.extend(Proto.build_null_str(self.authResponse))
        payload.extend(Proto.build_null_str(self.schema))
        payload.extend(Proto.build_fixed_int(2, self.characterSet))

        return payload

    @staticmethod
    def loadFromPacket(packet):
        obj = ChangeUser()
        proto = Proto(packet, 3)

        obj.sequenceId = proto.get_fixed_int(1)
        proto.get_filler(1)
        obj.user = proto.get_null_str()
        if not obj.hasCapabilityFlag(Flags.CLIENT_SECURE_CONNECTION):
            obj.authResponse = proto.get_lenenc_str()
        else:
            obj.authResponse = proto.get_null_str()
        obj.schema = proto.get_null_str()
        obj.characterSet = proto.get_fixed_int(2)

        return obj
