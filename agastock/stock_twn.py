# -*- coding: utf-8 -*-
#=============================================================
# <agastock>
# stock_twn.py
# 分析台股用的 StockTwn
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
#from IPython.core.display import HTML
from pyquery import PyQuery as pq
from urllib.error import * #HTTPError
import twstock, requests, io


#=========== FinMind ============ 
_FM_URL_DATA = "https://api.finmindtrade.com/api/v4/data"
_FM_URL_SNAPSHOT= "https://api.finmindtrade.com/api/v4/taiwan_stock_tick_snapshot"


class StockTwn(StockBase):
    #=========== PARAMETER ============
    #股票清單
    _ticker_list= TW_TICKET_LIST

    #台股Google Trend預設使用證交所名稱，但像雄獅會搜尋到雄獅文具，就需要覆寫在下表
    #空字串代表不搜尋Google Trend。 ETF不用特別寫會自動忽略
    __gt_name_overwrite_list= TW_GT_NAME_OVERWRITE_LIST


    #=========== 一般設定 ============ 
    _TITLE= "[TW STOCK PARSER]"  #標題，用於log首行
    REGION= "tw"
    REGION_TEXT= "台股"
    

    #============ MEMBER VARIABLE ============
    __punish_list= {}


    #============ PRIVITE FUNCTION ============
	#取得處置股字串
    def _get_cust_notify_msg(self, ticker) -> str:
        msg= ''
        if is_valid2(self.__punish_list, ticker):
            msg= "處置：%s\n\n"%self.__punish_list[ticker].replace("分:","分 ")
        return msg


    def __get_url_csv(self, url, data_name='', iStart=None, iEndBoundary=None, exp_columns=[], min_rows=0, decode='big5'):
        try:
            csv = requests.get(url, timeout=URL_TIMEOUT_SEC).content.decode(decode)
            csv= '\r\n'.join( csv.split("\r\n")[iStart:iEndBoundary] ) #如果資料行數不夠，[:]不會造成exception，頂多回傳空陣列
            df= pd.read_csv( io.StringIO(csv) )
            
            if len(df) < min_rows:
                self._add_warn_msg("  __get_url_csv 讀取'%s'得到的資料太少，預期至少%d筆但只得到%d筆. url:%s"%(data_name, min_rows, len(df), url)) 
                return None
            elif not df_check_columns(df, exp_columns): #欄位不正確的狀況沒實際遇過
                self._add_warn_msg("  __get_url_csv 讀取'%s'得到的欄位不正確, 預期%s, 實際為%s. url:%s"%(data_name, exp_columns, df.columns, url)) 
                return None
        
            return df
            
        except (ResponseError, KeyError, ConnectionError, InvalidURL, InvalidSchema, UnicodeError, MissingSchema, ReadTimeout) as e: 
            #ResponseError是FinMind query超過次數, KeyError是FinMind API名稱輸入錯誤例如TaiwanStockInfo輸入成TaiwanStockInfoXXX
            #ConnectionError是DNS解析錯誤, InvalidURL是網址DNS解析失敗可能網址打錯, InvalidSchema是http協定打錯, UnicodeError可能是網址錯誤造成回傳資料不是big5
            #MissingSchema是網址空白
            self._add_warn_msg("__get_url_csv 讀取'%s'失敗, %s"%(data_name, get_exception_msg(e))) 
            return None        


    def __query_finmind(self, param={}, data_name='', min_rows=0, exp_columns=[], fm_url=_FM_URL_DATA, index_col=None):
        try:
            param2= param.copy()  #使用param2來request url，但印出錯誤時使用原來的param，才不會把私人資料token也印出
            param2['token']= TW_FM_TOKEN
            resp_json = requests.get(fm_url, params=param2, timeout=URL_TIMEOUT_SEC).json()  #params為GET參數
            data= pd.DataFrame(resp_json["data"])
            
            if len(data) < min_rows:
                self._add_warn_msg("  __query_finmind 讀取'%s'得到的資料太少，預期至少%d筆但只得到%d筆. Param: %s"%(data_name, min_rows, len(data), param)) 
                return None
            elif not df_check_columns(data, exp_columns): #欄位不正確的狀況沒實際遇過
                self._add_warn_msg("  __query_finmind 讀取'%s'得到的欄位不正確, 預期%s, 實際為%s. Param: %s"%(data_name, exp_columns, data.columns, param)) 
                return None
        
            if index_col is not None:
                data.index= data[index_col]
            return data
            
        except (ResponseError, KeyError, ConnectionError, InvalidURL, InvalidSchema, UnicodeError, MissingSchema, ReadTimeout) as e: 
            #ResponseError是FinMind query超過次數, KeyError是FinMind API名稱輸入錯誤例如TaiwanStockInfo輸入成TaiwanStockInfoXXX
            #ConnectionError是DNS解析錯誤, InvalidURL是網址DNS解析失敗可能網址打錯, InvalidSchema是http協定打錯, UnicodeError可能是網址錯誤造成回傳資料不是big5
            #MissingSchema是網址空白
            self._add_warn_msg("[錯誤] __query_finmind 讀取'%s'失敗. Param: %s, %s"%(data_name, param, get_exception_msg(e))) 
            return None

    #============ PUBLIC FUNCTION ============
    #初始化，並處理台股美股不同的資料，目前只有台股的處置股，寫入(通知訊息)
    #處置股儲存於 _df_pusish_list[]
    def init(self):
        super().init()

        #台股處置股寫入_df_pusish_list[]
        self._query_punish_stock()
    
    
    #============ PUBLIC FUNCTION - get_XXX 系列取得股票資訊 ============
    #寫入處置股清單. 從櫃買中心讀取，不能太頻繁
    @QueryHandler_NoLoop() #不需要init_var. 不能使用expire_hours，因為_data_reuse()不會複製__punish_list[]，但LINE通知訊息需要它
    def _query_punish_stock(self, data_name) -> bool:                
        pun_name_list= {}
            
        #上市處置股
        df= self.__get_url_csv(url="https://www.twse.com.tw/announcement/punish?response=csv&startDate=&endDate=",
                        data_name="上市處置股",
                        iStart=1, iEndBoundary=-1, #第一行說明資料日期沒用，最後兩行沒資料(-1代表最後兩行都捨棄)
                        exp_columns=["證券代號","處置起迄時間","處置內容",],
                        decode='big5')
        if df is not None:
            for i in df.index:
                #[上市處置內容]
                #１處置原因：該有價證券之交易，最近十個營業日內已有六個營業日達本公司「公布注意交易資訊」標準，且該股票於最近三十個營業日內曾發布處置交易資訊。
                #２處置期間：自民國一百十年七月七日起至一百十年七月二十日﹝十個營業日，如遇：
                #  ａ有價證券最後交易日在處置期間，僅處置至最後交易日，
                #  ｂ有價證券停止買賣、全日暫停交易則順延執行，
                #  ｃ開休市日變動則調整處置迄日〕。
                #３處置措施：
                #  ａ以人工管制之撮合終端機執行撮合作業（約每二十分鐘撮合一次）。
                #  ｂ所有投資人每日委託買賣該有價證券時，應就其當日已委託之買賣，向該投資人收取全部之買進價金或賣出證券。
                #  ｃ信用交易部分，應收足融資自備款或融券保證金。有關信用交易了結部分，則依相關規定辦理。 
                #agalog.info("%s => %s"%(i,df['處置內容'].iloc[i]))
                if "每九十分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "90分:"
                elif "每六十分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "60分:"
                elif "每四十五分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "45分:"
                elif "每二十五分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "25分:"
                elif "每二十分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "20分:"
                elif "每十五分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "15分: "
                elif "每十分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "10分: "
                elif "每五分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "5分:"
                else:
                    text= "未知的處置：%s"%df['處置內容'].iloc[i]
                
                #110/07/07~110/07/20
                text+= " %s"%df["處置起迄時間"].iloc[i]  #注意上櫃是"起訖"，上市是"起迄"，兩個欄位名不同，不能複製貼上
                
                #一支股票可能被處置多次，多行用<br>分隔
                ticker= str(df['證券代號'].iloc[i]) #上市可以直接比對'證券代號'，但跟著上櫃一起轉str更安全
                pun_name_list[ticker]= df['證券名稱'].iloc[i]
                if ticker in self._ticker_list:
                    if ticker not in self.__punish_list:
                        self.__punish_list[ticker]= text
                    else:
                        self.__punish_list[ticker]+= ", " + text
                    agalog.debug( "  [上市] 找到處置股在清單中 (%s %s) => %s"%(ticker, df['證券名稱'].iloc[i], text))
                else:
                    agalog.debug( "  [上市] 找到不在清單中的處置股 (%s %s) => %s"%(ticker, df['證券名稱'].iloc[i], text))
         
      
        #上櫃處置股
        t= time.localtime()
        roc_date= "%d/%02d/%02d"%(t.tm_year-1911, t.tm_mon, t.tm_mday) # 西元 2011/07/14 轉成民國 110/07/14，上櫃處置參數需要民國年
        
        #若不指定起訖日期，則預設為昨天到今天，也就是昨天處置結束的股票還在. 因此指定起訖都是今天，只顯示今天還在處置期的上櫃股
        df= self.__get_url_csv(url="https://www.tpex.org.tw/web/bulletin/disposal_information/disposal_information_download.php?l=zh-tw&sd=%s&ed=%s"%(roc_date,roc_date),
                        data_name="上櫃處置股",
                        iStart=2, iEndBoundary=-3, #第兩行說明資料日期沒用，最後四行沒資料(-3代表最後四行都捨棄)
                        exp_columns=["證券代號","處置起訖時間","處置內容",], #注意上櫃是"起訖"，上市是"起迄"，兩個欄位名不同，不能複製貼上
                        decode='big5')
        if df is not None:
            for i in df.index:                
                #[上櫃處置內容]
                #因連續3個營業日達本中心作業要點第四條第一項第一款經本中心公布注意交易資訊，爰自110年07月02日起10個營業日(110年07月02日至110年07月15日，如遇休市、
                #有價證券停止買賣、全日暫停交易則順延執行)改以人工管制之撮合終端機執行撮合作業(約每5分鐘撮合一次)，各證券商於投資人每日委託買賣該有價證券數量單筆達10
                #交易單位或多筆累積達30交易單位以上時，應就其當日已委託之買賣，向該投資人收取全部之買進價金或賣出證券。信用交易部分，則收足融資自備款或融券保證金。但信用
                #交易了結及違約專戶委託買賣該有價證券時，不在此限。         
                #agalog.info("%s => %s"%(i,df['處置內容'].iloc[i]))
                if "每90分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "90分:"
                elif "每60分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "60分:"
                elif "每45分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "45分:"
                elif "每25分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "25分:"
                elif "每20分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "20分:"
                elif "每15分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "15分:"
                elif "每10分鐘撮合一次" in df['處置內容'].iloc[i]:
                    text= "10分:"
                elif "每5分鐘撮合一次" in df['處置內容'].iloc[i]:
                    #text= "5分/單筆十張或累積30張則全額交割"
                    text= "5分:"
                else:
                    text= ""
                    self._add_warn_msg("  %-5s: 處置內容找不到每幾分鐘交割，訊息： %s"%(ticker,df['處置內容'].iloc[i]))
                
                #110/07/07~110/07/20
                text+= " %s"%df["處置起訖時間"].iloc[i]  #注意上櫃是"起訖"，上市是"起迄"，兩個欄位名不同，不能複製貼上
                 
                #一支股票可能被處置多次，多行用<br>分隔
                ticker= str(df['證券代號'].iloc[i]) #上櫃的'證券代號'是Numpy type，要轉成str比對，不然會不符合
                pun_name_list[ticker]= df['證券名稱'].iloc[i]
                if ticker in self._ticker_list:
                    if ticker not in self.__punish_list:
                        self.__punish_list[ticker]= text
                    else:
                        self.__punish_list[ticker]+= ", " + text
                    agalog.debug( "  [上櫃] 找到不在清單中的處置股 (%s %s) => %s"%(ticker, df['證券名稱'].iloc[i], text))
                else:
                    agalog.debug( "  [上櫃] 找到處置股在清單中 (%s %s) => %s"%(ticker, df['證券名稱'].iloc[i], text))
           
        for ticker in self._ticker_list:
            if ticker in self.__punish_list:
                reason= "處置股 %s"%(self.__punish_list[ticker])
                msg= "台股: %s %s列處置股, %s"%(ticker, pun_name_list[ticker], self.__punish_list[ticker])
                
                #處置14天就結束，二次處置日期不同，應該會因為reason可以重複通知
                self._queue_line_notify(ticker, pun_name_list[ticker], reason, msg, data_name, expire_days=14)
                
        return True
                
        
    #寫入基本資料： 代號，名稱，產業，TMP_GTName
    #前提： query_info() 已經執行，並填入 __gt_name_overwrite_list[]
    @QueryHandler_ForLoop( init_vars=['代號','名稱', '產業', 'TMP_GTName'] ) #init_vars[] 為網頁顯示順序
    def query_info(self, data_name, ticker, tdata, prev_tdata) -> bool:  
        tdata['代號']= ticker        
        tdata['名稱']= ''
        tdata['產業']= ''    
        if ticker in twstock.codes:
            tdata['名稱']= twstock.codes[ticker].name
            if twstock.codes[ticker].type=='ETF':
                tdata['產業']= 'ETF'
            else:
                tdata['產業']= twstock.codes[ticker].group.replace("工業","").replace("事業","").replace("金融保險","金融")\
                                .replace("生技醫療","生技").replace("電子商務","電商").replace("其他電子類","電子").replace("其他電子","電子")\
                                .replace("文化創意","文化").replace("子零組件","電子").replace("業","")
        else:
            self._add_err_msg("  %-5s: 在 twstock.codes[] 找不到此代號，可嘗試執行 python3 -c 'import twstock;twstock.__update_codes()' 更新代號資料庫"%ticker) 
    
        #google trend名稱
        if ticker in self.__gt_name_overwrite_list:
            tdata['TMP_GTName']= self.__gt_name_overwrite_list[ticker]
        else:
            tdata['TMP_GTName']= tdata['名稱']
            
        return True
        

    #寫入股價資料： 股價，漲跌，成交金額，成交量
    #股價寫到 _df_price_list (若是盤中，最新一筆為即時資料)
    def query_price(self) -> bool:
        #yfinance 台股代號需加上.TW(上市) or .TWO(上櫃)
        tickets_yf_str= ''
        for ticker in self._ticker_list:
            if (ticker in twstock.codes) and (twstock.codes[ticker].market=='上櫃'):
                ticker_yf= "%s.TWO"%ticker
            else:
                ticker_yf= "%s.TW"%ticker
            tickets_yf_str+= " %s"%ticker_yf
            
        return self._query_price_yfinance(tickets_yf_str)
        

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
        

    #寫入財報資料： 本益比，EPS，財報季
    #前提： 已執行 query_price() 取得股價，存在tdata['股價']
    #FinMind下載的EPS符合公開資訊觀測站 https://mops.twse.com.tw/mops/web/t163sb04，但後者的EPS為年度累積，例如第三季EPS為第一季+第二季+第三季
    @QueryHandler_ThreadLoop( expire_hours=FINANCE_EXPIRE_HOURS, init_vars=['本益比',  'EPS', '財報季'] )  #init_vars[] 為網頁顯示順序
    def query_finance(self, data_name, ticker, tdata, prev_tdata) -> bool:
        if tdata['產業']=='ETF':
            agalog.debug("  %-5s: ETF 不查詢財報"%ticker)
            return True
        
        start_date= date.today() - timedelta(days=30*28) #至少取得四季財報
        fin_list = self.__query_finmind( param={"dataset": "TaiwanStockFinancialStatements", "data_id": ticker, "start_date": start_date}, 
                                           data_name="%s 財報"%ticker,
                                           min_rows=1,
                                           exp_columns=['date', 'stock_id', 'type', 'value'])
        if is_invalid(fin_list) :
            self._add_err_msg("  %-5s: 從 FinMind 下載財報錯誤，fin_list is None"%ticker) 
            return False        
        
        if not df_check_columns(fin_list, ['date', 'stock_id', 'type', 'value', 'origin_name']) :
            self._add_err_msg("  %-5s: 從 FinMind 下載財報錯誤, columns 不正確，讀到 %s"%(ticker, fin_list.columns.to_list())) 
            return False   
        
        eps_list= fin_list.loc[fin_list['type']=='EPS']
        if len(eps_list['date']) < 4:
            agalog.info("  %-5s: 財報的EPS不足4季，只有%d季，無法計算TTM EPS (近四季EPS)"%(ticker, len(eps_list['date'])))
            return True
        
        #只留下近四季財報，舊的刪除
        while len(eps_list)>4:
            eps_list= eps_list.drop( eps_list.index[[0]] )
            
        try:
           d0= datetime.strptime(eps_list['date'].iloc[0],'%Y-%m-%d')
           d3= datetime.strptime(eps_list['date'].iloc[3],'%Y-%m-%d')
        except ValueError as e:
           self._add_err_msg("  %-5s: 從 FinMind 下載財報錯誤的日期格式錯誤，[3]:%s, [0]:%s"%(ticker, eps_list['date'].iloc[3], eps_list['date'].iloc[0])) 
           return False   
            
        if (d3 - d0).days > 290:  #連續四季財報，例如	2020-09-30 ~ 2021-06-30，間隔日期為九個月 273 天左右，超過代表有不連續資料
            agalog.info("  %-5s: 近4季財報的不連續，期間為 %s 到 %s，無法計算TTM EPS"%(ticker, d3, d0))
            return True
            
        tdata['EPS']= eps_list['value'].sum() #過去四季EPS總和
        if is_valid(tdata['股價']):
           tdata['本益比'] = tdata['股價'] / tdata['EPS']  #本益比定義好像要用月均價，此處用即時價格
        tdata['財報季'] =  "~" + eps_list['date'].iloc[3][2:4] + eps_list['date'].iloc[3][5:].replace('03-31','Q1').replace('06-30','Q2').replace('09-30','Q3').replace('12-31','Q4')            
        agalog.debug("  %-5s: 本益比 %.2f = 股價 %.2f / EPS %.1f (%s ~ %s)"%(ticker, tdata['本益比'], tdata['股價'], tdata['EPS'], eps_list['date'].iloc[0], eps_list['date'].iloc[3]))
        return True
         
