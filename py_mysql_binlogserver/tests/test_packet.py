import unittest

from py_mysql_binlogserver.packet.dump_gtid import DumpGtid
from py_mysql_binlogserver.packet.semiack import SemiAck
from py_mysql_binlogserver.packet.slave import Slave
from py_mysql_binlogserver.protocol.err import ERR
from py_mysql_binlogserver.protocol.packet import dump_my_packet

__all__ = ["TestPacket"]


class TestPacket(unittest.TestCase):

    def test_err(self):
        err2 = ERR(1045, '28000', 'Access denied for user %s.' % ("alvinzane",))
        err2.sequenceId = 2
        buff2 = err2.toPacket()
        dump_my_packet(buff2)

    def test_slave(self):
        slave = Slave("127.0.0.1", 'repl', 'repl1234', 3306, 3306100, 3306201)
        slave.sequenceId = 2
        # dump_my_packet(slave)
        buf = slave.getPayload()
        dump_my_packet(buf)

    def test_semiack(self):
        dump = SemiAck("mysql-bin.000007", 4)
        dump.sequenceId = 0
        buf = dump.toPacket()
        dump_my_packet(buf)

    def test_dumpgtid(self):
        dump = DumpGtid(3306201, "f0ea18e0-3cff-11e9-9488-0800275ae9e7:1-10")
        dump.sequenceId = 0
        buf = dump.toPacket()
        dump_my_packet(buf)
