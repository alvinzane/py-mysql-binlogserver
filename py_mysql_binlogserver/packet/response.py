#!/usr/bin/env python
# coding=utf-8

from py_mysql_binlogserver.protocol import Flags
from py_mysql_binlogserver.protocol.packet import Packet
from py_mysql_binlogserver.protocol.proto import Proto

import collections


class Response(Packet):
    __slots__ = ('capabilityFlags', 'maxPacketSize', 'characterSet',
                 'username', 'authResponse', 'schema',
                 'pluginName', 'clientAttributes') + Packet.__slots__

    def __init__(self):
        super(Response, self).__init__()
        self.capabilityFlags = Flags.CLIENT_PROTOCOL_41
        self.maxPacketSize = 0
        self.characterSet = 0
        self.username = ''
        self.authResponse = ''
        self.schema = ''
        self.pluginName = ''
        self.clientAttributes = collections.OrderedDict()

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

        if self.hasCapabilityFlag(Flags.CLIENT_PROTOCOL_41):
            payload.extend(Proto.build_fixed_int(4, self.capabilityFlags))
            payload.extend(Proto.build_fixed_int(4, self.maxPacketSize))
            payload.extend(Proto.build_fixed_int(1, self.characterSet))
            payload.extend(Proto.build_filler(23))
            payload.extend(Proto.build_null_str(self.username))

            if self.hasCapabilityFlag(Flags.CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA):
                payload.extend(Proto.build_lenenc_int(len(self.authResponse)))
                payload.extend(Proto.build_fixed_str(len(self.authResponse),
                                                     self.authResponse))
            elif self.hasCapabilityFlag(Flags.CLIENT_SECURE_CONNECTION):
                payload.extend(Proto.build_lenenc_int(len(self.authResponse)))
                payload.extend(Proto.build_fixed_str(len(self.authResponse),
                                                     self.authResponse))
            else:
                payload.extend(Proto.build_null_str(self.authResponse))

            if self.hasCapabilityFlag(Flags.CLIENT_CONNECT_WITH_DB):
                payload.extend(Proto.build_null_str(self.schema))

            if self.hasCapabilityFlag(Flags.CLIENT_PLUGIN_AUTH):
                payload.extend(Proto.build_null_str(self.pluginName))

            if self.hasCapabilityFlag(Flags.CLIENT_CONNECT_ATTRS):
                attributes = bytearray()
                for k,v in self.clientAttributes.items():
                    attributes.extend(Proto.build_lenenc_str(k))
                    attributes.extend(Proto.build_lenenc_str(v))
                payload.extend(Proto.build_lenenc_int(len(attributes)))
                payload.extend(attributes)

        else:
            payload.extend(Proto.build_fixed_int(2, self.capabilityFlags))
            payload.extend(Proto.build_fixed_int(3, self.maxPacketSize))
            payload.extend(Proto.build_null_str(self.username))
            if self.hasCapabilityFlag(Flags.CLIENT_CONNECT_WITH_DB):
                payload.extend(Proto.build_null_str(self.authResponse))
                payload.extend(Proto.build_null_str(self.schema))
            else:
                payload.extend(Proto.build_eop_str(self.authResponse))

        return payload

    @staticmethod
    def loadFromPacket(packet):
        obj = Response()
        proto = Proto(packet, 3)

        obj.sequenceId = proto.get_fixed_int(1)
        obj.capabilityFlags = proto.get_fixed_int(2)
        proto.offset -= 2

        if obj.hasCapabilityFlag(Flags.CLIENT_PROTOCOL_41):
            obj.capabilityFlags = proto.get_fixed_int(4)
            obj.maxPacketSize = proto.get_fixed_int(4)
            obj.characterSet = proto.get_fixed_int(1)
            proto.get_filler(23)
            obj.username = proto.get_null_str()

            if obj.hasCapabilityFlag(Flags.CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA):
                authResponseLen = proto.get_lenenc_int()
                obj.authResponse = proto.get_fixed_str(authResponseLen)
            elif obj.hasCapabilityFlag(Flags.CLIENT_SECURE_CONNECTION):
                authResponseLen = proto.get_lenenc_int()
                obj.authResponse = proto.get_fixed_str(authResponseLen)
            else:
                obj.authResponse = proto.get_null_str()

            if obj.hasCapabilityFlag(Flags.CLIENT_CONNECT_WITH_DB):
                obj.schema = proto.get_null_str()

            if obj.hasCapabilityFlag(Flags.CLIENT_PLUGIN_AUTH):
                obj.pluginName = proto.get_null_str()

            if obj.hasCapabilityFlag(Flags.CLIENT_CONNECT_ATTRS):
                attribute_length = proto.get_lenenc_int()
                while proto.has_remaining_data():
                    k = proto.get_lenenc_str()
                    v = proto.get_lenenc_str()
                    obj.clientAttributes[k] = v

        else:
            obj.capabilityFlags = proto.get_fixed_int(2)
            obj.maxPacketSize = proto.get_fixed_int(3)
            obj.username = proto.get_null_str()
            if obj.hasCapabilityFlag(Flags.CLIENT_CONNECT_WITH_DB):
                obj.authResponse = proto.get_null_str()
                obj.schema = proto.get_null_str()
            else:
                obj.authResponse = proto.get_eop_str()

        return obj


__TEST_PACKETS__ = [
    # HandshakeResponse320
    [
      '11 00 00 01 85 24 00 00',
      '00 6f 6c 64 00 47 44 53',
      '43 51 59 52 5f',
    ],
    #
    [
        '2f 00 00 01 0d a6 03 00',
        '00 00 00 01 08 00 00 00',
        '00 00 00 00 00 00 00 00',
        '00 00 00 00 00 00 00 00',
        '00 00 00 00 72 6f 6f 74',
        '00 00 73 79 73 62 65 6e',
        '63 68 00',
    ],
    # MySQL 5.5.8 with CLIENT_PROTOCOL_41 CLIENT_PLUGIN_AUTH,
    # CLIENT_SECURE_CONNECTION, and CLIENT_CONNECT_WITH_DB set
    [
        '54 00 00 01 8d a6 0f 00',
        '00 00 00 01 08 00 00 00',
        '00 00 00 00 00 00 00 00',
        '00 00 00 00 00 00 00 00',
        '00 00 00 00 70 61 6d 00',
        '14 ab 09 ee f6 bc b1 32',
        '3e 61 14 38 65 c0 99 1d',
        '95 7d 75 d4 47 74 65 73',
        '74 00 6d 79 73 71 6c 5f',
        '6e 61 74 69 76 65 5f 70',
        '61 73 73 77 6f 72 64 00',
    ],
    # MySQL 5.6.6 the client may send attributes if CLIENT_CONNECT_ATTRS is set
    [
        'b2 00 00 01 85 a2 1e 00',
        '00 00 00 40 08 00 00 00',
        '00 00 00 00 00 00 00 00',
        '00 00 00 00 00 00 00 00',
        '00 00 00 00 72 6f 6f 74',
        '00 14 22 50 79 a2 12 d4',
        'e8 82 e5 b3 f4 1a 97 75',
        '6b c8 be db 9f 80 6d 79',
        '73 71 6c 5f 6e 61 74 69',
        '76 65 5f 70 61 73 73 77',
        '6f 72 64 00 61 03 5f 6f',
        '73 09 64 65 62 69 61 6e',
        '36 2e 30 0c 5f 63 6c 69',
        '65 6e 74 5f 6e 61 6d 65',
        '08 6c 69 62 6d 79 73 71',
        '6c 04 5f 70 69 64 05 32',
        '32 33 34 34 0f 5f 63 6c',
        '69 65 6e 74 5f 76 65 72',
        '73 69 6f 6e 08 35 2e 36',
        '2e 36 2d 6d 39 09 5f 70',
        '6c 61 74 66 6f 72 6d 06',
        '78 38 36 5f 36 34 03 66',
        '6f 6f 03 62 61 72      ',
    ],
]
