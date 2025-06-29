# 安装必要的包（如果还没有安装）
# !pip install lib-pybroker akshare

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import akshare as ak
from datetime import datetime
import time
import warnings

warnings.filterwarnings("ignore")

# 设置matplotlib中文字体
plt.rcParams["font.sans-serif"] = [
    "SimHei",
    "Microsoft YaHei",
    "DejaVu Sans",
    "Arial Unicode MS",
]  # 用来正常显示中文标签
plt.rcParams["axes.unicode_minus"] = False  # 用来正常显示负号

# 导入 pybroker 和 talib
try:
    import pybroker

    try:
        from pybroker import Strategy, StrategyConfig, ExecContext
    except ImportError:
        from pybroker.strategy import Strategy
        from pybroker.config import StrategyConfig
        from pybroker.context import ExecContext

    from pybroker.common import PriceType
    import talib

    print("PyBroker 和 TA-Lib 导入成功")
except ImportError:
    print("请先安装 PyBroker 和 TA-Lib: pip install lib-pybroker TA-Lib")
    raise

# 设置回测参数
BACKTEST_START = "2023-01-01"
BACKTEST_END = datetime.now().strftime("%Y-%m-%d")
MAX_POSITIONS = 3
INITIAL_CASH = 1000000

print(f"回测期间: {BACKTEST_START} 到 {BACKTEST_END}")

# 启用缓存 (如果支持)
try:
    pybroker.enable_data_source_cache("yang_bao_yin_strategy")
except AttributeError:
    print("注意：当前PyBroker版本不支持enable_data_source_cache")


# 全局变量存储股票代码到名称的映射
STOCK_NAME_MAP = {}

# 全局变量存储情绪判断结果
MARKET_SENTIMENT = {
    "date": None,
    "hot_stocks": [],
    "sentiment_active": False,
    "max_7day_gain": 0.0,
}


# 获取主板股票列表
def get_main_board_stocks():
    """获取主板股票列表"""
    global STOCK_NAME_MAP

    # 使用akshare获取A股股票信息
    try:
        # 获取A股股票基本信息
        print("正在获取A股股票基本信息...")
        all_stocks = ak.stock_info_a_code_name()
        time.sleep(1)  # 获取股票列表后休眠1秒
    except Exception as e:
        print(f"获取股票列表失败，尝试备用方法: {e}")
        try:
            # 备用方法：获取沪深A股实时数据
            print("使用备用方法获取股票列表...")
            time.sleep(2)  # 切换方法前休眠2秒
            all_stocks = ak.stock_zh_a_spot_em()
            time.sleep(1)  # 获取成功后休眠1秒
        except Exception as e2:
            print(f"备用方法也失败: {e2}")
            # 如果都失败，返回空DataFrame
            return pd.DataFrame()

    def is_main_board_stock(code, name):
        if any(code.startswith(prefix) for prefix in ["300", "688"]):
            return False
        if any(keyword in name for keyword in ["ST", "st", "退"]):
            return False
        main_board_prefixes = ["600", "601", "603", "605", "000", "001", "002"]
        return any(code.startswith(prefix) for prefix in main_board_prefixes)

    # akshare返回的列名可能不同，需要适配
    try:
        # 尝试标准列名
        code_col = "代码" if "代码" in all_stocks.columns else "code"
        name_col = "名称" if "名称" in all_stocks.columns else "name"
        if code_col not in all_stocks.columns:
            # 查找可能的代码列
            for col in all_stocks.columns:
                if "代码" in col or "code" in col.lower():
                    code_col = col
                    break
        if name_col not in all_stocks.columns:
            # 查找可能的名称列
            for col in all_stocks.columns:
                if "名称" in col or "name" in col.lower():
                    name_col = col
                    break
    except Exception:
        # 如果都没有，使用第一列和第二列
        if len(all_stocks.columns) >= 2:
            code_col = all_stocks.columns[0]
            name_col = all_stocks.columns[1]
        else:
            return pd.DataFrame()

    main_board_stocks = all_stocks[
        all_stocks.apply(
            lambda row: is_main_board_stock(row[code_col], row[name_col]), axis=1
        )
    ]

    # 创建股票代码到名称的映射
    for _, row in main_board_stocks.iterrows():
        STOCK_NAME_MAP[row[code_col]] = row[name_col]

    return main_board_stocks


# 获取单只股票历史数据的辅助函数
def get_single_stock_data(stock_code, start_date, end_date, max_retries=3):
    """获取单只股票的历史数据 - 使用akshare的stock_zh_a_hist接口"""

    for retry in range(max_retries):
        try:
            # 使用akshare的stock_zh_a_hist获取历史K线数据
            # 参数说明：
            # symbol: 股票代码，直接使用6位数字代码
            # period: 周期，'daily'表示日线
            # start_date: 开始日期，格式YYYYMMDD
            # end_date: 结束日期，格式YYYYMMDD
            # adjust: 复权类型，"qfq"表示前复权

            # stock_zh_a_hist接口直接使用股票代码，不需要市场前缀
            formatted_code = stock_code

            start_formatted = start_date.replace("-", "")
            end_formatted = end_date.replace("-", "")

            data = ak.stock_zh_a_hist(
                symbol=formatted_code,
                period="daily",
                start_date=start_formatted,
                end_date=end_formatted,
                adjust="qfq",  # 使用前复权
            )

            if data is not None and not data.empty:
                # akshare的stock_zh_a_hist返回的列名标准化
                # stock_zh_a_hist列名: 日期, 股票代码, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
                data = data.reset_index()  # 确保日期列可访问

                # 检查并重命名列
                column_mapping = {
                    "日期": "date",
                    "开盘": "open",
                    "最高": "high",
                    "最低": "low",
                    "收盘": "close",
                    "成交量": "volume",
                    "成交额": "amount",
                    "股票代码": "symbol_code",
                    "date": "date",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                }

                # 重命名现有列
                for old_col, new_col in column_mapping.items():
                    if old_col in data.columns:
                        data = data.rename(columns={old_col: new_col})

                # 确保有必要的列
                if "date" in data.columns:
                    data["date"] = pd.to_datetime(data["date"])
                elif data.index.name and (
                    "date" in str(data.index.name).lower()
                    or "日期" in str(data.index.name)
                ):
                    data = data.reset_index()
                    data["date"] = pd.to_datetime(data.iloc[:, 0])  # 第一列作为日期

                # 添加symbol列
                data["symbol"] = stock_code

                # 计算涨跌幅（如果没有的话）
                if "pct_change" not in data.columns and "close" in data.columns:
                    data["pct_change"] = data["close"].pct_change() * 100

                # 选择需要的列
                required_cols = [
                    "symbol",
                    "date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
                available_cols = [col for col in required_cols if col in data.columns]

                if "pct_change" in data.columns:
                    available_cols.append("pct_change")

                data = data[available_cols]

                return data
            else:
                print(f"stock_zh_a_hist返回空数据: {stock_code}")
                return None

        except Exception as e:
            if retry < max_retries - 1:
                # 逐次增加重试间隔，防止频繁请求被限制
                sleep_time = 1.0 * (retry + 1)  # 1秒、2秒、3秒
                print(
                    f"获取 {stock_code} 数据失败，{sleep_time}秒后重试 (第{retry+1}次)"
                )
                time.sleep(sleep_time)
                continue
            else:
                print(f"获取 {stock_code} 数据失败，已重试{max_retries}次: {e}")
                return None

    return None


# 获取股票历史数据并转换为PyBroker格式
def prepare_stock_data():
    """准备PyBroker格式的股票数据 - 使用akshare的stock_zh_a_hist接口"""
    print("正在获取主板股票列表...")
    main_board_stocks = get_main_board_stocks()

    # 获取股票代码列表
    try:
        code_col = (
            "代码"
            if "代码" in main_board_stocks.columns
            else main_board_stocks.columns[0]
        )
        stock_codes = main_board_stocks[code_col].tolist()  # [:100]  # 限制数量以便测试
    except:
        stock_codes = []

    print(f"回测期间: {BACKTEST_START} 到 {BACKTEST_END}")
    print(f"正在获取 {len(stock_codes)} 只股票的历史数据...")

    all_data = []
    failed_count = 0

    for i, stock_code in enumerate(stock_codes):
        if i % 50 == 0:
            progress = (i + 1) / len(stock_codes) * 100
            print(f"进度: {i+1}/{len(stock_codes)} ({progress:.1f}%)")

        try:
            # 使用stock_zh_a_hist获取单只股票历史数据
            data = get_single_stock_data(stock_code, BACKTEST_START, BACKTEST_END)

            if data is not None and not data.empty and len(data) > 50:
                all_data.append(data)
            else:
                failed_count += 1

            time.sleep(0.1)  # 基础请求间隔

            # 每获取100只股票休眠10秒防止被风控
            if (i + 1) % 100 == 0:
                print(f"已获取{i+1}只股票，休眠10秒防止风控...")
                time.sleep(10)

        except Exception as e:
            print(f"获取 {stock_code} 数据失败: {e}")
            failed_count += 1
            continue

    if all_data:
        combined_data = pd.concat(all_data, ignore_index=True)
        print(f"✅ 成功获取 {len(all_data)} 只股票的数据")
        print(f"❌ 失败 {failed_count} 只股票")
        print(f"📊 总数据行数: {len(combined_data)}")
        print(
            f"📅 数据日期范围: {combined_data['date'].min()} 到 {combined_data['date'].max()}"
        )
        return combined_data
    else:
        print("❌ 没有获取到有效数据")
        print("💡 可能的原因：")
        print("   1. 网络连接问题")
        print("   2. stock_zh_a_hist接口限制")
        print("   3. 股票代码格式问题")
        return None


# 注册自定义列 (如果支持)
try:
    pybroker.register_columns("pct_change")
except AttributeError:
    print("注意：当前PyBroker版本不支持register_columns")

# 定义5日均线指标 - 使用 talib (用于选股)
try:
    ma5_indicator = pybroker.indicator(
        "ma5", lambda data: talib.SMA(data.close.astype(float), timeperiod=5)
    )
except AttributeError:
    from pybroker.indicator import indicator

    ma5_indicator = indicator(
        "ma5", lambda data: talib.SMA(data.close.astype(float), timeperiod=5)
    )

# 定义13日均线指标 - 使用 talib (用于卖出)
try:
    ma13_indicator = pybroker.indicator(
        "ma13", lambda data: talib.SMA(data.close.astype(float), timeperiod=13)
    )
except AttributeError:
    ma13_indicator = indicator(
        "ma13", lambda data: talib.SMA(data.close.astype(float), timeperiod=13)
    )

# 新增：20日均线指标 - 用于趋势判断
try:
    ma20_indicator = pybroker.indicator(
        "ma20", lambda data: talib.SMA(data.close.astype(float), timeperiod=20)
    )
except AttributeError:
    ma20_indicator = indicator(
        "ma20", lambda data: talib.SMA(data.close.astype(float), timeperiod=20)
    )

# 修改：30日均线指标 - 降低周期要求，加速启动
try:
    ma30_indicator = pybroker.indicator(
        "ma30", lambda data: talib.SMA(data.close.astype(float), timeperiod=30)
    )
except AttributeError:
    ma30_indicator = indicator(
        "ma30", lambda data: talib.SMA(data.close.astype(float), timeperiod=30)
    )

# 新增：RSI指标 - 用于强势判断
try:
    rsi_indicator = pybroker.indicator(
        "rsi", lambda data: talib.RSI(data.close.astype(float), timeperiod=14)
    )
except AttributeError:
    rsi_indicator = indicator(
        "rsi", lambda data: talib.RSI(data.close.astype(float), timeperiod=14)
    )

# 新增：MACD线指标 - 用于动量判断
try:
    macd_line_indicator = pybroker.indicator(
        "macd_line",
        lambda data: talib.MACD(
            data.close.astype(float), fastperiod=12, slowperiod=26, signalperiod=9
        )[
            0
        ],  # [0] 是MACD线
    )
except AttributeError:
    macd_line_indicator = indicator(
        "macd_line",
        lambda data: talib.MACD(
            data.close.astype(float), fastperiod=12, slowperiod=26, signalperiod=9
        )[
            0
        ],  # [0] 是MACD线
    )

# 新增：DEA线指标 - 用于动量判断
try:
    dea_line_indicator = pybroker.indicator(
        "dea_line",
        lambda data: talib.MACD(
            data.close.astype(float), fastperiod=12, slowperiod=26, signalperiod=9
        )[
            1
        ],  # [1] 是DEA线（信号线）
    )
except AttributeError:
    dea_line_indicator = indicator(
        "dea_line",
        lambda data: talib.MACD(
            data.close.astype(float), fastperiod=12, slowperiod=26, signalperiod=9
        )[
            1
        ],  # [1] 是DEA线（信号线）
    )

# 新增：成交量均线指标 - 用于量能判断
try:
    volume_ma_indicator = pybroker.indicator(
        "volume_ma", lambda data: talib.SMA(data.volume.astype(float), timeperiod=20)
    )
except AttributeError:
    volume_ma_indicator = indicator(
        "volume_ma", lambda data: talib.SMA(data.volume.astype(float), timeperiod=20)
    )

# 新增：10日成交量均线指标 - 用于买入时的成交量过滤
try:
    volume_ma10_indicator = pybroker.indicator(
        "volume_ma10", lambda data: talib.SMA(data.volume.astype(float), timeperiod=10)
    )
except AttributeError:
    volume_ma10_indicator = indicator(
        "volume_ma10", lambda data: talib.SMA(data.volume.astype(float), timeperiod=10)
    )

# 新增：KDJ指标 - 用于过滤超买状态
try:
    kdj_k_indicator = pybroker.indicator(
        "kdj_k",
        lambda data: talib.STOCH(
            data.high.astype(float),
            data.low.astype(float),
            data.close.astype(float),
            fastk_period=9,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0,
        )[
            0
        ],  # K值
    )
    kdj_d_indicator = pybroker.indicator(
        "kdj_d",
        lambda data: talib.STOCH(
            data.high.astype(float),
            data.low.astype(float),
            data.close.astype(float),
            fastk_period=9,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0,
        )[
            1
        ],  # D值
    )
except AttributeError:
    kdj_k_indicator = indicator(
        "kdj_k",
        lambda data: talib.STOCH(
            data.high.astype(float),
            data.low.astype(float),
            data.close.astype(float),
            fastk_period=9,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0,
        )[
            0
        ],  # K值
    )
    kdj_d_indicator = indicator(
        "kdj_d",
        lambda data: talib.STOCH(
            data.high.astype(float),
            data.low.astype(float),
            data.close.astype(float),
            fastk_period=9,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0,
        )[
            1
        ],  # D值
    )

# 定义全局参数存储选股结果 (如果支持)
try:
    pybroker.param("selected_stocks", [])
except AttributeError:
    # 如果不支持，我们使用全局变量
    SELECTED_STOCKS = []


# 市场情绪判断函数
def market_sentiment_analysis(ctxs):
    """市场情绪判断函数 - 检查是否有7日涨幅超过60%的标的"""
    global MARKET_SENTIMENT
    current_date = None
    hot_stocks = []
    max_7day_gain = 0.0

    for symbol, ctx in ctxs.items():
        if current_date is None:
            current_date = (
                ctx.date[-1] if hasattr(ctx.date, "__getitem__") else ctx.date
            )

        try:
            # 检查数据长度是否足够计算7日涨幅
            if len(ctx.close) < 8:  # 需要至少8天数据（今天+过去7天）
                continue

            # 计算7日涨幅
            current_price = ctx.close[-1]  # 今日收盘价
            price_7days_ago = ctx.close[-8]  # 7天前收盘价

            if price_7days_ago > 0:
                gain_7days = (current_price - price_7days_ago) / price_7days_ago * 100

                # 更新最大7日涨幅
                if gain_7days > max_7day_gain:
                    max_7day_gain = gain_7days

                # 如果7日涨幅超过60%，记录为热门股票
                if gain_7days > 60:
                    stock_name = STOCK_NAME_MAP.get(symbol, symbol)
                    hot_stocks.append(
                        {
                            "symbol": symbol,
                            "name": stock_name,
                            "gain_7days": gain_7days,
                            "current_price": current_price,
                            "price_7days_ago": price_7days_ago,
                        }
                    )

        except Exception as e:
            continue

    # 判断市场情绪是否活跃
    sentiment_active = len(hot_stocks) > 0

    # 更新全局情绪状态
    MARKET_SENTIMENT.update(
        {
            "date": current_date,
            "hot_stocks": hot_stocks,
            "sentiment_active": sentiment_active,
            "max_7day_gain": max_7day_gain,
        }
    )

    # 输出情绪分析结果
    if sentiment_active:
        print(f"\n🔥 {current_date} 市场情绪活跃 - 发现{len(hot_stocks)}只热门股票:")
        print(f"📈 市场最大7日涨幅: {max_7day_gain:.1f}%")

        # 按涨幅排序显示前5只
        hot_stocks_sorted = sorted(
            hot_stocks, key=lambda x: x["gain_7days"], reverse=True
        )
        for i, stock in enumerate(hot_stocks_sorted[:5]):
            stock_display = f"{stock['name']}({stock['symbol']})"
            print(
                f"   {i+1}. {stock_display}: +{stock['gain_7days']:.1f}% "
                f"({stock['price_7days_ago']:.2f} → {stock['current_price']:.2f})"
            )

        if len(hot_stocks) > 5:
            print(f"   ... 还有{len(hot_stocks)-5}只热门股票")

        print("✅ 情绪共振条件满足，可执行十字星反转买入")

        # 记录到情绪日志
        try:
            with open("market_sentiment.log", "a", encoding="utf-8") as log_file:
                log_file.write(f"\n{'='*60}\n")
                log_file.write(f"{current_date} 市场情绪分析\n")
                log_file.write(f"情绪状态: 活跃 (发现{len(hot_stocks)}只热门股票)\n")
                log_file.write(f"最大7日涨幅: {max_7day_gain:.1f}%\n")
                log_file.write("热门股票列表:\n")

                for stock in hot_stocks_sorted:
                    stock_display = f"{stock['name']}({stock['symbol']})"
                    log_file.write(
                        f"  {stock_display}: +{stock['gain_7days']:.1f}% "
                        f"({stock['price_7days_ago']:.2f} → {stock['current_price']:.2f})\n"
                    )

                log_file.write(
                    f"时间戳: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
        except Exception as e:
            print(f"写入情绪日志失败: {e}")

    else:
        print(f"\n😴 {current_date} 市场情绪平淡 - 无热门股票")
        print(f"📊 市场最大7日涨幅: {max_7day_gain:.1f}%")
        print("❌ 情绪共振条件不满足，暂停十字星反转买入")

        # 记录到情绪日志
        try:
            with open("market_sentiment.log", "a", encoding="utf-8") as log_file:
                log_file.write(
                    f"\n{current_date} 市场情绪: 平淡 (最大7日涨幅: {max_7day_gain:.1f}%)\n"
                )
        except Exception as e:
            print(f"写入情绪日志失败: {e}")


# 缩量十字星反转选股函数
def doji_reversal_screening(ctxs):
    """缩量十字星反转选股函数 - 识别十字星反转信号，第三天买入"""
    current_date = None
    selected_stocks = []

    for symbol, ctx in ctxs.items():
        if current_date is None:
            current_date = ctx.date

        try:
            # 获取最近的数据
            df_length = len(ctx.close)

            # 基本数据检查 - 需要至少22天数据（20日均线+十字星日+确认日）
            if df_length < 22:
                continue

            # 检查是否有足够的成交量数据
            if len(ctx.volume) < 22:
                continue

            # 获取20日成交量均线
            volume_ma20 = ctx.indicator("volume_ma")
            if len(volume_ma20) < 2:
                continue

            # 获取最近三天的数据
            # 今天（ctx.date[-1]）：策略执行日，今天要做买入决策
            # 昨天（ctx.date[-2]）：确认日，验证反转信号
            # 前天（ctx.date[-3]）：十字星日，出现十字星形态

            confirm_close = ctx.close[-2]  # 确认日收盘价
            confirm_open = ctx.open[-2]  # 确认日开盘价
            confirm_high = ctx.high[-2]  # 确认日最高价
            confirm_volume = ctx.volume[-2]  # 确认日成交量

            doji_close = ctx.close[-3]  # 十字星日收盘价
            doji_open = ctx.open[-3]  # 十字星日开盘价
            doji_high = ctx.high[-3]  # 十字星日最高价
            doji_low = ctx.low[-3]  # 十字星日最低价
            doji_volume = ctx.volume[-3]  # 十字星日成交量

            # 避免除零错误
            if doji_open <= 0 or doji_close <= 0:
                continue

            # === 第一步：判断十字星形态 ===
            # 1. 实体小于1个点
            body_size = abs(doji_close - doji_open) / doji_open * 100
            is_small_body = body_size < 1.0

            # 2. 判断十字星的上下影线条件
            is_valid_doji = False

            if doji_close >= doji_open:  # 收盘价大于等于开盘价
                # 最高价大于收盘价，最低价小于开盘价
                upper_shadow = doji_high > doji_close
                lower_shadow = doji_low < doji_open
                is_valid_doji = upper_shadow and lower_shadow
            else:  # 收盘价小于开盘价
                # 最高价大于开盘价，最低价低于收盘价
                upper_shadow = doji_high > doji_open
                lower_shadow = doji_low < doji_close
                is_valid_doji = upper_shadow and lower_shadow

            # 3. 缩量条件：十字星当天成交量低于20日平均成交量
            volume_ma20_value = volume_ma20[-2]  # 十字星当天的20日均量
            is_low_volume = doji_volume < volume_ma20_value

            # === 第二步：验证反转信号 ===
            # 确认日收盘价高于十字星日最高价，确认反转
            is_reversal = confirm_close > doji_high

            # 新增：确认日必须为阳线（收盘价 > 开盘价）
            is_positive_candle = confirm_close > confirm_open

            # === 第三步：最高价超过30日均线确认 ===
            # 获取30日均线数据
            ma5 = ctx.indicator("ma5")
            ma20 = ctx.indicator("ma20")
            ma30 = ctx.indicator("ma30")
            confirm_high = ctx.high[-2]  # 确认日最高价
            # is_above_ma30 = len(ma30) > 0 and confirm_high > max(ma30[-2], ma20[-2])

            # === 第四步：DEA 增大且相关条件 ===
            # 获取MACD线和DEA线数据
            macd_line = ctx.indicator("macd_line")
            dea_line = ctx.indicator("dea_line")
            is_dea_conditions_met = False
            dea_yesterday = 0
            dea_today = 0
            macd_today = 0

            if (
                macd_line is not None
                and len(macd_line) >= 2
                and dea_line is not None
                and len(dea_line) >= 2
            ):

                dea_doji_day = dea_line[-3]  # 十字星日的DEA值
                dea_confirm_day = dea_line[-2]  # 确认日的DEA值
                macd_confirm_day = macd_line[-2]  # 确认日的MACD值

                # 条件1：DEA增大（确认日DEA > 十字星日DEA）
                is_dea_increasing = dea_confirm_day > dea_doji_day
                # 条件2：DEA小于0
                is_dea_negative = dea_confirm_day < 0
                # 条件3：MACD大于DEA
                is_macd_above_dea = macd_confirm_day > dea_confirm_day

                # 所有条件都满足
                is_dea_conditions_met = (
                    is_dea_increasing and is_dea_negative and is_macd_above_dea
                )

            # === 第五步：KDJ指标条件 ===
            # 获取KDJ指标数据并计算J值
            kdj_k = ctx.indicator("kdj_k")
            kdj_d = ctx.indicator("kdj_d")
            is_kdj_conditions_met = False
            j_value = 0

            if (
                kdj_k is not None
                and len(kdj_k) >= 1
                and kdj_d is not None
                and len(kdj_d) >= 1
            ):
                k_value = kdj_k[-2]  # 确认日的K值
                d_value = kdj_d[-2]  # 确认日的D值
                j_value = 3 * k_value - 2 * d_value  # J = 3K - 2D

                # J值小于90，避免超买状态
                is_kdj_conditions_met = j_value < 90

            # === 综合判断 ===
            if (
                is_small_body
                and is_valid_doji
                and is_low_volume
                and is_reversal
                and is_positive_candle
                and is_dea_conditions_met
                and is_kdj_conditions_met
            ):
                # 计算评分
                score = 0
                reasons = []

                # 基础分：十字星质量
                doji_quality = 0

                # 实体越小越好
                if body_size < 0.5:
                    doji_quality += 20
                    reasons.append("极小实体")
                elif body_size < 1.0:
                    doji_quality += 15
                    reasons.append("小实体")

                # 上下影线长度评分
                upper_shadow_pct = (
                    (doji_high - max(doji_open, doji_close))
                    / max(doji_open, doji_close)
                    * 100
                )
                lower_shadow_pct = (
                    (min(doji_open, doji_close) - doji_low)
                    / min(doji_open, doji_close)
                    * 100
                )

                if upper_shadow_pct > 2 and lower_shadow_pct > 2:
                    doji_quality += 15
                    reasons.append("明显上下影线")
                elif upper_shadow_pct > 1 or lower_shadow_pct > 1:
                    doji_quality += 10
                    reasons.append("有上下影线")

                score += doji_quality

                # 缩量程度评分
                volume_ratio = doji_volume / volume_ma20_value
                volume_score = 0
                if volume_ratio < 0.5:
                    volume_score = 20
                    reasons.append("大幅缩量")
                elif volume_ratio < 0.8:
                    volume_score = 15
                    reasons.append("明显缩量")
                else:
                    volume_score = 10
                    reasons.append("缩量")

                score += volume_score

                # 反转强度评分
                reversal_pct = (confirm_close - doji_high) / doji_high * 100
                reversal_score = 0
                if reversal_pct > 3:
                    reversal_score = 20
                    reasons.append("强势反转")
                elif reversal_pct > 1:
                    reversal_score = 15
                    reasons.append("有效反转")
                else:
                    reversal_score = 10
                    reasons.append("反转确认")

                score += reversal_score

                # 技术面加分
                tech_bonus = 0

                # 开盘价和收盘价位置评分（替代原来的单一开盘价位置逻辑）
                confirm_open = ctx.open[-2]  # 确认日开盘价
                confirm_close = ctx.close[-2]  # 确认日收盘价

                # 获取20日和30日均线值
                ma20_value = ma20[-2] if len(ma20) > 0 else 0
                ma30_value = ma30[-2] if len(ma30) > 0 else 0

                # 开盘价位置评分：开盘价低于均线加分（低位启动）
                if confirm_open < ma30_value:
                    tech_bonus += 20
                    reasons.append("开盘价低于30日线")

                if confirm_open < ma20_value:
                    tech_bonus += 10
                    reasons.append("开盘价低于20日线")

                # 收盘价位置评分：收盘价高于均线加分（突破确认）
                if confirm_close > ma30_value:
                    tech_bonus += 10
                    reasons.append("收盘价突破30日线")

                if confirm_close > ma20_value:
                    tech_bonus += 20
                    reasons.append("收盘价突破20日线")

                # 新增：确认日收盘价相对于30日均线的超越程度评分
                if ma30_value > 0 and confirm_close > ma30_value:
                    exceed_ma30_pct = (confirm_close - ma30_value) / ma30_value * 100
                    exceed_bonus = 0
                    if exceed_ma30_pct > 10:  # 超越30日线10%以上
                        exceed_bonus = 25
                        reasons.append(f"大幅超越30日线({exceed_ma30_pct:.1f}%)")
                    elif exceed_ma30_pct > 5:  # 超越30日线5%-10%
                        exceed_bonus = 20
                        reasons.append(f"明显超越30日线({exceed_ma30_pct:.1f}%)")
                    elif exceed_ma30_pct > 2:  # 超越30日线2%-5%
                        exceed_bonus = 15
                        reasons.append(f"有效超越30日线({exceed_ma30_pct:.1f}%)")
                    elif exceed_ma30_pct > 0:  # 刚好超越30日线
                        exceed_bonus = 5
                        reasons.append(f"突破30日线({exceed_ma30_pct:.1f}%)")

                    tech_bonus += exceed_bonus

                # 均线多头排列判断：5日线 > 20日线 > 30日线（上升趋势）
                if (
                    len(ma5) > 0
                    and len(ma20) > 0
                    and len(ma30) > 0
                    and ma5[-2] > ma20[-2] > ma30[-2]
                ):
                    tech_bonus += 20
                    reasons.append("均线多头排列")

                # DEA增大加分
                if is_dea_conditions_met:
                    dea_improvement = dea_confirm_day - dea_doji_day  # 改善程度
                    if dea_improvement > 0.02:  # 改善幅度较大
                        tech_bonus += 15
                        reasons.append("DEA明显改善")
                    else:
                        tech_bonus += 10
                        reasons.append("DEA增大")

                # 确认日涨幅加分
                confirm_daily_gain_pct = (
                    (confirm_close - confirm_open) / confirm_open * 100
                )
                if confirm_daily_gain_pct > 9:
                    tech_bonus += 20
                    reasons.append(f"确认日大涨({confirm_daily_gain_pct:.1f}%)")
                elif confirm_daily_gain_pct > 5:
                    tech_bonus += 10
                    reasons.append(f"确认日上涨({confirm_daily_gain_pct:.1f}%)")

                score += tech_bonus

                # === 新增：确认日成交量判断 ===
                confirmation_day_volume = ctx.volume[-2]  # 确认日成交量
                doji_day_volume = ctx.volume[-3]  # 十字星日成交量
                confirmation_volume_bonus = 0

                if doji_day_volume > 0:
                    confirmation_to_doji_volume_ratio = (
                        confirmation_day_volume / doji_day_volume
                    )
                    if confirmation_to_doji_volume_ratio > 6.0:
                        confirmation_volume_bonus = 10
                        tech_bonus += confirmation_volume_bonus
                        reasons.append(
                            f"确认日大幅放量({confirmation_to_doji_volume_ratio:.1f}倍)"
                        )
                else:
                    # Handle case where doji_day_volume is 0, perhaps skip or assign neutral ratio
                    confirmation_to_doji_volume_ratio = float(
                        "inf"
                    )  # Or some other indicator

                # 计算30日均线超越程度（用于记录）
                exceed_ma30_pct = 0
                if ma30_value > 0 and confirm_close > ma30_value:
                    exceed_ma30_pct = (confirm_close - ma30_value) / ma30_value * 100

                selected_stocks.append(
                    {
                        "symbol": symbol,
                        "score": score,
                        "doji_date": ctx.date,  # 记录验证日期
                        "doji_body_size": body_size,
                        "volume_ratio": volume_ratio,
                        "reversal_pct": reversal_pct,
                        "doji_high": doji_high,
                        "confirm_close": confirm_close,
                        "confirm_daily_gain_pct": confirm_daily_gain_pct,  # 确认日涨幅
                        "exceed_ma30_pct": exceed_ma30_pct,  # 30日均线超越程度
                        "ma30_value": ma30_value,  # 30日均线值
                        "reasons": reasons,
                        "doji_quality": doji_quality,
                        "volume_score": volume_score,
                        "reversal_score": reversal_score,
                        "tech_bonus": tech_bonus,
                        "upper_shadow_pct": upper_shadow_pct,
                        "lower_shadow_pct": lower_shadow_pct,
                        "dea_doji_day": (
                            dea_doji_day
                            if (
                                macd_line is not None
                                and len(macd_line) >= 3
                                and dea_line is not None
                                and len(dea_line) >= 3
                            )
                            else 0
                        ),
                        "dea_confirm_day": (
                            dea_confirm_day
                            if (
                                macd_line is not None
                                and len(macd_line) >= 3
                                and dea_line is not None
                                and len(dea_line) >= 3
                            )
                            else 0
                        ),
                        "dea_improvement": (
                            (dea_confirm_day - dea_doji_day)
                            if (
                                is_dea_conditions_met
                                and macd_line is not None
                                and len(macd_line) >= 3
                                and dea_line is not None
                                and len(dea_line) >= 3
                            )
                            else 0
                        ),
                        "j_value": j_value,  # KDJ的J值
                        "confirmation_to_doji_volume_ratio": (
                            confirmation_to_doji_volume_ratio
                            if doji_day_volume > 0
                            else -1
                        ),  # Store the ratio
                        "confirmation_volume_bonus": confirmation_volume_bonus,
                    }
                )

        except Exception as e:
            continue

    # 按评分排序，并筛选出分数高于80的股票
    if selected_stocks:
        selected_stocks = sorted(
            selected_stocks, key=lambda x: x["score"], reverse=True
        )
        # 筛选分数高于80的股票
        selected_stocks = [stock for stock in selected_stocks if stock["score"] > 100]

    # 保存选股结果
    try:
        pybroker.param("selected_stocks", selected_stocks)
    except (AttributeError, NameError):
        global SELECTED_STOCKS
        SELECTED_STOCKS = selected_stocks

    # 输出选股结果并记录到日志文件
    if selected_stocks:
        # 获取当前日期字符串
        current_date_str = (
            current_date[-1]
            if hasattr(current_date, "__getitem__") and len(current_date) > 0
            else str(current_date)
        )
        print(f"\n{current_date_str} 缩量十字星反转选股结果:")

        # 写入日志文件
        log_filename = "daily_stock_selection.log"
        try:
            with open(log_filename, "a", encoding="utf-8") as log_file:
                log_file.write(f"\n{'='*60}\n")
                log_file.write(f"{current_date_str} 缩量十字星反转选股结果 (前10名)\n")
                log_file.write(f"{'='*60}\n")

                for i, stock in enumerate(selected_stocks[:10]):  # 显示前10只
                    symbol = stock["symbol"]
                    name = STOCK_NAME_MAP.get(symbol, symbol)  # 获取股票名称
                    stock_display = f"{name}({symbol})"

                    # 控制台输出
                    print(
                        f"{i+1}. {stock_display} - 评分:{stock['score']:.0f} "
                        f"实体:{stock['doji_body_size']:.2f}% 缩量:{stock['volume_ratio']:.2f} "
                        f"反转:{stock['reversal_pct']:.1f}% 确认日涨幅:{stock['confirm_daily_gain_pct']:.1f}% "
                        f"超越30日线:{stock['exceed_ma30_pct']:.1f}% "
                        f"DEA:{stock['dea_confirm_day']:.4f} J值:{stock['j_value']:.1f} "
                        f"确认日量比:{stock['confirmation_to_doji_volume_ratio']:.1f}"
                    )
                    print(f"   原因: {', '.join(stock['reasons'])}")

                    # 日志文件输出
                    log_file.write(
                        f"{i+1:2d}. {stock_display}\n"
                        f"    总评分: {stock['score']:.0f}分\n"
                        f"    十字星质量: {stock['doji_quality']}分 (实体{stock['doji_body_size']:.2f}%)\n"
                        f"    缩量程度: {stock['volume_score']}分 (量比{stock['volume_ratio']:.2f})\n"
                        f"    反转强度: {stock['reversal_score']}分 (反转{stock['reversal_pct']:.1f}%)\n"
                        f"    确认日涨幅: {stock['confirm_daily_gain_pct']:.1f}%\n"
                        f"    30日均线: ¥{stock['ma30_value']:.2f}, 超越程度: {stock['exceed_ma30_pct']:.1f}%\n"
                        f"    技术面: {stock['tech_bonus']}分\n"
                        f"    DEA: 十字星日{stock['dea_doji_day']:.4f} → 确认日{stock['dea_confirm_day']:.4f} (改善{stock['dea_improvement']:.4f})\n"
                        f"    KDJ: J值={stock['j_value']:.1f} (需<90)\n"
                        f"    上影线: {stock['upper_shadow_pct']:.1f}%, 下影线: {stock['lower_shadow_pct']:.1f}%\n"
                        f"    十字星最高价: ¥{stock['doji_high']:.2f}, 确认日收盘: ¥{stock['confirm_close']:.2f}\n"
                        f"    原因: {', '.join(stock['reasons'])}\n"
                        f"    确认日成交量比例: {stock['confirmation_to_doji_volume_ratio']:.2f}\n"
                        f"    确认日成交量奖励: {stock['confirmation_volume_bonus']}\n\n"
                    )

                log_file.write(f"总计十字星反转信号数: {len(selected_stocks)}\n")
                log_file.write(
                    f"时间戳: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )

        except Exception as e:
            print(f"写入日志文件失败: {e}")

        print(f"✅ 选股结果已记录到: {log_filename}")
    else:
        # 当没有选出任何股票时的提示
        current_date_str = (
            current_date[-1]
            if hasattr(current_date, "__getitem__") and len(current_date) > 0
            else str(current_date)
        )
        print(f"\n{current_date_str} 选股结果: 今日无十字星反转信号")

        # 也记录到日志文件
        log_filename = "daily_stock_selection.log"
        try:
            with open(log_filename, "a", encoding="utf-8") as log_file:
                log_file.write(f"\n{'='*60}\n")
                log_file.write(f"{current_date_str} 选股结果: 今日无十字星反转信号\n")
                log_file.write(
                    f"时间戳: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
        except Exception as e:
            print(f"写入日志文件失败: {e}")


# 缩量十字星反转执行函数
def doji_reversal_execution(ctx: ExecContext):
    """缩量十字星反转策略执行函数

    策略逻辑：
    1. 卖出：保持原有的止损逻辑
    2. 买入：识别到十字星反转信号后，第三天开盘买入
    """

    # 当前持仓
    pos = ctx.long_pos()
    current_symbol = ctx.symbol

    # === 卖出逻辑：保持原有止损机制 ===
    if pos and len(ctx.close) > 2:
        # 获取价格数据
        latest_close = ctx.close[-1]  # 最新收盘价
        latest_open = ctx.open[-1]  # 最新开盘价
        prev_close = ctx.close[-2]  # 前一天收盘价

        # 获取均线数据
        ma5 = ctx.indicator("ma5")
        ma30 = ctx.indicator("ma30")

        # 卖出条件1：当前价格跌破30日均线
        should_sell_ma30 = len(ma30) > 0 and latest_close < ma30[-1]

        # 卖出条件2：放量大跌（成交量超过前一天1.6倍且当天下跌5个点以上）
        volume_enlarged = len(ctx.volume) > 1 and ctx.volume[-1] > ctx.volume[-2] * 1.6
        daily_decline_pct = (latest_close - prev_close) / prev_close * 100
        price_big_declined = daily_decline_pct < -5  # 下跌5个点以上
        should_sell_volume = volume_enlarged and price_big_declined

        # 卖出条件3：当天相对于前一天放量3倍以上且下跌
        volume_high_enlarged = (
            len(ctx.volume) > 1 and ctx.volume[-1] > ctx.volume[-2] * 3.0
        )
        price_declined = daily_decline_pct < 0  # 任何程度的下跌
        should_sell_high_volume = volume_high_enlarged and price_declined

        if should_sell_ma30 or should_sell_volume or should_sell_high_volume:
            # 计算总收益率（使用实际买入价格）
            if pos.entries:
                # 获取最新的买入价格（加权平均成本）
                total_cost = sum(
                    float(entry.price) * float(entry.shares) for entry in pos.entries
                )
                total_shares = sum(float(entry.shares) for entry in pos.entries)
                avg_entry_price = (
                    total_cost / total_shares if total_shares > 0 else latest_close
                )

                pnl_pct = (
                    (latest_close - avg_entry_price) / avg_entry_price * 100
                    if avg_entry_price > 0
                    else 0
                )
            else:
                # 如果没有entry信息，使用简化计算
                pnl_pct = (latest_close - prev_close) / prev_close * 100

            ctx.sell_fill_price = latest_open
            ctx.sell_all_shares()

            # 记录交易日志
            stock_name = STOCK_NAME_MAP.get(current_symbol, current_symbol)
            stock_display = f"{stock_name}({current_symbol})"

            # 确定卖出原因
            volume_ratio = (
                ctx.volume[-1] / ctx.volume[-2]
                if len(ctx.volume) > 1 and ctx.volume[-2] > 0
                else 0
            )

            # 构建卖出原因说明
            reasons = []
            if should_sell_ma30:
                reasons.append("跌破30日均线")
            if should_sell_volume:
                reasons.append(
                    f"放量大跌(量比{volume_ratio:.1f}倍,跌{abs(daily_decline_pct):.1f}%)"
                )
            if should_sell_high_volume:
                volume_ratio_3x = (
                    ctx.volume[-1] / ctx.volume[-2]
                    if len(ctx.volume) > 1 and ctx.volume[-2] > 0
                    else 0
                )
                reasons.append(
                    f"放量下跌({volume_ratio_3x:.1f}倍,跌{abs(daily_decline_pct):.1f}%)"
                )

            sell_reason = (
                " + ".join(reasons)
                if len(reasons) > 1
                else reasons[0] if reasons else "未知原因"
            )

            # 优化日志格式
            if pos.entries:
                trade_log = (
                    f"{ctx.date[-1]}: 卖出 {stock_display} "
                    f"({sell_reason}), "
                    f"收益率: {pnl_pct:.1f}%, "
                    f"平均成本: ¥{avg_entry_price:.2f}, 当前价: ¥{latest_close:.2f}"
                )
            else:
                trade_log = (
                    f"{ctx.date[-1]}: 卖出 {stock_display} "
                    f"({sell_reason}), 收益率: {pnl_pct:.1f}%"
                )
            print(trade_log)

            # 写入交易日志
            try:
                with open("trading_log.log", "a", encoding="utf-8") as log_file:
                    log_file.write(f"{trade_log}\n")
            except Exception as e:
                print(f"写入交易日志失败: {e}")
            return

    # === 买入逻辑：十字星反转第三天买入 ===
    # 获取选股结果（十字星反转股票）
    try:
        selected_stocks = pybroker.param("selected_stocks")
    except (AttributeError, NameError):
        global SELECTED_STOCKS
        selected_stocks = SELECTED_STOCKS

    if not selected_stocks:
        # 获取当前持仓数量用于显示
        all_positions = ctx.long_positions()
        current_positions = len([p for p in all_positions if p.shares > 0])
        print(
            f"{ctx.date[-1]}: 今日无十字星反转信号，保持持仓 ({current_positions}/{MAX_POSITIONS})"
        )
        return

    # 获取所有持仓
    all_positions = ctx.long_positions()
    current_positions = len([p for p in all_positions if p.shares > 0])

    # 如果持仓未满，按评分排序买入十字星反转股票
    if current_positions < MAX_POSITIONS:
        # 按评分排序，找到评分最高的十字星反转股票
        top_stocks = sorted(selected_stocks, key=lambda x: x["score"], reverse=True)

        # 计算需要补足的仓位数量
        positions_needed = MAX_POSITIONS - current_positions

        # 获取当前已持仓的股票代码
        held_symbols = set()
        for position in all_positions:
            if position.shares > 0:
                held_symbols.add(position.symbol)

        # 找出评分最高的且未持仓的十字星反转股票
        target_stocks = []
        for stock in top_stocks:
            if stock["symbol"] not in held_symbols:
                target_stocks.append(stock)
                if len(target_stocks) >= positions_needed:
                    break

        # 检查当前股票是否在十字星反转列表中
        current_stock = None
        stock_rank = None
        for i, stock in enumerate(target_stocks):
            if stock["symbol"] == current_symbol:
                current_stock = stock
                stock_rank = i + 1  # 在目标买入列表中的排名
                break

        # 如果当前股票出现十字星反转信号，且当前没有持仓，则今日开盘买入
        # 新增：检查市场情绪共振条件
        if current_stock and not pos:
            # 检查市场情绪是否活跃（存在7日涨幅超过60%的标的）
            if not MARKET_SENTIMENT.get("sentiment_active", False):
                print(
                    f"{ctx.date[-1]}: {current_symbol} 符合十字星反转条件，但市场情绪不活跃，跳过买入"
                )
                return
            # 获取当前可用现金
            available_cash = float(ctx.cash)

            # 如果可用现金不足，记录并跳过
            if available_cash < 5000:  # 最小买入金额5000元
                print(
                    f"{ctx.date}: 现金不足，跳过买入 {current_symbol}，"
                    f"可用现金: ¥{available_cash:,.0f}"
                )
                return

            # 计算目标权重：每个持仓占总资金的等比例
            target_weight = 1.0 / MAX_POSITIONS

            # 获取当前总资产价值（现金 + 持仓市值）
            total_equity = float(ctx.total_equity)

            # 计算目标买入金额：总资产 * 目标权重
            target_amount = total_equity * target_weight

            # 使用当日开盘价作为买入价格
            estimated_price = ctx.open[-1]

            # 直接计算目标股数
            target_shares = target_amount / estimated_price

            # 转换为整数股数（向下取整到100的倍数）
            shares_to_buy = int(target_shares) // 100 * 100

            # 确保最小买入数量和金额
            min_shares = max(100, int(5000 / estimated_price / 100) * 100)
            if shares_to_buy < min_shares:
                shares_to_buy = min_shares

            # 最终检查：确保买入金额不超过可用现金
            estimated_cost = shares_to_buy * estimated_price
            if estimated_cost > available_cash:
                # 重新计算最大可买股数（受现金限制）
                max_affordable_shares = (
                    int(available_cash / estimated_price / 100) * 100
                )
                if max_affordable_shares >= 100:  # 至少买100股
                    shares_to_buy = max_affordable_shares
                    estimated_cost = shares_to_buy * estimated_price
                    print(
                        f"{ctx.date}: 现金不足按目标权重买入 {current_symbol}，"
                        f"目标金额¥{target_amount:,.0f}，实际买入¥{estimated_cost:,.0f}"
                    )
                else:
                    print(
                        f"{ctx.date[-1]}: 资金不足买入 {current_symbol}，"
                        f"目标金额¥{target_amount:,.0f}，可用现金¥{available_cash:,.0f}"
                    )
                    return

            if shares_to_buy > 0:
                ctx.buy_fill_price = ctx.open[-1]
                ctx.buy_shares = shares_to_buy

                # 记录交易日志
                stock_name = STOCK_NAME_MAP.get(current_symbol, current_symbol)
                stock_display = f"{stock_name}({current_symbol})"

                # 计算在所有候选股票中的总排名
                total_rank = None
                for i, stock in enumerate(top_stocks):
                    if stock["symbol"] == current_symbol:
                        total_rank = i + 1
                        break

                trade_log = (
                    f"{ctx.date[-1]}: 买入 {stock_display} "
                    f"(十字星反转排名:{total_rank}, 买入序列:{stock_rank}/{len(target_stocks)}) "
                    f"股数:{shares_to_buy}, 评分:{current_stock['score']:.0f}, "
                    f"实体:{current_stock['doji_body_size']:.2f}%, "
                    f"缩量:{current_stock['volume_ratio']:.2f}, "
                    f"反转:{current_stock['reversal_pct']:.1f}%, "
                    f"买入金额:¥{estimated_cost:,.0f}"
                )
                print(trade_log)

                # 写入交易日志
                try:
                    with open("trading_log.log", "a", encoding="utf-8") as log_file:
                        log_file.write(f"{trade_log}\n")
                except Exception as e:
                    print(f"写入交易日志失败: {e}")


# 初始化日志文件
def initialize_log_files():
    """初始化日志文件"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 初始化选股日志
    try:
        with open("daily_stock_selection.log", "w", encoding="utf-8") as log_file:
            log_file.write("缩量十字星反转策略 - 每日选股记录\n")
            log_file.write(f"策略启动时间: {current_time}\n")
            log_file.write(f"回测期间: {BACKTEST_START} 到 {BACKTEST_END}\n")
            log_file.write(
                "选股条件: 十字星形态 + 缩量 + 反转确认 + 均线多头排列 + DEA增大且DEA<0且MACD>DEA + KDJ的J值<90\n"
            )
            log_file.write("十字星: 实体<1% + 有上下影线 + 成交量<20日均量\n")
            log_file.write("反转确认: 确认日收盘价>十字星日最高价 且 确认日为阳线\n")
            log_file.write(
                "确认日成交量: 适度放量，若确认日成交量 > 十字星日成交量 * 6倍，则技术面加分+10分\n"
            )
            log_file.write(
                "技术面: 开盘价位置评分(低于30日线+20分，低于20日线+10分)，收盘价位置评分(高于30日线+10分，高于20日线+20分)，均线多头排列(5>20>30)加分\n"
            )
            log_file.write("DEA条件: 今日DEA > 昨日DEA 且 DEA < 0 且 MACD > DEA\n")
            log_file.write("KDJ条件: J值 < 90 (避免超买状态)\n")
            log_file.write("买入时机: 十字星反转确认后次日开盘买入\n")
            log_file.write("评分筛选: 仅选择总评分 > 80 分的股票\n")
            log_file.write("注: PyBroker自动处理技术指标预热\n")
            log_file.write(f"{'='*80}\n")
    except Exception as e:
        print(f"初始化选股日志失败: {e}")

    # 初始化交易日志
    try:
        with open("trading_log.log", "w", encoding="utf-8") as log_file:
            log_file.write("缩量十字星反转策略 - 交易记录\n")
            log_file.write(f"策略启动时间: {current_time}\n")
            log_file.write(f"回测期间: {BACKTEST_START} 到 {BACKTEST_END}\n")
            log_file.write(f"最大持仓: {MAX_POSITIONS}只股票\n")
            log_file.write(f"初始资金: ¥{INITIAL_CASH:,.0f}\n")
            log_file.write(
                "买入逻辑: 十字星+缩量+反转确认+最高价超过30日线+均线空头排列+情绪共振，次日开盘买入\n"
            )
            log_file.write(
                "止损规则: 跌破30日均线、放量大跌(1.6倍且跌5%)或放量下跌(3倍且下跌)\n"
            )
            log_file.write("情绪共振: 市场存在7日涨幅超过60%的标的时才买入\n")
            log_file.write("注: PyBroker自动处理技术指标预热\n")
            log_file.write(f"{'='*80}\n")
    except Exception as e:
        print(f"初始化交易日志失败: {e}")

    # 初始化情绪分析日志
    try:
        with open("market_sentiment.log", "w", encoding="utf-8") as log_file:
            log_file.write("缩量十字星反转策略 - 市场情绪分析记录\n")
            log_file.write(f"策略启动时间: {current_time}\n")
            log_file.write(f"回测期间: {BACKTEST_START} 到 {BACKTEST_END}\n")
            log_file.write("情绪判断标准: 存在7日涨幅超过60%的标的\n")
            log_file.write("共振逻辑: 情绪活跃 + 十字星反转信号 = 买入\n")
            log_file.write("情绪作用: 平淡时暂停买入，活跃时允许买入\n")
            log_file.write(f"{'='*80}\n")
    except Exception as e:
        print(f"初始化情绪分析日志失败: {e}")


# 准备数据
print("开始准备回测数据...")
initialize_log_files()  # 初始化日志文件
stock_data = prepare_stock_data()

if stock_data is not None:
    print("开始回测...")

    # 获取股票代码列表
    symbols = stock_data["symbol"].unique().tolist()
    print(f"回测股票数量: {len(symbols)}")
    print(f"数据总行数: {len(stock_data)}")
    print(f"数据日期范围: {stock_data['date'].min()} 到 {stock_data['date'].max()}")

    # 创建策略配置 - 使用支持的参数
    config = StrategyConfig(
        initial_cash=INITIAL_CASH,
        max_long_positions=MAX_POSITIONS,
        # 可以尝试添加其他支持的费用参数
        # fees=0.0002,  # 如果支持统一费用设置
    )

    print("交易设置: 使用当天开盘价交易")

    # 直接使用DataFrame创建策略
    strategy = Strategy(
        stock_data,  # 直接传递DataFrame
        start_date=BACKTEST_START,
        end_date=BACKTEST_END,
        config=config,
    )

    # 先设置市场情绪分析函数，再设置选股函数
    def combined_before_exec(ctxs):
        """组合的预执行函数：先进行情绪分析，再进行选股"""
        # 1. 先进行市场情绪分析
        market_sentiment_analysis(ctxs)
        # 2. 再进行十字星反转选股
        doji_reversal_screening(ctxs)

    strategy.set_before_exec(combined_before_exec)

    # 添加缩量十字星反转执行逻辑 - 使用必要的技术指标
    strategy.add_execution(
        doji_reversal_execution,
        symbols,
        indicators=[
            ma5_indicator,
            ma20_indicator,
            ma30_indicator,  # 用于止损
            volume_ma_indicator,  # 用于缩量判断
            macd_line_indicator,  # 用于MACD线判断
            dea_line_indicator,  # 用于DEA线判断
            kdj_k_indicator,  # 用于KDJ K值判断
            kdj_d_indicator,  # 用于KDJ D值判断
        ],
    )

    # 运行回测
    try:
        result = strategy.backtest()

        # 显示回测结果
        print("\n" + "=" * 60)
        print("缩量十字星反转策略回测结果汇总")
        print("=" * 60)

        # 获取组合数据和统计信息
        portfolio = result.portfolio

        # 获取组合统计信息（使用PyBroker标准方式：result.metrics_df）
        try:
            if hasattr(result, "metrics_df") and result.metrics_df is not None:
                metrics = result.metrics_df
                print("\n💰 投资组合表现:")
                print(f"初始资金: ¥{INITIAL_CASH:,.2f}")

                # 创建指标字典方便查找
                metrics_dict = {}
                for _, row in metrics.iterrows():
                    metrics_dict[row["name"]] = row["value"]

                # 显示关键指标
                key_metrics = [
                    ("end_market_value", "最终资金", "¥{:,.2f}"),
                    ("total_pnl", "总收益", "¥{:,.2f}"),
                    ("total_return_pct", "总收益率", "{:.2f}%"),
                    ("max_drawdown_pct", "最大回撤", "{:.2f}%"),
                    ("win_rate", "胜率", "{:.2f}%"),
                    ("trade_count", "交易次数", "{:.0f}"),
                    ("sharpe", "夏普比率", "{:.3f}"),
                ]

                for key, label, fmt in key_metrics:
                    if key in metrics_dict:
                        value = metrics_dict[key]
                        print(f"{label}: {fmt.format(value)}")

                # 显示完整的metrics表格
                print("\n📊 详细指标:")
                print(metrics.to_string(index=False))
            else:
                print("\n⚠️ 无法获取详细的回测指标")
                print(f"初始资金: ¥{INITIAL_CASH:,.2f}")

        except Exception as stats_error:
            print(f"获取统计信息时出错: {stats_error}")
            print(f"初始资金: ¥{INITIAL_CASH:,.2f}")

        # 获取交易记录
        if hasattr(result, "orders") and len(result.orders) > 0:
            orders = result.orders
            print(f"交易次数: {len(orders)}")

            # 计算胜率
            completed_trades = orders[orders["type"] == "sell"]
            if len(completed_trades) > 0:
                # 这里需要更复杂的逻辑来计算盈亏，简化处理
                print(f"卖出交易次数: {len(completed_trades)}")

                # 获取沪深300基准数据

        def get_hs300_benchmark():
            """获取沪深300指数数据作为基准"""
            try:
                print("正在获取沪深300基准数据...")
                # 使用akshare获取沪深300指数历史数据
                try:
                    # 使用akshare的指数日线数据接口
                    hs300_data = ak.index_zh_a_hist(
                        symbol="000300",  # 沪深300指数代码
                        period="daily",
                        start_date=BACKTEST_START.replace("-", ""),
                        end_date=BACKTEST_END.replace("-", ""),
                    )

                    if hs300_data is not None and not hs300_data.empty:
                        # 标准化列名
                        hs300_data = hs300_data.reset_index()

                        # 重命名列以匹配后续处理
                        column_mapping = {
                            "日期": "date",
                            "收盘": "close",
                            "date": "date",
                            "close": "close",
                        }

                        for old_col, new_col in column_mapping.items():
                            if old_col in hs300_data.columns:
                                hs300_data = hs300_data.rename(
                                    columns={old_col: new_col}
                                )

                        # 确保日期列格式正确
                        if "date" in hs300_data.columns:
                            hs300_data["date"] = pd.to_datetime(hs300_data["date"])
                            hs300_data = hs300_data[["date", "close"]].set_index("date")
                            print("✅ 沪深300基准数据获取成功")
                            return hs300_data
                        else:
                            print("⚠️ 沪深300数据格式异常")
                    else:
                        print("❌ 沪深300数据获取失败")

                except Exception as e:
                    print(f"❌ 获取沪深300基准数据失败: {e}")

                return None
            except Exception as e:
                print(f"获取沪深300基准数据失败: {e}")
                return None

        # 绘制收益曲线
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # 获取组合价值数据用于绘图（portfolio是DataFrame）
        try:
            portfolio_value = portfolio["market_value"]
        except Exception as plot_error:
            print(f"获取绘图数据时出错: {plot_error}")
            portfolio_value = None

        if portfolio_value is not None:
            # 资金曲线
            ax1.plot(
                portfolio_value.index, portfolio_value.values, linewidth=2, color="blue"
            )
            ax1.set_title(
                "缩量十字星反转策略 - 资金曲线", fontsize=14, fontweight="bold"
            )
            ax1.set_ylabel("资金 (元)", fontsize=12)
            ax1.grid(True, alpha=0.3)
            ax1.tick_params(axis="x", labelsize=10)
            ax1.tick_params(axis="y", labelsize=10)

            # 格式化y轴显示

            ax1.yaxis.set_major_formatter(
                FuncFormatter(lambda x, p: f"¥{x/10000:.1f}万")
            )

            # 计算累计收益率
            initial_value = portfolio_value.iloc[0]
            cumulative_returns = (portfolio_value - initial_value) / initial_value * 100

            # 获取沪深300基准数据并计算基准收益率
            hs300_data = get_hs300_benchmark()
            hs300_returns = None

            if hs300_data is not None:
                try:
                    # 对齐日期范围，只取与portfolio相同的日期范围
                    portfolio_start_date = portfolio_value.index[0]
                    portfolio_end_date = portfolio_value.index[-1]

                    # 筛选沪深300数据到相同日期范围
                    hs300_aligned = hs300_data[
                        (hs300_data.index >= portfolio_start_date)
                        & (hs300_data.index <= portfolio_end_date)
                    ]

                    if not hs300_aligned.empty:
                        # 计算沪深300累计收益率
                        hs300_initial = hs300_aligned["close"].iloc[0]
                        hs300_returns = (
                            (hs300_aligned["close"] - hs300_initial)
                            / hs300_initial
                            * 100
                        )
                        hs300_points = len(hs300_returns)
                        print(f"沪深300基准收益率计算完成，数据点数: {hs300_points}")
                    else:
                        print("沪深300数据与组合数据日期范围不匹配")

                except Exception as e:
                    print(f"处理沪深300基准数据时出错: {e}")
                    hs300_returns = None

            # 收益率曲线
            ax2.fill_between(
                cumulative_returns.index,
                cumulative_returns.values,
                0,
                alpha=0.3,
                color="green",
                where=(cumulative_returns >= 0),
                label="策略正收益",
                interpolate=True,
            )
            ax2.fill_between(
                cumulative_returns.index,
                cumulative_returns.values,
                0,
                alpha=0.3,
                color="red",
                where=(cumulative_returns < 0),
                label="策略负收益",
                interpolate=True,
            )

            # 绘制策略收益率曲线
            ax2.plot(
                cumulative_returns.index,
                cumulative_returns.values,
                linewidth=2,
                color="darkgreen",
                label="缩量十字星反转策略",
                zorder=3,
            )

            # 绘制沪深300基准收益率曲线
            if hs300_returns is not None:
                ax2.plot(
                    hs300_returns.index,
                    hs300_returns.values,
                    linewidth=2,
                    color="red",
                    label="沪深300基准",
                    alpha=0.8,
                    zorder=2,
                )

                # 计算并显示相对基准的超额收益
                try:
                    final_strategy_return = cumulative_returns.iloc[-1]
                    final_benchmark_return = hs300_returns.iloc[-1]
                    excess_return = final_strategy_return - final_benchmark_return

                    print(f"\n📈 收益率对比:")
                    print(f"策略总收益率: {final_strategy_return:.2f}%")
                    print(f"沪深300基准: {final_benchmark_return:.2f}%")
                    print(f"超额收益: {excess_return:+.2f}%")

                except Exception as e:
                    print(f"计算超额收益时出错: {e}")

            ax2.axhline(y=0, color="black", linestyle="-", alpha=0.3)  # 添加零线
            ax2.set_title("累计收益率曲线对比", fontsize=14, fontweight="bold")
            ax2.set_ylabel("收益率 (%)", fontsize=12)
            ax2.set_xlabel("日期", fontsize=12)
            ax2.grid(True, alpha=0.3)
            ax2.tick_params(axis="x", labelsize=10)
            ax2.tick_params(axis="y", labelsize=10)
            ax2.legend(fontsize=10, loc="upper left")

            # 调整布局
            plt.tight_layout()
            plt.savefig(
                "yang_bao_yin_backtest_results.png",
                dpi=300,
                bbox_inches="tight",
                facecolor="white",
                edgecolor="none",
            )
            plt.close()  # 关闭图形，释放内存
        else:
            print("⚠️ 无法绘制图表：没有找到组合价值数据")

        # 保存交易记录
        if hasattr(result, "orders") and len(result.orders) > 0:
            result.orders.to_csv(
                "yang_bao_yin_trade_records.csv", index=False, encoding="utf-8-sig"
            )
            print("\n交易记录已保存到 yang_bao_yin_trade_records.csv")
        else:
            print("\n没有生成交易记录")

        print("\n🎯 缩量十字星反转策略回测完成！")
        print("📊 图表已保存为 yang_bao_yin_backtest_results.png")
        print("📋 交易记录已保存为 yang_bao_yin_trade_records.csv")
        print("📝 每日选股记录已保存为 daily_stock_selection.log")
        print("📈 交易日志已保存为 trading_log.log")

    except Exception as e:
        print(f"回测运行失败: {e}")
        import traceback

        traceback.print_exc()

else:
    print("数据准备失败，无法进行回测")

# 显示缩量十字星反转策略说明
print("\n📋 缩量十字星反转策略说明:")
print("🎯 1. 十字星形态识别:")
print("   ✓ 核心条件: 标准十字星")
print("     - 实体大小 < 1%（开盘价与收盘价差距小）")
print("     - 有明显上下影线")
print("     - 如果收盘≥开盘：最高>收盘，最低<开盘")
print("     - 如果收盘<开盘：最高>开盘，最低<收盘")
print("   📉 缩量条件:")
print("     - 十字星当日成交量 < 20日平均成交量")
print("     - 表示市场犹豫，多空平衡")
print("   📊 DEA条件:")
print("     - 今日DEA > 昨日DEA 且 DEA < 0 且 MACD > DEA")
print("     - 表示下跌动能减弱，可能反转")
print("   🎯 KDJ条件:")
print("     - J值 < 90 (J = 3K - 2D)")
print("     - 避免在超买状态买入")
print("   📈 确认日成交量:")
print("     - 要求温和放量，确认反转有效性")
print("     - 若确认日成交量 > 十字星日成交量 * 2.5，则总评分-100分 (避免过度放量)")
print("\n🔄 2. 反转确认:")
print("   - 确认日收盘价 > 十字星日最高价")
print("   - 确认日必须为阳线（收盘价 > 开盘价）")
print("   - 确认向上反转，信号有效")
print("   - 次日开盘买入，避免追高")
print("\n📈 3. 评分体系:")
print("   - 十字星质量: 实体越小、影线越长得分越高")
print("   - 缩量程度: 成交量越小得分越高")
print("   - 反转强度: 反转幅度越大得分越高")
print("   - 技术面评分:")
print("     * 开盘价低于30日线: +20分（低位启动）")
print("     * 开盘价低于20日线: +10分")
print("     * 收盘价高于30日线: +10分（突破确认）")
print("     * 收盘价高于20日线: +20分")
print("     * 30日均线超越程度评分:")
print("       - 超越30日线10%以上: +25分（大幅超越）")
print("       - 超越30日线5%-10%: +20分（明显超越）")
print("       - 超越30日线2%-5%: +15分（有效超越）")
print("       - 超越30日线0%-2%: +10分（刚好突破）")
print("     * 均线多头排列(5>20>30): +20分")
print("     * DEA增大: +10分（改善幅度大+15分）")
print("     * 确认日涨幅>5%: +10分（确认日上涨）")
print("     * 确认日涨幅>9%: +20分（确认日大涨）")
print("     * 确认日放量>6倍: +10分（大幅放量确认）")
print("   🎯 最终筛选: 仅选择总评分 > 100 分的股票")
print("\n🛡️ 4. 止损机制:")
print("   - 跌破30日均线时卖出")
print("   - 放量大跌时卖出（成交量超过前一天1.6倍且当天下跌5个点以上）")
print("   - 放量下跌时卖出（成交量超过前一天3倍且当天下跌）")

print("\n⚙️ 5. 技术指标体系:")
print("   - 均线系统: 5/20/30日均线")
print("   - 均线多头排列: 5日线>20日线>30日线（上升趋势信号更强）")
print("   - 开盘价位置: 低于30日线+20分，低于20日线+10分（低位启动）")
print("   - 收盘价位置: 高于30日线+10分，高于20日线+20分（突破确认）")
print("   - 成交量: 20日成交量均线")
print("   - K线形态: 十字星识别算法")
print("   - DEA: 12/26/9参数，识别增大")
print("   - KDJ: 9/3/3参数，J值过滤超买")
print("\n📊 6. 资金管理:")
print(f"   - 最大持仓{MAX_POSITIONS}只股票")
print("   - 等权重分配：每次买入目标金额 = 总资产 / 最大持仓数")
print("   - 严格执行止损，保护资金安全")
print("   - 捕捉反转机会，追求稳健收益")

print("\n📊 7. 情绪共振机制:")
print("   - 市场情绪判断: 检测7日涨幅超过60%的热门股票")
print("   - 情绪活跃标准: 至少存在1只7日涨幅>60%的标的")
print("   - 共振买入逻辑: 情绪活跃 + 十字星反转信号 = 执行买入")
print("   - 情绪平淡时: 暂停所有买入操作，避免逆势交易")
print("   - 情绪过热保护: 识别市场极端情绪，提高成功率")

print("\n📊 8. 基准对比:")
print("   - 沪深300指数作为基准对照")
print("   - 图表中红色曲线显示沪深300收益率")
print("   - 绿色曲线显示策略收益率")
print("   - 自动计算并显示超额收益")
print("   - 评估策略相对市场的表现")
