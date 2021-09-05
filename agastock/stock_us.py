# -*- coding: utf-8 -*-
#=============================================================
# <agastock>
# stock_us.py
# 分析美股用的 StockUs
#
# Copyright ©2021 [Gavin Lee], et. al.
#=============================================================
#agastock module
from common import *
from config import *
from stock_base import *
import agalog

#other module
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from pytrends.exceptions import ResponseError
from requests.exceptions import *  #ConnectionError, InvalidURL, InvalidSchema, ...


class StockUs(StockBase):
    #=========== PARAMETER ============
    _ticker_list= US_TICKER_LIST  #股票清單
    _name_list = US_NAME_LIST   #股票名稱，用於網頁顯示
    _group_list = US_GROUP_LIST   #產業，用於網頁顯示
    _gt_name_list = US_GT_NAME_LIST  #Google Trend 查詢字串


    #=========== 一般設定 ============ 
    _TITLE= "[US STOCK PARSER]"  #標題，用於log首行
    REGION= "us"
    REGION_TEXT= "美股"
    

    #============ PRIVITE FUNCTION ============
    def _get_cust_notify_msg(self, ticker) -> str:
        return ''
        

    #============ PUBLIC FUNCTION ============
    def init(self,):
        super().init()
    
    
    #============ PUBLIC FUNCTION - get_XXX 系列取得股票資訊 ============    
    #寫入基本資料： 代號，名稱，產業，TMP_GTName
    @QueryHandler_ForLoop( init_vars=['代號','名稱', '產業', 'TMP_GTName'] ) #init_vars[] 為網頁顯示順序
    def query_info(self, data_name, ticker, tdata, prev_tdata) -> bool:           
        tdata['代號']= ticker
        
        #使用_name_list[] 來設定名稱，沒包含的用股票代號當名稱
        if ticker in self._name_list:
            tdata['名稱']= self._name_list[ticker]
        else:
            tdata['名稱']= ticker
        
        #使用_group_list[] 設定產業， 沒包含的產業都是None，代表網頁顯示空白
        if ticker in self._group_list:
            tdata['產業']= self._group_list[ticker]
            
        #使用_gt_name_list[] 設定Google Trend查詢字串，沒包含的都是None，代表不搜尋 Google Trend
        if ticker in self._gt_name_list:
            tdata['TMP_GTName']= self._gt_name_list[ticker]

        return True
        

    #寫入股價資料： 股價，漲跌，成交金額，成交量
    #股價寫到 self._df_price_list (若是盤中，最新一筆為即時資料)
    def query_price(self) -> bool:
        tickets_yf_str= ' '.join(self._ticker_list)
        return self._query_price_yfinance(tickets_yf_str)
        

    #寫入財報資料： 本益比，本益比預估，EPS，EPS預估，EPS成長預估，EPS成長預估
    @QueryHandler_ThreadLoop( expire_hours=FINANCE_EXPIRE_HOURS, init_vars=['本益比', '本益比預估', 'EPS', 'EPS預估', 'EPS成長預估', 'EPS成長預估'] )  #init_vars[] 為網頁顯示順序
    def query_finance(self, data_name, ticker, tdata, prev_tdata) -> None:        
        t = yf.Ticker(ticker)
        tdata['EPS']= get_valid_value2(t.info,'trailingEps')
        tdata['EPS預估']= get_valid_value2(t.info,'forwardEps')                
        if is_valid(tdata['EPS預估']) and is_valid(tdata['EPS']) and tdata['EPS預估']>0 and tdata['EPS']>0:
            tdata['EPS成長預估']= (float(tdata['EPS預估']) / float(tdata['EPS'])) -  1
        tdata['本益比']= get_valid_value2(t.info,'trailingPE')
        tdata['本益比預估']= get_valid_value2(t.info,'forwardPE')
        agalog.debug('  %-5s: 財報： EPS=%.2f, EPS預估=%.02f, EPS成長預估=%.1f%%, 本益比=%.2f, 本益比預估=%.2f'%(ticker, tdata['EPS'], tdata['EPS預估'], tdata['EPS成長預估']*100, tdata['本益比'], tdata['本益比預估']))
        return True
