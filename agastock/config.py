# -*- coding: utf-8 -*-
#=============================================================
# <agastock>
# config.py
# 參數設定
#
# Copyright ©2021 [Gavin Lee], et. al.
#=============================================================
import logging

#----------------------------------------------------------------------------------------
# 帳號設定
#----------------------------------------------------------------------------------------
#若要啟用Line通知，需在 https://developers.line.biz/zh-hant/ 申請LineBot，並填入ID及TOKEN
#空字串代表不通知
LINEBOT_ID= ''
LINEBOT_TOKEN= ''
                                  
#之前需要付費的FinMind帳號才能下載台股EPS，本益比等，現在好像不用了, https://finmindtrade.com/
TW_FM_TOKEN= ''




#----------------------------------------------------------------------------------------
# stock_us.py
#----------------------------------------------------------------------------------------
#美股清單
US_TICKER_LIST=[ 'QQQ','VT','VTI', 'ARKW','ARKG', #ETF
                   'GOOGL','AMZN', 'AAPL', 'TSLA', 'MSFT', 'AMD', 'FB', 'NVDA', 'TSM', 'UMC','INTC',   #科技股
                   'PYPL','NOW','CRM',    #穩定新創
                   'PLTR','NOW','CRM',    #新創中的毛票
                   'DAC', 'ZIM',    #航運
                   'ABNB', 'BA', 'RCL', 'CCL',  #航旅油
                   'X',  #原物料: X 美國鋼鐵
                   'WMT','SBUX', 'COST', 'DIS', #消費
]
#US_TICKER_LIST=['QQQ', 'AMZN', 'TSM']  #解除註解可改用較少股票來測試

#股票名稱，用於網頁顯示
#和 US_TICKER_LIST[] 不需一一對應，此處多的捨棄，少的顯示代號(例如QQQ適合顯示代號)
US_NAME_LIST = {'GOOGL':'Google','AMZN':'亞馬遜', 'AAPL':'Apple', 'TSLA':'Tesla',   #科技股
                 'MSFT':'微軟', 'FB':'Facebook', 'NVDA':'Nvidia', 'TSM':'台積電', 'UMC':'聯電','INTC':'Intel',   #科技股
                 'PYPL':'Paypal','NOW':'ServiceNow','CRM':'Salesforce',   #穩定新創
                 'PLTR':'Palantir',  #新創中的毛票
                 'DAC':'Danaos', 'ZIM':'ZIM',    #航運
                 'ABNB':'Airbnb', 'BA':'波音', 'RCL':'皇家郵輪', 'CCL':'嘉年華遊輪',  #航旅油
                 'X':'美國鋼鐵',  #原物料: X 美國鋼鐵
                 'WMT':'Walmat','SBUX':'星巴克', 'COST':'Costco', 'DIS':'Disney',  #消費
}

#產業，用於網頁顯示
#和 US_TICKER_LIST[] 不需一一對應，此處多的捨棄，少的顯示空白
US_GROUP_LIST = {'QQQ':'ETF','VT':'ETF','VTI':'ETF', 'ARKW':'ETF','ARKG':'ETF', #ETF
                 'GOOGL':'科技','AMZN':'科技', 'AAPL':'科技', 'TSLA':'科技','MSFT':'科技','AMD':'半導體',   #科技股
                 'FB':'科技', 'NVDA':'半導體', 'TSM':'半導體', 'UMC':'半導體','INTC':'半導體',   #科技股
                 'PYPL':'Fintech','NOW':'IT服務','CRM':'IT服務',    #穩定新創
                 'PLTR':'科技(毛票)',  #新創中的毛票
                 'BABA':'科技',   #中概股
                 'DAC':'海運', 'ZIM':'海運',    #航運
                 'ABNB':'旅遊', 'BA':'旅遊', 'RCL':'旅遊', 'CCL':'旅遊',  #航旅油
                 'X':'鋼鐵',  #原物料: X 美國鋼鐵
                 'WMT':'零售','SBUX':'零售', 'COST':'零售', 'DIS':'影視', #消費
} 

#Google Trend 查詢字串
#和 US_TICKER_LIST[] 不需一一對應，此處多的捨棄，少的不查 (例如聯電UMC，Google Trend 搜尋量太少，不適合列入)
US_GT_NAME_LIST = {'GOOGL':'Google','AMZN':'Amazon', 'AAPL':'Apple', 'TSLA':'Tesla',   #科技股
                     'MSFT':'Microsoft', 'FB':'Facebook', 'NVDA':'Nvidia', 'TSM':'TSM', 'INTC':'Intel', 'AMD':'AMD',   #科技股
                     'PYPL':'PayPal','NOW':'ServiceNow','CRM':'Salesforce',    #穩定新創
                     'PLTR':'PLTR',  #新創中的毛票
                     'DAC':'DAC', 'ZIM':'ZIM',    #航運
                     'ABNB':'Airbnb', 'BA':'Boeing', 'RCL':'RCL', 'CCL':'Carnival',  #航旅油
                     'X':'United States Steel',  #原物料: X 美國鋼鐵
                     'WMT':'Walmart','SBUX':'Starbucks', 'COST':'Costco', 'DIS':'Disney', #消費
}  




#----------------------------------------------------------------------------------------
# stock_twn.py
#----------------------------------------------------------------------------------------
#台股清單
TW_TICKET_LIST= ['0050',  #ETF
                   '2330', '2454','2303','2401',  #半導體:  2330台積電, 2454聯發科, 2303聯電, 2401凌陽,
                   '2615', '2603', '2609',  #航運:  2615萬海, 2603長榮海, 2609陽明
                   '9943','2731', '2727',  #娛樂:  9943好樂迪, 2731雄獅, 2727王品
                   '2317', '2451',    #電子:  2317鴻海, 2451創見
                   '6741',    #雲端:  6741 91-APP
]
#TW_TICKET_LIST= ['6741', '2317', '0050']   #解除註解可改用較少股票來測試

#PS: 台股名稱及產業顯示證交所資料

#台股Google Trend預設使用證交所名稱查詢，但像雄獅會搜尋到雄獅文具，就需要覆寫在下表
#空字串代表不搜尋 Google Trend。 ETF不用特別寫會自動忽略
TW_GT_NAME_OVERWRITE_LIST= {'2731':'雄獅旅遊', 
                               '6741':'91APP'}




#----------------------------------------------------------------------------------------
# web_root.py 
#----------------------------------------------------------------------------------------
#綁定的IP， "0.0.0.0" 代表所有網路介面
WEB_SERVER_BIND_IP= "0.0.0.0"   

#綁定的port. 若設定80，在ubnutu需執行下指令, 其中python要符合系統際版本
# sh sudo 
# sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3.8  
WEB_SERVER_PORT= 8080

#網頁 column 都有超連接可排序，預設升冪排序(ascend_next=1)，寫在下表的 column 則改為降冪排序(ascend_next=0)
#不該包含'訊息通知'，因為它大都空白，需要升冪(ascend_next=1)才會文字在前空白在後
WEB_SORT_DESCEND_LIST= ["代號", '名稱', "漲跌", "布林位置","本益比預估"]

#此站網址，用於 LINE 通知. 只要 domain name 不需要加 port，結尾不要加斜線
WEB_BASE_URL= "http://test.com"

#啟用flask debug mode，每次修改 .py 都自動重啟flask web server
WEB_DEBUG_FLASK= False

#顯示所有欄位，包括 HD_XXXX 及 VAR_XXXX 隱藏欄位，可幫助除錯
WEB_DEBUG_SHOW_ALL_COLUMNS= False




#----------------------------------------------------------------------------------------
# stock_base.py
#----------------------------------------------------------------------------------------
#=====< 一般設定 >======
#URL Query Timeout, 目前只用於台股
URL_TIMEOUT_SEC= 10 

#繪圖顯示天數. 考慮Google Trend使用'today 3-m'下載90天資料，所有圖一律顯示90天
DIAGRAM_DAYS= 90

#歷史股價下載天數. 為了配合DIAGRAM_DAYS=90：
# 約需170天股價，才能在紅綠燭圖畫出90天MA60()
# 約需110天股價，才能畫出90天布林通道(使用20日均線繪製)。至少30天股價才能算出當天布林通道
STOCK_QUERY_DAYS= 180

#布林通道
BBAND_DAYS= 20 #布林通道計算天數，一般取20日，即中線為MA20 (20日移動平均)
BBAND_WIDTH_DISPLAY_MIN= 0.08  #0.1代表10%以上寬度才顯示布林通道位置，設門檻是因為寬度太小用布林通道沒意義，一天漲跌就超過了

#Google Trend 顯示條件
#50代表 "本週或上週MA7" 在50以上才顯示 G-Trend 漲跌. 值太小顯示漲跌沒意義
GTREND_MA7_RATE_DISPLAY_MIN= 50  


#=====< 有效時限 >======
#Google Trend 更新頻率
#經測試，台股設定台灣區域，大都台灣時間凌晨12點更新到三天前資料，例如 2021-08-01 00:00:00 更新到 2021-07-29 的資料
#但一整天測試下來，Google Trend的值會變化，原因不明
GTREAD_EXPIRE_HOURS= 4  #4小時, 可以是浮點數例如 0.5

#財報更新頻率
#台股財報: Q1在5/15前公布, Q2在8/14前公布, Q3在11/14前公布, Q4和年報在隔年3/31前公布 (此套件在台股只查季報，不查年報)
FINANCE_EXPIRE_HOURS= 3*24  #3天, 可以是浮點數例如半小時為 0.5


#===< LINE 通知條件 >===
#布林通道
NOTIFY_BBAND_LOWER= 0.0  #0.0 代表股價小於布林通道下緣(0%)即通知買入. 0.1 代表 10%. 百分比為股價距離布林通道下緣位置

#Google Trend，和七日前的MA7相比，本週MA7漲70%以上，並且結果大於70就通知，代表可買入
NOTIFY_GT_MA7_RISE_RATE= 0.7 #70%
NOTIFY_GT_MA7_RISE_TO= 70

#Google Trend，七日前MA7超過70，並且本週MA7跌70%以上就通知，代表可賣出
NOTIFY_GT_MA7_FALL_RATE= -0.7 #-70%
NOTIFY_GT_MA7_FALL_FROM= 70

#Google Trend，和前三日最低值相比，升高超過200%(也就是三倍), 並大於三個月最大值的1.5倍
NOTIFY_GT_RISE_RATE= 2.0 #三倍
NOTIFY_GT_COMPARE_RESULT_MAX= 1.5 #150%

#Google Trend 和前三日最高值相比，下降超過-70% 並低於三個月最小值的50%
NOTIFY_GT_FALL_RATE= -0.7 #-70%
NOTIFY_GT_COMPARE_RESULT_MAX= 0.5 #50%


#=======< 設定 >=======
#啟用 multi-thread 支援
# 美股: 35支股票，初次執行由 243sec 加速到 42sec，再次執行都是 31sec. 主要加速 query_info()，每支股票耗時 5sec
# 台股: 35支股票，初次執行由  53sec 加速到 39sec，再次執行都是 25sec. 稍微加速 query_finance()，每支股票耗時 0.3sec
MULTI_THREAD_SUPPORT= True


#=== Yahoo Finance === 
#刪除 9:00-9:20 因為台股延遲報價 20min 造成當天 NaN 股價. 刪除後，Summary 頁面可顯示前一天股價，避免顯示NaN
YFINANCE_FIX_TW_TIME_SHIFT= True

#修正Yahoo Finance的bug: 有時部分日期的價為NaN，發生日前數天的volume剛好被乘以一百倍. 此功能還原正確volume，但最多連續還原20天，避免影響到volume爆量的狀況
YFINANCE_FIX_HIGH_VOLUME= False


#======< 繪圖用的色碼 >======
#default color order for matplotlib
# https://blog.csdn.net/mighty13/article/details/113764337
COLOR_BLUE='#1f77b4'
COLOR_ORANGE='#ff7f0e'
COLOR_GREEN='#2ca02c'
COLOR_RED='#d62728'
COLOR_PURPLE='#9467bd'
COLOR_BROWN='#8c564b'
COLOR_PINK='#e377c2'
COLOR_GRAY='#7f7f7f'
COLOR_YELLOW='#bcbd22'
COLOR_CYAN_BLUE='#17becf'




#----------------------------------------------------------------------------------------
# parse_stock.py
#----------------------------------------------------------------------------------------  
#選項：logging.DEBUG, logging.INFO, logging.WARN, logging.ERROR, logging.CRITICAL, logging.EXCEPTION
#設為 logging.DEBUG 可印出每個 QueryHandler 內容，例如 Google Trend, EPS, 本益比等
PARSE_STOCK_LOG_LEVEL= logging.INFO




#----------------------------------------------------------------------------------------
# agalog.py
#----------------------------------------------------------------------------------------
#設為True可啟用所有module的 debug print，包括 request 的 http 連線，可幫助了解爬蟲
ENABLE_GLOBAL_LOG= False


