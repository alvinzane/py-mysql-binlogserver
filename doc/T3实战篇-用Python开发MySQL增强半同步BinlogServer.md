# 用Python开发MySQL增强半同步BinlogServer-实战篇

## 概述
通过前两篇的基础，我们已经能够深入理解二进制与MySQL的协议关系了，并且能够结合自己的需求，能从官方文档找出相应的文档来实现自己的功能，希望大家鱼渔双收。需要特别强调的是，通过本中的例子和思路，要学会把一个复杂的问题进行以拆分，细化成一个一个的任务后再逐个去实现，特别是对接触编码不久的同学特别重要，从Hello World开始编码在任何阶段都适用，因为它能排除一切干扰项，让你可以专注自己的小目标进行编码和测试。

目前我们已经能够用Socket和MySQL进行基本通信了，也能够处理Binlog文件的Event了，离我们的BinlogServer仅有一步之遥了，这一步就是通过Socket读取Binlog Event并保存到本地。

这一篇之所以叫实战篇，就是希望你不要停在只看不练的阶段，这里再重提一下基础篇的要点：

```
只有会认真看文档的DBA才是好DBA，只会认真看代码的Engineer,一定不是好Engineer。代码一定要运行起来，On Runtime才会有价值，才会让你变成好Engineer. ^_^
```

在这面在分享一个快速提高Python Coding的方法：
- Re-inventing the wheel

从产品设计和生产上说，要避免重复造轮子，但是学习方法中，重复造轮子是最好的方式，没有之一。

把py-mysql-binlogserver就是一个现成的轮子，并配备了完整入门教程，剩下就事情就是需要你去"搬砖"了，一行一行的搬到自己的项目或目录中（不一定要照抄，最后是在理解的基础上，用变通的方式来实现），达到相同的效果，相信用这种方式你很快就能学到很多东西。



## 学习使用tcpdump和Wireshark
抓包工具组合tcpdump和Wireshark对特别重要工具对我们非常有帮助，它对程序的分析和排错起到最重要的作用。在实现BinlogServer之前，必须要先用一个正常的复制环境中dump出一个正常无误的数据包进行参考，当自己的程序出现问题，则可以一个包一个包的进行对比，有时甚至要一个字节一个字节对行对比，方能最快的找出程序的问题。

### 使用tcpdump抓包
首先我们需要建立一个MySQL的复制环境，一主一从即可，在从库Change Master之后，start slave之前，使用tcpdump记录下发生的一切：
```
# Master
$ tcpdump -i enp0s8 port 3306 -w /tmp/3306-repl.cap

# Slave
mysql> start slave;

# Master
mysql> do some trx;

# Slave
mysql> stop slave;

# Master, 中断tcpdump，得到 3306-repl.cap 文件。

```
### 使用Wireshark看包

直接用Wireshark打开/tmp/3306-repl.cap， 我们先分析出start slave后，从库都发送了哪些包：
```
# 第一步部分，先认证
Server Greeting
Login Request

# 第二部分， 从库发起各种查询和指令， 这里可先不用关心每一个是做什么用的
Statement: SELECT UNIX_TIMESTAMP()
Statement: SELECT @@GLOBAL.SERVER_ID
Statement: SET @master_heartbeat_period= 30000001024
Statement: SET @master_binlog_checksum= @@global.binlog_checksum
Statement: SELECT @@GLOBAL.GTID_MODE
Statement: SELECT @@GLOBAL.SERVER_UUID
Statement: SET @slave_uuid= 'ba66414c-d10d-11e9-b4b0-0800275ae9e7'
Command: Register Slave (21)
Statement: SELECT @@global.rpl_semi_sync_master_enabled
Statement: SET @rpl_semi_sync_slave= 1
Command: Send Binlog GTID (30)
```
可以发现，除了Command: Register Slave 和 Command: Register Slave 外，其它Statement都是普通query,在上一节中我们都实现了。 其中发送Register Slave后，就可以在主库用show slave hosts进行查看了，发送Send Binlog GTID之后，Master就源源不断的把Binlog Event发送过来了。如果执行了SET @rpl_semi_sync_slave= 1后，Master将会启用半同步协议进行传输并等待从库发送ACK直到超时。

## 异步Binlog dump协议
上面的抓包是一个标准的启动半同步复制的流程，有一些query不是必须的（如:验证Master状态，注册Slave,设置心跳值等），接下来我们先模拟一个最简单的Binlog dump流程：
```sql
# learn_packet4_dump.py

# 封装binlog dump包
def get_dump_pos(log_file, log_pos, server_id):
    """
    https://dev.mysql.com/doc/internals/en/com-binlog-dump.html
    1              [12] COM_BINLOG_DUMP
    4              binlog-pos
    2              flags
    4              server-id
    string[EOF]    binlog-filename
    """
    COM_BINLOG_DUMP = 0x12
    buffer = struct.pack('<i', len(log_file) + 11) \
             + struct.pack('<B', COM_BINLOG_DUMP)

    buffer += struct.pack('<I', log_pos)

    flags = 0
    buffer += struct.pack('<H', flags)
    buffer += struct.pack('<I', server_id)
    buffer += log_file.encode()

    return buffer


if __name__ == "__main__":

    conn = get_conn("192.168.1.100", 3306, "repl", "repl1234")

    # 请跟据自己的环境进行修改
    log_file = "mysql-bin.000012"
    log_pos = 4
    dump = get_dump_pos(log_file, log_pos, 3306100)
    conn.send(dump)

    print("=== Dump Binlog Event ===")
    while True:
        _header = conn.recv(5)
        _length = struct.unpack("<I", (_header[0:3] + b"\x00"))[0]
        _sequenceId = struct.unpack("<B", _header[3:4])[0]
        _packetType = struct.unpack("<B", _header[4:])[0]

        if _packetType == 0xfe:  # EOF
            break

        _payload = conn.recv(_length - 1)
        dump_packet(_header + _payload, f"read packet [{_sequenceId}]")
```
一个简单Binlog dump进程就写好了，为了简单化，它省略了所有的非必要动作，通过验证后得到连接后，直接向服务器发送Binlob dump指令，看一下输出：
```
=== Dump Binlog Event ===
read packet [1]
00000000  2C 00 00 01 00 00 00 00  00 04 74 72 32 00 2B 00   ,....... ..tr2.+.
00000010  00 00 00 00 00 00 20 00  04 00 00 00 00 00 00 00   ...... . ........
00000020  6D 79 73 71 6C 2D 62 69  6E 2E 30 30 30 30 31 35   mysql-bi n.000015

read packet [2]
00000000  78 00 00 02 00 76 4C C9  5D 0F 74 72 32 00 77 00   x....vLÉ ].tr2.w.
00000010  00 00 7B 00 00 00 00 00  04 00 35 2E 37 2E 32 30   ..{..... ..5.7.20
00000020  2D 6C 6F 67 00 00 00 00  00 00 00 00 00 00 00 00   -log.... ........
00000030  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ........ ........
00000040  00 00 00 00 00 00 00 00  00 00 00 00 76 4C C9 5D   ........ ....vLÉ]
00000050  13 38 0D 00 08 00 12 00  04 04 04 04 12 00 00 5F   .8...... ......._
00000060  00 04 1A 08 00 00 00 08  08 08 02 00 00 00 0A 0A   ........ ........
00000070  0A 2A 2A 00 12 34 00 00  3B CE F1 09               .**..4.. ;Îñ.

read packet [3]
00000000  6C 00 00 03 00 77 4C C9  5D 23 74 72 32 00 6B 00   l....wLÉ ]#tr2.k.
00000010  00 00 E6 00 00 00 80 00  02 00 00 00 00 00 00 00   ..æ.... ........
00000020  F0 EA 18 E0 3C FF 11 E9  94 88 08 00 27 5A E9 E7   ðê.à<..é ..'Zéç
00000030  01 00 00 00 00 00 00 00  01 00 00 00 00 00 00 00   ........ ........
00000040  1B 00 00 00 00 00 00 00  F6 70 08 50 F3 FD 11 E9   ........ öp.Póý.é
00000050  B2 C1 08 00 27 5A E9 E7  01 00 00 00 00 00 00 00   ²Á..'Zéç ........
00000060  01 00 00 00 00 00 00 00  0F 00 00 00 00 00 00 00   ........ ........

read packet [4]
00000000  3E 00 00 04 00 FF 4C C9  5D 21 74 72 32 00 3D 00   >.....LÉ ]!tr2.=.
00000010  00 00 23 01 00 00 00 00  00 F0 EA 18 E0 3C FF 11   ..#..... .ðê.à<..
00000020  E9 94 88 08 00 27 5A E9  E7 1B 00 00 00 00 00 00   é..'Zé ç.......
00000030  00 02 00 00 00 00 00 00  00 00 01 00 00 00 00 00   ........ ........
00000040  00 00                                             ..

read packet [5]
00000000  44 00 00 05 00 FF 4C C9  5D 02 74 72 32 00 43 00   D.....LÉ ].tr2.C.
00000010  00 00 66 01 00 00 08 00  05 00 00 00 00 00 00 00   ..f..... ........
00000020  03 00 00 1A 00 00 00 00  00 00 01 00 00 20 40 00   ........ ..... @.
00000030  00 00 00 06 03 73 74 64  04 E0 00 E0 00 E0 00 64   .....std .à.à.à.d
00000040  62 33 00 42 45 47 49 4E                            b3.BEGIN 
```


接下来我们再"优雅"一下我们的码，并把Package中header去掉，只要真正的Binlog Event内容（把它存到文件中，就是我们Binlog File了）：
```sql
# learn_packet4_dump2.py

def fetch_events(conn):
    while True:
        _header = conn.recv(5)
        _length = struct.unpack("<I", (_header[0:3] + b"\x00"))[0]
        _sequenceId = struct.unpack("<B", _header[3:4])[0]
        _packetType = struct.unpack("<B", _header[4:])[0]

        if _packetType == 0xfe:  # EOF
            break
        _payload = conn.recv(_length - 1)
        yield _payload


if __name__ == "__main__":

    conn = get_conn("192.168.1.100", 3306, "repl", "repl1234")

    log_file = "mysql-bin.000015"
    log_pos = 4
    dump = get_dump_pos(log_file, log_pos, 3306100)
    conn.send(dump)

    print("=== Dump Binlog Event ===")
    for event in fetch_events(conn):
        timestamp, event_type, server_id, event_size, log_pos, flags = struct.unpack('<IBIIIH', event[:19])
        print("Binlog Event[%s]: [%s] %s %s" % (timestamp,
                                                event_type,
                                                event_map.get(event_type), log_pos))
        dump_packet(event, f"Read event packet:")
```
使用Python yield生成器来处理event的获取动作，就可以使用很优雅的方式来迭代event。来看一下输出：
```
=== Dump Binlog Event ===
Binlog Event[0]: [4] ROTATE_EVENT 0
Read event packet:
00000000  00 00 00 00 04 74 72 32  00 2B 00 00 00 00 00 00   .....tr2 .+......
00000010  00 20 00 04 00 00 00 00  00 00 00 6D 79 73 71 6C   . ...... ...mysql
00000020  2D 62 69 6E 2E 30 30 30  30 31 35                  -bin.000 015

Binlog Event[1573473398]: [15] FORMAT_DESCRIPTION_EVENT 123
Read event packet:
00000000  76 4C C9 5D 0F 74 72 32  00 77 00 00 00 7B 00 00   vLÉ].tr2 .w...{..
00000010  00 00 00 04 00 35 2E 37  2E 32 30 2D 6C 6F 67 00   .....5.7 .20-log.
00000020  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ........ ........
00000030  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ........ ........
00000040  00 00 00 00 00 00 00 76  4C C9 5D 13 38 0D 00 08   .......v LÉ].8...
00000050  00 12 00 04 04 04 04 12  00 00 5F 00 04 1A 08 00   ........ .._.....
00000060  00 00 08 08 08 02 00 00  00 0A 0A 0A 2A 2A 00 12   ........ ....**..
00000070  34 00 00 3B CE F1 09                              4..;Îñ.

Binlog Event[1573473399]: [35] PREVIOUS_GTIDS_LOG_EVENT 230
Read event packet:
00000000  77 4C C9 5D 23 74 72 32  00 6B 00 00 00 E6 00 00   wLÉ]#tr2 .k...æ..
00000010  00 80 00 02 00 00 00 00  00 00 00 F0 EA 18 E0 3C   ....... ...ðê.à<
00000020  FF 11 E9 94 88 08 00 27  5A E9 E7 01 00 00 00 00   ..é..' Zéç.....
00000030  00 00 00 01 00 00 00 00  00 00 00 1B 00 00 00 00   ........ ........
00000040  00 00 00 F6 70 08 50 F3  FD 11 E9 B2 C1 08 00 27   ...öp.Pó ý.é²Á..'
00000050  5A E9 E7 01 00 00 00 00  00 00 00 01 00 00 00 00   Zéç..... ........
00000060  00 00 00 0F 00 00 00 00  00 00 00                  ........ ...

Binlog Event[1573473535]: [33] GTID_LOG_EVENT 291
Read event packet:
00000000  FF 4C C9 5D 21 74 72 32  00 3D 00 00 00 23 01 00   .LÉ]!tr2 .=...#..
00000010  00 00 00 00 F0 EA 18 E0  3C FF 11 E9 94 88 08 00   ....ðê.à <..é..
00000020  27 5A E9 E7 1B 00 00 00  00 00 00 00 02 00 00 00   'Zéç.... ........
00000030  00 00 00 00 00 01 00 00  00 00 00 00 00            ........ .....

Binlog Event[1573473535]: [2] QUERY_EVENT 358
Read event packet:
00000000  FF 4C C9 5D 02 74 72 32  00 43 00 00 00 66 01 00   .LÉ].tr2 .C...f..
00000010  00 08 00 05 00 00 00 00  00 00 00 03 00 00 1A 00   ........ ........
00000020  00 00 00 00 00 01 00 00  20 40 00 00 00 00 06 03   ........  @......
00000030  73 74 64 04 E0 00 E0 00  E0 00 64 62 33 00 42 45   std.à.à. à.db3.BE
00000040  47 49 4E                                          GIN

Binlog Event[1573473535]: [19] TABLE_MAP_EVENT 401
Read event packet:
00000000  FF 4C C9 5D 13 74 72 32  00 2B 00 00 00 91 01 00   .LÉ].tr2 .+.....
00000010  00 00 00 70 00 00 00 00  00 01 00 03 64 62 33 00   ...p.... ....db3.
00000020  02 74 33 00 02 03 0F 02  28 00 02                  .t3..... (..

Binlog Event[1573473535]: [30] WRITE_ROWS_EVENT 441
Read event packet:
00000000  FF 4C C9 5D 1E 74 72 32  00 28 00 00 00 B9 01 00   .LÉ].tr2 .(...¹..
00000010  00 00 00 70 00 00 00 00  00 01 00 02 00 02 FF FC   ...p.... .......ü
00000020  06 00 00 00 03 32 32 32                            .....222 

Binlog Event[1573473535]: [16] XID_EVENT 468
Read event packet:
00000000  FF 4C C9 5D 10 74 72 32  00 1B 00 00 00 D4 01 00   .LÉ].tr2 .....Ô..
00000010  00 00 00 12 00 00 00 00  00 00 00                  ........ ...
```

## 半同步Binlog dump协议

在普通的Dump基础上，我们只需要在会话级别设置SET @rpl_semi_sync_slave=1就可以让Master使用半同步复制协议进行传送Binlog Event,同时Master开始半同步协议后，Packet中会多两个字节， 需要额外处理。

另外，需要注意的是发送ACK的时机，format=ROW时，在每个事务的最后一个XID——EVENT发送Semi ack给Master, 当事务中DDL或format=Statement时，在QUERY_EVENT之后发送Semi ack给Master：
```
def get_semi_ack(log_file, log_pos):
    # 1 0xef kPacketMagicNum
    # 8 log_pos
    # n binlog_filename

    buff = b'\xef'
    buff += struct.pack("<Q", log_pos)
    buff += log_file.encode("utf8")

    return struct.pack("<I", len(buff)) + buff


if __name__ == "__main__":
    conn = get_conn("192.168.1.100", 3306, "repl", "repl1234")
    query(conn, "select @@version_comment")
    # 启用增强半同步
    query(conn, "SET @rpl_semi_sync_slave=1")

    log_file = "mysql-bin.000016"
    log_pos = 4

    dump = get_dump_pos(log_file, log_pos, 3306100)
    dump_packet(dump, "Dump bin log:")
    conn.send(dump)

    for event in fetch_events(conn):

        timestamp, event_type, server_id, event_size, log_pos, flags = struct.unpack('<IBIIIH', event[2:21])
        print("Binlog Event[%s]: [%s] %s %s" % (timestamp,
                                                event_type,
                                                event_map.get(event_type), log_pos))
        dump_packet(event, f"Read event packet:")

        if event_type in (XID_EVENT, QUERY_EVENT):
            # TODO  从ROTATE_EVENT中解析当前的binlog文件名
            semi_ack = get_semi_ack(log_file, log_pos)
            dump_packet(semi_ack,  "Send semi ack:")
            conn.sendall(semi_ack)
```

输出结果：
```
Dump Binlog Event:
00000000  1B 00 00 00 12 04 00 00  00 00 00 74 72 32 00 6D   ........ ...tr2.m
00000010  79 73 71 6C 2D 62 69 6E  2E 30 30 30 30 31 36      ysql-bin .000016

Binlog Event[0]: [4] ROTATE_EVENT 0
Read event packet:
00000000  00 00 00 00 04 74 72 32  00 2B 00 00 00 00 00 00   .....tr2 .+......
00000010  00 20 00 04 00 00 00 00  00 00 00 6D 79 73 71 6C   . ...... ...mysql
00000020  2D 62 69 6E 2E 30 30 30  30 31 36                  -bin.000 016

Binlog Event[1573474715]: [15] FORMAT_DESCRIPTION_EVENT 123
Read event packet:
00000000  9B 51 C9 5D 0F 74 72 32  00 77 00 00 00 7B 00 00   QÉ].tr2 .w...{..
00000010  00 00 00 04 00 35 2E 37  2E 32 30 2D 6C 6F 67 00   .....5.7 .20-log.
00000020  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ........ ........
00000030  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00   ........ ........
00000040  00 00 00 00 00 00 00 00  00 00 00 13 38 0D 00 08   ........ ....8...
00000050  00 12 00 04 04 04 04 12  00 00 5F 00 04 1A 08 00   ........ .._.....
00000060  00 00 08 08 08 02 00 00  00 0A 0A 0A 2A 2A 00 12   ........ ....**..
00000070  34 00 00 B0 58 2A BE                              4..°X*¾

Binlog Event[1573474715]: [35] PREVIOUS_GTIDS_LOG_EVENT 230
Read event packet:
00000000  9B 51 C9 5D 23 74 72 32  00 6B 00 00 00 E6 00 00   QÉ]#tr2 .k...æ..
00000010  00 80 00 02 00 00 00 00  00 00 00 F0 EA 18 E0 3C   ....... ...ðê.à<
00000020  FF 11 E9 94 88 08 00 27  5A E9 E7 01 00 00 00 00   ..é..' Zéç.....
00000030  00 00 00 01 00 00 00 00  00 00 00 1F 00 00 00 00   ........ ........
00000040  00 00 00 F6 70 08 50 F3  FD 11 E9 B2 C1 08 00 27   ...öp.Pó ý.é²Á..'
00000050  5A E9 E7 01 00 00 00 00  00 00 00 01 00 00 00 00   Zéç..... ........
00000060  00 00 00 0F 00 00 00 00  00 00 00                  ........ ...

Binlog Event[1573474750]: [33] GTID_LOG_EVENT 291
Read event packet:
00000000  BE 51 C9 5D 21 74 72 32  00 3D 00 00 00 23 01 00   ¾QÉ]!tr2 .=...#..
00000010  00 00 00 00 F0 EA 18 E0  3C FF 11 E9 94 88 08 00   ....ðê.à <..é..
00000020  27 5A E9 E7 1F 00 00 00  00 00 00 00 02 00 00 00   'Zéç.... ........
00000030  00 00 00 00 00 01 00 00  00 00 00 00 00            ........ .....

Binlog Event[1573474750]: [2] QUERY_EVENT 358
Read event packet:
00000000  BE 51 C9 5D 02 74 72 32  00 43 00 00 00 66 01 00   ¾QÉ].tr2 .C...f..
00000010  00 08 00 05 00 00 00 00  00 00 00 03 00 00 1A 00   ........ ........
00000020  00 00 00 00 00 01 00 00  20 40 00 00 00 00 06 03   ........  @......
00000030  73 74 64 04 E0 00 E0 00  E0 00 64 62 33 00 42 45   std.à.à. à.db3.BE
00000040  47 49 4E                                          GIN

Send semi ack:
00000000  19 00 00 00 EF 66 01 00  00 00 00 00 00 6D 79 73   ....ïf.. .....mys
00000010  71 6C 2D 62 69 6E 2E 30  30 30 30 31 36            ql-bin.0 00016
```
我们的程序是从第1个Event开始Dump, 包含了Master上已经提交的事务（只要Binlog File没有被Purge掉之前，都可以Dump下来），当Semi Ack的位置追上Master后，Mater的每个事务提交就会等待Slave进程发送ACK包，再开启下一下事务的提交流程。我们可以通过在 Master上查询status确认半同步是否生效：
```
mysql> show global status like '%semi%';
+--------------------------------------------+-------+
| Variable_name                              | Value |
+--------------------------------------------+-------+
| Rpl_semi_sync_master_clients               | 1     |
| Rpl_semi_sync_master_net_avg_wait_time     | 0     |
| Rpl_semi_sync_master_net_wait_time         | 0     |
| Rpl_semi_sync_master_net_waits             | 29    |
| Rpl_semi_sync_master_no_times              | 1     |
| Rpl_semi_sync_master_no_tx                 | 8     |
| Rpl_semi_sync_master_status                | ON    |  <== 重点
| Rpl_semi_sync_master_timefunc_failures     | 0     |
| Rpl_semi_sync_master_tx_avg_wait_time      | 1654  |
| Rpl_semi_sync_master_tx_wait_time          | 8271  |
| Rpl_semi_sync_master_tx_waits              | 5     |
| Rpl_semi_sync_master_wait_pos_backtraverse | 0     |
| Rpl_semi_sync_master_wait_sessions         | 0     |
| Rpl_semi_sync_master_yes_tx                | 5     |  <== 重点
| Rpl_semi_sync_slave_status                 | OFF   |
+--------------------------------------------+-------+
15 rows in set (0.00 sec)

mysql> insert into t3 select null,222;
Query OK, 1 row affected (0.00 sec)
Records: 1  Duplicates: 0  Warnings: 0

mysql> show global status like '%semi%';
+--------------------------------------------+-------+
| Variable_name                              | Value |
+--------------------------------------------+-------+
| Rpl_semi_sync_master_clients               | 1     |
| Rpl_semi_sync_master_net_avg_wait_time     | 0     |
| Rpl_semi_sync_master_net_wait_time         | 0     |
| Rpl_semi_sync_master_net_waits             | 30    |
| Rpl_semi_sync_master_no_times              | 1     |
| Rpl_semi_sync_master_no_tx                 | 8     |
| Rpl_semi_sync_master_status                | ON    |
| Rpl_semi_sync_master_timefunc_failures     | 0     |
| Rpl_semi_sync_master_tx_avg_wait_time      | 1721  |
| Rpl_semi_sync_master_tx_wait_time          | 10328 |
| Rpl_semi_sync_master_tx_waits              | 6     |
| Rpl_semi_sync_master_wait_pos_backtraverse | 0     |
| Rpl_semi_sync_master_wait_sessions         | 0     |
| Rpl_semi_sync_master_yes_tx                | 6     |  <== 重点
| Rpl_semi_sync_slave_status                 | OFF   |
+--------------------------------------------+-------+
15 rows in set (0.00 sec)
```
可以看出通semi_sync提交的事务在增加了，说明我们的半同步Binlog Dump已经大功告成。

## 如何实现Master协议
server.py是在socketserver的基础上实现了一些必要的MySQL Server协议（简单例子：learn_socket4_server_mulit_thread.py），如认证，执行查询，发送Binlog Event等等，为了简化代简，一些查询被用"缓存包"的形式来实际的，这些缓存包可以通过proxy.py来获取，同时使用proxy.py也可以非常方便的拿来观察MySQL的通信包， 也为开发MySQL中间件提供了基础， 更多的功能等待大家来实现。

## 小结
到目前为此，我们通过循序渐进的方式，从MySQL的第一个Greeting包，到最后得半同步下Binlog Event包全部搞定了，接下来我们只需要再增加Binlog文件的存储功能、Dump断点续传功能等，就可以实现一个完整的Binlog Sever功能了， 当然这些功能都已经含在项目，通过这一系列的教程， 相信你已经有能力去读懂py-mysql-binlogserver的大部分代码了。

