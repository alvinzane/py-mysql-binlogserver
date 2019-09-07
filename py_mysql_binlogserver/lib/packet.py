# coding=utf-8
import os

import sys

from py_mysql_binlogserver.lib import Flags
from py_mysql_binlogserver.lib.Flags import header_name
from py_mysql_binlogserver.lib.proto import Proto
import logging
import logging.handlers

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


if sys.platform == "win32":
    tmp_dir = "D:/Work/PyCharm/mysql-piper/py_mysql_binlogserver/cap"
else:
    tmp_dir = "/tmp"


def packet2file(packet, filename):
    # return
    fo = open(tmp_dir + "/" + filename, "w+b")
    fo.write(packet)
    fo.close()


def file2packet(filename):
    fi = open(tmp_dir + "/" + filename, "r+b")
    packet = bytearray(fi.read())
    fi.close()
    return packet


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


def read_client_packet3(socket_in):
    buff = socket_in.recv(1024)
    return


def read_client_packet(socket_in):
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
    if __debug__:
        # logger.debug("read_client_packet:")
        # dump(psize)
        pass

    return psize


def send_client_socket(socket, buff):
    socket.sendall(buff)
    if __debug__:
        logger.debug("send_client_socket:")
        dump(buff)


def read_full_result_set(socket_in, socket_out, buff, bufferResultSet=True,
                         packedPacketSize=65535,
                         resultsetType=Flags.RS_FULL):
    """
    Reads a full result set
    """
    from colcount import ColCount
    from eof import EOF

    colCount = ColCount.loadFromPacket(buff).colCount

    # Evil optimization
    if not bufferResultSet:
        # socket_out.sendall(buff)
        send_client_socket(socket_out, buff)
        del buff[:]

    # Read columns
    for i in range(0, colCount):
        packet = read_server_packet(socket_in)

        # Evil optimization
        if not bufferResultSet:
            # socket_out.sendall(packet)
            send_client_socket(socket_out, packet)
        else:
            buff.extend(packet)

    # Check for OK or ERR
    # Stop on ERR
    packet = read_server_packet(socket_in)
    packetType = getType(packet)

    # Evil optimization
    if not bufferResultSet:
        # socket_out.sendall(packet)
        send_client_socket(socket_out, packet)
    else:
        buff.extend(packet)

    # Error? Stop now
    if packetType == Flags.ERR:
        return

    if packetType == Flags.EOF and resultsetType == Flags.RS_HALF:
        return

    # Read rows
    while True:
        packet = read_server_packet(socket_in)
        packetType = getType(packet)
        if packetType == Flags.EOF:
            moreResults = EOF.loadFromPacket(packet).hasStatusFlag(
                Flags.SERVER_MORE_RESULTS_EXISTS)

        # Evil optimization
        if not bufferResultSet:
            # socket_out.sendall(packet)
            send_client_socket(socket_out, packet)
        else:
            buff.extend(packet)
            if packedPacketSize > 0 and len(buff) > packedPacketSize:
                # socket_out.sendall(buff)
                send_client_socket(socket_out, buff)
                del buff[:]

        if packetType == Flags.EOF or packetType == Flags.ERR:
            break

    # Evil optimization
    if not bufferResultSet:
        # socket_out.sendall(buff)
        send_client_socket(socket_out, buff)
        del buff[:]

    # Show Create Table or similar?
    if packetType == Flags.ERR:
        return

    # Multiple result sets?
    if moreResults:
        buff.extend(
            read_full_result_set(
                socket_in,
                socket_out,
                read_server_packet(socket_in),
                bufferResultSet=bufferResultSet,
                packedPacketSize=packedPacketSize,
                resultsetType=resultsetType)
        )
    return


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
