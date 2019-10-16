# 用Python开发MySQL增强半同步BinlogServer-实战篇

## 概述
通过前两篇的基础，我们已经能够深入理解二进制与MySQL的协议关系了，并且能够结合自己的需求，能从官方文档找出相应的文档来实现自己的功能，希望大家鱼渔双收。需要特别强调的是，通过本中的例子和思路，要学会把一个复杂的问题进行以拆分，细化成一个一个的任务后再逐个去实现，特别是对接触编码不久的同学特别重要，从Hello World开始编码在任何阶段都适用，因为它能排除一切干扰项，让你可以专注自己的小目标进行编码和测试。

目前我们已经能够用Socket和MySQL进行基本通信了，也能够处理Binlog文件的Event了，离我们的BinlogServer仅有一步之遥了，这一步就是通过Socket读取Binlog Event并保存到本地。

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
可以发现，除了Command: Register Slave 和 Command: Register Slave 外，其它Statement都是普能query,在上一节中我们都实现了。 其中发送Register Slave后，就可以在主库用show slave hosts进行查看了，发送Send Binlog GTID之后，Master就源源不断的把Binlog Event发送过来了。如果执行了SET @rpl_semi_sync_slave= 1后，Master将会启用半同步协议进行传输并等待从库发送ACK直到超时。

## 异步Binlog dump协议
上面的抓包是一个标准的启动半同步复制的流程，有一些query不是必须的，接下来我们先模拟一个简单的Binlog dump流程：


## 半同步Binlog dump协议
