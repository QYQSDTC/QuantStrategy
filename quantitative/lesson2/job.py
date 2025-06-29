#!/Users/yiqianqian/miniforge3/envs/quant/bin/python
# -*- coding:utf-8 -*-
"""
Author: Yiqian Qian
Description: RSRS择时交易策略
Date: 2021-10-24 19:08:29
LastEditors: Yiqian Qian
LastEditTime: 2021-10-27 10:56:07
FilePath: /Users/yiqianqian/Library/Mobile Documents/com~apple~CloudDocs/Development/量化交易/quantitative/lesson2/job.py
"""

import math
import time
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# from jqdatasdk.technical_analysis import *
# import jqdatasdk as jq
import qstock as qs
import seaborn as sns
import talib

from sendmail import mail, send_wechat

# the default backend TKAgg can not be run in a new process, when this script is automated.
plt.switch_backend("Agg")

plt.rcParams["font.sans-serif"] = ["Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
# use sns default theme and set font for Chinese
sns.set_style({"font.sans-serif": ["Arial Unicode MS", "Arial"]})

# https://www.joinquant.com/help/api/help#api:API%E6%96%87%E6%A1%A3
# https://www.joinquant.com/help/api/help#JQData:JQData


# aa 为你自己的帐号， bb 为你自己的密码
# jq.auth("18687751766", "qyqisNo.1")

# http://fund.eastmoney.com/ETFN_jzzzl.html
# stock_pool = [
#     '159915.XSHE', # 易方达创业板ETF
#     '510300.XSHG', # 华泰柏瑞沪深300ETF
#     '510500.XSHG', # 南方中证500ETF
# ]

# 从多个热门概念中选出市值在50亿以上，300亿一下的标的。


def get_stock_pool():
    # 需要购买股票正式版6999/年！赶快赚钱！！！
    # q = jq.query(jq.valuation.code).filter(
    #     jq.valuation.market_cap >= 30,
    #     jq.valuation.market_cap <= 500,
    #     jq.valuation.code.in_(all_concept_stocks),
    # )
    # stock_df = jq.get_fundamentals(q)
    # stock_pool_all = [code for code in stock_df["code"]]
    # current_dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    all_stock = qs.realtime_data()
    # 剔除创业板、科创板、ST和退市的股票
    all_stock = all_stock[
        (~all_stock["名称"].str.contains("ST"))  # 剔除ST股票
        & (~all_stock["名称"].str.contains("退"))  # 剔除退市股票
        & (~all_stock["代码"].str.startswith("300"))  # 剔除创业板股票
        & (~all_stock["代码"].str.startswith("688"))  # 剔除科创板股票
    ]
    stock_pool = all_stock["代码"].tolist()
    return list(set(stock_pool))


# 动量轮动参数
stock_num = 5  # 买入评分最高的前 stock_num 只股票
momentum_day = 29  # 29神奇的数字  # 最新动量参考最近 momentum_day 的

ref_stock = "000300"  # 用 ref_stock 做择时计算的基础数据
N = 14  # 计算最新斜率 slope，拟合度 r2 参考最近 N 天
M = 600  # 计算最新标准分 zscore，rsrs_score 参考最近 M 天
score_threshold = 0.7  # rsrs 标准分指标阈值
# ma 择时参数
mean_day = 7  # 计算结束 ma 收盘价，参考最近 mean_day
# 计算初始 ma 收盘价，参考(mean_day + mean_diff_day)天前，窗口为 mean_diff_day 的一段时间
mean_diff_day = 14

# 计算个股MA
# mean_sec = 5

num_days = 5  # plot 5 day line plot

# send_info = [] # define it in function so that it will be re-initialized every time when run_today function runs.

today = datetime.now().date()
before = today - timedelta(days=100)
current_dt = datetime.strftime(today, "%Y%m%d")
before_dt = datetime.strftime(before, "%Y%m%d")
print(f"Start Calculating {current_dt}")


# 财务数据查询


# def get_fundamentals_info(stock):
#     q = jq.query(
#         jq.valuation.turnover_ratio, jq.valuation.market_cap, jq.indicator.eps
#     ).filter(jq.valuation.code.in_([stock]))
#     current_dt = time.strftime("%Y-%m-%d", time.localtime())
#     df = jq.get_fundamentals_continuously(
#         q, end_date=current_dt, count=5, panel=False)
#     print(df)


# 根据股票名，获取股票 code


def get_stock_code(stock_name):
    securities = qs.realtime_data()
    stock_code = securities[securities["名称"] == stock_name]["代码"].values[0]
    return stock_code


# 根据市值，获取股票池


# def market_cap():
#     wholeA = jq.get_fundamentals(
#         jq.query(jq.valuation.code).filter(jq.valuation.market_cap > 2000)
#     )
#     wholeAList = list(wholeA["code"])
#     return wholeAList


# 1-1 选股模块-动量因子轮动
# 基于股票年化收益和判定系数打分,并按照分数从大到小排名


def get_rank_120(stock_pool):
    """get rank score for stocks in stock pool"""
    send_info = []
    stock_dict_list = []
    MA3_list = []
    MA10_list = []
    stock_pool_copy = stock_pool.copy()  # to remove stocks in a for loop
    for stock in stock_pool_copy:
        score_list = []
        data = qs.get_data(
            stock,
            start=before_dt,
            freq=120,
        )  # 最新的在最下面
        if len(data) == 0:
            stock_pool.remove(stock)
            continue  # skip 0 data stock
        else:
            # print(f"Stock name is {data['name'].values[0]} has {len(data)} data")
            stock_name = data["name"].values[0]

            # 对于次新股票，可能没有数据，所以要drop NA
            data = data.dropna()
            data = data.drop_duplicates(subset=["close"])  # for 120m data
            # 收盘价
            y = data["log"] = np.log(data.close)
            # 分析的数据个数（天）
            x = data["num"] = np.arange(data.log.size)
            # 拟合 1 次多项式
            # y = kx + b, slope 为斜率 k，intercept 为截距 b
            # slope, intercept = np.polyfit(x, y, 1)
            # 直接连接首尾点计算斜率
            if len(y) < momentum_day + num_days:
                print("次新股，用所有数据")
                slope = (y.iloc[-1] - y.iloc[0]) / momentum_day  # 最新的在最上面
                # print(f'slope: {slope}\n')
                # 用拟合出的截距效果更好
                # intercept = y.iloc[0]
                try:  # 一些次新股数据不够，拟合出错
                    _, intercept = np.polyfit(x, y, 1)
                except:
                    print("Can not fit intercept, use first y value instead")
                    intercept = y.iloc[0]
                # (e ^ slope) ^ 250 - 1
                annualized_returns = math.pow(math.exp(slope), 250) - 1
                r_squared = 1 - (
                    sum((y - (slope * x + intercept)) ** 2)
                    / ((momentum_day - 1) * np.var(y, ddof=1))
                )
                score = annualized_returns * np.abs(r_squared)
                # print(f'score: {score}\n')
                score_list.append(score)
            else:
                slope = [
                    (y.iloc[-1 - D] - y.iloc[-momentum_day - D]) / momentum_day
                    for D in range(num_days)
                ]  # 最新的在最上面
                # print(f'slope: {slope}\n')
                # intercept = [y.iloc[-momentum_day-D] for D in range(num_days)]
                # (e ^ slope) ^ 250 - 1
                for i in range(num_days):
                    annualized_returns = math.pow(math.exp(slope[i]), 250) - 1
                    if i == 0:  # 如果i=0，则前n天数据为df.iloc[-n::]
                        _, intercept = np.polyfit(
                            x[-momentum_day - i : :], y[-momentum_day - i : :], 1
                        )
                        r_squared = 1 - (
                            sum(
                                (
                                    y[-momentum_day - i : :]
                                    - (slope[i] * x[-momentum_day - i : :] + intercept)
                                )
                                ** 2
                            )
                            / (
                                (momentum_day - 1)
                                * np.var(y[-momentum_day - i : :], ddof=1)
                            )
                        )
                        score = annualized_returns * np.abs(r_squared)
                        # print(f'score: {score}\n')
                        score_list.append(score)
                    else:
                        _, intercept = np.polyfit(
                            x[-momentum_day - i : -i], y[-momentum_day - i : -i], 1
                        )
                        r_squared = 1 - (
                            sum(
                                (
                                    y[-momentum_day - i : -i]
                                    - (slope[i] * x[-momentum_day - i : -i] + intercept)
                                )
                                ** 2
                            )
                            / (
                                (momentum_day - 1)
                                * np.var(y[-momentum_day - i : -i], ddof=1)
                            )
                        )
                        score = annualized_returns * np.abs(r_squared)
                        # print(f'score: {score}\n')
                        score_list.append(score)
            stock_dict_tmp = {stock_name: score_list}
            stock_dict_list.append(stock_dict_tmp)
            # 2023-03-16 update: use TA-Lib to calculate MA3 and MA10
            MA3 = talib.SMA(data["close"], timeperiod=3)
            MA3_list.append(MA3.iloc[-1])  # only need the latest one
            MA10 = talib.SMA(data["close"], timeperiod=10)
            MA10_list.append(MA10.iloc[-1])
    # merge list of dictionaries into one dictionary
    stock_dict = {k: v for d in stock_dict_list for k, v in d.items()}
    # create pandas dataframe from dict
    stock_df = pd.DataFrame.from_dict(stock_dict, orient="index")
    # add new cols
    stock_df["code"] = stock_pool
    stock_df["MA3"] = MA3_list
    stock_df["MA10"] = MA10_list
    # sort by latest score
    stock_df = stock_df.sort_values(by=[0], ascending=False)
    # get top num stocks
    stock_top_names = stock_df.index.to_list()[:30]
    stock_top_codes = stock_df["code"].to_list()[:30]
    # get all stock names and codes
    stock_names = stock_df.index.to_list()
    stock_codes = stock_df["code"].to_list()
    # print results
    print("#" * 30 + "候选" + "#" * 30)
    for name, code in zip(stock_names, stock_codes):
        print("{}({}):{}".format(name, code, stock_df[0][name]))
    print("#" * 64)
    # add results to send_info
    for name, code in zip(stock_top_names, stock_top_codes):
        send_info.append("{}({}):{}".format(name, code, stock_df[0][name]))
    return stock_top_names, stock_df, send_info


def get_rank_daily(stock_pool):
    """get rank score for stocks in stock pool"""
    send_info = []
    stock_dict_list = []
    MA3_list = []
    MA10_list = []
    stock_pool_copy = stock_pool.copy()  # to remove stocks in a for loop
    for stock in stock_pool_copy:
        score_list = []
        data = qs.get_data(
            stock,
            start=before_dt,
            freq="d",
        )  # 最新的在最下面
        if len(data) == 0:
            stock_pool.remove(stock)
            continue  # skip 0 data stock
        else:
            # print(f"Stock name is {data['name'].values[0]} has {len(data)} data")
            stock_name = data["name"].values[0]
            print(f"{stock_name}获取到{len(data['close'])}个数据")

            # 对于次新股票，可能没有数据，所以要drop NA
            data = data.dropna()
            # 收盘价
            y = data["log"] = np.log(data.close)
            # 分析的数据个数（天）
            x = data["num"] = np.arange(data.log.size)
            # 拟合 1 次多项式
            # y = kx + b, slope 为斜率 k，intercept 为截距 b
            # slope, intercept = np.polyfit(x, y, 1)
            # 直接连接首尾点计算斜率
            if len(y) < momentum_day + num_days:
                print(
                    f"经过处理后{stock_name}只有{len(y)} 个数据，少于{momentum_day + num_days}，需要用全部数据"
                )

                slope = (y.iloc[-1] - y.iloc[0]) / len(y)
                # print(f'slope: {slope}\n')
                # 用拟合出的截距效果更好
                # intercept = y.iloc[0]
                try:  # 一些次新股数据不够，拟合出错
                    _, intercept = np.polyfit(x, y, 1)
                except Exception as e:
                    print(f"Error {e}")
                    print("Can not fit intercept, use first y value instead")
                    intercept = y.iloc[0]
                # (e ^ slope) ^ 250 - 1
                annualized_returns = math.pow(math.exp(slope), 250) - 1
                r_squared = 1 - (
                    sum((y - (slope * x + intercept)) ** 2)
                    / ((momentum_day - 1) * np.var(y, ddof=1))
                )
                score = annualized_returns * np.abs(r_squared)
                # print(f'score: {score}\n')
                score_list.append(score)
            else:
                slope = [
                    (y.iloc[-1 - D] - y.iloc[-momentum_day - D]) / momentum_day
                    for D in range(num_days)
                ]  # 最新的在最上面
                # print(f'slope: {slope}\n')
                # intercept = [y.iloc[-momentum_day-D] for D in range(num_days)]
                # (e ^ slope) ^ 250 - 1
                for i in range(num_days):
                    annualized_returns = math.pow(math.exp(slope[i]), 250) - 1
                    if i == 0:  # 如果i=0，则前n天数据为df.iloc[-n::]
                        _, intercept = np.polyfit(
                            x[-momentum_day - i : :], y[-momentum_day - i : :], 1
                        )
                        r_squared = 1 - (
                            sum(
                                (
                                    y[-momentum_day - i : :]
                                    - (slope[i] * x[-momentum_day - i : :] + intercept)
                                )
                                ** 2
                            )
                            / (
                                (momentum_day - 1)
                                * np.var(y[-momentum_day - i : :], ddof=1)
                            )
                        )
                        score = annualized_returns * np.abs(r_squared)
                        # print(f'score: {score}\n')
                        score_list.append(score)
                    else:
                        _, intercept = np.polyfit(
                            x[-momentum_day - i : -i], y[-momentum_day - i : -i], 1
                        )
                        r_squared = 1 - (
                            sum(
                                (
                                    y[-momentum_day - i : -i]
                                    - (slope[i] * x[-momentum_day - i : -i] + intercept)
                                )
                                ** 2
                            )
                            / (
                                (momentum_day - 1)
                                * np.var(y[-momentum_day - i : -i], ddof=1)
                            )
                        )
                        score = annualized_returns * np.abs(r_squared)
                        # print(f'score: {score}\n')
                        score_list.append(score)
            stock_dict_tmp = {stock_name: score_list}
            stock_dict_list.append(stock_dict_tmp)
            # 2023-03-16 update: use TA-Lib to calculate MA3 and MA10
            MA3 = talib.SMA(data["close"], timeperiod=3)
            MA3_list.append(MA3.iloc[-1])  # only need the latest one
            MA10 = talib.SMA(data["close"], timeperiod=10)
            MA10_list.append(MA10.iloc[-1])
    # merge list of dictionaries into one dictionary
    stock_dict = {k: v for d in stock_dict_list for k, v in d.items()}
    # create pandas dataframe from dict
    stock_df = pd.DataFrame.from_dict(stock_dict, orient="index")
    # add new cols
    stock_df["code"] = stock_pool
    stock_df["MA3"] = MA3_list
    stock_df["MA10"] = MA10_list
    # sort by latest score
    stock_df = stock_df.sort_values(by=[0], ascending=False)
    # get top num stocks
    stock_top_names = stock_df.index.to_list()[:30]
    stock_top_codes = stock_df["code"].to_list()[:30]
    # get all stock names and codes
    stock_names = stock_df.index.to_list()
    stock_codes = stock_df["code"].to_list()
    # print results
    print("#" * 30 + "候选" + "#" * 30)
    for name, code in zip(stock_names, stock_codes):
        print("{}({}):{}".format(name, code, stock_df[0][name]))
    print("#" * 64)
    # add results to send_info
    for name, code in zip(stock_top_names, stock_top_codes):
        send_info.append("{}({}):{}".format(name, code, stock_df[0][name]))
    return stock_top_names, stock_df, send_info


def rank_stock_plot_120(stock_df):
    """rank_stock_plot
    line plot the score variation for *num_days* for each rank stock.
    """
    stock_df = stock_df.drop(["code", "MA3", "MA10"], axis=1)
    stock_df = stock_df.head()  # only care about the top stocks
    stock_var_df = (stock_df.div(stock_df.shift(-1, axis=1)) - 1).dropna(axis=1)
    stock_var_df.to_csv("rank_stock_variation_120.csv")

    # plot the variation of rank stock scores
    fig, axis = plt.subplots(1, 1, figsize=(8, 10))
    for name in stock_df.index.to_list():
        axis.semilogy(stock_df.loc[name], "-", label=name)
    axis.set_xlabel("Num of 120 Minutes Ago")
    axis.set_ylabel("Fitting Scores")
    axis.legend()
    fig.savefig("rank_stock_scores_120.png", dpi=500)

    # plot the relative variation of rank stock scores
    fig, axis = plt.subplots(1, 1, figsize=(8, 10))
    for name in stock_var_df.index.to_list():
        axis.plot(stock_var_df.loc[name], "-", label=name)
    axis.set_xlabel("Num of 120 Minutes Ago")
    axis.set_ylabel("Relative Variation")
    axis.legend()
    fig.savefig("rank_stock_variations_120.png", dpi=500)
    return None


def rank_stock_plot_daily(stock_df):
    """rank_stock_plot
    line plot the score variation for *num_days* for each rank stock.
    """
    stock_df = stock_df.drop(["code", "MA3", "MA10"], axis=1)
    stock_df = stock_df.head()  # only care about the top stocks
    stock_var_df = (stock_df.div(stock_df.shift(-1, axis=1)) - 1).dropna(axis=1)
    stock_var_df.to_csv("rank_stock_variation.csv")

    # plot the variation of rank stock scores
    fig, axis = plt.subplots(1, 1, figsize=(8, 10))
    for name in stock_df.index.to_list():
        axis.semilogy(stock_df.loc[name], "-", label=name)
    axis.set_xlabel("Num of Days Ago")
    axis.set_ylabel("Fitting Scores")
    axis.legend()
    fig.savefig("rank_stock_scores.png", dpi=500)

    # plot the relative variation of rank stock scores
    fig, axis = plt.subplots(1, 1, figsize=(8, 10))
    for name in stock_var_df.index.to_list():
        axis.plot(stock_var_df.loc[name], "-", label=name)
    axis.set_xlabel("Num of Days Ago")
    axis.set_ylabel("Relative Variation")
    axis.legend()
    fig.savefig("rank_stock_variations.png", dpi=500)
    return None


def catch_rising_stars(df):
    """catch_rising_stars
    catch rising stars from the dataframe.
    """
    # get the rising stars
    df["rising scores"] = df[0] - df[1]
    rising_stars = df.sort_values(by="rising scores", ascending=False)
    return rising_stars


# 2-1 择时模块-计算线性回归统计值
# 对输入的自变量每日最低价 x(series) 和因变量每日最高价 y(series) 建立 OLS 回归模型,返回元组(截距,斜率,拟合度)
# R2 统计学线性回归决定系数，也叫判定系数，拟合优度。
# R2 范围 0 ~ 1，拟合优度越大，自变量对因变量的解释程度越高，越接近 1 越好。
# 公式说明： https://blog.csdn.net/snowdroptulip/article/details/79022532
#           https://www.cnblogs.com/aviator999/p/10049646.html


def get_ols(x, y):
    slope, intercept = np.polyfit(x, y, 1)
    r2 = 1 - (
        sum((y - (slope * x + intercept)) ** 2) / ((len(y) - 1) * np.var(y, ddof=1))
    )
    return (intercept, slope, r2)


# 2-2 择时模块-设定初始斜率序列
# 通过前 M 日最高最低价的线性回归计算初始的斜率,返回斜率的列表


def initial_slope_series():
    current_dt = datetime.now().date()
    previous_date = current_dt - timedelta((N + M) * 2)
    previous_date = datetime.strftime(previous_date, "%Y%m%d")
    data = qs.get_data(
        ref_stock,
        start=previous_date,
        freq="d",
    )
    data = data[-(N + M) :]  # make sure only N+M points are used
    return [get_ols(data.low[i : i + N], data.high[i : i + N])[1] for i in range(M)]


# 2-3 择时模块-计算标准分
# 通过斜率列表计算并返回截至回测结束日的最新标准分


def get_zscore(slope_series):
    mean = np.mean(slope_series)
    std = np.std(slope_series)
    return (slope_series[-1] - mean) / std


# 2-4 择时模块-计算综合信号
# 1.获得 rsrs 与 MA 信号,rsrs 信号算法参考优化说明，MA 信号为一段时间两个端点的 MA 数值比较大小
# 2.信号同时为 True 时返回买入信号，同为 False 时返回卖出信号，其余情况返回持仓不变信号
# 3.加入个股择时
# 解释：
#       MA 信号：MA 指标是英文(Moving average)的简写，叫移动平均线指标。
#       RSRS 择时信号：
#               https://www.joinquant.com/view/community/detail/32b60d05f16c7d719d7fb836687504d6?type=1


def get_timing_signal(stock):
    """
    计算大盘择时+个股择时
    大盘择时：MA + RSRS
    个股择时：
    1. MA5均线（还行）
    2. 移动止盈（不太行）
    3. 3点斜率
    4. MACD
    """
    # 计算 MA 信号
    current_dt = time.strftime("%Y%m%d", time.localtime())
    current_dt = datetime.strptime(current_dt, "%Y%m%d")
    previous_date = current_dt - timedelta(
        mean_day + mean_diff_day + 50
    )  # select 50 more days to ensure there are enough data
    previous_date = datetime.strftime(previous_date, "%Y%m%d")
    close_data = qs.get_data(
        stock,
        start=previous_date,
        freq="d",
    )
    close_data = close_data[
        -(mean_day + mean_diff_day) :
    ]  # only takes the last mean_day + mean_diff_day points

    # 0 0 0 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1，23 天，要后 20 天
    today_MA = close_data.close[mean_diff_day:].mean()
    # 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 0，23 天，要前 20 天
    before_MA = close_data.close[:-mean_diff_day].mean()
    # 计算RSRS信号
    high_low_data = qs.get_data(
        stock,
        start=previous_date,
        freq="d",
    )
    high_low_data = high_low_data[-N:]
    intercept, slope, r2 = get_ols(high_low_data.low, high_low_data.high)
    slope_series.append(slope)
    rsrs_score = get_zscore(slope_series[-M:]) * r2

    # 计算个股择时信号
    # MA5
    #  close_data_sec = jq.get_price(
    # stock,
    # end_date=previous_date,
    # count=mean_sec,
    # frequency="daily",
    # fields=["close"]
    # )
    # MA_sec = close_data_sec.close.mean()

    # MACD
    # dif, dea, macd = MACD(
    #    stock, check_date=current_dt, SHORT=12, LONG=29, MID=7, unit="1d"
    # )

    # 判断大盘信号
    if rsrs_score > score_threshold and today_MA > before_MA:
        return "BUY"
    elif rsrs_score < -score_threshold and today_MA < before_MA:
        return "SELL"
    else:
        return "KEEP"


slope_series = initial_slope_series()[
    :-1
]  # 除去回测第一天的 slope ，避免运行时重复加入


def test_100_days():
    for each_day in range(1, 100)[::-1]:
        current_dt = time.strftime("%Y-%m-%d", time.localtime())
        current_dt = datetime.strptime(current_dt, "%Y-%m-%d")
        previous_date = current_dt - timedelta(days=each_day - 1)
        day = each_day
        print(each_day, previous_date)
        check_out_list = get_rank_120(stock_pool)
        for each_check_out in check_out_list:
            security_info = jq.get_security_info(each_check_out)
            stock_name = security_info.display_name
            stock_code = each_check_out
            print("今日自选股:{}({})".format(stock_name, stock_code))
        # 获取综合择时信号
        timing_signal = get_timing_signal(ref_stock)
        print("今日择时信号:{}".format(timing_signal))
        print("*" * 100)


def run_today_120():
    current_dt = time.strftime("%Y-%m-%d", time.localtime())
    current_dt = datetime.strptime(current_dt, "%Y-%m-%d")
    message = "这是120分钟数据\n"
    stock_pool = get_stock_pool()
    check_out_list, rank_stock, send_info = get_rank_120(stock_pool)
    # save rank_stock as csv
    rank_stock.to_csv("rank_stock_120.csv")
    rank_stock_plot_120(rank_stock)  # make the plots
    rank_stock_dif = (
        rank_stock.drop(["code"], axis=1)
        .diff(axis=1, periods=-1)
        .dropna(axis=1, how="all")
    )
    rank_stock_dif.to_csv("rank_stock_dif_120.csv")
    # get rising stars
    rising_stars = catch_rising_stars(rank_stock)

    # MA_day = 3  # x 日均线
    # for each_check_out in check_out_list:
    #     security_info = jq.get_security_info(each_check_out)
    #     stock_name = security_info.display_name
    #     stock_close = jq.get_price(
    #         each_check_out,
    #         end_date=current_dt,
    #         count=MA_day,
    #         frequency="daily",
    #         fields="close",
    #         skip_paused=True,
    #     )
    # stock_MA = stock_close.close.mean()

    for stock_name in check_out_list[:stock_num]:
        # number of days that score continuously droped
        drop_days = np.sum((rank_stock_dif.loc[stock_name] < 0).astype(int))
        message += f"今日自选股: {stock_name} "
        # print(
        #    f'{stock_name} {each_check_out} previouse close price {stock_close.close[-1]}, MA{MA_day}: {stock_MA}')
        # print('今日自选股:{}({})'.format(stock_name, stock_code))
        # 个股信号
        # 2023-03-16 update: use MA3 and MA10 as indicator
        MA3 = rank_stock["MA3"][stock_name]
        MA10 = rank_stock["MA10"][stock_name]

        if MA3 < MA10:  # drop_days >= 2:  # stock_close.close[-1] <= stock_MA:
            message += f"注意：3日线下叉10日线，分数连续下降{drop_days}，赶快跑路！\n"
        else:
            message += f"相信自己，冲冲冲！\n"
    # 获取综合择时信号
    timing_signal = get_timing_signal(ref_stock)
    message += f"今日大盘信号：{timing_signal}！\n"
    print(message)

    # print('*' * 100)
    message += "\r\n\r\n"
    message += "祝大家股路长盈!\n"
    message += "*" * 20 + "极速上升股" + "*" * 20
    message += "\r\n"
    for star in rising_stars.head().index.to_list():
        message += f"极速之星: {star} 上涨 {rising_stars.loc[star]['rising scores']}\n"
    message += "*" * 20 + "备选股" + "*" * 20
    message += "\r\n\r\n"
    message += "\r\n\r\n".join(send_info[:21])
    message += "\r\n\r\n"
    message += "食用方式：当第一只股是'冲冲冲'并且大盘信号也是'买买买'时，只买入排名第一的股，后面几只仅供参考;当大盘信号或个股信号只要其中之一是跑路，就卖出。极速之星是每日评分上升最快的股，可以留意观察机会。\n"
    ret = 0
    for _ in range(10):
        if ret:
            # 邮件发送成功推出
            print("Push notification successfully")
            break
        else:
            # 没有发送成功或失败继续
            # ret = mail(message)
            ret = send_wechat(message)
            time.sleep(1)


def run_today_daily():
    current_dt = time.strftime("%Y-%m-%d", time.localtime())
    current_dt = datetime.strptime(current_dt, "%Y-%m-%d")
    message = "这是日K数据\n"
    stock_pool = get_stock_pool()
    print(f"The number of stock pool is {len(stock_pool)}")
    check_out_list, rank_stock, send_info = get_rank_daily(stock_pool)
    # save rank_stock as csv
    rank_stock.to_csv("rank_stock.csv")
    rank_stock_plot_daily(rank_stock)  # make the plots
    rank_stock_dif = (
        rank_stock.drop(["code"], axis=1)
        .diff(axis=1, periods=-1)
        .dropna(axis=1, how="all")
    )
    rank_stock_dif.to_csv("rank_stock_dif.csv")
    # get rising stars
    rising_stars = catch_rising_stars(rank_stock)

    # MA_day = 3  # x 日均线
    # for each_check_out in check_out_list:
    #     security_info = jq.get_security_info(each_check_out)
    #     stock_name = security_info.display_name
    #     stock_close = jq.get_price(
    #         each_check_out,
    #         end_date=current_dt,
    #         count=MA_day,
    #         frequency="daily",
    #         fields="close",
    #         skip_paused=True,
    #     )
    # stock_MA = stock_close.close.mean()

    for stock_name in check_out_list[:stock_num]:
        # number of days that score continuously droped
        drop_days = np.sum((rank_stock_dif.loc[stock_name] < 0).astype(int))
        message += f"今日自选股: {stock_name} "
        # print(
        #    f'{stock_name} {each_check_out} previouse close price {stock_close.close[-1]}, MA{MA_day}: {stock_MA}')
        # print('今日自选股:{}({})'.format(stock_name, stock_code))
        # 个股信号
        # 2023-03-16 update: use MA3 and MA10 as indicator
        MA3 = rank_stock["MA3"][stock_name]
        MA10 = rank_stock["MA10"][stock_name]

        if MA3 < MA10:  # drop_days >= 2:  # stock_close.close[-1] <= stock_MA:
            message += f"注意：3日线下叉10日线，分数连续下降{drop_days}，赶快跑路！\n"
        else:
            message += f"相信自己，冲冲冲！\n"
    # 获取综合择时信号
    timing_signal = get_timing_signal(ref_stock)
    if timing_signal == "SELL":
        message += f"今日大盘信号：赶快跑路！\n"
    else:
        message += f"今日大盘信号：可冲\n"
    print(message)

    # print('*' * 100)
    message += "\r\n\r\n"
    message += "祝大家股路长盈!\n"
    message += "*" * 20 + "极速上升股" + "*" * 20
    message += "\r\n"
    for star in rising_stars.head().index.to_list():
        message += f"极速之星: {star} 上涨 {rising_stars.loc[star]['rising scores']}\n"
    message += "*" * 20 + "备选股" + "*" * 20
    message += "\r\n\r\n"
    message += "\r\n\r\n".join(send_info[:21])
    message += "\r\n\r\n"
    message += "食用方式：当第一只股是'冲冲冲'并且大盘信号也是'买买买'时，只买入排名第一的股，后面几只仅供参考;当大盘信号或个股信号只要其中之一是跑路，就卖出。极速之星是每日评分上升最快的股，可以留意观察机会。\n"
    ret = 0
    for _ in range(10):
        if ret:
            # 邮件发送成功推出
            print("Push notification successfully")
            break
        else:
            # 没有发送成功或失败继续
            # ret = mail(message)
            ret = send_wechat(message)
            time.sleep(1)


# itchat error: unvalid wxsid
# retw = wechat(message)
# if retw:
#     print('Send Wecaht successfully')
# else:
#     print('Failed to send Wechat')


def func_test():
    current_dt = time.strftime("%Y-%m-%d", time.localtime())
    current_dt = datetime.strptime(current_dt, "%Y-%m-%d")
    message = ""
    stock_pool = get_stock_pool()
    rising_stars = catch_rising_stars(stock_pool)


if __name__ == "__main__":
    # run_today_120()
    run_today_daily()
    # func_test()
