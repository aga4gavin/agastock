# -*- coding: utf-8 -*-
#=============================================================
# <agastock>
# aga_logger.py
# 
# 此module是為了啟用DEBUG level卻不印出其他module訊息
#
# Gavin 2021/08
#=============================================================
#agastock module
from config import *

#other module
import logging, sys, colorlog, os



#=========== VARIABLE ============
_logger= logging.getLogger(name="agastock")  


#=========== FUNCTION ============
def init(log_level, log_file) -> None:
    global _logger
    if ENABLE_GLOBAL_LOG:
        _logger = logging.getLogger()  #若沒有name，連其他module的level都會改變，設為DEBUG會有很多request的http query訊息
        log_level= logging.DEBUG
    
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    _logger.setLevel(log_level)
    
    fmt= '%(name)s[%(asctime)s][%(levelname)-8s] %(message)s'
    datefmt= '%Y-%m-%d  %H:%M:%S'
    
    #印在 console 加顏色
    fmt_color = colorlog.ColoredFormatter( fmt='%(log_color)s'+fmt, datefmt=datefmt,
            log_colors={'DEBUG':'green', 'INFO':'white', 'WARNING':'yellow', 'ERROR':'red', 'CRITICAL':'bold_red' }
    )
    streamHandler= logging.StreamHandler(sys.stdout)
    streamHandler.setFormatter(fmt_color)
    _logger.addHandler(streamHandler)
    
    #印在檔案不加色碼，不然開啟檔案有亂碼
    fmt= logging.Formatter(fmt=fmt, datefmt=datefmt)
    fileHandler= logging.FileHandler(log_file)
    fileHandler.setFormatter(fmt)
    _logger.addHandler(fileHandler)
    

def debug(msg):
    _logger.debug(msg)
    
def info(msg):
    _logger.info(msg)
    
def warning(msg):
    _logger.warning(msg)
    
def error(msg):
    _logger.error(msg)
    
def critical(msg):
    _logger.critical(msg)
    
def exception(msg):
    _logger.exception(msg)
    
    