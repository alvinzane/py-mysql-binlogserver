# 用Python开发MySQL增强半同步BinlogServer-基础篇

## 概述
  前不久知数堂吴老师在公开课上把MHA拉下神坛，是因为MHA无法从根本上解决丢数据的可能性，只是尝试性的去补偿未同步的数据。使用MySQL的半同步复制可以解决数据丢失的问题，但原生io_thread会破坏掉Master上的Binlog File的命名，对后继的运维造成不便，所以使用原生增强半同步+blackhole引擎做binlog备份的方案几乎没有人使用，而更多的公司则使用mysqlbinlog命令来实现轻量的BinlogServer，不足的是官方mysqlbinlog并不支持半同步复制，仍然会丢数据。
  
  据我所知，Facebook,Google和国内的美团公司都有研发自己的BinlogServer，但是目前我没有找到一个开源的支持半同步的BinlogServer项目，于是就诞生了py-mysql-binlogserver这个项目。
  
主要特性如下：
* 全Python标准模块开发，无第三方库依赖，减少学习成本
* 独立Dumper进程，用于同步保存Binlog event
* 支持半同步协议，数据零丢失
* 独立Server进程，支持Failover时Change master to来补数据
* 支持GTID，方便切换Master
* 暂不支持级联复制模式
* 仅在MySQL官方版5.7+下测试通过
* 仅支持Python3, 不兼容Python2

TODO特性
* 使用mysql client协议来管理binlogserver
* 实现状态信息查询，满足监控需求

具体功能请到项目首页进行查看和下载体验。

项目地址为：
```
https://github.com/alvinzane/py-mysql-binlogserver
```

目录结构：
```
py-mysql-binlogserver
├── README.doc
├── doc
│   ├── T1基础篇-用Python开发MySQL增强半同步BinlogServer.md
│   ├── T2通信篇-用Python开发MySQL增强半同步BinlogServer.md
│   ├── T3实战篇-用Python开发MySQL增强半同步BinlogServer.md
│   ├── T4架构篇-用Python开发MySQL增强半同步BinlogServer.md
│   └── readme.md
└── py_mysql_binlogserver
    ├── __init__.py
    ├── _playground                             # 练习场，随便玩
    │   ├── __init__.py
    │   ├── socket_client.py
    │   ├── socket_client_semi-repl.py
    │   └── test_slave.py
    ├── _tutorial                               # 教程实例代码
    │   ├── __init__.py
    │   ├── learn_bin1_charset.py
    │   ├── learn_bin2_binlog.py
    │   ├── learn_packet1_greeting.py
    │   ├── learn_packet2_auth.py
    │   ├── learn_packet3_query.py
    │   ├── learn_packet4_dump.py
    │   ├── learn_packet4_dump2.py
    │   ├── learn_packet5_dump_with_semi_ack.py
    │   ├── learn_socket1_client.py
    │   ├── learn_socket2_server.py
    │   ├── learn_socket3_server_mulit_thread.py
    │   └── learn_socket4_server_mulit_thread.py
    ├── binlogs                                 # Binlog文件保存目录
    │   ├── mysql-bin.000014
    │   ├── mysql-bin.gtid.index
    │   └── mysql-bin.index
    ├── cap
    ├── constants
    │   ├── EVENT_TYPE.py
    │   └── FIELD_TYPE.py
    ├── dump
    │   └── readme.md
    ├── packet
    │   ├── __init__.py
    │   ├── binlog_event.py
    │   ├── challenge.py
    │   ├── dump_gtid.py
    │   ├── dump_pos.py
    │   ├── event_header.py
    │   ├── gtid_event.py
    │   ├── query.py
    │   ├── response.py
    │   ├── semiack.py
    │   └── slave.py
    ├── protocol
    │   ├── Flags.py
    │   ├── __init__.py
    │   ├── err.py
    │   ├── gtid.py
    │   ├── ok.py
    │   ├── packet.py
    │   └── proto.py
    └── tests                               # 单元测试
    │   ├── __init__.py
    │   └── test_packet.py
    ├── proxy.py                            # 简单代理，用于观察和保存MySQL Packet
    ├── server.py                           # 实现Master协议
    ├── dumper.py                           # Binlog Dumper,相当于IO Thread
    ├── example.conf                        # 配置文件
    └─── example.py                         # 同时启动 Server&Dumper
```


  假设你已经有了一定的Python编程基础，并且完全理解MySQL半同步复制的原理，接下来我们就一步一步走进实现BinlogServer的技术细节。
  
## 二进制基础复习
  MySQL的Binlog文件是二进制的，MySQL在网络上传送的数据也是二进制的，所以我们先来复习一下二进制的一些基础知识。
  
### 数字的表示：
 数字通常可以用十进制，二进制和十六进制来表示。在计算机中，数据的运算、存储、传输最终都会用到二进制，但由于二进制不便于人类阅读（太长了），所以我们通常用一位十六进制来表示四个bite的二进制，即2位十六制表示一个Byte(字节)。
```
二进制     十六进制  十进制
0000 0001    01      1
0000 0010    02      2
...
0000 1010    0A      10
1111 1111    FF      255
```
在Python中，用非零开头的数字，表示十进制，0x,0b开头分别表示十六进制和二进制：
```
# 数字10的三种表示：
>>> print(10,0xa,0b1010)
10 10 10
```
十六进制和二进制与十进制转换：
```
>>> print(hex(10),bin(10))
0xa 0b1010
>>> print(int('0xa',16),int('0b1010',2))
10 10
```
由于1个字节（byte)最大能表示的数字为255，所以更大的数字需要用多个字节来表示，如：
```
# 2个字节，16bit,最大为 65535
>>> 0b1111111111111111
65535

# 4个字节，32bit, 最大数（0x为十六进制，1位十六进制等于4位二进制 0xf = 0b1111
>>> 0xffffffff
4294967295
```
以上均为无符号的数字，即全为正数，对于有符号的正负数，则最高位的1个bit用0和1分别表示正数和负数。对于1个byte的数字，实际就只有7bit表示实际的数字，范围为[-128，127].

### 字符的表示
在计算机中所有的数据最终都要转化为数字，而且是二进制的数字。字符也不例外，也需要用到一个"映射表"来完成字符的表示。这个"映射表"叫作字符集，ASCII是最早最基础的"单字节"字符集，它可以表示键盘上所有的可打印字符，如52个大小写字母及标点符号。

Python中，使用ord()和chr()完成ASCII字符与数字之间的转换：
```
>>> ord('a'),ord('b'),ord('c')
(97, 98, 99)
>>> chr(97),chr(98),chr(99)
('a', 'b', 'c')
```
"单字节"最大为数字是255，能表示的字符有限，所以后来就有了"多字节"字符集，如GBK，UTF8等等，用来表示更多的字符。其中UTF8是变长的字符编码，用1-6个字节表示一个字符，可以表示全世界所有的文字与符号，也叫万国码。
 
Python中，多字节字符与数字间的转换：
 ```
# Python3中，字符对象（str), 可以使用 .encode方法将字符转为bytes对象
>>> "中国".encode("utf8")
b'\xe4\xb8\xad\xe5\x9b\xbd'
>>> "中国".encode("gbk")
b'\xd6\xd0\xb9\xfa'

# bytes对象转成字符
b'\xe4\xb8\xad\xe5\x9b\xbd'.decode("utf8")
'中国'
bytes([0xe4,0xb8,0xad,0xe5,0x9b,0xbd]).decode("utf8")
'中国'

 ```
使用hexdump查看文本文件的字符编码：
```
$ file /tmp/python_chr.txt
/tmp/python_chr.txt: UTF-8 Unicode text
$ cat /tmp/python_chr.txt
Python
中国
$ hexdump -C /tmp/python_chr.txt
00000000  50 79 74 68 6f 6e 0a e4  b8 ad e5 9b bd 0a        |Python........|
0000000e
```
使用python来验证编码：
```
# 前三个字符
>>> chr(0x50),chr(0x79),chr(0x74)
('P', 'y', 't')
# 剩下的字符大家动手试一试， 特别是汉字"中国"的编码
```
## Python二进制相关
### bytes对象
bytes是Python3中新增的一个处理二进制"流"的对象。可以下几种方式我们可以得到bytes对象：
* 字符对象的encode方法
* 二进制文件read方法
* 网络socket的recv方法
* 使用b打头的字符申明
* 使用bytes对象初始化

一些简单的例子：
```
>>> b'a'
b'a'
>>> type(b'a')
<class 'bytes'>
>>> bytes([97])
b'a'
>>> bytes("中国",'utf8')
b'\xe4\xb8\xad\xe5\x9b\xbd'
```

可以把bytes看作是一个特殊的数组，由连续的字节(byte)组成，单字节最大数不能超过255，具有数组的切片，迭代等特性，它总是尝试以ASCII编码将数据转成可显示字符，超出ASCII可显示范围则使用\x打头的二位十六进制进行显示。

bytes对象的本质是存的二进制数组，存放的是0-255的数字数组，它只有结合"字符集"才能转换正确的字符，或者要结合某种"协议"才能解读出具体的"含义"，这一点后面就会详细的讲到。

再来一个例子, 打印GBK编码表：
```
# GBK编码从0x8140 开始，显示 30 行
for row in [0x8140 + x*16 for x in range(30)]:
    print(hex(row), end=" ")
    # 每行显示16个
    for i in range(16):
        high = row+i >> 8 & 0xff        # 高位
        low = row+i & 0xff              # 低位
        try:
            # 用bytes对象转换成GBK字符
            print(bytes([high, low]).decode("gbk"), end="")
        except:
            print(end=" ")
    print("")
```
输出：
```
0x8140 丂丄丅丆丏丒丗丟丠両丣並丩丮丯丱
0x8150 丳丵丷丼乀乁乂乄乆乊乑乕乗乚乛乢
0x8160 乣乤乥乧乨乪乫乬乭乮乯乲乴乵乶乷
0x8170 乸乹乺乻乼乽乿亀亁亂亃亄亅亇亊 
0x8180 亐亖亗亙亜亝亞亣亪亯亰亱亴亶亷亸
0x8190 亹亼亽亾仈仌仏仐仒仚仛仜仠仢仦仧
0x81a0 仩仭仮仯仱仴仸仹仺仼仾伀伂伃伄伅
0x81b0 伆伇伈伋伌伒伓伔伕伖伜伝伡伣伨伩
0x81c0 伬伭伮伱伳伵伷伹伻伾伿佀佁佂佄佅
0x81d0 佇佈佉佊佋佌佒佔佖佡佢佦佨佪佫佭
0x81e0 佮佱佲併佷佸佹佺佽侀侁侂侅來侇侊
0x81f0 侌侎侐侒侓侕侖侘侙侚侜侞侟価侢 
```

### struct
计算机中几乎所有的数据都可以最终抽象成数字和字符来表示，在C语言中用struct(结构体)来描述一个复杂的对象，通过这个结构可以方便的将复杂对象转换成二进制流用于存储与网络传输。Python中提供了struct模块方便处理二进制流(bytes对象）与数字，字符对象的转换功能。

#### 用struct处理数字
```
>>> import struct
# 单字节数字
>>> struct.pack("<B", 255)
b'\xff'

# 双字节数字
>>> struct.pack("<H", 255)
b'\xff\x00'

# 四字节数字
>>> struct.pack("<I", 255)
b'\xff\x00\x00\x00'

# 八字节数字
>>> struct.pack("<Q", 255)
b'\xff\x00\x00\x00\x00\x00\x00\x00'

#unpack可以找出8，4，2位符号整型的最大值
>>> struct.unpack("<Q",b'\xff\xff\xff\xff\xff\xff\xff\xff')
(18446744073709551615,)
>>> struct.unpack("<I",b'\xff\xff\xff\xff')
(4294967295,)
>>> struct.unpack("<H",b'\xff\xff')
(65535,)

```
struct处理数字的要点有：
* 字节数
* 有无符号位
* 字节序，本文中均使用低字节在前的字节序"<"

#### 用struct处理字符串
字符转换为bytes:
```
# 变长字符串，以0xff结束
>>> struct.pack("<4s",b"cat")
b'cat\x00'

>>> struct.pack("<5s","中国".encode("gbk"))
b'\xd6\xd0\xb9\xfa\x00'

>>> struct.pack("<7s","中国".encode("utf8"))
b'\xe4\xb8\xad\xe5\x9b\xbd\x00'

# 定长字符串，第1个字节为字符串的长度
>>> struct.pack("<4p",b"cat")
b'\x03cat'

>>> struct.pack("<5p","中国".encode("gbk"))
b'\x04\xd6\xd0\xb9\xfa'

>>> struct.pack("<7p","中国".encode("utf8"))
b'\x06\xe4\xb8\xad\xe5\x9b\xbd'

```

bytes转换为字符:
```
# 仅取一例，其他的请自己动手试一试
>>> struct.unpack("<7p", b'\x06\xe4\xb8\xad\xe5\x9b\xbd')[0].decode("utf8")
'中国'
```
需要特别说明的是，unpack返回的是元组，哪怕是只有一个元素，这样做的好处是，我们可以按照规则将多个数据的format写在一起，让代码更加简洁：
```
>>> struct.pack("<HBI6p",1, 19, 3306, b'alvin')
b'\x01\x00\x13\xea\x0c\x00\x00\x05alvin'

>>> struct.unpack("<HBI6p", b'\x01\x00\x13\xea\x0c\x00\x00\x05alvin')
(1, 19, 3306, b'alvin')
>>> id, no, port, name = struct.unpack("<HBI6p", b'\x01\x00\x13\xea\x0c\x00\x00\x05alvin')

>>> id, no, port, name
(1, 19, 3306, b'alvin')

```
这种写法会大量应用到后继的demo代码中，请务必多加练习，并细仔阅读官方文档。

## Python Socket编程
简单说Socket编程，就是面向网络传输层的接口编程，系统通过IP地址和端口号建立起两台电脑之间网络连接，并提供两个最基础的通信接口发送数据和接收数据，供开发者调用，先来看一个最简单的客户端Socket例子：
```
import socket

# 创建一个socket对象
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# 建立连接
s.connect(("192.168.1.101", 3306))
# 接收数据
buf = s.recv(10240)
print(type(buf))    # <class 'bytes'>
# 发送数据
s.send(b'hello')
```
可以看出通过socket接收和发送的数据都是前面讲的bytes对象，因为bytes对象本身只是一个二进制流，所以在没有"协议"的前提下，我们是无法理解传输内容的具体含义。常见的http,https,ftp,smtp,ssh协议都是建立socket通信之上的协议。换句说，就是通socket编程可以实现与现有的任何协议进行通信。如果你熟悉了ssh协议，那么实现ssh端口扫描程序就易如反掌了。

用socket不仅可以和其它协议的服务端进行通信，而且可以实现socket服务端，监听和处理来自client的连接和数据。
```
import socket

# 创建一个socket对象
s = socket.socket()
# 监听端口
s.bind(('127.0.0.1', 8000))
s.listen(5)

while True:
    conn, addr = s.accept()
    conn.send(bytes('Welcome python socket server.', 'utf8'))
    # 关闭链接
    conn.close()
```
通过上面两个简单的例子，相信大家对Python的socket编程已经有一个初步的认识，那就是"相当的简单"，没有想象中那么复杂。

接下再来看一个多线程版的SocketServer, 可以通过telnet来实现一个网络计算器：
```
# learn_socket3_server_mulit_thread.py

import threading
import socketserver

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

    def handle(self):
        """
        网络计算器，返回表达式的值
        """
        while True:
            try:
                # 接收表达式数据
                data = str(self.request.recv(1024), 'ascii').strip()
                if "q" in data:
                    self.finish()
                    break
                # 计算结果
                response = bytes("{} = {}\r\n".format(data, eval(data)), 'ascii')
                print(response.decode("ascii").strip())
                # 返回结果
                self.request.sendall(response)
            except:
                self.request.sendall(bytes("\n", 'ascii'))

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

if __name__ == "__main__":

    server = ThreadedTCPServer(("127.0.0.1", 9000), ThreadedTCPRequestHandler)
    ip, port = server.server_address

    server_thread = threading.Thread(target=server.serve_forever)
    print(f"Calculator Server start at {ip} : {port}")
    server_thread.start()

```
使用telnet进行测试：
```
$ telnet 127.0.0.1 9000
Trying 127.0.0.1...
Connected to localhost.
Escape character is '^]'.
12345679*81                 # 按回车
12345679*81 = 999999999     # 返回结果
3+2-5*0                     # Enter
3+2-5*0 = 5
(123+123)*123               # Enter
(123+123)*123 = 30258
quit                        # Enter
```
服务端日志：
```
Calculator Server start at 127.0.0.1 : 9000
12345679*81 = 999999999
3+2-5*0 = 5
(123+123)*123 = 30258
```

## 小结
理解二进制，字符/编码，socket通信，以及如何使用Python来处理它们，是实现BinlogServer最重要的基础，由于篇幅问题，很多知识点只能点到为止，虽然很基础，但是还是需要自己的动手去实验，举一反三地多实践自己的想法，会对理解后面的文章大有帮助。

只有会认真看文档的DBA才是好DBA，只会认真看代码的Engineer,一定不是好Engineer。代码一定要运行起来，On Runtime才会有价值，才会让你变成好Engineer. ^_^

最后，祝你编码快乐〜

## 相关文档
- https://docs.python.org/3/library/struct.html
- https://docs.python.org/3/library/socketserver.html

## 附：基于mysqlbinlog命令的BinlogServer简单实现

```
#!/bin/sh

REMOTE_HOST={{host}}
REMOTE_PORT={{mysql_port}}
REMOTE_USER={{mysql_repl_user}}
REMOTE_PASS={{mysql_repl_password}}

BACKUP_BIN=/usr/local/mysql/bin/mysqlbinlog
LOCAL_BACKUP_DIR=/data/backup/mysql/binlog_3306
BACKUP_LOG=/data/backup/mysql/binlog_3306/backup_3306.log

FIRST_BINLOG=mysql-bin.000001
#time to wait before reconnecting after failure
SLEEP_SECONDS=10

##create local_backup_dir if necessary
mkdir -p ${LOCAL_BACKUP_DIR}

cd ${LOCAL_BACKUP_DIR}
##  Function while loop ， After the connection is disconnected, wait for the specified time. ， Reconnect
while :
do
    if [ `ls -A "${LOCAL_BACKUP_DIR}" |wc -l` -eq 0 ];then
        LAST_FILE=${FIRST_BINLOG}
    else
        LAST_FILE=`ls -l ${LOCAL_BACKUP_DIR} | grep -v backuplog |tail -n 1 |awk '{print $9}'`
    fi
    
    ${BACKUP_BIN} --raw --read-from-remote-server --stop-never --host=${REMOTE_HOST} --port=${REMOTE_PORT} --user=${REMOTE_USER} --password=${REMOTE_PASS} ${LAST_FILE}
    echo "`date +"%Y/%m/%d %H:%M:%S"` mysqlbinlog Stop it ， Return code ：$?" | tee -a ${BACKUP_LOG}
    echo "${SLEEP_SECONDS} After the second connect and continue to backup " | tee -a ${BACKUP_LOG}
    sleep ${SLEEP_SECONDS}
done
```
