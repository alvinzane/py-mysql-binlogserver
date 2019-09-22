py-mysql-binlogserver
=====================


This package is a pure-Python MySQL BinlogServer which implemented mysql semi sync replication protocol, and it also supported a MySQL master protocol so that you can change master to the server when failover.


Requirements
-------------

* Python -- one of the following:

  - Python_ : >= 3.5

* MySQL Server -- one of the following:

  - MySQL_ >= 5.7

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
from py_mysql_binlogserver.dumper import BinlogDumper
from py_mysql_binlogserver.server import BinlogServer


def main():
    logging.basicConfig(format="%(asctime)s %(message)s")
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    connection_settings = {
        "host": "192.168.1.100",
        "port": 3306,
        "user": "repl",
        "password": "repl1234",
        "master_id": 3306101,
        "server_id": 3306202,
        "semi_sync": True,
        "server_uuid": "a721031c-d2c1-11e9-897c-080027adb7d7",
        "heartbeat_period": 30000001024,
        "binlog_name": "mysql-bin"
    }
    logger.info("Start Binlog Dumper from %s: %s" % (connection_settings['host'], connection_settings['port']))

    try:

        server = BinlogServer(host="0.0.0.0", port=3308)
        server.run()

        client = BinlogDumper(connection_settings)
        client.run()

    except KeyboardInterrupt:
        logger.info("Stop Binlog Dumper from %s: %s at %s %s" % (connection_settings['host'],
                                                                 connection_settings['port'],
                                                                 client._log_file,
                                                                 client._log_pos,
                                                                 ))
        client.close()


if __name__ == "__main__":
    main()

```

Test BinlogServer
-----------------
```sql

$mysql -h192.168.1.1 -urepl -prepl1234 -P3308
mysql: [Warning] Using a password on the command line interface can be insecure.
Welcome to the MySQL monitor.  Commands end with ; or \g.
Your MySQL connection id is 2
Server version: 5.7.20-log (Py-MySQL-BinlogServer GPL)

Copyright (c) 2000, 2017, Oracle and/or its affiliates. All rights reserved.

Oracle is a registered trademark of Oracle Corporation and/or its
affiliates. Other names may be trademarks of their respective
owners.

Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.

mysql> select user();
+---------------------------------------------+
| msg                                         |
+---------------------------------------------+
| Could not exec query on this Binlog server. |
+---------------------------------------------+
1 row in set (0.00 sec)
```


License
-------

py-mysql-binlogserver is released under the MIT License.
