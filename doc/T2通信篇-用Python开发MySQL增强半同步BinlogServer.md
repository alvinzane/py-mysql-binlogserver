# 用Python开发MySQL增强半同步BinlogServer-通信篇

## 概述
从前一篇文章我们已经了解了：
* 二进制在计算机中的应用
* 字符集与二进制的关系及其在Python中处理
* 用struct来处理二进制的转换问题
* Socket通信的基本编程方法
在本节中，我们将结合这些内容进一步来了解如何使Python来和MySQL进行交互。

## MySQL通信协议基础
在Python中，使用socket.secv接收数据或send发送数据的都是二进制流对象Bytes，我们需要结合MySQL通信协议来逐字节解析其具体的含义。

MySQL基础通信单位Packet，它由4个字节的 payload header + payload body组成，header由3个字节的payload长度（最大16M字节数）和1个字节的流水号组成，在读取一个Packet时，通常先读4个字节，解析出payload的长度和payload的序号，再根据payload的长度把余下的正文读取出来。

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

TODO

## Binlog文件格式
## 异步Binlog dump协议
## 半同步Binlog dump协议


- https://dev.mysql.com/doc/internals/en/mysql-packet.html
