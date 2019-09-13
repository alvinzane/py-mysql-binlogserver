# coding=utf-8

import logging
import logging.handlers

from py_mysql_binlogserver.protocol.Flags import header_name
from py_mysql_binlogserver.protocol.proto import Proto

logger = logging.getLogger('py_mysql_binlogserver')


class Packet(object):
    """
    Basic class for all mysql proto classes to inherit from
    """
    __slots__ = ('sequenceId',)

    def __init__(self):
        self.sequenceId = None

    def getPayload(self):
        """
        Return the payload as a bytearray
        """
        raise NotImplementedError('getPayload')

    def toPacket(self):
        """
        Convert a Packet object to a byte array stream
        """
        payload = self.getPayload()

        # Size is payload + packet size + sequence id
        size = len(payload)

        packet = bytearray(size + 4)

        packet[0:2] = Proto.build_fixed_int(3, size)
        packet[3] = Proto.build_fixed_int(1, self.sequenceId)[0]
        packet[4:] = payload

        return packet


def hex_ba(string):
    ba = bytearray()
    fields = string.strip().split(' ')
    for field in fields:
        if field == '':
            continue
        ba_tmp = bytearray(1)
        ba_tmp[0] = int(field, 16)
        ba.extend(ba_tmp)
    return ba


def getSize(packet):
    """
    Returns a specified packet size
    """
    return Proto(packet).get_fixed_int(3)


def getType(packet):
    """
    Returns a specified packet type
    """
    return packet[4]


def getSequenceId(packet):
    """
    Returns the Sequence ID for the given packet
    """
    return Proto(packet, 3).get_fixed_int(1)


def dump(packet):
    """
    Dumps a packet to the logger
    """
    offset = 0
    #
    if not logger.isEnabledFor(logging.DEBUG):
        return

    dump = 'Packet Dump\n'

    while offset < len(packet):
        dump += hex(offset)[2:].zfill(8).upper()
        dump += '  '

        for x in range(16):
            if offset + x >= len(packet):
                dump += '   '
            else:
                dump += hex(packet[offset + x])[2:].upper().zfill(2)
                dump += ' '
                if x == 7:
                    dump += ' '

        dump += '  '

        for x in range(16):
            if offset + x >= len(packet):
                break
            c = chr(packet[offset + x])
            if (len(c) > 1
                    or packet[offset + x] < 32
                    or packet[offset + x] == 255):
                dump += '.'
            else:
                dump += c

            if x == 7:
                dump += ' '

        dump += '\n'
        offset += 16
    logger.debug(dump)


def read_server_packet(socket_in):
    """
    Reads a packet from a socket
    """
    # Read the size of the packet
    psize = bytearray(3)
    socket_in.recv_into(psize, 3)

    size = getSize(psize) + 1

    # Read the rest of the packet
    packet_payload = bytearray(size)
    socket_in.recv_into(packet_payload, size)

    # Combine the chunks
    psize.extend(packet_payload)
    # if __debug__:
    #     dump(psize)

    return psize


def dump_my_packet(packet):
    """
    Dumps a packet to the string
    """
    offset = 0
    try:
        header = getType(packet)
    except:
        header = 0
    dump = 'Length: %s, SequenceId: %s, Header: %s=%s \n' % (
    getSize(packet), getSequenceId(packet), header_name(header), header,)

    while offset < len(packet):
        dump += hex(offset)[2:].zfill(8).upper()
        dump += '  '

        for x in range(16):
            if offset + x >= len(packet):
                dump += '   '
            else:
                dump += hex(packet[offset + x])[2:].upper().zfill(2)
                dump += ' '
                if x == 7:
                    dump += ' '

        dump += '  '

        for x in range(16):
            if offset + x >= len(packet):
                break
            c = chr(packet[offset + x])
            if (len(c) > 1
                    or packet[offset + x] < 32
                    or packet[offset + x] == 255):
                dump += '.'
            else:
                dump += c

            if x == 7:
                dump += ' '

        dump += '\n'
        offset += 16

    print(dump)
