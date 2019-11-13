py-mysql-binlogserver
=====================


This package is a pure-Python MySQL BinlogServer which implemented mysql semi sync replication protocol, and it also supported a MySQL master protocol so that you can change master to the server when failover.


Requirements
-------------

* Python -- one of the following:

  - Python >= 3.5

* MySQL Server -- one of the following:

  - MySQL >= 5.7

Installation
------------

```
git clone https://github.com/alvinzane/py-mysql-binlogserver.git
```


Documentation
-------------

TODO

Example
-------
example.py
```python
import logging
import configparser
import os
import sys

from py_mysql_binlogserver.dumper import BinlogDumper
from py_mysql_binlogserver.server import BinlogServer


def main():
    config = configparser.ConfigParser()
    conf_file = len(sys.argv) > 1 and sys.argv[1] or os.path.dirname(__file__)+"/example.conf"
    config.read(conf_file)

    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s')
    logger = logging.getLogger()
    logger.setLevel(config["Logging"].getint("level"))

    logger.info("Start Binlog Dumper from %s: %s" % (config["Dumper"]['host'], config["Dumper"]['port']))

    server = BinlogServer(config["Server"])
    server.run()

    client = BinlogDumper(config["Dumper"])
    client.run()

if __name__ == "__main__":
    main()

```

Connecting BinlogServer
----------------------
```sql

$ mysql -h127.0.0.1 -P3308 -urepl -p
Enter password: 
Welcome to the MySQL monitor.  Commands end with ; or \g.
Your MySQL connection id is 2
Server version: 5.7.20-log (Py-MySQL-BinlogServer GPL)

Copyright (c) 2000, 2019, Oracle and/or its affiliates. All rights reserved.

Oracle is a registered trademark of Oracle Corporation and/or its
affiliates. Other names may be trademarks of their respective
owners.

Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.

mysql> select @@version_comment limit 1;
+-----------------------------+
| version_comment             |
+-----------------------------+
| (Py-MySQL-BinlogServer GPL) |
+-----------------------------+
1 row in set (0.00 sec)

mysql> select user();
+---------------------------------------------+
| msg                                         |
+---------------------------------------------+
| Could not exec query on this Binlog server. |
+---------------------------------------------+
1 row in set (0.00 sec)

```

How to use
----------

Server list:
============
```
+--------------+-------------+
| Host         | Role        |
+--------------+-------------+
|192.168.1.100 | Master      |
+--------------+-------------+
|192.178.1.101 | Slave       |
+--------------+-------------+
|192.168.1.1   | BinlogServer|
+--------------+-------------+
```

Master:
=======
```
mysql> show slave hosts;
+-----------+------+------+-----------+--------------------------------------+
| Server_id | Host | Port | Master_id | Slave_UUID                           |
+-----------+------+------+-----------+--------------------------------------+
|   3306101 |      | 3306 |   3306100 | ba66414c-d10d-11e9-b4b0-0800275ae9e7 |
|   3306202 |      | 3306 |   3306101 | a721031c-d2c1-11e9-897c-080027adb7d7 |
+-----------+------+------+-----------+--------------------------------------+
2 rows in set (0.00 sec)
```

Slave:
=====
```
mysql> show slave status\G
*************************** 1. row ***************************
                  Master_Host: 192.168.1.100
                  Master_User: repl
                  Master_Port: 3306
                Connect_Retry: 60
              Master_Log_File: mysql-bin.000008
          Read_Master_Log_Pos: 190
               Relay_Log_File: relay-bin.000002
                Relay_Log_Pos: 355
        Relay_Master_Log_File: mysql-bin.000008
             Slave_IO_Running: Yes
            Slave_SQL_Running: Yes
             Master_Server_Id: 3306100
                  Master_UUID: f0ea18e0-3cff-11e9-9488-0800275ae9e7
             Master_Info_File: /data/mysql/3306/data/master.info
                    SQL_Delay: 0
          SQL_Remaining_Delay: NULL
      Slave_SQL_Running_State: Slave has read all relay log; waiting for more updates
           Master_Retry_Count: 86400
            Executed_Gtid_Set: f0ea18e0-3cff-11e9-9488-0800275ae9e7:1-16
                Auto_Position: 1
1 row in set (0.00 sec)
```

BinlogServer:
============
Running log:
```
# python3 example.py
2019-10-12 22:09:17,272 INFO Start Binlog Dumper from 192.168.1.100: 3306
2019-10-12 22:09:17,272 INFO BinlogServer running in thread: Thread-1 0.0.0.0 3307
2019-10-12 22:09:17,280 INFO Dump binlog from mysql-bin.000008 at 190
```
Binlog directory：
```
$ ll binlogs/
total 72
-rw-r--r--  1 alvin  staff  2130 Oct 12 20:44 mysql-bin.000002
-rw-r--r--  1 alvin  staff   472 Oct 12 20:44 mysql-bin.000003
-rw-r--r--  1 alvin  staff   233 Oct 12 20:44 mysql-bin.000004
-rw-r--r--  1 alvin  staff   472 Oct 12 20:44 mysql-bin.000005
-rw-r--r--  1 alvin  staff   472 Oct 12 20:44 mysql-bin.000006
-rw-r--r--  1 alvin  staff   950 Oct 12 20:44 mysql-bin.000007
-rw-r--r--  1 alvin  staff   190 Oct 12 20:44 mysql-bin.000008
-rw-r--r--  1 alvin  staff   342 Oct 12 20:44 mysql-bin.gtid.index
-rw-r--r--  1 alvin  staff   119 Oct 12 20:44 mysql-bin.index
```

Testing
=======

### Step 1:
Make some data at Master.
```
# Master
mysql> create database db3;
Query OK, 1 row affected (0.01 sec)

mysql> use db3;
Database changed
mysql> create table t3 (id int not null auto_increment primary key,name varchar(10));
Query OK, 0 rows affected (0.02 sec)

mysql> insert into t3 select null,'alvin';
Query OK, 1 row affected (0.01 sec)
Records: 1  Duplicates: 0  Warnings: 0

mysql> flush logs;
Query OK, 0 rows affected (0.03 sec)
```

### Step 2:
Ensure Slave is running normally, then stop slave.
```
# Slave
mysql> use db3;
Reading table information for completion of table and column names
You can turn off this feature to get a quicker startup with -A

Database changed
mysql> select * from t3;
+----+-------+
| id | name  |
+----+-------+
|  1 | alvin |
+----+-------+
1 row in set (0.00 sec)

mysql> show slave status\G
*************************** 1. row ***************************
               Slave_IO_State: Waiting for master to send event
                  Master_Host: 192.168.1.100
                  Master_User: repl
                  Master_Port: 3306
                Connect_Retry: 60
              Master_Log_File: mysql-bin.000009
          Read_Master_Log_Pos: 190
               Relay_Log_File: relay-bin.000004
                Relay_Log_Pos: 395
        Relay_Master_Log_File: mysql-bin.000009
             Slave_IO_Running: Yes
            Slave_SQL_Running: Yes
             Master_Server_Id: 3306100
                  Master_UUID: f0ea18e0-3cff-11e9-9488-0800275ae9e7
             Master_Info_File: /data/mysql/3306/data/master.info
                    SQL_Delay: 0
          SQL_Remaining_Delay: NULL
      Slave_SQL_Running_State: Slave has read all relay log; waiting for more updates
           Master_Retry_Count: 86400
           Retrieved_Gtid_Set: f0ea18e0-3cff-11e9-9488-0800275ae9e7:17-19
            Executed_Gtid_Set: f0ea18e0-3cff-11e9-9488-0800275ae9e7:1-19
                Auto_Position: 1

1 row in set (0.00 sec)

mysql> stop slave;
Query OK, 0 rows affected (0.00 sec)
```

### Step 3:
Make new data at Master, ensure data was replicated to the BinlogServer only.
```
# Master
mysql> insert into t3 select null,'zane';
Query OK, 1 row affected (0.01 sec)
Records: 1  Duplicates: 0  Warnings: 0

mysql> insert into t3 select null,'test';
Query OK, 1 row affected (0.00 sec)
Records: 1  Duplicates: 0  Warnings: 0

mysql> flush logs;
Query OK, 0 rows affected (0.01 sec)

mysql> show slave hosts;
+-----------+------+------+-----------+--------------------------------------+
| Server_id | Host | Port | Master_id | Slave_UUID                           |
+-----------+------+------+-----------+--------------------------------------+
|   3306202 |      | 3306 |   3306101 | a721031c-d2c1-11e9-897c-080027adb7d7 |
+-----------+------+------+-----------+--------------------------------------+
1 row in set (0.00 sec)

mysql> show master status;
+------------------+----------+--------------+------------------+-------------------------------------------+
| File             | Position | Binlog_Do_DB | Binlog_Ignore_DB | Executed_Gtid_Set                         |
+------------------+----------+--------------+------------------+-------------------------------------------+
| mysql-bin.000010 |      190 |              |                  | f0ea18e0-3cff-11e9-9488-0800275ae9e7:1-21 |
+------------------+----------+--------------+------------------+-------------------------------------------+
1 row in set (0.00 sec)
```

### Step 4:
Change master to the BinlogServer, ensure that new data was replicated from the new Master.
```
# Slave
mysql> CHANGE MASTER TO  MASTER_HOST='192.168.1.1',MASTER_PORT=3307;
Query OK, 0 rows affected (0.00 sec)

mysql> start slave;
Query OK, 0 rows affected (0.00 sec)

mysql> show slave status\G
*************************** 1. row ***************************
               Slave_IO_State: Waiting for master to send event
                  Master_Host: 192.168.1.1
                  Master_User: repl
                  Master_Port: 3307
                Connect_Retry: 60
              Master_Log_File: mysql-bin.000010
          Read_Master_Log_Pos: 190
               Relay_Log_File: relay-bin.000003
                Relay_Log_Pos: 395
        Relay_Master_Log_File: mysql-bin.000010
             Slave_IO_Running: Yes
            Slave_SQL_Running: Yes
             Master_Server_Id: 3306192
                  Master_UUID: 18f03682-ab70-11e9-aba4-32068899652e
             Master_Info_File: /data/mysql/3306/data/master.info
                    SQL_Delay: 0
          SQL_Remaining_Delay: NULL
      Slave_SQL_Running_State: Slave has read all relay log; waiting for more updates
           Master_Retry_Count: 86400
           Retrieved_Gtid_Set: f0ea18e0-3cff-11e9-9488-0800275ae9e7:19-21
            Executed_Gtid_Set: f0ea18e0-3cff-11e9-9488-0800275ae9e7:1-21
                Auto_Position: 1
1 row in set (0.01 sec)

mysql> select * from t3;
+----+-------+
| id | name  |
+----+-------+
|  1 | alvin |
|  2 | zane  |
|  3 | test  |
+----+-------+
3 rows in set (0.00 sec)

```

### Step 5:
Checking BinlogServer logs.
```

2019-10-12 22:09:17,272 INFO Start Binlog Dumper from 192.168.1.100: 3306
2019-10-12 22:09:17,272 INFO BinlogServer running in thread: Thread-1 0.0.0.0 3307
2019-10-12 22:09:17,280 INFO Dump binlog from mysql-bin.000008 at 190
2019-10-12 22:20:05,601 INFO Received Event[1570889415]: [33] GTID_LOG_EVENT 61 251
2019-10-12 22:20:05,601 INFO Received Event[1570889415]: [2] QUERY_EVENT 87 338
2019-10-12 22:21:06,817 INFO Received Event[1570889477]: [33] GTID_LOG_EVENT 61 399
2019-10-12 22:21:06,817 INFO Received Event[1570889477]: [2] QUERY_EVENT 145 544
2019-10-12 22:22:01,985 INFO Received Event[1570889532]: [33] GTID_LOG_EVENT 61 605
2019-10-12 22:22:01,985 INFO Received Event[1570889532]: [2] QUERY_EVENT 67 672
2019-10-12 22:22:01,985 INFO Received Event[1570889532]: [19] TABLE_MAP_EVENT 43 715
2019-10-12 22:22:01,985 INFO Received Event[1570889532]: [30] WRITE_ROWS_EVENT 42 757
2019-10-12 22:22:01,986 INFO Received Event[1570889532]: [16] XID_EVENT 27 784
2019-10-12 22:22:16,418 INFO Received Event[1570889546]: [4] ROTATE_EVENT 43 827
2019-10-12 22:22:16,418 INFO Rotate new binlog file: mysql-bin.000009
2019-10-12 22:22:16,419 INFO Received Event[0]: [4] ROTATE_EVENT 43 0
2019-10-12 22:22:16,419 INFO Received Event[1570889546]: [15] FORMAT_DESCRIPTION_EVENT 119 123
2019-10-12 22:22:16,419 INFO Received Event[1570889546]: [35] PREVIOUS_GTIDS_LOG_EVENT 67 190
2019-10-12 22:26:36,612 INFO Received Event[1570889807]: [33] GTID_LOG_EVENT 61 251
2019-10-12 22:26:36,612 INFO Received Event[1570889807]: [2] QUERY_EVENT 67 318
2019-10-12 22:26:36,613 INFO Received Event[1570889807]: [19] TABLE_MAP_EVENT 43 361
2019-10-12 22:26:36,613 INFO Received Event[1570889807]: [30] WRITE_ROWS_EVENT 41 402
2019-10-12 22:26:36,613 INFO Received Event[1570889807]: [16] XID_EVENT 27 429
2019-10-12 22:26:42,746 INFO Received Event[1570889813]: [33] GTID_LOG_EVENT 61 490
2019-10-12 22:26:42,747 INFO Received Event[1570889813]: [2] QUERY_EVENT 67 557
2019-10-12 22:26:42,747 INFO Received Event[1570889813]: [19] TABLE_MAP_EVENT 43 600
2019-10-12 22:26:42,747 INFO Received Event[1570889813]: [30] WRITE_ROWS_EVENT 41 641
2019-10-12 22:26:42,747 INFO Received Event[1570889813]: [16] XID_EVENT 27 668
2019-10-12 22:26:50,096 INFO Received Event[1570889820]: [4] ROTATE_EVENT 43 711
2019-10-12 22:26:50,096 INFO Rotate new binlog file: mysql-bin.000010
2019-10-12 22:26:50,097 INFO Received Event[0]: [4] ROTATE_EVENT 43 0
2019-10-12 22:26:50,097 INFO Received Event[1570889820]: [15] FORMAT_DESCRIPTION_EVENT 119 123
2019-10-12 22:26:50,097 INFO Received Event[1570889820]: [35] PREVIOUS_GTIDS_LOG_EVENT 67 190
2019-10-12 22:28:52,494 INFO login user:repl
2019-10-12 22:28:52,495 INFO query: SELECT UNIX_TIMESTAMP()
2019-10-12 22:28:52,537 INFO query: SELECT @@GLOBAL.SERVER_ID
2019-10-12 22:28:52,579 INFO query: SET @master_heartbeat_period= 30000001024
2019-10-12 22:28:52,580 INFO query: SET @master_binlog_checksum= @@global.binlog_checksum
2019-10-12 22:28:52,580 INFO query: SELECT @master_binlog_checksum
2019-10-12 22:28:52,622 INFO query: SELECT @@GLOBAL.GTID_MODE
2019-10-12 22:28:52,663 INFO query: SELECT @@GLOBAL.SERVER_UUID
2019-10-12 22:28:52,704 INFO query: SET @slave_uuid= 'ba66414c-d10d-11e9-b4b0-0800275ae9e7'
2019-10-12 22:28:52,705 INFO Received COM_REGISTER_SLAVE
2019-10-12 22:28:52,706 INFO Received COM_BINLOG_DUMP_GTID
2019-10-12 22:28:52,708 INFO Begin dump gtid binlog from f0ea18e0-3cff-11e9-9488-0800275ae9e7:1-19 
2019-10-12 22:28:52,708 INFO Finding f0ea18e0-3cff-11e9-9488-0800275ae9e7:19 in mysql-bin.000008
2019-10-12 22:28:52,708 INFO Binlog pos has found: mysql-bin.000008 544
2019-10-12 22:28:52,709 INFO Sending binlog file: mysql-bin.000008
2019-10-12 22:28:52,709 INFO Sending binlog file: mysql-bin.000009
2019-10-12 22:28:52,710 INFO Sending binlog file: mysql-bin.000010
```

License
-------

py-mysql-binlogserver is released under the MIT License.
