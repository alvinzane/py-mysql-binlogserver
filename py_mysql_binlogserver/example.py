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

    try:

        server = BinlogServer(config["Server"])
        server.run()

        client = BinlogDumper(config["Dumper"])
        client.run()

    except KeyboardInterrupt:
        logger.info("Stop Binlog Dumper from %s: %s at %s %s" % (config["Dumper"]['host'],
                                                                 config["Dumper"]['port'],
                                                                 client._log_file,
                                                                 client._log_pos,
                                                                 ))
        client.close()


if __name__ == "__main__":
    main()
