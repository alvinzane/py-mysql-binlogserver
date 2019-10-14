import socket
import struct
from pprint import pprint

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
