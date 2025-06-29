#!/Users/qyq/miniconda3/envs/quant/bin/python

from datetime import datetime, timedelta

import akshare as ak
import numpy as np
import pandas as pd
import talib


# 工具函数：过滤股票
def filter_stocks(stock_list):
    """过滤创业板、科创板、新股、ST股"""
    filtered = []
    for code in stock_list:
        # 过滤创业板(30/300开头)和科创板(688开头)
        if code.startswith(("30", "688")):
            continue

        # 获取股票基本信息
        try:
            info = ak.stock_individual_info_em(symbol=code)
            listing_date = pd.to_datetime(info.iloc[7, 1])  # 上市时间
            name = info.iloc[1, 1]  # 股票名称
        except Exception as e:
            print(f"Error getting stock info: {str(e)}")
            continue

        # 过滤新股(上市不足60个交易日)
        if (datetime.now() - listing_date).days < 60:
            continue

        # 过滤ST/*ST股
        if "ST" in name:
            continue

        filtered.append(code)
    return filtered


# 模块1：增强版数据获取
def get_enhanced_data(days=3):
    """获取行业数据并过滤"""
    industry_data = {}
    industry_df = ak.stock_board_industry_name_em()
    number = len(industry_df)
    cnt = 0

    for _, row in industry_df.iterrows():
        try:
            # 获取板块成分股并过滤
            cons_df = ak.stock_board_industry_cons_em(symbol=row["板块名称"])
            # print(cons_df.head())
            valid_codes = filter_stocks(
                cons_df["代码"].tolist()
            )  # 先过滤得到有效代码列表
            cons_df = cons_df[cons_df["代码"].isin(valid_codes)]  # 使用 isin 进行过滤
            # print(cons_df)

            # 获取板块指数数据
            index_df = ak.stock_board_industry_hist_em(
                symbol=row["板块名称"],
                start_date=(datetime.now() - timedelta(days * 10)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
                period="日k",
                adjust="qfq",
            )
            index_df["日期"] = pd.to_datetime(index_df["日期"])
            # print(index_df.head())

            industry_data[row["板块名称"]] = {
                "index_data": index_df,
                "constituents": cons_df,
            }
            cnt += 1
            print(f"获取{row['板块名称']}数据成功 ({cnt}/{number})")
        except Exception as e:
            print(f"Error processing {row['板块名称']}: {str(e)}")
            continue
    return industry_data


# 模块2：增强版板块分析（加入轮动监测）
def analyze_industry_rotation(industry_data):
    """分析板块强度及轮动"""
    strength_list = []

    for industry, data in industry_data.items():
        df = data["index_data"]
        print(f"分析{industry}板块数据...")
        # print(df.head())
        if len(df) < 11:
            print(f"数据不足，跳过{industry}")
            continue

        # 计算不同时间窗口收益率
        returns_3d = (df["收盘"].iloc[-1] / df["收盘"].iloc[-3] - 1) * 100
        returns_5d = (df["收盘"].iloc[-1] / df["收盘"].iloc[-5] - 1) * 100
        returns_10d = (df["收盘"].iloc[-1] / df["收盘"].iloc[-10] - 1) * 100

        # 计算动量加速度
        momentum_acc = returns_3d - returns_5d

        # 计算资金流向(板块内个股主力净流入总和)
        main_net_inflow = 0
        for code in data["constituents"]["代码"].head(20):
            try:
                flow = ak.stock_individual_fund_flow(stock=code).iloc[-1]
                main_net_inflow += flow["主力净流入-净额"]
            except Exception as e:
                print(f"Error getting fund flow for stock {code}: {str(e)}")
                continue

        strength_list.append(
            {
                "行业": industry,
                "3日涨幅": returns_3d,
                "5日涨幅": returns_5d,
                "10日涨幅": returns_10d,
                "动量加速度": momentum_acc,
                "主力净流入(亿)": main_net_inflow / 1e8,
                "强度得分": 0.4 * returns_3d
                + 0.3 * momentum_acc
                + 0.3 * (main_net_inflow / 1e8),
            }
        )

    strength_df = pd.DataFrame(strength_list)
    return strength_df.sort_values("强度得分", ascending=False)


# 模块3：增强版龙头股筛选
def select_leading_stocks_enhanced(industry_data, industry):
    """筛选龙头股"""
    cons_df = industry_data[industry]["constituents"]
    selected = []

    for _, row in cons_df.iterrows():
        code = row["代码"]
        try:
            # 获取个股数据
            daily_df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                adjust="qfq",
                start_date="20240601",
                end_date=datetime.now().strftime("%Y%m%d"),
            )
            # print(f'获取{row["名称"]}({code})数据成功')
            # print(daily_df.head())
            if len(daily_df) < 20:
                continue

            # 获取资金流向数据
            flow_df = ak.stock_individual_fund_flow(stock=code)

            # 技术指标
            close = daily_df["收盘"].values
            macd, signal, _ = talib.MACD(close)
            rsi = talib.RSI(close)[-1]

            # 资金指标
            main_net_3d = flow_df["主力净流入-净额"].tail(3).sum()  # 最近3日主力净流入
            # main_net_5d = flow_df["主力净流入-净额"].tail(5).sum()  # 最近5日主力净流入

            # 量价指标
            vol_ratio = (
                daily_df["成交量"].iloc[-1]
                / daily_df["成交量"].rolling(20).mean().iloc[-1]
            )

            # 获取流通市值
            info = ak.stock_individual_info_em(symbol=code)
            capital = info.iloc[5, 1]  # 流通市值
            # print(
            #     f"{code} 流通市值: {capital / 1e8} 亿, 3日主力净流入 {main_net_3d / 1e8} 亿"
            # )

            # 评分模型
            score = (
                0.15 * (macd[-1] - signal[-1]) * 100
                + 0.2 * min(rsi, 70)  # 限制RSI最大值
                + 0.25 * (main_net_3d / 1e8)
                + 0.15 * vol_ratio
                + 0.25 * (capital / 1e10)  # 适度偏好大市值
            )

            selected.append(
                {
                    "代码": code,
                    "名称": row["名称"],
                    "市值(亿)": capital / 1e8,
                    "3日主力净流入(亿)": main_net_3d / 1e8,
                    "MACD差值": macd[-1] - signal[-1],
                    "RSI": rsi,
                    "量比": vol_ratio,
                    "综合得分": score,
                }
            )
        except Exception as e:
            print(f"Error processing stock: {e}")
            continue

    return pd.DataFrame(selected).sort_values("综合得分", ascending=False).head(3)


# 模块4：增强版择时系统
def enhanced_market_timing():
    """改进的择时系统"""
    # 大盘趋势判断
    sh_df = ak.stock_zh_index_hist_csindex(
        symbol="000001",
        start_date="20250101",
        end_date=datetime.now().strftime("%Y%m%d"),
    )
    sh_df["MA20"] = sh_df["收盘"].rolling(20).mean()
    trend_score = 0.7 if sh_df["收盘"].iloc[-1] > sh_df["MA20"].iloc[-1] else 0.3

    # 市场情绪指标
    spot_df = ak.stock_zh_a_spot_em()
    limit_up = len(spot_df[spot_df["涨跌幅"] >= 9.8])
    limit_down = len(spot_df[spot_df["涨跌幅"] <= -9.8])
    emotion_score = limit_up / (limit_up + limit_down + 1e-5)  # 防止除零

    # 主力资金流向
    market_flow = ak.stock_market_fund_flow()
    main_net = market_flow.iloc[-1]["主力净流入-净额"]
    flow_score = np.tanh(main_net / 1e10)  # 归一化处理

    # 综合评分
    timing_score = 0.5 * trend_score + 0.4 * emotion_score + 0.1 * flow_score

    return {
        "趋势得分": trend_score,
        "情绪得分": emotion_score,
        "资金得分": flow_score,
        "综合评分": timing_score,
    }


# 主程序
def main():
    print("数据获取中...")
    industry_data = get_enhanced_data()
    print("数据获取完成")

    print("\n板块强度分析:")
    strength_df = analyze_industry_rotation(industry_data)
    # print(strength_df.head(5))

    print("\n市场择时分析:")
    timing = enhanced_market_timing()
    print(pd.Series(timing))

    if timing["综合评分"] >= 0.6:
        print("\n=== 推荐标的 ===")
        for industry in strength_df["行业"].head(2):
            print(
                f"\n行业：{industry}, 3日涨幅：{strength_df[strength_df['行业'] == industry]['3日涨幅'].values[0]:.2f}%"
            )
            stocks = select_leading_stocks_enhanced(industry_data, industry)
            print(stocks[["代码", "名称", "综合得分"]])

            # 生成交易信号
            for _, stock in stocks.iterrows():
                conditions = [
                    stock["RSI"] < 68,
                    stock["MACD差值"] > 0,
                    stock["3日主力净流入(亿)"] > 5,
                    stock["市值(亿)"] > 100,
                ]
                if sum(conditions) >= 2:
                    print(
                        f"建议买入：{stock['名称']} ({stock['代码']}) 满足{sum(conditions)}/4条件"
                    )
                else:
                    print(f"观望：{stock['名称']} 条件不足")
    else:
        print("\n市场综合评分低于0.6，建议空仓观望")


if __name__ == "__main__":
    main()
