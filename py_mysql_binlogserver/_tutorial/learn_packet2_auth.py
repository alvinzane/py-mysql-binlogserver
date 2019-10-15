import socket
import struct
import hashlib
from functools import partial
from py_mysql_binlogserver._tutorial.learn_packet1_greeting import get_greeting


def dump_packet(packet, title=None):
    """
    Dumps a packet to the console
    """
    title = title or "Packet Dump"
    offset = 0
    dump = title + '\n'
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


def scramble_native_password(password, message):
    SCRAMBLE_LENGTH = 20
    sha1_new = partial(hashlib.new, 'sha1')

    """Scramble used for mysql_native_password"""
    if not password:
        return b''

    password = password.encode("utf-8")
    message = message.encode("utf-8")

    stage1 = sha1_new(password).digest()
    stage2 = sha1_new(stage1).digest()
    s = sha1_new()
    s.update(message[:SCRAMBLE_LENGTH])
    s.update(stage2)
    result = s.digest()
    return _my_crypt(result, stage1)


def _my_crypt(message1, message2):
    result = bytearray(message1)
    for i in range(len(result)):
        result[i] ^= message2[i]

    return bytes(result)


def get_response(s, username, password, challenge1, challenge2):
    '''
    https://dev.mysql.com/doc/internals/en/connection-phase-packets.html
    简化版
    4              capability flags, CLIENT_PROTOCOL_41 always set
    4              max-packet size
    1              character set
    string[23]     reserved (all [0])
    string[NUL]    username
    lenenc-int     length of auth-response
    string[n]      auth-response
    string[NUL]    auth plugin name
    '''
    scramble_password = scramble_native_password(password, challenge1 + challenge2)

    response = b''
    response += struct.pack('<I', 32482821)
    response += struct.pack('<I', 16777216)
    response += struct.pack('<b', 33)
    response += b''.join([b'\x00' for i in range(23)])
    response += username.encode() + b'\x00'
    response += struct.pack('<b', len(scramble_password))
    response += scramble_password
    response += "mysql_native_password".encode() + b'\x00'
    response = struct.pack('<I', len(response))[:-1] + struct.pack('<B', 1) + response
    return response


if __name__ == "__main__":

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("192.168.1.100", 3306))

    greeting = get_greeting(s)

    username = 'repl'
    password = 'repl1234'
    response = get_response(s, username, password, greeting["challenge1"], greeting["challenge2"])
    s.send(response)
    dump_packet(response, "Response packet:")

    result = s.recv(1024)
    dump_packet(result, "Result packet:")
