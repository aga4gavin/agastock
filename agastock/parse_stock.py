# -*- coding: utf-8 -*-
#=============================================================
# <agastock>
# parse_stock.py
#
# Usage:
#   parse_stock.py <-us|-tw>
#
# Copyright ©2021 [Gavin Lee], et. al.
#=============================================================
#agastock module
from common import *
from config import *
from stock_us import StockUs
from stock_twn import StockTwn
import agalog

#other module
import time, sys, os, traceback, math, fcntl, logging
from datetime import date, datetime, timedelta


#=========== PARAMETER ============    
_PATH_LOCK_FILE= '/tmp/parse_stock_%s.lock'

    
#============ FUNCTION ============   
#避免重複執行
#需使用全域變數接收回傳值，因為區域變數在function結束，回收變數一併釋放file locking         
def exit_if_dup_execute(lock_file):
    try:
        h_lock_file= open(lock_file, 'w')  #create if not exist 
        fcntl.flock(h_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return h_lock_file
    except BlockingIOError as e: 
        agalog.warning("Terminate due to duplicated running. lock_file=%s"%lock_file)
        sys.exit(1)

    
#============ MAIN ============
try:
    prog_start= datetime.now() #記錄程式執行時間
    if len(sys.argv)==2 and sys.argv[1]=='-us':
        stock= StockUs()
    else:
        stock= StockTwn()
    
    agalog.init(PARSE_STOCK_LOG_LEVEL, PATH_STOCK_PARSER_LOG_REGION%stock.REGION) 
    h_lock_file= exit_if_dup_execute(_PATH_LOCK_FILE%stock.REGION)  #避免重複執行
    
    #初始化，並處理台股美股不同的資料，目前只有台股的處置股，寫入(通知訊息)
    #處置股存在 _df_pusish_list[]
    stock.init() #必須在其他function之前執行
    
    #儲存基本資料： 代號，名稱，產業，TMP_GTName
    stock.query_info() 
    
    #儲存股價資料： 股價，漲跌，成交金額，成交量
    #股價存在 _df_price_list[] (若是盤中，最新一筆為即時資料)
    stock.query_price()  
    
    #儲存布林資料： 布林位置，布林寬度，(通知訊息)
    stock.query_bband()     
    
    #儲存Google Trend資料： G-Trend，G-Trend漲跌，HD_GT_URL (通知訊息)
    stock.query_google_trend()
    
    #寫入財報資料：  
    # 台股: 本益比，EPS，財報季，HD_FinQueryTime
    # 美股: 本益比，本益比預估，EPS，EPS預估，EPS成長預估，HD_FinQueryTime
    stock.query_finance()   
    
    #[程式修改注意] 新的 queue_xxx()　股票分析函式請加在此，init() 和　push_out_line_notify() 之間
    
    #送出前面queue_XXX()系列放入_df_notify_list[]的LINE通知，並寫入notify csv
    stock.push_out_line_notify() 
    
    #儲存： VAR_WebMsg，VAR_PriceUpdateDate
    #並將以上所有資料寫入 stock csv
    stock.write_stock_csv()   

    spend= datetime.now() - prog_start
    agalog.info( "Parse %d tickers successfully. Spend %s"%( len(stock._ticker_list), spend) ) 

except Exception as e:
    #未處理的exception寫入log
    agalog.exception("意外錯誤") 


        