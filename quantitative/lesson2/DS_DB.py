#!/Users/qyq/miniconda3/envs/quant/bin/python


import akshare as ak
import pandas as pd
import talib
from datetime import datetime, timedelta


# 主函数：每日策略执行
def dragon_strategy_main():
    # 获取交易日
    trade_date = datetime.now().strftime("%Y%m%d")  # 收盘后运行，使用当天日期

    # 步骤1：选股
    selected_stocks = select_main_board_stocks(trade_date)

    # 步骤2：情绪判断
    sentiment_analyzer = MarketSentiment(trade_date)
    sentiment = sentiment_analyzer.get_sentiment_phase()

    # 步骤3：大盘判断
    trend = market_trend_judge()

    # 步骤4：生成信号
    signals = generate_trading_signal(selected_stocks, sentiment, trend)

    # 输出结果
    print(f"\n【{trade_date}交易策略】")
    print(f"市场情绪: {sentiment} | 大盘趋势: {trend}")
    pd.set_option("display.unicode.ambiguous_as_wide", True)
    pd.set_option("display.unicode.east_asian_width", True)
    print(pd.DataFrame(signals).to_markdown(index=False))


def select_main_board_stocks(date):
    """主板选股逻辑"""
    # 获取涨停数据
    zt_pool = ak.stock_zt_pool_em(date=date)
    zt_pool = zt_pool[
        zt_pool["代码"].apply(
            lambda x: x[:3] not in ["300", "688"] and x[0] in ["6", "0"]
        )
    ]

    # 获取炸板数据用于计算炸板次数
    zbgc_data = ak.stock_zt_pool_zbgc_em(date=date)

    # 主板筛选条件
    filtered = zt_pool[
        (zt_pool["流通市值"].between(80e8, 500e8))
        & (zt_pool["成交额"] > 5e8)
        & (~zt_pool["名称"].str.contains("ST"))
        & (zt_pool["首次封板时间"] < "110000")
    ].copy()

    # 添加炸板次数字段（当日是否炸过板）
    filtered["炸板次数"] = filtered["代码"].isin(zbgc_data["代码"]).astype(int)

    # 指标评分（权重可调整）
    def calculate_scores(df):
        # 时间评分：越早封板得分越高（09:30=100分，11:00=0分）
        df["封板时间分钟"] = df["首次封板时间"].apply(
            lambda x: int(x[:2]) * 60 + int(x[2:4])
        )
        df["时间得分"] = (1 - (df["封板时间分钟"] - 570) / 90) * 0.3  # 9:30=570分钟

        # 封板资金评分：金额越大得分越高
        df["资金得分"] = (df["封板资金"] / df["封板资金"].max()) * 0.3

        # 连板数评分：连板越多得分越高
        df["连板得分"] = (df["连板数"] / df["连板数"].max()) * 0.3

        # 炸板次数评分：没炸板得满分
        df["炸板得分"] = (1 - df["炸板次数"] / 1) * 0.1

        return df["时间得分"] + df["资金得分"] + df["连板得分"] + df["炸板得分"]

    # 计算总分并排序
    filtered["总分"] = calculate_scores(filtered)

    return filtered.sort_values("总分", ascending=False).head(5)[
        ["代码", "名称", "连板数", "所属行业", "总分"]
    ]


class MarketSentiment:
    """情绪周期判断"""

    def __init__(self, trade_date):
        self.trade_date = trade_date
        self.zt_data = ak.stock_zt_pool_em(date=trade_date)  # 涨停股池
        self.zbgc_data = ak.stock_zt_pool_zbgc_em(date=trade_date)  # 新增炸板股池
        self.index_data = ak.stock_zh_index_daily(symbol="sh000001")

    def _get_stock_data(self, symbol):
        """获取个股历史数据（含前收盘价）"""
        try:
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
            return df[["日期", "开盘", "收盘"]]
        except Exception as e:
            print(f"获取{symbol}数据失败：{str(e)}")
            return None

    def _calculate_zt_premium(self):
        """计算涨停股溢价率（当日开盘相对前收盘的涨幅）"""
        if self.zt_data.empty:
            return 0

        total_premium = 0
        valid_count = 0

        for symbol in self.zt_data["代码"].unique():
            # 获取个股数据
            hist_data = self._get_stock_data(symbol)
            if hist_data is None:
                continue

            # 找到交易日前一天的收盘价
            prev_day = datetime.strptime(self.trade_date, "%Y%m%d") - timedelta(days=1)
            trade_day = datetime.strptime(self.trade_date, "%Y%m%d")

            try:
                prev_close = hist_data[hist_data["日期"] == prev_day]["收盘"].values[0]
                today_open = hist_data[hist_data["日期"] == trade_day]["开盘"].values[0]

                premium = (today_open - prev_close) / prev_close
                total_premium += premium
                valid_count += 1
            except (IndexError, KeyError):
                continue

        return total_premium / valid_count if valid_count > 0 else 0

    def get_sentiment_phase(self):
        day_data = self.zt_data

        # 情绪指标
        zt_count = len(day_data)
        lb_height = day_data["连板数"].max()

        # 计算真实炸板率：炸板股数 / (涨停股数 + 炸板股数)
        zt_codes = set(day_data["代码"])
        zb_codes = set(self.zbgc_data["代码"])
        real_zb_count = len(zt_codes & zb_codes)  # 先涨停后炸板的股票

        zhaban_rate = (
            real_zb_count / (zt_count + len(zb_codes))
            if (zt_count + len(zb_codes)) > 0
            else 0
        )

        # 情绪判断逻辑
        if zhaban_rate > 0.4 or lb_height <= 4:
            return "退潮期"
        elif lb_height >= 6 and zt_count > 80:
            return "高潮期"
        elif lb_height in [4, 5] and self._calculate_zt_premium() > 0.03:
            return "发酵期"
        else:
            return "启动期"


def market_trend_judge():
    """大盘趋势判断"""
    index_data = ak.stock_zh_index_daily(symbol="sh000001")
    index_data["MA20"] = index_data["close"].rolling(20).mean()
    macd, _, _ = talib.MACD(index_data["close"])

    last_close = index_data["close"].iloc[-1]
    if (last_close > index_data["MA20"].iloc[-1]) and (macd.iloc[-1] > 0):
        return "多头趋势"
    else:
        return "空头趋势"


def generate_trading_signal(stocks, sentiment, trend):
    """生成交易信号"""
    signals = []
    for _, stock in stocks.iterrows():
        signal = {
            "代码": stock["代码"],
            "名称": stock["名称"],
            "连板数": stock["连板数"],
            "推荐操作": "观望",
            "买入条件": [],
            "止损位": "N/A",
        }

        if trend == "多头趋势":
            if sentiment in ["启动期", "发酵期"]:
                if stock["连板数"] == 1:
                    signal.update(
                        {
                            "推荐操作": "打板介入",
                            "买入条件": ["高开3%-5%", "竞价量>昨日15%"],
                            "止损位": "当日最低价-3%",
                        }
                    )
                elif stock["连板数"] >= 3:
                    signal.update(
                        {
                            "推荐操作": "分歧低吸",
                            "买入条件": ["早盘回踩5日线"],
                            "止损位": "成本价-5%",
                        }
                    )
            elif sentiment == "高潮期":
                signal["推荐操作"] = "持有观察"

        signals.append(signal)
    return signals


if __name__ == "__main__":
    dragon_strategy_main()
