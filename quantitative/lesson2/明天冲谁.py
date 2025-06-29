#!/Users/yiqianqian/miniforge3/envs/quant/bin/python

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# 配置参数
TRADE_DATE = datetime.now().strftime("%Y%m%d")  # 指定交易日
CAPITAL_LIMIT = 100  # 市值限制（亿）
VOLUME_MULTIPLE = 2  # 量能倍数
SENTIMENT_PARAMS = {  # 情绪冰点阈值
    "zt_threshold": 30,  # 涨停家数阈值
    "jr_rate": 0.4,  # 晋级率阈值
    "avg_pct": -0.5,  # 昨日涨停股平均涨幅阈值
}


def get_zt_pool(date):
    """获取当日涨停板数据"""
    zt_pool = ak.stock_zt_pool_em(date=date)
    return zt_pool[["代码", "名称", "首次封板时间", "封板资金"]]


def get_stock_data(symbol, days=30):
    """获取个股历史数据"""
    end_date = datetime.strptime(TRADE_DATE, "%Y%m%d")
    start_date = end_date - timedelta(days=days * 2)
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date.strftime("%Y%m%d"),
        end_date=TRADE_DATE,
        adjust="qfq",
    )
    return df


def calculate_technical(df):
    """计算技术指标"""
    # 均线系统
    df["MA5"] = df["收盘"].rolling(5).mean()
    df["MA10"] = df["收盘"].rolling(10).mean()

    # MACD
    short_ema = df["收盘"].ewm(span=12, adjust=False).mean()
    long_ema = df["收盘"].ewm(span=26, adjust=False).mean()
    df["MACD"] = short_ema - long_ema
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    return df


def evaluate_stock(symbol, zt_data):
    """评估个股是否符合策略"""
    try:
        # 获取基础数据
        hist_data = get_stock_data(symbol)
        # print(f'{symbol} 历史数据: {len(hist_data)}天')
        if len(hist_data) < 30:
            return None

        # 计算技术指标
        hist_data = calculate_technical(hist_data)

        # 在DataFrame上使用shift，然后再获取最新值进行比较
        hist_data["MA10_shifted"] = hist_data["MA10"].shift(5)

        latest = hist_data.iloc[-1]

        # 涨停特征筛选
        zt_info = zt_data[zt_data["代码"] == symbol].iloc[0]

        # 处理首次封板时间格式，将092500转换为09:25:00格式
        time_str = zt_info["首次封板时间"]
        # print(f"length of time_str: {len(time_str)}")
        if len(time_str) == 6:  # 确保格式为6位数字
            formatted_time = f"{time_str[:2]}:{time_str[2:4]}:{time_str[4:]}"
            zt_time = datetime.strptime(formatted_time, "%H:%M:%S").time()
            # print(f"{symbol} 涨停时间: {formatted_time}")
        else:
            # 如果格式不符合预期，则跳过该股票
            return None

        # 条件1：早盘涨停
        condition1 = zt_time <= datetime.strptime("10:30:00", "%H:%M:%S").time()

        # 条件2：量能达标
        avg_volume = hist_data["成交量"].iloc[-6:-1].mean()
        condition2 = latest["成交量"] >= VOLUME_MULTIPLE * avg_volume

        # 条件3：均线多头 - 修复shift方法的使用并处理NaN值
        if pd.isna(latest["MA10_shifted"]):
            condition3 = False  # 如果MA10_shifted是NaN，则条件不满足
        else:
            condition3 = (latest["MA5"] > latest["MA10"]) & (
                latest["MA10"] > latest["MA10_shifted"]
            )

        # 条件4：MACD金叉
        condition4 = (latest["MACD"] > latest["Signal"]) & (
            hist_data.iloc[-2]["MACD"] < hist_data.iloc[-2]["Signal"]
        )

        # 市值筛选
        info = ak.stock_individual_info_em(symbol=symbol)
        market_cap = float(info.iloc[4].value) / 100000000  # 将单位从元转换为亿
        # print(f"{symbol} 市值: {market_cap}")
        condition5 = market_cap >= CAPITAL_LIMIT

        if all([condition1, condition2, condition3, condition4, condition5]):
            return {
                "代码": symbol,
                "名称": zt_info["名称"],
                "涨停时间": formatted_time,  # 使用格式化后的时间
                "封单金额(万)": zt_info["封板资金"]
                / 10000,  # 注意这里使用'封板资金'而不是'封单金额'
                "市值(亿)": market_cap,
            }
    except Exception as e:
        print(f"Error processing {symbol}: {str(e)}")
    return None


def get_previous_trade_date(current_date):
    """获取前一个有效交易日"""
    current_dt = datetime.strptime(current_date, "%Y%m%d")
    for i in range(1, 10):
        prev_dt = current_dt - timedelta(days=i)
        prev_date = prev_dt.strftime("%Y%m%d")
        try:
            df = ak.stock_zt_pool_em(date=prev_date)
            if not df.empty:
                return prev_date
        except:
            continue
    raise ValueError("前序交易日获取失败")


def get_market_sentiment(current_date):
    """计算市场情绪指标"""
    # 获取前后交易日数据
    prev_date = get_previous_trade_date(current_date)
    prev_zt = ak.stock_zt_pool_em(date=prev_date)
    curr_zt = ak.stock_zt_pool_em(date=current_date)

    # 基础指标
    zt_count = len(curr_zt)  # 当日涨停家数
    jr_count = len(set(prev_zt["代码"]) & set(curr_zt["代码"]))  # 晋级数量
    jr_rate = jr_count / len(prev_zt) if len(prev_zt) > 0 else 0  # 晋级率

    # 昨日涨停股今日平均表现
    def get_pct_change(code):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=current_date,
                end_date=current_date,
            )
            return df.iloc[0]["涨跌幅"] if not df.empty else None
        except:
            return None

    pct_changes = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(get_pct_change, code) for code in prev_zt["代码"]]
        pct_changes = [f.result() for f in futures if f.result() is not None]

    avg_pct = np.mean(pct_changes) if pct_changes else 0
    
    # 判断冰点条件
    is_ice = (
        (zt_count < SENTIMENT_PARAMS["zt_threshold"])
        and (jr_rate < SENTIMENT_PARAMS["jr_rate"])
        and (avg_pct < SENTIMENT_PARAMS["avg_pct"])
    )
    
    # 添加单个条件的警告信息
    warnings = []
    if zt_count < SENTIMENT_PARAMS["zt_threshold"]:
        warnings.append(f"涨停家数({zt_count})低于阈值({SENTIMENT_PARAMS['zt_threshold']})")
    if jr_rate < SENTIMENT_PARAMS["jr_rate"]:
        warnings.append(f"晋级率({jr_rate:.2%})低于阈值({SENTIMENT_PARAMS['jr_rate']:.2%})")
    if avg_pct < SENTIMENT_PARAMS["avg_pct"]:
        warnings.append(f"平均涨幅({avg_pct:.2f}%)低于阈值({SENTIMENT_PARAMS['avg_pct']}%)")

    return {
        "涨停家数": zt_count,
        "晋级率": jr_rate,
        "平均涨幅": avg_pct,
        "冰点信号": is_ice,
        "警告信息": warnings,
    }


if __name__ == "__main__":
    # 市场情绪判断
    sentiment = get_market_sentiment(TRADE_DATE)
    print(
        f"[市场情绪] 涨停:{sentiment['涨停家数']} 晋级率:{sentiment['晋级率']:.2%} 均涨:{sentiment['平均涨幅']:.2f}%"
    )
    
    # 输出警告信息
    if sentiment["警告信息"]:
        print("\n[市场警告]")
        for warning in sentiment["警告信息"]:
            print(f"- {warning}")

    if sentiment["冰点信号"]:
        print("\n！！情绪冰点，今日暂停操作！！")
    else:
        # 执行原有选股逻辑
        zt_data = get_zt_pool(TRADE_DATE)

        # 使用多线程处理股票评估
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(evaluate_stock, code, zt_data)
                for code in zt_data["代码"]
            ]
            results = [f.result() for f in futures if f.result() is not None]

        # 创建结果DataFrame
        result_df = pd.DataFrame(results)

        print(f"\n符合策略的标的：{len(result_df)}只")
        if not result_df.empty:
            print(result_df.to_string(index=False))
