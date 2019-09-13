py-mysql-binlogserver
=====================

.. contents:: Table of Contents
   :local:

This package is a pure-Python MySQL BinlogServer which implemented mysql semi sync replication protocol.


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
from py_mysql_binlogserver.server import BinlogServer


def main():
    connection_settings = {
        "host": "192.168.1.100",
        "port": 3306,
        "user": "repl",
        "password": "*******",
        "master_id": 3306101,
        "server_id": 3306202,
        "semi_sync": True,
        "server_uuid": "a721031c-d2c1-11e9-897c-080027adb7d7",
        "heartbeat_period": 30000001024
    }

    server = BinlogServer(connection_settings)
    server.run()


if __name__ == "__main__":
    main()
```


License
-------

py-mysql-binlogserver is released under the MIT License. See LICENSE for more information.
