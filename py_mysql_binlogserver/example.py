from py_mysql_binlogserver.server import BinlogServer


def main():
    connection_settings = {
        "host": "192.168.1.100",
        "port": 3306,
        "user": "repl",
        "password": "repl1234",
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
