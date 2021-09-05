# -*- coding: utf-8 -*-
#=============================================================
# <agastock>
# common.py
#
# Copyright ©2021 [Gavin Lee], et. al.
#=============================================================
#agastock module
from config import *
import agalog

#other module
import time, sys, os, traceback, colorlog, math
import numpy as np
import pandas as pd
from datetime import datetime


#=========== COMMON PARAMETER ============
DIR_BASE= os.path.dirname( os.path.abspath(__file__) ) #此檔案所在目錄
DIR_OUT= DIR_BASE + "/out"

PATH_STOCK_CSV_REGION= DIR_OUT + "/stock_summary_%s.csv"  #%s 將代換為 tw or us
PATH_NOTIFY_CSV_REGION= DIR_OUT + "/line_notify_%s.csv"  #%s 將代換為 tw or us

URL_STOCK_PARSER_LOG_REGION= "/static/logs/stock_parser_%s.log"  #%s代換為tw or us
PATH_STOCK_PARSER_LOG_REGION= DIR_BASE + URL_STOCK_PARSER_LOG_REGION

URL_IMG_REGION= "/static/img/%s_stock_%s_%s.png"  #第一個%s將代換為tw or us, 第二個%s將代換為股票代號(例如0050, AAPL), 第三個%s將代換為bb or gtrend or ma
PATH_IMG_REGION= DIR_BASE + URL_IMG_REGION
   
 
# ============ FUNCTION DataFrame處理 ============
def df_check_columns(df, exp_columns):
    for col in exp_columns:
        if col not in df.columns:
            return False
    return True
   
   
#因為每筆股票讀回資料不同，例如t.info['trailingEps']不存在會導致exception，因此設計get_valid系列，若是不存在就回傳錯誤值
#本來使用None當錯誤值，但是 print('%f'%None) 會發生exception，因此改用float('nan')，print('%f'%float('nan')) 可印出nan。
#但注意不能用整數印出，要避免用'%d'印出get_valid_XXX得到的資料
def get_valid_value3(dic, index1, index2):
    if is_invalid3(dic, index1, index2):
        return float('nan')
    return dic[index1][index2]
            
def get_valid_value2(dic, index):
    if is_invalid2(dic, index):
        return float('nan')
    return dic[index]
            
def get_valid_value(val):
    if is_invalid(val):
        return float('nan')
    return val
            

def is_invalid3(dic, index1, index2):
    try:
        return is_invalid( dic[index1][index2] )
    except (TypeError, KeyError) as e: #TypeError代表dic is None, KeyError代表dic[]不存在index
        return True     
            
def is_invalid2(dic, index):
    try:
        return is_invalid( dic[index] )
    except (TypeError, KeyError) as e: #TypeError代表dic is None, KeyError代表dic[]不存在index
        return True        
            
def is_invalid(val):
    if val is None:
        return True
    elif type(val)==float:
        return math.isnan(val)
    if type(val)==np.float64:
        return np.isnan(val)
    elif type(val)==str:
        return val.strip()==''
    elif type(val)==int or type(val)==np.int64:
        return False
    elif type(val)==pd.core.frame.DataFrame or type(val)==pd.core.series.Series:
        return (val is None) or (len(val)==0)
    else:
        raise Exception("is_invalid() 無法處理 %s"%type(val))
        
            
def is_valid3(dic, index1, index2):
    return not is_invalid3(dic, index1, index2)
    
def is_valid2(dic, index):
    return not is_invalid2(dic, index)
            
def is_valid(val):
    return not is_invalid(val)
        

# ============ FUNCTION 陣列處理 ============
#取得array最後一個, 或是指定-2, -3等倒數index
def last(arr, index=-1):
    return arr[arr.size+index]
    
    
def last_iloc(arr, index=-1):
    return arr.iloc[arr.size+index]
        
        
#init_dic_var 初始化 self._data[ticker][XXX] 的順序，在轉換為 DataFrame 之後即是網頁顯示順序
#本來初始值設為None，但這樣再print時因為None轉成str會報exception，需要額外判斷，用''比較簡單，即使沒有賦值也可以print
def init_dic_var(dic, var_list):
    for var in var_list:
        dic[var]= float('nan')
        

# ============ FUNCTION 時間處理 ============
def file_time_str(fpath: str):
    if os.path.isfile(fpath):
        ftime= os.stat(fpath).st_mtime
        return time.strftime("%Y/%m/%d %H:%M:%S",time.localtime(ftime))
    else:
        return ''


def datetime_str():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) 
    

#取得月日字串 "7/23" 
#input: str "2021-07-23" or datetime
def date_to_md(date_str:str) -> str:
    if isinstance(date_str,datetime):
        md_str= datetime.strftime(date_str,'%m/%d')
    elif isinstance(date_str,str):
        md_str= date_str[5:].replace("-","/")
    else:
        return ''
        
    if md_str[0]=='0':
        md_str= md_str[1:]
    return md_str
    

# ============ FUNCTION 其他 ============
def read_stock_summary_csv(region):   
    path_csv= PATH_STOCK_CSV_REGION%region
    if not os.path.isfile(path_csv):
        return None, None, None
    
    #(1) 若沒設定dtype，代號0050會轉成int變成50
    #(2) read_csv()當中不能指定index_col="代號"，一旦指定，台股的index為數字(例如0050)，將強制轉型為Int64，0050的00立即遺失，即使dtype設定0:str也沒用
    #     解法1: read_csv不指定index_col, 然後df= df.set_index('代號', drop=False)，但造成 web_root.py 無法用 '代號' 排序，說和 index 名稱 ambiguous
    #     解法2(採納): to_csv(index=True)，read_csv指定dtype={0:str}或是{'Unnamed: 0':str}，再設定df= df.set_index(0,drop=True)即可
    df = pd.read_csv(path_csv, 
                       dtype={0:str, '代號':str, 'G-Trend':float, 'G-Trend漲跌':float, '漲跌':float, '布林位置':float, '布林寬度':float, 'VAR_WebMsg':str})  
    df= df.set_index(df.columns[0], drop=True)
    csv_update_time_str= file_time_str(path_csv)
    
    price_update_time_str= ''
    if is_valid(df) and ('VAR_PriceUpdateDate' in df.columns):
        price_update_time_str= df['VAR_PriceUpdateDate'].iloc[0]
        
    return df, csv_update_time_str, price_update_time_str
    
    
def get_exception_msg(e):
    error_class = e.__class__.__name__ #寫入錯誤類型
    detail = e.args #寫入詳細內容
    cl, exc, tb = sys.exc_info() #寫入Call Stack
    extract_tb= traceback.extract_tb(tb)
   
    #顯示agastock的最後一個執行點。若找不到agastock就顯示最後執行點(但不應該發生)
    for i in range(-1,-len(extract_tb)-1,-1):
        if "agastock" in extract_tb[i][0]:
            break
    else:
        i= -1
        
    fileName = extract_tb[i][0] #寫入發生的檔案名稱
    lineNum = extract_tb[i][1] #寫入發生的行號
    funcName = extract_tb[i][2] #寫入發生的函數名稱
    errMsg = "File \"{}\", line {}, in {}, [{}] {}".format(os.path.basename(fileName), lineNum, funcName, error_class, detail)
    return errMsg
    
    
def is_float(s):
    try:
        float(s) # for int, long and float
    except ValueError:
        return False
    return True


# ============ FUNCTION 檔案系統 ============
#remove file if not exist
def silence_remove(fpath: str):
    if os.path.isfile(fpath):
        os.remove(fpath)
    assert(not os.path.isfile(fpath))
        
