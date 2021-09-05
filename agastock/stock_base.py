# -*- coding: utf-8 -*-
#=============================================================
# <agastock>
# stock_base.py
# StockBase 為股票分析基礎類別，被StockUs和StockTwn繼承
#
# _data[] 儲存所有股票資料，結果將寫入stock csv，讓web_root.py讀取顯示於網頁。
#
# _data[] 的 column 命名規則為：
#   TMP_XXX: 運算暫存使用，寫入 stock csv 之前會刪除 (例如TMP_GTName)
#   VAR_XXX： 給 web_root.py 的資料，和ticker無關所以只存在 _data 首位 (例如VAR_WebMsg)
#   HD_XXX： 其他隱藏欄位，例如 (例如VAR_finance_ExpireTime是給Stock class自己看的， HD_GT_URL是讓web_root.py產生超連接使用)
#   其他： 寫入 stock csv， 由 web_root.py 讀取顯示於 summary 頁面
#
# Copyright ©2021 [Gavin Lee], et. al.
#=============================================================
#agastock module
from common import *
from config import *
import agalog

#other module
import os, talib, re, threading
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.dates import * #MO, TU, WE, TH, FR, SA, SU
import pandas as pd
import mplfinance as mpf
from datetime import date, datetime, timedelta
from linebot import LineBotApi
from linebot.models import TextSendMessage
from linebot.exceptions import LineBotApiError 
from pytrends.request import TrendReq
from pytrends.exceptions import ResponseError
from functools import wraps 
import yfinance as yf


#=========== Decorator QueryHandler ============
#針對處理股票的Query系列函式，設計三個 Decorator，具有以下功能：
# 1, ticker loop
#     QueryHandler_NoLoop: 由函式自行處理loop，例如台股 _query_punish_stock()，一次下載所有處置股
#     QueryHandler_ForLoop: 以single-thread處理loop，函式只需要處理單支ticker，例如台股 query_info() 是簡單的迴圈，single-thread即可
#     QueryHandler_ThreadLoop: 以multi-thread處理loop，函式只需要處理單支ticker，並例如美股 query_info()，每支股票須時5秒，用multi-thread大幅縮短時間
#
# 2, Exception Handler, 避免錯誤造成整個 parse_stock.py 錯誤，確保即使有錯還是能產生 stock csv
#
# 3, init_vars['XX', 'YY', ...], 初始化 _data[ticker]['XX'],_data[ticker]['YY'], ...
#    由於初次建立 'XX', 'YY' 等, 初始化順序即為 DataFrame _data 轉為 csv 的顯示順序，例如代號、名稱、漲跌、...
#
# 4, 傳入參數 expire_hours 啟動暫存功能，逾期才查詢
#
# Query Decorator 介面:
#    QueryHandler_ForLoop( expire_hours=TT, init_vars=['XX','YY'] ) 
#    參數 expire_hours 代表啟動用暫存功能
#    參數 init_vars 代表網頁顯示順序，並且init var成float('nan')，確保後續function使用不會錯誤，並且print("%s")不會發生exception
#
# Query函式標準interface:
#    query_XX(self) #QueryHandler_NoLoop 
#    query_OO(self, ticker, tdata, prev_tdata)  #QueryHandler_ForLoop, QueryHandler_ThreadLoop
#    查詢成功回傳True，若有設定expire_hours代表到期前不再查詢。失敗回傳False

#過期才執行，沒過期就從 stock csv 讀回資料
def _data_reuse(self, fun_name, init_vars, expire_hours):
    data_name= fun_name.replace('query_','')
    var_expire_time= "VAR_%s_ExpireTime"%data_name
    prev_data= self._df_prev_data
    
    #前置檢查，決定是否複製資料        
    if is_invalid(prev_data): #可能是None，若之前stock csv不存在，或是不包含此ticker
        agalog.info("  重新下載 %s，因為 stock csv 不存在"%(data_name))
        return var_expire_time, data_name
        
    diff_ticker= set(self._ticker_list).difference(prev_data.columns.to_list()) #這個還要確認
    if len(diff_ticker)>0:
        agalog.info("  重新下載 %s，因為 stock csv 股票不完整，缺少 %s"%(data_name, diff_ticker))
        return var_expire_time, data_name
        
    diff_var= set(init_vars+['通知訊息']).difference(prev_data.index)
    if len(diff_var)>0:
        agalog.info("  重新下載 %s，因為 stock csv 欄位不完整，缺少 %s"%(data_name, diff_var))
        return var_expire_time, data_name
        
    if var_expire_time not in prev_data.index:
        agalog.info("  重新下載 %s，因為 stock csv 欄位不完整，缺少 %s，可能因為上次查詢失敗"%(data_name, var_expire_time))
        return var_expire_time, data_name
    
    expire_time_str= prev_data[prev_data.columns[0]][var_expire_time]
    if is_invalid(expire_time_str):
        agalog.info("  重新下載 %s，因為 stock csv 的 var_expire_time 內容為空"%(data_name))
        return var_expire_time, data_name
        
    expire_time= datetime.strptime(expire_time_str, "%Y-%m-%d %H:%M:%S")        
    if datetime.now() >= expire_time:
        agalog.info("  重新下載 %s，因為 %.1f 小時效期已經過期"%(data_name, expire_hours))
        return var_expire_time, data_name
         

    #複製資料
    agalog.info("  沿用之前下載的 %s，因為 %.1f 小時效期尚未到期"%(data_name, expire_hours))
    for ticker in self._ticker_list:
        for var in init_vars:
            self._data[ticker][var]= get_valid_value3(prev_data, ticker, var)
        
        if is_valid(prev_data[ticker]['通知訊息']):
            for line in prev_data[ticker]['通知訊息'].split('<br>'):
                if data_name in line:
                    self._data[ticker]['通知訊息']+= "%s<br>"%line
    
    
    #複製之前的query time，注意不能以上for loop複製，因為上次的ticker0可能不同
    ticker0= self._ticker_list[0]
    self._data[ticker0][var_expire_time]= prev_data[prev_data.columns[0]][var_expire_time]    
    
    return None, None #代表資料複製完成


#成功query之後，填入 expire time
def _data_reuse_update_expire(self, var_expire_time, expire_hours):
    ticker0= self._ticker_list[0]
    expire_time= datetime.now() + timedelta(hours=expire_hours)  
    self._data[ticker0][var_expire_time]= datetime.strftime(expire_time,'%Y-%m-%d %H:%M:%S')       


#直接執行 func(), 但加上 init var, exception handler, 過期複製
#執行順序： _query_punish_stock() > QueryHandler_NoLoop.__call__() > wraps() > func() == _query_punish_stock()
class QueryHandler_NoLoop(object):
    def __init__(s, expire_hours=None, init_vars=[]):
        s.expire_hours= expire_hours
        s.init_vars= init_vars

    def __call__(s, func):
        def wrap(self, *args,**kwargs):
            agalog.info(func.__name__ + " (@QueryHandler_NoLoop)")
            if not self._init_done:
                raise Exception("執行 %s() 發生錯誤，尚未執行 init()"%func.__name__)
                
            #若有設定expire_hours並且尚未過期，就從 stock csv 複製資料
            data_name= ''
            if s.expire_hours is not None:
                var_expire_time, data_name= _data_reuse(self, func.__name__, s.init_vars, s.expire_hours)
                if var_expire_time is None: #代表資料複製成功
                    return True
            
            #執行實際function
            try:
                for ticker in self._ticker_list:
                    init_dic_var(self._data[ticker], s.init_vars)                 
                ret= func(self, data_name, *args,**kwargs)
            except Exception as e:
                self._add_err_msg("執行 %s 發生 exception, %s"%(func.__name__, get_exception_msg(e)))  
                return False
                
            #若有設定expire_hours就寫入expire time
            if s.expire_hours is not None:
                if ret:
                    _data_reuse_update_expire(self, var_expire_time, s.expire_hours)
                else:
                    self._add_warn_msg("  %s 查詢失敗，下次執行時將重新查詢，不等待 %d 小時效期"%(data_name, s.expire_hours))
                    
            return ret
            
        return wrap        
    

#使用 single-thread 對所有 ticker 執行函式
#執行順序： __main__ call query_info() > QueryHandler_ForLoop.__call__() > wraps() 
#        > 對所有 ticker 執行 func() == query_info()
class QueryHandler_ForLoop(object):
    def __init__(s, expire_hours=None, init_vars=[]):
        s.expire_hours= expire_hours
        s.init_vars= init_vars

    def __call__(s, func):
        def wrap(self):
            agalog.info(func.__name__ + " (@QueryHandler_ForLoop)")
            if not self._init_done:
                raise Exception("執行 %s() 發生錯誤，尚未執行 init()"%func.__name__)
            
            #若有設定expire_hours並且尚未過期，就從 stock csv 複製資料
            data_name= ''
            if s.expire_hours is not None:
                var_expire_time, data_name= _data_reuse(self, func.__name__, s.init_vars, s.expire_hours)
                if var_expire_time is None: #代表資料複製成功
                    return True
                    
            #執行實際function
            ret= True
            for ticker in self._ticker_list: 
                try:
                    tdata= self._data[ticker] #已經在__init__初始化為{}，不會是None
                    init_dic_var(tdata, s.init_vars) #初始化self._data[ticker][XXX]，亦為網頁顯示順序
                    prev_tdata= get_valid_value2(self._df_prev_data, ticker) #可能是None，若之前stock csv不存在，或是不包含此ticker
                    ret= ret and func(self, data_name, ticker, tdata, prev_tdata)                    
                except Exception as e:
                    self._add_err_msg("  %-5s: 執行 %s 發生 exception, %s"%(ticker, func.__name__, get_exception_msg(e)))
                    ret= False
                
            #若有設定expire_hours就寫入expire time
            if s.expire_hours is not None:
                if ret:
                    _data_reuse_update_expire(self, var_expire_time, s.expire_hours)
                else:
                    self._add_warn_msg("  %s 部分或全部股票查詢失敗，下次執行時將重新查詢，不等待 %d 小時效期"%(data_name, s.expire_hours))
                    
            return ret
            
        return wrap 

    
#使用 multi-thread 對所有 ticker 執行函式
#執行順序： __main__ call query_bband() > QueryHandler_ThreadLoop.__call__() > wraps()
#        > 對所有 ticker 執行 ===(thread)===>  multi_thread_exp_cather > func() == query_bband()
class QueryHandler_ThreadLoop(object):
    def __init__(s, expire_hours=None, init_vars=[]):
        s.expire_hours= expire_hours
        s.init_vars= init_vars

    def __call__(s, func):
        #在 function 外面加一層 exception handler
        def multi_thread_exp_cather(func, ret, self, data_name, ticker, tdata, prev_tdata):
            try:
                ret[0]= func(self, data_name, ticker, tdata, prev_tdata)
            except Exception as e:
                self._add_err_msg("  %-5s: 執行 %s 發生 exception, %s"%(ticker, func.__name__, get_exception_msg(e)))
                ret[0]= False
        
        def wrap(self):
            agalog.info(func.__name__ + " (@QueryHandler_ThreadLoop)")
            if not self._init_done:
                raise Exception("執行 %s() 發生錯誤，尚未執行 init()"%func.__name__)
            
            #若有設定expire_hours並且尚未過期，就從 stock csv 複製資料
            data_name= ''
            if s.expire_hours is not None:
                var_expire_time, data_name= _data_reuse(self, func.__name__, s.init_vars, s.expire_hours)
                if var_expire_time is None: #代表資料複製成功
                    return True
                
            #執行實際function
            threads= {}
            rets= {}
            for ticker in self._ticker_list: 
                tdata= self._data[ticker] #_data已經在__init__初始化為{}，不會是None
                init_dic_var(tdata, s.init_vars) #_data[ticker][XXX]，亦為網頁顯示順序
                prev_tdata= get_valid_value2(self._df_prev_data, ticker) #可能是None，若之前stock csv不存在，或是不包含此ticker
                rets[ticker]= [None]
                threads[ticker]= threading.Thread(target=multi_thread_exp_cather, args=(func, rets[ticker], self, data_name, ticker, tdata, prev_tdata))
                threads[ticker].start()
                if not MULTI_THREAD_SUPPORT:
                    threads[ticker].join()  
            
            #並等待Thread結束並計算回傳值            
            ret= True
            for ticker in self._ticker_list: 
                threads[ticker].join()
                ret= ret and rets[ticker][0]
                
            #若有設定expire_hours就寫入expire time
            if s.expire_hours is not None:
                if ret:
                    _data_reuse_update_expire(self, var_expire_time, s.expire_hours)
                else:
                    self._add_warn_msg("  %s 部分或全部股票查詢失敗，下次執行時將重新查詢，不等待 %d 小時效期"%(data_name, s.expire_hours))
                    
            return ret
            
        return wrap
        
    
#=========== Decorator Thread-Save ============
#在multi-thread function 中執行的 function 必須 thread-save，自訂function須由 @ThreadSaver 保護
#可槽狀進入
def ThreadSaver(func):
    @wraps(func)
    def wrap(self, *args, **kwds):
        self._thread_mutex.acquire()
        ret= func(self, *args, **kwds)
        self._thread_mutex.release()
        return ret
    return wrap
        

#=============================================================
class StockBase:
    #============ MEMBER VARIABLE ============       
    #csv 路徑，將在 init() 賦值
    _PATH_STOCK_CSV= None  
    _PATHNOTIFY_CSV= None 
    
    #RLock允許同一個thread重複lock，用於設計@ThreadSaver
    _thread_mutex= threading.RLock()  
    
    #init() 執行後設為 True
    _init_done= False  
    
    #儲存所有股票資料，例如 _data[ticker]['代號']. 
    _data= {}  
    
    #儲存 init() 讀取的 stock csv
    _df_prev_data= None   
    
    #儲存 ger_price() 讀取的歷史股價
    _df_price_list= None   
    
    #交給網頁顯示的訊息
    _web_msg= '' 
    
    #當query_price(), query_bband(), query_google_trend(), query_info() 等 function 需要通知LINE時，暫存 LINE 通知內容
    #由於 _df_notify_list[] 包含之前已送出的 notify csv 加上這次的新通知，使用 notified 欄位區別. push_out_line_notify()在寫入notify csv前會設定notified=True
    #欄位 notify_date, msg 目前無作用
    _df_notify_list= pd.DataFrame( {'ticker':[], 'name':[], 'expire_date':[], 'notify_date':[], 'reason':[], 'notified':[], 'msg':[]} )  

    
    #============ MEMBER FUNCTION - UNILITY ============
    @ThreadSaver
    def _add_warn_msg(self, msg:str) -> None:
        agalog.warning(msg)
        self._web_msg+= "[警告] " + msg.strip() + "<br>\n"
        
        
    @ThreadSaver
    def _add_err_msg(self, msg:str) -> None:
        agalog.error(msg)
        self._web_msg+= "[錯誤] " + msg.strip() + "<br>\n"
        

    #============ MEMBER FUNCTION ============
    #將 notify msg 加入 _df_notify_list
    @ThreadSaver
    def _queue_line_notify(self, ticker:str, name:str, reason:str, msg: str, data_name:str, expire_days) -> None:
        self._data[ticker]['通知訊息']+= '<div name="%s">%s<br>'%(data_name,reason)
        
        #忽略已通知過的訊息
        for i in range(len(self._df_notify_list['expire_date'])):
            if ticker==self._df_notify_list['ticker'].iloc[i] and reason==self._df_notify_list['reason'].iloc[i]:
                agalog.info("  忽略已通知過的訊息: %s"%msg.replace("\n","."))
                return
        
        #紀錄這次noitify，之前從notify csv讀出的notified=False，這次新加的notified=True
        notify_date= datetime.today() #type: datetime.datetime
        expire_date= notify_date + timedelta(days=expire_days) #type: datetime.datetime
        _df_new= pd.DataFrame(  {"notify_date":[notify_date], "expire_date":[expire_date], "reason":[reason], "ticker":[ticker], "name":[name], 'notified':[False], 'msg':msg} )
        self._df_notify_list= self._df_notify_list.append(_df_new)    
                
        
    #等所有資訊蒐集完，把 _queue_line_notify() 累積的 notify msg 加上 cust_msg 並送出
    def push_out_line_notify(self) -> None: 
        df= self._df_notify_list.loc[self._df_notify_list['notified']==False] # notified=False 代表這次新加的
        for i in range(len(df)):
            ticker= df.iloc[i]['ticker']                
            tdata= self._data[ticker]
            
            #即使部分資料還沒賦值，初始值為''，*100等於把字串成以一百倍，''還是''不會改變
            msg_tail= '此時股價%.1f位於布林位置%.1f%%, 布林寬度%.0f%%, 今天漲跌%.1f%%\n'%(tdata['股價'], tdata['布林位置']*100, tdata['布林寬度']*100, tdata['漲跌']*100)

            #WEB_BASE_URL 尾端如果有 '\' 已經在 init() 被移除
            if WEB_SERVER_PORT==80:
                URL_FULL= WEB_BASE_URL
            else:        
                URL_FULL= "%s:%d"%(WEB_BASE_URL,WEB_SERVER_PORT)
                
            cust_msg= self._get_cust_notify_msg(ticker) #台股處置股            
            msg2= "[%s]\n\n%s\n\n%s\n%s%s/%s/%s"%(datetime_str(), df.iloc[i]['msg'], msg_tail, cust_msg, URL_FULL, self.REGION, ticker)
            
            #通知LINE
            if LINEBOT_ID=='' or LINEBOT_TOKEN=='':
                agalog.info("  LINE通知(未設定ID不發出): %s"%df.iloc[i]['msg'].replace("\n",".")) 
            else:
                try:
                    agalog.info("  LINE通知: %s"%df.iloc[i]['msg'].replace("\n","."))
                    line_bot_api = LineBotApi(LINEBOT_TOKEN)  #事前準備 
                    line_bot_api.push_message(LINEBOT_ID, TextSendMessage(text=msg2))
                except LineBotApiError as e:
                    self._add_err_msg("  Line發送錯誤, 訊息:%s, %s"%(msg2, get_exception_msg(e)))
            
        #設為已通知
        self._df_notify_list['notified']= self._df_notify_list['notified'].apply(lambda x: True)  
        
        #儲存notify檔案，_df_notify_list的index沒設定，也不需儲存。此時的columns及index為:
        # columns  =>  Index(['ticker', 'name', 'expire_date', 'notify_date', 'reason', 'notified', 'msg']
        # index  =>  RangeIndex(start=0, stop=3, step=1)
        self._df_notify_list.to_csv(self._PATHNOTIFY_CSV, index=False)
        
        
    #輸出 stock csv
    def write_stock_csv(self):
        #給web_root.py看的資訊，放在table首位[0]，後面[1:]都不填
        ticker0= self._ticker_list[0]
        self._data[ticker0]['VAR_WebMsg']= self._web_msg 
        
        #yfinance 回報的股價更新時間
        if is_valid(self._df_price_list): #type: pd.core.frame.DataFrame
            self._data[ticker0]['VAR_PriceUpdateDate']= self._df_price_list.index[-1]
            
        #本來使用_data[ticker][XXX] 儲存，這是為了multi-thread當中，各個 thread 只存取自己的_data[ticker] dict，確保 thread-save
        #輸出前倒置為 _data[XXX][ticker] 的存取方式，給 web_root.py 顯示出來才是橫資料，縱軸股票
        df_data= pd.DataFrame(self._data).T
        
        #刪除TMP開頭的欄位，不寫數 csv
        for col in df_data.columns: 
            if "TMP_" in col:
                df_data= df_data.drop(col, axis = 1)
                
        #'通知訊息' 移到最後，給 web_root.py 顯示用
        if '通知訊息' in df_data:
            df_notify= df_data['通知訊息']
            df_data= df_data.drop('通知訊息', axis = 1)
            df_data['通知訊息']= df_notify
            
        #需要存入index，因為讀出來後，要用 df['代號'][ticker] 方式存取
        df_data.to_csv(self._PATH_STOCK_CSV, index=True)
                
                
    def init(self) -> None:    
        #檔案路徑
        self._PATH_STOCK_CSV= PATH_STOCK_CSV_REGION%self.REGION    #stock csv
        self._PATHNOTIFY_CSV= PATH_NOTIFY_CSV_REGION%self.REGION  #Line通知紀錄
        
        #印出設定檔
        agalog.info( "-----------------------------------------------------------")
        agalog.info(self._TITLE)
        agalog.info("DIR_BASE: %s"%DIR_BASE)
        agalog.info("PATH_STOCK_CSV: %s"%self._PATH_STOCK_CSV)
        agalog.info("PATHNOTIFY_CSV: %s"%self._PATHNOTIFY_CSV)
        
        #建立目錄
        os.makedirs( os.path.dirname(PATH_IMG_REGION), exist_ok=True)
        os.makedirs( os.path.dirname(self._PATH_STOCK_CSV), exist_ok=True)
        os.makedirs( os.path.dirname(self._PATHNOTIFY_CSV), exist_ok=True)
        
        #讀取notify csv
        if os.path.isfile(self._PATHNOTIFY_CSV):
            # 1 parse_dates 會把 notify_date, expire_date 讀取成 <class 'pandas._libs.tslibs.timestamps.Timestamp'>
            # 2 必須設定dtype，不然台股ticker 0050會讀成50
            # 3 push_out_line_notify() 存入時沒設定index，讀出來也不需要。讀出的columns及index為：
            #     columns  =>  Index(['ticker', 'name', 'expire_date', 'notify_date', 'reason', 'notified', 'msg']
            #     index  =>  RangeIndex(start=0, stop=3, step=1)
            df_notify_list= pd.read_csv( self._PATHNOTIFY_CSV, parse_dates= ['expire_date', 'notify_date'],
                                            dtype={'reason':str, 'ticker':str, 'name':str} )
            if df_notify_list.columns.tolist()==self._df_notify_list.columns.tolist():
                #理應都是 notified=True，但若真有False會造成 push_out_line_notify() 誤認新訊息，因此再寫一次True
                df_notify_list['notified']= df_notify_list['notified'].apply(lambda x: True)  
                self._df_notify_list= df_notify_list
            else:
                self._add_err_msg("%s 欄位不正確，放棄讀取，Column:%s"%(os.path.basename(self._PATHNOTIFY_CSV),df_notify_list.columns.tolist()))
        
        #移除過期的notify
        for i in reversed(range(len(self._df_notify_list['expire_date']))):  #必須要倒著算，如果從0往上算，刪除列會影響後面index導致錯誤
            if self._df_notify_list['expire_date'].iloc[i] <= datetime.today():
                agalog.info("  刪除過期LINE通知: %s %s => %s expire on %s"%(self._df_notify_list.iloc[i]['ticker'],self._df_notify_list.iloc[i]['name'],self._df_notify_list.iloc[i]['reason'],self._df_notify_list.iloc[i]['expire_date']) )
                self._df_notify_list= self._df_notify_list.drop( self._df_notify_list.index[[i]] )
        
        #讀取上次寫入的 stock csv
        df_prev_data, dummy, dummy= read_stock_summary_csv(self.REGION)
                
        if is_valid2(df_prev_data, '代號'):
            self._df_prev_data= df_prev_data.T
            agalog.info("stock csv 讀取成功")
        else:
            agalog.info("stock csv 讀取失敗")
        
        #確保ticker_list股票都是唯一的，刪除重複股票
        self._ticker_list= list(set(self._ticker_list))
        
        #刪除空字串股票，空字串會造成yf.download()報錯
        if '' in self._ticker_list:
            self._ticker_list.remove('')
        
        #刪除空字串和重複股票後，若股票是空的就報錯
        if len(self._ticker_list)==0:
            raise Exception("_ticker_list 內容為空")
            
        for ticker in self._ticker_list:
            self._data[ticker]= {} #確保_data[ticker]都有資料，後續操作即不用再判斷
            self._data[ticker]['通知訊息']= '' #確保_data[ticker]['通知訊息']都有資料，才能直接用 += 加新訊息
            
        #解決中文顯示問題
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']  
        plt.rcParams['axes.unicode_minus'] = False
        
        self._init_done= True

        
    #============ MEMBER FUNCTION - QUERY HANDLER ============
    
    #寫入股價資料： 股價，漲跌，成交金額，成交量
    #歷史股價寫到 self._df_price_list[]. 若是盤中，最新一筆為即時資料
    @QueryHandler_NoLoop( init_vars=['股價', '漲跌', '成交金額', '成交量'] )  #init_vars[] 為網頁顯示順序. 不能設定expire_hours, 因為此函式要寫入df_price_list[]給BBand使用
    def _query_price_yfinance(self, data_name, tickets_yf_str:str) -> None:
        #======== 下載 yfinance 歷史股價 ========
        #注意： yfinance 常下載到無資料的日期，若一支支股票下載日期會直接消失，因此需要整批股票一起下載，部分股票的無資料日才能顯示斷層
        start_date= datetime.now() - timedelta(days=STOCK_QUERY_DAYS)
        df_price_list= yf.download(tickers= tickets_yf_str, start=start_date, group_by='ticker', auto_adjust=False, progress=False)
        if is_invalid(df_price_list): #若股票都不存在， 會回傳 len(df_price_list)==0 的 dataframe， 但column都還是存在
            self._add_err_msg("  從 Yahoo Finance 讀不到任何股價")
            return False
            
        #yfinance 台股使用 2412.TW/6741.TWO 這種 ticker，但 _ticker_list 沒有 .TW/.TWO，為了後續處理方便，移除df_price_list的.TW/.TWO
        #此迴圈會讀到('AAA','Open')，('AAA','Close'),..., ('MSFT','Open') 等， col[0]重複相同ticker好幾次，但重複rename看來沒問題
        for col in df_price_list.columns: 
            if '.TWO' in col[0]:
                #agalog.debug("  %s remove .TWO"%(col[0]))
                df_price_list.rename(columns={col[0]:col[0].replace('.TWO','')}, inplace=True)
            elif '.TW' in col[0]:
                #agalog.debug("  %s remove .TW"%(col[0]))
                df_price_list.rename(columns={col[0]:col[0].replace('.TW','')}, inplace=True)
        
        #當天資料都是NaN可能是台股9:00-9:20尚無當天資料，刪除最新一天
        if YFINANCE_FIX_TW_TIME_SHIFT:
            for col in df_price_list.columns:
                if is_valid(df_price_list[col][-1]):
                    break
            else:
                self._add_warn_msg("  Yahoo Finance 讀回的股價最新一天 %s 都是 Nan，可能是台股延遲20分鐘，早上9:00-9:20尚無當天資料"%(df_price_list.index[-1]))
                df_price_list= df_price_list.drop( df_price_list.index[-1] )
            
            
        #======== 處理每支股票 ========
        for ticker in self._ticker_list:
            #確保網頁顯示都是新圖，如果錯誤中斷舊圖也已不存在
            img_ma= PATH_IMG_REGION%(self.REGION, ticker, "ma") 
            silence_remove(img_ma)  
            
            #若代號錯誤，yfinance 還是會包含ticker，但是內容全為NaN. dropna()會清空資料回傳len()==0的Dataframe
            if (ticker in df_price_list) and len(df_price_list[ticker].dropna())==0:
                #每次 drop 都是 Nan 的股票時，會印出 PerformanceWarning: dropping on a non-lexsorted multi-index without a level parameter may impact performance.
                #執行 remove_unused_levels() 可造成只印一次，不確定如何完全消除
                df_price_list.columns = df_price_list.columns.remove_unused_levels() 
                df_price_list.drop(ticker, axis=1, inplace=True)
                
            if (ticker not in df_price_list):
                self._add_err_msg("  %-5s: 從 Yahooo Finance 下載股價失敗"%ticker)
                continue
                
            try:
                tdata= self._data[ticker]
                df_price= df_price_list[ticker]
                
                if not df_check_columns(df_price, ['Open','High','Low','Close','Adj Close','Volume']):
                    self._add_err_msg("  %-5s: Yahoo Finance 讀回的股票欄位不正確，讀到 %s"%df_price.columns.to_list())
                    continue
                
                #當yfinance某些日期股價變成NaN，這日期之前數天的volume剛好乘以一百倍，此處還原正確volume，但最多連續還原20天，避免還原到真的爆量的天數
                if YFINANCE_FIX_HIGH_VOLUME:
                    volume_check= df_price['Volume'].median() * 30 #比中位數大30倍應該是觸發此問題
                    rollback_days= 0
                    #agalog.debug("  %-5s: volume-median=%d, volume_check=%d"%(ticker, df_price['Volume'].median(), volume_check))
                    for i in reversed(range(len(df_price['Volume']))):
                        if np.isnan(df_price['Volume'].iloc[i]):
                            #agalog.debug("  %-5s: (rollback_days=%02d) [%d] %s is NaA   ====> set rollback_days to 30"%(ticker, rollback_days, i, df_price_list.index[i]))
                            rollback_days= 20  #觀察發現Volume問題大概7-14天，設定20天為修正上限
                        elif rollback_days>0:
                            if df_price['Volume'].iloc[i] > volume_check:
                                #agalog.debug("  %-5s: (rollback_days=%d) [%d] %s = %.2f > volume_check %.2f ====> devide by 100"%(ticker, rollback_days, i, df_price_list.index[i], df_price['Volume'].iloc[i], volume_check))
                                df_price_list.loc[:, (ticker,'Volume')].iloc[i]/= 100
                                self._add_warn_msg("  %-5s: Yahoo Finance 股價 NaN 並且 Volume 爆量，可能觸發 bug，啟動修復機制"%(ticker))
                                rollback_days-= 1
                                if rollback_days==0:
                                    self._add_err_msg("  %-5s: Yahoo Finance 的 Volumne 從 Nan 回修 20 天還是有爆量 Volume， 可能尚未修完或有其他錯誤"%(ticker))
                            else:
                                #agalog.debug("  %-5s: (rollback_days=%d) [%d] %s = %.2f <= volume_check %.2f ====> set rollback_days to 0"%(ticker, rollback_days, i, df_price_list.index[i], df_price['Volume'].iloc[i], volume_check))
                                rollback_days= 0
                            
                tdata= self._data[ticker]
                tdata['股價']= df_price['Close'][-1]
                tdata['漲跌']= (df_price['Close'][-1] / df_price['Close'][-2] ) - 1
                tdata['成交量']= df_price['Volume'][-1]  
                tdata['成交金額']= tdata['成交量'] * tdata['股價']  #今日成交金額, 使用成交價 x 成交量估算
                agalog.debug("  %-5s: 股價%.2f, 漲跌%.0f%%, 成交量%.0f, 成交金額%.0f"%(ticker, tdata['股價'], tdata['漲跌']*100, tdata['成交量'], tdata['成交金額']))
                
                #======== 繪製紅綠燭型圖 ========
                now = datetime.now()
                weekday= now.weekday()  #0-6 代表週一到週日
                if weekday in range(0,2):
                    dend = now + timedelta(days=7-weekday)   #若今天是周一到周三，就畫圖到下周一，右邊才有空間繪製股價數值
                else: #周日為7
                    dend = now + timedelta(days=7-weekday+7)   #若今天是週四到周日，就畫圖到第二個周一，右邊才有空間繪製股價數值
                dstart = dend + timedelta(days=-DIAGRAM_DAYS)
                
                df_ma= df_price.copy() #先複製再修改，才不會影響後續繪圖
                df_ma.index = pd.DatetimeIndex(df_ma.index) 
                mc = mpf.make_marketcolors(up='r', down='g', edge='', wick='inherit', volume='inherit')  #上漲紅色，下跌綠色
                s = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=mc)
                title= "%s %s MA5/MA10/MA20/MA60 均線圖"%(ticker, tdata['名稱'])
                fig,ax= mpf.plot(df_ma, type='candle', style=s, mav=(5, 10, 20, 60), title=title, ylabel_lower='成交量', ylabel='股價', 
                        volume=True,  figsize=(14,7.5), returnfig=True, columns=['Open', 'High', 'Low', 'Close', 'Volume'],
                        xlim=(dstart, dend), #不能用獨立的\plt.xlim(left=dstart, right=dend)，無法顯示線，原因不明
                        #savefig=dict(fname=img_ma,bbox_inches='tight')
                        )
                fig.savefig(fname=img_ma,bbox_inches='tight')
                plt.close(fig)
                
            except (TypeError, KeyError) as e:  #_df_prev_data==None觸發TypeError, _df_prev_data["本益比"]不存在觸發KeyError
                self._add_err_msg("  %s 處理歷史股價發生 exception, %s"%(ticker, get_exception_msg(e)))
        
        self._df_price_list= df_price_list
        return True
                
                

    #寫入財報資料： 布林位置，布林寬度，(通知訊息)
    #前提條件: query_price() 已執行過，並將歷史股價寫入 _df_price_list[ticker] 
    #注意： yfinance 寫入 _df_price_list[ticker] 的股價有些是NaN，導致upper, middle, lower 等回傳值都是 NaN
    @QueryHandler_ThreadLoop( init_vars=['布林位置','布林寬度'] )  #init_vars[] 為網頁顯示順序
    def query_bband(self, data_name, ticker, tdata, prev_tdata) -> bool:        
        #確保網頁顯示都是新圖，如果錯誤中斷舊圖也已不存在
        img_bb= PATH_IMG_REGION%(self.REGION, ticker, "bb") 
        silence_remove(img_bb) 
        
        if is_invalid(self._df_price_list) or (ticker not in self._df_price_list):
            self._add_err_msg("  %-5s: 忽略 BBand 計算，因為沒有股價資料"%ticker)
            return False
            
        df_price= self._df_price_list[ticker]
        upper, middle, lower= talib.BBANDS( df_price['Close'], timeperiod=BBAND_DAYS, nbdevup=2, nbdevdn=2, matype=0)    
        close_today= df_price['Close'][-1]
        lower_today= last(lower)
        upper_today= last(upper)
        middle_today= last(middle) 
        bb_width= (upper_today/middle_today - 1)*2  #因為lower有可能是負數，不能直接用upper/lower
        
        if bb_width >= BBAND_WIDTH_DISPLAY_MIN:
            tdata['布林位置']=  (close_today - lower_today) / (upper_today - lower_today) 
            agalog.debug("  %-5s: bb_width=%.2f, upper_today=%.2f, middle_today=%.2f, lower_today=%.2f"%(ticker, bb_width, upper_today, middle_today, lower_today))
             
            #LINE通知
            if tdata['布林位置'] <= NOTIFY_BBAND_LOWER:
                notify_lower_price= NOTIFY_BBAND_LOWER * (upper_today - lower_today)  +  lower_today
                reason= "股價低於布林通道下緣" #注意: NOTIFY_BBAND_LOWER可能不是剛好下緣，例如設為0.1 (10%) 即為下緣上方，但文字統一寫下緣
                msg= "%s: %s %s股價%.1f低於布林通道下緣%.1f"%(self.REGION_TEXT, ticker, tdata['名稱'], close_today, notify_lower_price)
                self._queue_line_notify(ticker, tdata['名稱'], reason, msg, data_name, expire_days=6)  #若在布林通道下緣來回震盪，6 天內不會重複通知

        tdata['布林寬度']= bb_width
        now = datetime.now()
        weekday= now.weekday()  #0-6 代表週一到週日
        if weekday in range(0,2):
            dend = now + timedelta(days=7-weekday)   #若今天是周一到周三，就畫圖到下周一，這樣才有空間繪製股價數值
        else: #周日為7
            dend = now + timedelta(days=7-weekday+7)   #若今天是週四到周日，就畫圖到第二個周一，這樣才有空間繪製股價數值
        dstart = dend + timedelta(days=-DIAGRAM_DAYS)

        #======== 布林通道圖 ======== 
        self._thread_mutex.acquire()  #matplotlib不是thread-save，需要被保護
        df_bb= pd.DataFrame();
        df_bb['收盤價']= df_price['Close']
        df_bb['上緣']= upper
        df_bb['下緣']= lower
        df_bb['中線MA20']= middle
        df_bb.index = pd.DatetimeIndex(df_price.index) #要有日期作為index, 橫軸裁示時間
        ax = df_bb.plot.line(  figsize=(12,4),  title="%s %s 布林通道圖"%(ticker,tdata['名稱']), color={'收盤價':COLOR_ORANGE, '上緣':COLOR_RED, '下緣':COLOR_GREEN, '中線MA20':COLOR_GRAY})
        
        #樣式
        ax.yaxis.tick_right() 
        ax.yaxis.set_label_position("right") 
        ax.xaxis.set_major_locator( mdates.WeekdayLocator(byweekday=(MO)) ) #mdates.DayLocator(7)會造成刻度顯示不在最新一天，但WeekdayLocator()會在最新天  
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))    
        plt.xlim(left=dstart, right=dend)  #X軸時間區間    
        ax.xaxis.set_minor_locator( plt.NullLocator() ) #Google Trend圖需要此行才能隱藏次刻度，但布林通道不用，原因不明

        ax.xaxis.grid(True, which='major')
        plt.xticks(rotation=40)   #X軸刻度斜著顯示
        for tick in ax.get_xticklabels(): #X軸刻度靠右對齊
            tick.set_horizontalalignment('right') #Google Trend若沒此行，會變成置中對齊
        plt.xlabel('')
        plt.ylabel('即時股價')
        
        df= df_price.loc[ df_price['Close'].apply(lambda x: not np.isnan(x))  ]  #yfinance有bug會些部分日期的股價為NaN，需去除NaN留下正確數字            
        price= df['Close'][-1]
        date_str= date_to_md(df.index[-1])            
        x_text= df_price.index[-1] + timedelta(days=1)
        plt.text(x_text, price, '%.1f\n( %s )'%(price, date_str), ha='left', va= 'center',fontsize=12, color=COLOR_ORANGE )
        plt.legend(loc="best", bbox_to_anchor=(1.2, 1.03)) #Legend放在圖右側，避免覆蓋數值文字
        fig = ax.get_figure()
        fig.savefig(fname=img_bb, bbox_inches='tight')
        plt.close(fig)
        self._thread_mutex.release()
        return True

            
            
    #前提： get_stock_data() 寫好_data: TMP_GTName
    #寫入資料： G-Trend，G-Trend漲跌，HD_GT_URL
    @QueryHandler_ThreadLoop( expire_hours=GTREAD_EXPIRE_HOURS, init_vars=['G-Trend','G-Trend漲跌', 'HD_GT_URL'] )  #init_vars[] 為網頁顯示順序
    def query_google_trend(self, data_name, ticker, tdata, prev_tdata) -> None:
        #ETF不查詢 Google Trend，未設定 TMP_GTName 也不查詢
        if is_invalid(tdata['TMP_GTName']):  
            agalog.debug("  %-5s:　未設定  Google Trend 字串，不查詢 Google Trend"%(ticker))
            return True
        elif tdata['產業']=='ETF':  
            agalog.debug("  %-5s: ETF 不查詢 Google Trend"%(ticker))
            return True
            
            
        #=============== 變數準備 ===============
        gt_name= tdata["TMP_GTName"]
        name= tdata["名稱"]
        tdata['HD_GT_URL']= "https://trends.google.com.tw/trends/explore?date=today%203-m&geo=" + self.REGION.upper() +"&q=" + gt_name.replace(" ","%20")
        msg_gt= "\n\n" + tdata['HD_GT_URL']
        img_gtrend= PATH_IMG_REGION%(self.REGION, ticker, "gtrend") 
        
        #確保網頁顯示都是新圖，如果錯誤中斷舊圖也已不存在
        silence_remove(img_gtrend)   
        
        #========== 查詢 Google Trend ==========        
        # 若使用'today 12-m'，不滿一週的部分partial=False，如果從上個完整周計算的話，資料可能延後1-6天，所以改成'today 1-m' or 'today 3-m'手動計算MA7移動平均線
        # 若使用'now 7-d', 雖然可以去除近三天資料，但只有七天不足以判斷
        # 最後使用'toady 3-m', 有每日資料，缺點是近三天的資料沒有, 例如今天是2021/7/14, 最新資料只到2021/7/11
        try:
            pytrend= TrendReq(hl='zh-TW', tz=360) #實驗過設定 hl='zh-TW' or 'en-US' 結果完全相同
            pytrend.build_payload(kw_list=[gt_name], cat=0, timeframe='today 3-m', geo=self.REGION.upper(), gprop='') #一次最多查詢五個字串，此處只查一個
            df_gtrend= pytrend.interest_over_time()
        except ResponseError as e:
            self._add_err_msg("  %-5s: Google Trend 搜尋失敗，%s"%(ticker, get_exception_msg(e)))
            return False
            
        if len(df_gtrend) < 10:
            self._add_warn_msg("  %-5s: Google Trend 下載資料過少，只有 %d 筆"%(ticker, len(df_gtrend)))
            return False
            
        #計算七日移動平均
        #注意：Google Trend 週末搜尋量劇減，用單日比較若比到週末不公平，八日九日都會計算到週末，七日或七日倍數最適合
        df_gtrend['MA7'] =talib.MA(df_gtrend[gt_name], timeperiod=7, matype=0)
        tdata["G-Trend"]= df_gtrend['MA7'][-1]
        
        #============== 漲跌計算及LINE通知 ==============
        #Google Trend MA7 太小就不計算漲跌
        if (df_gtrend['MA7'][-1]<GTREND_MA7_RATE_DISPLAY_MIN) and (df_gtrend['MA7'][-8]<GTREND_MA7_RATE_DISPLAY_MIN):
            agalog.debug("  %-5s: Google Trend 本週 MA7 (%d) 和上週 MA7 (%d) 均小於 %d，不計算漲跌"%(ticker, df_gtrend['MA7'][-1], df_gtrend['MA7'][-8], GTREND_MA7_RATE_DISPLAY_MIN))
        else:
            #MA7漲跌計算
            if df_gtrend['MA7'][-8]==0:
                gt_ma7_rate= float((df_gtrend['MA7'][-1] / 1                     ) - 1)
            else:
                gt_ma7_rate= float((df_gtrend['MA7'][-1] / df_gtrend['MA7'][-8]) - 1)
            tdata["G-Trend漲跌"]= gt_ma7_rate
            
            #MA7漲跌 - LINE通知
            if gt_ma7_rate <= NOTIFY_GT_MA7_FALL_RATE and df_gtrend['MA7'][-2]>=NOTIFY_GT_MA7_FALL_FROM:
                reason= "Google Trend MA7 降低"
                msg= "%s: %s %s 的 Google Trend MA7從上週 %.0f 降低至本週 %.0f (%.1f%%)"%(self.REGION_TEXT, ticker, name, df_gtrend['MA7'][-8], df_gtrend['MA7'][-1], gt_ma7_rate*100 )
                self._queue_line_notify(ticker, tdata['名稱'], reason, (msg+msg_gt), data_name, expire_days=1)
            
            if gt_ma7_rate >= NOTIFY_GT_MA7_RISE_RATE and df_gtrend['MA7'][-1]>=NOTIFY_GT_MA7_RISE_TO:
                reason= "Google Trend MA7 拉高"
                msg= "%s: %s %s 的 Google Trend MA7從上週 %.0f 拉高至本週 %.0f (%.1f%%)"%(self.REGION_TEXT, ticker, name, df_gtrend['MA7'][-8], df_gtrend['MA7'][-1], gt_ma7_rate*100 )
                self._queue_line_notify(ticker, tdata['名稱'], reason, (msg+msg_gt), data_name, expire_days=1)

            #trend MA1 up
            gt_min_prev= min(df_gtrend[gt_name][-2], df_gtrend[gt_name][-3], df_gtrend[gt_name][-4])
            if gt_min_prev==0:
                gt_min_prev= 1
            gt_raise_rate= float( df_gtrend[gt_name][-1] / gt_min_prev ) - 1
            
            #trend MA1 up - LINE通知
            if gt_raise_rate >= NOTIFY_GT_RISE_RATE and df_gtrend[gt_name][-1]>df_gtrend[gt_name][:len(df_gtrend[gt_name])-4].max()*2:
                reason= "Google Trend 三日內急升"
                msg= "%s: %s %s 的 Google Trend 三日內從 %.0f 急升至%.0f (%.1f%%)，並超過三個月最大值%.0f一倍以上"%(self.REGION_TEXT, ticker, name, gt_min_prev, df_gtrend[gt_name][-1], gt_raise_rate*100, df_gtrend[gt_name][:len(df_gtrend[gt_name])-4].max() )	
                self._queue_line_notify(ticker, tdata['名稱'], reason, (msg+msg_gt), data_name, expire_days=1)

            #trend MA1 down
            gt_max_prev= max(df_gtrend[gt_name][-2], df_gtrend[gt_name][-3], df_gtrend[gt_name][-4])
            if gt_max_prev==0:
                gt_max_prev= 1
            gt_down_rate= float( df_gtrend[gt_name][-1] / gt_max_prev ) - 1
            agalog.debug("  %-5s: Google Trend ma7: %.0f -> %.0f (%.1f%%), up: %.0f -> %.0f (%.1f%%), down: %.0f -> %.0f (%.1f%%)"%(ticker, 
                                df_gtrend['MA7'][-8],df_gtrend['MA7'][-1], tdata["G-Trend漲跌"]*100,
                                gt_min_prev,df_gtrend[gt_name][-1], gt_raise_rate*100,
                                gt_max_prev,df_gtrend[gt_name][-1], gt_down_rate*100))
                    
            #trend MA1 down - LINE通知
            if gt_down_rate <= NOTIFY_GT_FALL_RATE and df_gtrend[gt_name][-1]<df_gtrend[gt_name][:len(df_gtrend[gt_name])-4].min()*0.5:
                reason= "Google Trend 三日內急降"
                msg= "%s: %s %s 的 Google Trend 三日內從 %.0f 急降至%.0f (%.1f%%)，並小於三個月最小值%.0f一半"%(self.REGION_TEXT, ticker, name, gt_max_prev, df_gtrend[gt_name][-1], gt_down_rate*100, df_gtrend[gt_name][:len(df_gtrend[gt_name])-4].min())
                self._queue_line_notify(ticker, tdata['名稱'], reason, (msg+msg_gt), data_name, expire_days=1)
            
        #================ 繪圖 ================
        self._thread_mutex.acquire()  #matplotlib不是thread-save，需要被保護
        now = datetime.now()
        weekday= now.weekday()  #0-6 代表週一到週日
        if weekday in range(0,2):
            dend = now + timedelta(days=7-weekday)   #若今天是周一到周三，就畫圖到下周一，這樣才有空間繪製股價數值
        else: #周日為7
            dend = now + timedelta(days=7-weekday+7)   #若今天是週四到周日，就畫圖到第二個周一，這樣才有空間繪製股價數值
        dstart = dend + timedelta(days=-DIAGRAM_DAYS)

        ax = df_gtrend.plot.line(  figsize=(12,4),  title="%s %s Google Trend (查詢字串： %s)"%(ticker, name, gt_name), color={'MA7':COLOR_ORANGE, gt_name:COLOR_GRAY})
        plt.xlim(left=dstart, right=dend)  #Y軸時間區間
        plt.ylim(-5, 105)  #X軸時間區間
        ax.yaxis.tick_right() 
        ax.yaxis.set_label_position("right") 
        ax.xaxis.set_major_locator( mdates.WeekdayLocator(byweekday=(MO)) ) #mdates.DayLocator(7)會造成刻度顯示不在最新一天，但WeekdayLocator()會在最新天
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.grid(True, which='major') #x坐标轴的网格使用主刻度
        ax.xaxis.set_minor_locator( plt.NullLocator() )
        plt.xticks(rotation=40)   #X軸刻度斜著顯示
        
        for tick in ax.get_xticklabels(): #X軸刻度靠右對齊
            tick.set_horizontalalignment('right') #Google Trend若沒此行，會變成置中對齊
        plt.xlabel('')
        plt.ylabel('Google Trend')

        #避免Trend和Trend MA7數值標示重疊。fontsize 12，字母的高度在Y軸0-100當中, 兩排字距離7比較好看
        y_text_ma7= df_gtrend['MA7'][-1] 
        y_text_trend= df_gtrend[gt_name][-1]
        diff= abs(y_text_trend - y_text_ma7)
        if abs(y_text_trend - y_text_ma7) <= 7:
            if y_text_trend > y_text_ma7:
                y_text_trend+= ( 7- diff ) / 2
                y_text_ma7-= ( 7 - diff ) / 2
            else:
                y_text_trend-= ( 7 - diff ) / 2
                y_text_ma7+= ( 7 - diff ) / 2

        plt.legend(loc="best", bbox_to_anchor=(1.17, 1.01)) #Legend放在圖右側，避免覆蓋數值文字
        x_text = last(df_gtrend.index) + timedelta(days=1)
        plt.text( x_text, y_text_trend, '%.0f'%df_gtrend[gt_name][-1],  ha='left', va= 'center',fontsize=12, color=COLOR_GRAY )
        plt.text( x_text, y_text_ma7,   '%.0f ( %s )'%(df_gtrend['MA7'][-1],date_to_md(last(df_gtrend.index))),  ha='left', va= 'center',fontsize=12, color=COLOR_ORANGE )
        fig = ax.get_figure()
        fig.savefig(fname=img_gtrend, bbox_inches='tight')
        plt.close(fig)
        self._thread_mutex.release()
        return True
   