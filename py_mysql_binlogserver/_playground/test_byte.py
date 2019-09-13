import struct

pos = bytes.fromhex("9F210000")
print(pos)

pos = struct.unpack("<I", pos)[0]
print(pos)


pos = bytes.fromhex("DF02000000000000")
print(pos)

pos = struct.unpack("<Q", pos)[0]
print(pos)

# print(0x0400)
# print(0x2000)
