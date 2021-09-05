# -*- coding: utf-8 -*-
#=============================================================
# <agastock>
# web_root.py
#
# URL:
#   /   => tw summary
#   /tw => tw summary
#   /tw/0050 => tw 0050 detail
#   /staic/img/tw_stock_0050_ma.png  => tw 0050 image
#
#   /us => us summary
#   /us/AAPL => us AAPL detail
#   /staic/img/us_stock_AAPL_bb.png  => us AAPL image
#
# Gavin Lee 2021/08
#=============================================================
#agastock module
from common import *
from config import *
import agalog

#other module
from flask import Flask, render_template, request, Response
import pandas as pd
import time, os, sys, math, re, logging

    
# ======== FUNCTION ========
def request_stock_summary(region):
    html_global_log_file= URL_STOCK_PARSER_LOG_REGION%region
    
    #讀取csv股票資料
    df_data, csv_update_time_str, price_update_time_str= read_stock_summary_csv(region)
    if df_data is None: #csv讀取失敗
        html_global_warn= "[錯誤] %s 讀取失敗"%(PATH_STOCK_CSV_REGION%region)
        html_stock_table= ''
        return (render_template('summary_%s.html'%region, **locals() ))

    #讀取 parse_stock.ps1 儲存的 WebMsg
    html_global_warn= ''
    if ('VAR_WebMsg' in df_data) and len(df_data['VAR_WebMsg'])>0 and is_valid(df_data['VAR_WebMsg'].iloc[0]):
        html_global_warn= ''
        for line in df_data['VAR_WebMsg'].iloc[0].split('<br>\n'):
            if re.match('^\[錯誤\]', line) is not None:
                color= '#d62728' #red
            else:
                color= '#ff7f0e'  #orange
            html_global_warn+= "<font color='%s'>%s</font><br>"%(color, line)
    
    #get得到的ascend參數代表升冪或降冪排序
    ascend = request.args.get('ascend')
    if ascend=='1' or ascend=='0':
        ascend= int(ascend)
    else: 
        ascend= 1  #預設升冪, 小排到大
            
    #此處先排序，之後會改變內容加超連接。內容改變就沒法排序了
    sort = request.args.get('sort')
    if not (sort in df_data.columns): #布林位置為預設排序
        sort= '布林位置'
    sort_list= [sort,'代號'] #除了網頁傳入參數sort，還有次級排序'代號'
    for s in reversed(sort_list):
        if (s not in df_data.columns):
            sort_list.remove(s)
    df_data= df_data.sort_values(by=sort_list, ascending=(ascend==1)) #小排到大           
    
    #美股股價需小數點兩位，台股只要一位
    if '股價' in df_data.columns:
        if region=="us":
            df_data['股價']= df_data['股價'].apply(lambda x: format(x, '.2f'))  
        else: #tw
            df_data['股價']= df_data['股價'].apply(lambda x: format(x, '.1f'))
        
    #顯示為百分比
    for col in ['布林寬度', '布林位置']:
        if col in df_data.columns:
            df_data[col]= df_data[col].apply(lambda x: '' if ((not is_float(x)) or math.isnan(x)) else format(x, '.1%'))  
        
    #顯示為貨幣
    for col in ['成交金額']:
        if col in df_data.columns:
            df_data["成交金額"]= df_data["成交金額"].apply(lambda x: '' if ((not is_float(x)) or math.isnan(x)) else '${0:,.0f}'.format(x/1000000))
        
    #顯示$符號 + 小數兩位
    for col in ['EPS','EPS預估']:
        if col in df_data.columns:
            df_data[col]= df_data[col].apply(lambda x: '' if ((not is_float(x)) or math.isnan(x)) else '${0:,.02f}'.format(x))
  
    #顯示逗點數字，除以1000
    for col in ['成交量']:
        if col in df_data.columns:
            df_data[col]= df_data[col].apply(lambda x: '' if ((not is_float(x)) or math.isnan(x)) else '{0:,.0f}'.format(x/1000))
  
    #顯示小數兩位
    for col in ['本益比','本益比預估']:
        if col in df_data.columns:
            df_data[col]= df_data[col].apply(lambda x: '' if ((not is_float(x)) or math.isnan(x)) else '{0:,.02f}'.format(x))
        
    #紅漲綠跌-數字
    if '漲跌' in df_data.columns:
        df_data['漲跌']= df_data['漲跌'].apply(lambda x: ('<span style="color:#FF2D2D;font-weight:bolder;">' if x>=0  else '<span style="color:#009100;font-weight:bolder;">') + format(x, '.1%') + "</span>" )
    
    #紅漲綠跌-百分比
    for col in ['G-Trend漲跌','EPS成長預估']:
        if col in df_data.columns:
            df_data[col]= df_data[col].apply(lambda x: '' if ((not is_float(x)) or math.isnan(x)) else (('<span style="color:#FF2D2D;font-weight:bolder;">' if float(x)>=0  else '<span style="color:#009100;font-weight:bolder;">') + format(float(x), '.1%') + "</span>") )
    
    #超連接到Google Trend
    if ('G-Trend' in df_data.columns):
        df_data['G-Trend']= df_data['G-Trend'].apply(lambda x: '' if ((not is_float(x)) or math.isnan(x)) else str(format(x, '.0f')) ) #先轉成str才能做以下操作，但記先排序之後再轉，轉成str之後排許變成100 > 10 > 22 > 23 > ...
        if ('HD_GT_URL' in df_data.columns):
            df_data['G-Trend']= "<a target='_blank' href='" + df_data['HD_GT_URL'] + "'><div>" + df_data['G-Trend'] + "</div></a>"
                           
    #超連接到 Yahoo Finance (美股) 及 財報狗(台股)
    for col in ['本益比','本益比預估','EPS','EPS預估']:
        if (col in df_data.columns) and ('代號' in df_data.columns): 
            if region=='us': #Yahoo Finance
                if col in ['EPS預估']:
                    df_data[col]= "<a target='_blank' href='https://finance.yahoo.com/quote/"+df_data['代號']+"/analysis?p=" + df_data['代號'] + "'><div>" + df_data[col] + "</div></a>"
                else:
                    df_data[col]= "<a target='_blank' href='https://finance.yahoo.com/quote/" + df_data['代號'] + "'><div>" + df_data[col] + "</div></a>"
            else: #財報狗的EPS符合FinMind，但本益比計算為[月均價 / 近4季EPS總和]，和  agastock 計算[即時股價/ 近4季EPS總和]不同
                df_data[col]= "<a target='_blank' href='https://statementdog.com/analysis/" + df_data['代號'] + "/eps'><div>" + df_data[col] + "</div></a>"
                                        
    #超連接到detail頁面
    for col in ['名稱','代號']:
        if (col in df_data.columns) and ('代號' in df_data.columns): 
            df_data[col] = "<a href='/" + region + "/" + df_data['代號'] + "'><div>" + df_data[col] + "</div></a>"
    
    #刪除空欄位
    if not WEB_DEBUG_SHOW_ALL_COLUMNS:
        for col in df_data.columns:
            for item in df_data[col]:
                if is_valid(item):
                    break
            else:
                df_data= df_data.drop(col, axis = 1)   
            
    #刪除不顯示的欄位. 這個藥最後處理，等其他欄位讀完再刪
    if not WEB_DEBUG_SHOW_ALL_COLUMNS:
        for col in df_data.columns:
            if re.match('^(VAR_|HD_)', col) is not None:
                df_data= df_data.drop(col, axis = 1)  

    #Column 名稱加上超連接, 參數 ascend 代表升冪或降冪排序. 初次點column為升冪，再次點同個column變降冪. WEB_SORT_DESCEND_LIST 中的 column 相反
    #之後需存取 column name 需改用 col_new_name_list[]
    col_new_name_list= {}
    for col in df_data.columns:
        col_new_name_list[col]= col
    for col in df_data.columns:
        if col in df_data.columns: #如果前面已經刪掉就不用處理
            if col==sort:
                ascend_next= [1,0][ascend] #同個欄位，下個排序要顛倒
                symbol= ['&nbsp↑','&nbsp↓'][ascend]
            else:
                #以下 column list 預設排序由小到大(ascend_next=1), 沒包含的 column 由大到小(ascend_next=0)
                if col in WEB_SORT_DESCEND_LIST: 
                    ascend_next= 1
                else:
                    ascend_next= 0 
                symbol= ''
            col_new_name_list[col]= '<a href=/%s?sort=%s&ascend=%d>%s</a><span style="color:#EB0000;font-weight:bolder;">%s</span>'%(region, col, ascend_next, col, symbol)
            df_data= df_data.rename(columns={col:col_new_name_list[col]}) 
   
    #準備html
    def highlight_punish_grid(val):
        return 'background-color:#FF7575' if ("分:" in str(val)) else ''
    
    #df已經排序，印出column會發現順序是新的，index也就是[i]是亂的，此處的i期望還是0,1,2,3等陣列真正索引，因此要使用iloc[i]
    def highlight_notify_column(column): #row: 'pandas.core.series.Series' 
        if ('通知訊息' in col_new_name_list) and (col_new_name_list['通知訊息'] in df_data.columns):
            return ['' if is_invalid(df_data[col_new_name_list['通知訊息']].iloc[i]) else 'background-color:#FFFF93' for i in range(len(column))]
        else:
            return ['' for i in range(len(column))]
            
    #設定顏色格式
    s= df_data.style.hide_index() #第一行1,2,3,...不顯示
    s= s.set_na_rep('')  #set_na_rep(): 如果沒此行，空白欄位都顯示nan    
    s= s.apply(highlight_notify_column)  #有通知的行標黃色
    s= s.applymap(highlight_punish_grid)  #處置資訊標紅色
    s= s.set_properties(**{'text-align': 'center'})
    html_stock_table= s.render().replace("<table","<table border='1' class='stock_table'")
    return (render_template('summary_%s.html'%region, **locals() ))

 
def request_stock_detail(ticker, region):
    html_img_bb= URL_IMG_REGION%(region, ticker, "bb") 
    html_img_gtrend= URL_IMG_REGION%(region, ticker, "gtrend") 
    html_img_ma= URL_IMG_REGION%(region, ticker, "ma") 
    
    img_bb= PATH_IMG_REGION%(region, ticker, "bb") 
    img_gtrend= PATH_IMG_REGION%(region, ticker, "gtrend") 
    img_ma= PATH_IMG_REGION%(region, ticker, "ma") 
        
    img_bb_time_str= file_time_str(img_bb)
    img_gtrend_time_str= file_time_str(img_gtrend)
    img_ma_time_str= file_time_str(img_ma)
    
    df_data, csv_update_time_str, price_update_time_str= read_stock_summary_csv(region) 
    ticker_name= "%s.%s"%(ticker, str.upper(region))
    return (render_template('detail_%s.html'%region, **locals() ))


app = Flask(__name__)



# ======== DETAIL ========
@app.route("/<region>/<ticker>")
def tw_request_stock_detail(region, ticker):
    return request_stock_detail(ticker, region)



# ======== SUMMARY ========
@app.route("/tw", methods=['GET'])
@app.route("/", methods=['GET'])
def tw_stock():
    return request_stock_summary("tw")
    
@app.route("/us")
def us_stock():
    return request_stock_summary("us")



# ======== MAIN ========
if __name__ == "__main__":
    app.run(debug=WEB_DEBUG_FLASK, host=WEB_SERVER_BIND_IP, port=WEB_SERVER_PORT)


    

