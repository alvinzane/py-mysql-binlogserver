# coding=utf-8

from py_mysql_binlogserver.protocol import Flags
from py_mysql_binlogserver.protocol.packet import Packet
from py_mysql_binlogserver.protocol.proto import Proto


class Challenge(Packet):
    __slots__ = ('protocolVersion', 'serverVersion', 'connectionId',
                 'challenge1', 'capabilityFlags', 'characterSet',
                 'statusFlags', 'challenge2', 'authPluginDataLength',
                 'authPluginName',
                 ) + Packet.__slots__

    def __init__(self):
        super(Challenge, self).__init__()
        self.protocolVersion = 0x0a
        self.serverVersion = ''
        self.connectionId = 0
        self.challenge1 = ''
        self.capabilityFlags = Flags.CLIENT_PROTOCOL_41
        self.characterSet = 0
        self.statusFlags = 0
        self.challenge2 = ''
        self.authPluginDataLength = 0
        self.authPluginName = ''

    def setCapabilityFlag(self, flag):
        self.capabilityFlags |= flag

    def removeCapabilityFlag(self, flag):
        self.capabilityFlags &= ~flag

    def toggleCapabilityFlag(self, flag):
        self.capabilityFlags ^= flag

    def hasCapabilityFlag(self, flag):
        return ((self.capabilityFlags & flag) == flag)

    def setStatusFlag(self, flag):
        self.statusFlags |= flag

    def removeStatusFlag(self, flag):
        self.statusFlags &= ~flag

    def toggleStatusFlag(self, flag):
        self.statusFlags ^= flag

    def hasStatusFlag(self, flag):
        return ((self.statusFlags & flag) == flag)

    def getPayload(self):
        payload = bytearray()

        payload.extend(Proto.build_fixed_int(1, self.protocolVersion))
        payload.extend(Proto.build_null_str(self.serverVersion))
        payload.extend(Proto.build_fixed_int(4, self.connectionId))
        payload.extend(Proto.build_fixed_str(8, self.challenge1))
        payload.extend(Proto.build_filler(1))
        payload.extend(Proto.build_fixed_int(2, self.capabilityFlags >> 16))
        payload.extend(Proto.build_fixed_int(1, self.characterSet))
        payload.extend(Proto.build_fixed_int(2, self.statusFlags))
        payload.extend(Proto.build_fixed_int(2, self.capabilityFlags & 0xffff))

        if self.hasCapabilityFlag(Flags.CLIENT_PLUGIN_AUTH):
            payload.extend(Proto.build_fixed_int(1, self.authPluginDataLength))
        else:
            payload.extend(Proto.build_filler(1))

        payload.extend(Proto.build_filler(10))

        if self.hasCapabilityFlag(Flags.CLIENT_SECURE_CONNECTION):
            payload.extend(Proto.build_fixed_str(
                max(13, self.authPluginDataLength - 8),
                           self.challenge2))
        if self.hasCapabilityFlag(Flags.CLIENT_PLUGIN_AUTH):
            payload.extend(Proto.build_null_str(self.authPluginName))

        return payload

    @staticmethod
    def loadFromPacket(packet):
        obj = Challenge()
        proto = Proto(packet, 3)

        obj.sequenceId = proto.get_fixed_int(1)
        obj.protocolVersion = proto.get_fixed_int(1)
        obj.serverVersion = proto.get_null_str()
        obj.connectionId = proto.get_fixed_int(4)
        obj.challenge1 = proto.get_fixed_str(8)
        proto.get_filler(1)
        obj.capabilityFlags = proto.get_fixed_int(2) << 16
        if proto.has_remaining_data():
            obj.characterSet = proto.get_fixed_int(1)
            obj.statusFlags = proto.get_fixed_int(2)
            obj.setCapabilityFlag(proto.get_fixed_int(2))

            if obj.hasCapabilityFlag(Flags.CLIENT_PLUGIN_AUTH):
                obj.authPluginDataLength = proto.get_fixed_int(1)
            else:
                proto.get_filler(1)

            proto.get_filler(10)

            if (obj.hasCapabilityFlag(Flags.CLIENT_SECURE_CONNECTION)):
                obj.challenge2 = proto.get_fixed_str(max(13, obj.authPluginDataLength - 8))

            if (obj.hasCapabilityFlag(Flags.CLIENT_PLUGIN_AUTH)):
                obj.authPluginName = proto.get_null_str()

        return obj


__TEST_PACKETS__ = [
    # 5.5.2-m2
    [
        '36 00 00 00 0a 35 2e 35',
        '2e 32 2d 6d 32 00 0b 00',
        '00 00 64 76 48 40 49 2d',
        '43 4a 00 ff f7 08 02 00',
        '00 00 00 00 00 00 00 00',
        '00 00 00 00 00 2a 34 64',
        '7c 63 5a 77 6b 34 5e 5d',
        '3a 00                  ',
    ],
    # 5.6.4-m7-log
    [
        '50 00 00 00 0a 35 2e 36',
        '2e 34 2d 6d 37 2d 6c 6f',
        '67 00 56 0a 00 00 52 42',
        '33 76 7a 26 47 72 00 ff',
        'ff 08 02 00 0f c0 15 00',
        '00 00 00 00 00 00 00 00',
        '00 2b 79 44 26 2f 5a 5a',
        '33 30 35 5a 47 00 6d 79',
        '73 71 6c 5f 6e 61 74 69',
        '76 65 5f 70 61 73 73 77',
        '6f 72 64 00            ',
    ],
]
