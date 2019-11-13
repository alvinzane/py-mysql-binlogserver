# Readme

## 教程


## MySQL protocol
```
3   length
1   SequenceId
1   type: 00 OK packet or others without error

```

## Binlog protocol

### 不用hearbeat会从第一个event开始传送
### 使用增强半同步后，binlog的packet格式会产生变化

### Binlog event
```sql
1 OK value
4 timestamp
1 event_type
4 server_id
4 log_pos
2 flags
unpack = struct.unpack('<cIcIIIH', packet[4:24])
```

### semi ack
```sql
1 0xef kPacketMagicNum
8 log_pos
n binlog_filename

```
##  参加文档
-  https://docs.python.org/2/library/struct.html
-  https://dev.mysql.com/doc/internals/en/binlog-event-header.html
