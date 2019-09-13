from py_mysql_binlogserver.binlogstream import BinLogStreamReader


def file2packet(filename):
    fi = open(filename, "r+b")
    packet = bytearray(fi.read())
    fi.close()
    return packet


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

log_file = "mysql-bin.000001"
fw = open(log_file, 'wb')
fw.write(bytes.fromhex('fe62696e'))

br = BinLogStreamReader(connection_settings, log_file=log_file, log_pos=4)
for (timestamp, event_type, event_size, log_pos), packet in br:
    print(timestamp, event_type, event_size, log_pos)
    print(BinLogStreamReader.dump_packet(packet))
    fw.write(packet)
    fw.flush()
    if log_pos > 2200:
        break

fw.close()
br.close()

# print(file2packet(log_file))
# print(BinLogStreamReader.dump_packet(file2packet(log_file)))
