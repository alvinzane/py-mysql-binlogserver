# coding=utf-8
import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def init_logger(log_name=None, level=logging.INFO, logger=logging.getLogger()):
    """初始化logger"""
    log_dir, name = os.path.split(os.path.abspath(sys.argv[0]))
    if log_name:
        name = log_name

    log_filename = os.path.dirname(log_dir) + '/log/' + name.replace(".py", "") + '.log'
    fmt = logging.Formatter('%(asctime)s %(levelname)s [%(process)d] %(filename)s %(message)s ')

    if not os.path.isdir(os.path.dirname(log_filename)):
        os.makedirs(os.path.dirname(log_filename))

    # 单文件最大10M
    file_handler = RotatingFileHandler(log_filename, mode='a', maxBytes=10240000, backupCount=100,
                                       encoding="utf8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(fmt)
    logger.addHandler(stdout_handler)
    logger.setLevel(level)

    return logger
