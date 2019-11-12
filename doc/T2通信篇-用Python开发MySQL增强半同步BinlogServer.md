# 用Python开发MySQL增强半同步BinlogServer-通信篇

## 概述
从前一篇文章我们已经了解了：
* 二进制在计算机中的应用
* 字符集与二进制的关系及其在Python中处理
* 用struct来处理二进制的转换问题
* Socket通信的基本编程方法

在本节中，我们将结合这些内容进一步来了解如何使Python和MySQL进行交互。

## MySQL通信协议基础
在Python中，使用socket.secv接收数据或send发送数据的都是二进制流对象Bytes，我们需要结合MySQL通信协议来逐字节解析其具体的含义。

MySQL基础通信单位Packet，它由header + payload组成，header由3个字节的payload长度（最大16M字节数）和1个字节的流水号组成，在读取一个Packet时，通常先读4个字节，解析出payload的长度和payload的序号，再根据payload的长度把余下的正文读取出来。

```
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("127.0.0.1", 3306))
'''
# 先读Header
header = s.recv(4)
length = struct.unpack('<I', header[:3] + b'\x00')[0]
sequenceId = struct.unpack('<B', header[:-1])[0]

# 再读余下的正文，完成一个Packet的完整读取
body = s.recv(length)

```
### 解析Greeting包
当Client连接上MySQL Server后，MySQL会主动发送一个greeting包，把自己的状态和随机密文发送给Client, 等待Client响应帐户和密码等信息，验证失败发送ERR包并主动断开连接，验证成功后发送OK包，保持连接，等待Client发送其它"指令"。

接下来我先看一下Greeting包正文的官方说明：
```
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
```
为了更加直接的观察和理解，我这里去掉了对低版本的兼容格式，让其显得更加整洁。

我们来尝试用Python解析第一个Greeting包：
```
import socket
import struct
from pprint import pprint

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("192.168.56.101", 3306))

greeting = {}

# Header 3+1
greeting["length"] = struct.unpack('<I', s.recv(3) + b'\x00')[0]
greeting["sequenceId"] = struct.unpack('<B', s.recv(1))[0]

# 正文开始
greeting["protocolVersion"] = s.recv(1)

# serverVersion是string[NUL]类型，所以一直循环读取到\x00节束 
greeting["serverVersion"] = ""
while True:
    _byte = s.recv(1)
    if _byte == b'\x00':
        break
    greeting["serverVersion"] += chr(int(_byte.hex(), 16))

# 余下部分请自行参照上方文档进行一一对照    
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
```

输出：
```
{'authPluginDataLength': 21,
 'authPluginName': 'mysql_native_password',
 'capabilityFlag': b'\xff\x81',
 'capabilityFlags': b'\xff\xf7',
 'challenge1': 'X:u8\x11N4\x1b',
 'challenge2': 'dF\x04f~\x1f!%\x14\x1acV\x00',
 'characterSet': b'\xe0',
 'connectionId': 73,
 'length': 78,
 'protocolVersion': b'\n',
 'sequenceId': 0,
 'serverVersion': '5.7.20-log',
 'statusFlags': b'\x02\x00'}
```
可见用Python解析出Greeting包的内容并没有想象中那么难，只要结合官方文档，用Python struct很容易就把二进制流还原成可读的文本信息。

为了使代码可以复用,我们将上面的代码进行一个简单的函数化封装，以方便给后面的例子调用：
```
# learn_packet1_greeting.py

import socket
import struct
from pprint import pprint


def get_greeting(s):
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
    return greeting


if __name__ == "__main__":
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("192.168.1.100", 3306))
    greeting = get_greeting(s)
    pprint(greeting)
    
```

### 封装Response包，完成验证
当Client得到Greeting包后，就可以结合两个随机码，组成认证回应包，完成MySQL的认证：
```
# learn_packet2_auth.py

import socket
import struct
import hashlib
from functools import partial
from py_mysql_binlogserver._tutorial.learn_packet1_greeting import get_greeting


def dump_packet(packet, title=None):
    pass        # 省略代码，节约篇幅


def scramble_native_password(password, message):
    '''
    mysql_native_password
    https://dev.mysql.com/doc/internals/en/secure-password-authentication.html#packet-Authentication::Native41
    '''
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
```
向服务器发送帐号及加密的密文，通过验证后，会得到OK包：
```
Response packet:
00000000  50 00 00 01 05 A6 EF 01  00 00 00 01 21 00 00 00   P....¦ï. ....!...
00000010  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ........ ........
00000020  00 00 00 00 72 65 70 6C  00 14 F6 4A C1 E7 4F 2A   ....repl ..öJÁçO*
00000030  BB A3 CB 29 3C 5B 50 F9  3C AF E3 6C 1C A9 6D 79   »£Ë)<[Pù <¯ãl.©my
00000040  73 71 6C 5F 6E 61 74 69  76 65 5F 70 61 73 73 77   sql_nati ve_passw
00000050  6F 72 64 00                                       ord.

Result packet:
00000000  07 00 00 02 00 00 00 02  00 00 00                  ........ ...
```
验证失败会得到如下结果：
```
Response packet:
00000000  50 00 00 01 05 A6 EF 01  00 00 00 01 21 00 00 00   P....¦ï. ....!...
00000010  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ........ ........
00000020  00 00 00 00 72 65 70 6C  00 14 AB 41 90 72 07 98   ....repl ..«Ar.
00000030  0A 36 21 F8 FC CC 83 7B  8E 4E A3 75 A2 DB 6D 79   .6!øüÌ{ N£u¢Ûmy
00000040  73 71 6C 5F 6E 61 74 69  76 65 5F 70 61 73 73 77   sql_nati ve_passw
00000050  6F 72 64 00                                       ord.

Result packet:
00000000  4A 00 00 02 FF 15 04 23  32 38 30 30 30 41 63 63   J......# 28000Acc
00000010  65 73 73 20 64 65 6E 69  65 64 20 66 6F 72 20 75   ess deni ed for u
00000020  73 65 72 20 27 72 65 70  6C 27 40 27 31 39 32 2E   ser 'rep l'@'192.
00000030  31 36 38 2E 31 2E 31 27  20 28 75 73 69 6E 67 20   168.1.1'  (using 
00000040  70 61 73 73 77 6F 72 64  3A 20 59 45 53 29         password : YES)
```

### 执行查询
完成认证后，服务器就会保存连接，直到超时或Client主动退出才会中断连接。接下来我们就可以在完成认证后的socket上发送命令了，就像使用mysql client一样，只不过通过socket发送的数据还要是bytes对象，直接上菜：
```
# learn_packet3_query.py

import socket
import struct

from py_mysql_binlogserver._tutorial.learn_packet1_greeting import get_greeting
from py_mysql_binlogserver._tutorial.learn_packet2_auth import dump_packet, get_response


def read_packet(skt):
    while True:
        _header = skt.recv(5)
        _length = struct.unpack("<I", (_header[0:3] + b"\x00"))[0]
        _sequenceId = struct.unpack("<B", _header[3:4])[0]
        _packetType = struct.unpack("<B", _header[4:])[0]
        
        # 每个查询会产生多个数据包，读到 EOF 包后结束
        if _packetType == 0xfe:     # EOF
            break

        _payload = skt.recv(_length - 1)
        dump_packet(_header + _payload, f"read packet [{_sequenceId}]")


def get_query(sql):
    """
    https://dev.mysql.com/doc/internals/en/com-query.html
    1              [03] COM_QUERY
    string[EOF]    the query the server shall execute
    """
    query = b''
    query += struct.pack("<B", 3)
    query += sql.encode()

    query = struct.pack('<I', len(query))[:-1] + struct.pack('<B', 0) + query
    return query


if __name__ == "__main__":

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("192.168.1.100", 3306))

    greeting = get_greeting(s)
    username = 'repl'
    password = 'repl1234'
    response = get_response(s, username, password, greeting["challenge1"], greeting["challenge2"])
    s.send(response)
    result = s.recv(1024)

    sql = "select @@version_comment"
    query = get_query(sql)
    dump_packet(query, f"query packet:{sql}")
    s.send(query)

    read_packet(s)
```
## Binlog文件格式

先简单回顾一下binlog文件中都有些什么内容：
```
mysql> show binlog events in 'mysql-bin.000009';
+------------------+-----+----------------+-----------+-------------+--------------------------------------------------------------------+
| Log_name         | Pos | Event_type     | Server_id | End_log_pos | Info                                                               |
+------------------+-----+----------------+-----------+-------------+--------------------------------------------------------------------+
| mysql-bin.000009 |   4 | Format_desc    |   3306100 |         123 | Server ver: 5.7.20-log, Binlog ver: 4                              |
| mysql-bin.000009 | 123 | Previous_gtids |   3306100 |         190 | f0ea18e0-3cff-11e9-9488-0800275ae9e7:1-19                          |
| mysql-bin.000009 | 190 | Gtid           |   3306100 |         251 | SET @@SESSION.GTID_NEXT= 'f0ea18e0-3cff-11e9-9488-0800275ae9e7:20' |
| mysql-bin.000009 | 251 | Query          |   3306100 |         318 | BEGIN                                                              |
| mysql-bin.000009 | 318 | Table_map      |   3306100 |         361 | table_id: 223 (db3.t3)                                             |
| mysql-bin.000009 | 361 | Write_rows     |   3306100 |         402 | table_id: 223 flags: STMT_END_F                                    |
| mysql-bin.000009 | 402 | Xid            |   3306100 |         429 | COMMIT /* xid=286 */                                               |
| mysql-bin.000009 | 429 | Gtid           |   3306100 |         490 | SET @@SESSION.GTID_NEXT= 'f0ea18e0-3cff-11e9-9488-0800275ae9e7:21' |
| mysql-bin.000009 | 490 | Query          |   3306100 |         557 | BEGIN                                                              |
| mysql-bin.000009 | 557 | Table_map      |   3306100 |         600 | table_id: 223 (db3.t3)                                             |
| mysql-bin.000009 | 600 | Write_rows     |   3306100 |         641 | table_id: 223 flags: STMT_END_F                                    |
| mysql-bin.000009 | 641 | Xid            |   3306100 |         668 | COMMIT /* xid=287 */                                               |
| mysql-bin.000009 | 668 | Rotate         |   3306100 |         711 | mysql-bin.000010;pos=4                                             |
+------------------+-----+----------------+-----------+-------------+--------------------------------------------------------------------+
13 rows in set (0.00 sec)
```
可以看出，binlog文件内容就是有很多的Event组成，一个完整的binlog应该是由Format_desc event开始，Rotate event结束，它们充当Binlog文件的元数据，中间Event才是真正和数据相关Event,每一个Event的格式都不尽相同，需要单独作解析。不过我们的BinlogServer并不关心具体的Event内容，只需要把Event作为一个接收，存储和发送的基本单元即可，简单说就是，把Master发送的Event按顺序存储起来，当有Slave change过来以后，再从指定位置把Event一个一个的发送给Slave，仅此而以。

每一个Event都有自己的Header, 描述了它的创建时间、类型、Server Id、长度、下一个Event位置和flags信息，结合Event的长度和下个Event位置信息，我们可以很容易地实现顺序扫描一个Binlog文件中的所有Event：
```
# learn_bin2_binlog.py

import struct
from py_mysql_binlogserver.constants.EVENT_TYPE import event_type_name

event_map = event_type_name()

with open("mysql-bin.000009", mode="rb") as fr:
    _file_header = fr.read(4)
    if _file_header != bytes.fromhex("fe62696e"):
        print("It is not a binlog file.")
        exit()

    '''
    https://dev.mysql.com/doc/internals/en/binlog-event-header.html
    4              timestamp
    1              event type
    4              server-id
    4              event-size
    4              log pos
    2              flags
    '''
    while True:
        event_header = fr.read(19)
        if len(event_header) == 0:
            break
        timestamp, event_type, server_id, event_size, log_pos, flags = struct.unpack('<IBIIIH', event_header)
        print("Binlog Event[%s]: [%s] %s %s" % (timestamp,
                                                event_type,
                                                event_map.get(event_type), log_pos))
        event_body = fr.read(event_size - 19)
```
输出：
```
Binlog Event[1570889546]: [15] FORMAT_DESCRIPTION_EVENT 123
Binlog Event[1570889546]: [35] PREVIOUS_GTIDS_LOG_EVENT 190
Binlog Event[1570889807]: [33] GTID_LOG_EVENT 251
Binlog Event[1570889807]: [2] QUERY_EVENT 318
Binlog Event[1570889807]: [19] TABLE_MAP_EVENT 361
Binlog Event[1570889807]: [30] WRITE_ROWS_EVENT 402
Binlog Event[1570889807]: [16] XID_EVENT 429
Binlog Event[1570889813]: [33] GTID_LOG_EVENT 490
Binlog Event[1570889813]: [2] QUERY_EVENT 557
Binlog Event[1570889813]: [19] TABLE_MAP_EVENT 600
Binlog Event[1570889813]: [30] WRITE_ROWS_EVENT 641
Binlog Event[1570889813]: [16] XID_EVENT 668
Binlog Event[1570889820]: [4] ROTATE_EVENT 711
```
是不是比想象中简单，如果你把基础篇的内容全部理解了，我相信上面这段代码不会难到你，相反如果你还不能理解上面这段代码，请移步回去多看几遍，多练几遍再回来。更多的Binlog相关知识，请参考官方文档。


## 小结
这一节我们把Socket通信的难关功破了，已经完成了和MySQL服务器进行握手，登陆和执行查询，近距离的接触了MySQL的通信协议，学会了如何运用Python struct进行简单的解包和封包，也简单分析了binlog的组成及使用Python来解析binlog文件，最重要的是学会了结合官方文档来解决我们的实际问题。

下一节我们将在本节的基础上进入实战篇，利用Socket向Master发起Slave注册，发送BinlogDump指令，以获取Master上的Binlog Event并保存到本地文件中。


- https://dev.mysql.com/doc/internals/en/mysql-packet.html
- https://dev.mysql.com/doc/internals/en/binlog-file-header.html
- https://dev.mysql.com/doc/internals/en/binlog-event-header.html
- https://github.com/alvinzane/py-mysql-binlogserver/tree/master/py_mysql_binlogserver/_tutorial
