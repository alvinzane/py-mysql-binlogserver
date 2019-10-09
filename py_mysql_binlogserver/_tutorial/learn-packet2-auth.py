import socket
import struct
import hashlib
from pprint import pprint
from functools import partial
from py_mysql_binlogserver.protocol.packet import dump_my_packet


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


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("192.168.1.100", 3306))
'''
https://dev.mysql.com/doc/internals/en/connection-phase-packets.html
1              [0a] protocol version
string[NUL]    server version
4              connection id
string[8]      auth-plugin-data-part-1
1              [00] filler
2              capability flags (lower 2 bytes)
1              character set
2              status flags
2              capability flags (upper 2 bytes)
1              length of auth-plugin-data
string[10]     reserved (all [00])
string[$len]   auth-plugin-data-part-2 ($len=MAX(13, length of auth-plugin-data - 8))
string[NUL]    auth-plugin name
'''
greeting = {}
greeting["length"] = struct.unpack('<I', s.recv(3) + b'\x00')[0]
greeting["sequenceId"] = struct.unpack('<B', s.recv(1))[0]
greeting["protocolVersion"] = s.recv(1)
greeting["serverVersion"] = ""
while True:
    _byte = s.recv(1)
    if _byte == b'\x00':
        break
    greeting["serverVersion"] += chr(int(_byte.hex(), 16))
greeting["connectionId"] = struct.unpack('<I', s.recv(4))[0]
greeting["challenge1"] = s.recv(8).decode("utf8")
_filler = s.recv(1)
greeting["capabilityFlags"] = s.recv(2)
greeting["characterSet"] = s.recv(1)
greeting["statusFlags"] = s.recv(2)
greeting["capabilityFlag"] = s.recv(2)
greeting["authPluginDataLength"] = struct.unpack('<B', s.recv(1))[0]
_reserved = s.recv(10)
greeting["challenge2"] = s.recv(max(13, greeting["authPluginDataLength"] - 8)).decode("utf8")
greeting["authPluginName"] = ""
while True:
    _byte = s.recv(1)
    if _byte == b'\x00':
        break
    greeting["authPluginName"] += chr(int(_byte.hex(), 16))
pprint(greeting)

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

username = 'repl'
password = 'repl1234'
scramble_password = scramble_native_password(password, greeting["challenge1"] + greeting["challenge2"])

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
print("response packet:")
dump_my_packet(response)
s.send(response)

result = s.recv(1024)
print("result packet:")
dump_my_packet(result)
