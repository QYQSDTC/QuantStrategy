#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缩量十字星反转策略 - 每日选股脚本
只专注于当天的选股功能，无需回测框架
支持指定日期参数
"""

import pandas as pd
import akshare as ak
import talib
from datetime import datetime, timedelta
import time
import warnings
import numpy as np
import sys
import argparse

warnings.filterwarnings("ignore")

# 全局变量存储股票代码到名称的映射
STOCK_NAME_MAP = {}

# 全局变量存储情绪判断结果
MARKET_SENTIMENT = {
    "date": None,
    "hot_stocks": [],
    "sentiment_active": False,
    "max_7day_gain": 0.0,
}

print("🚀 缩量十字星反转策略 - 每日选股脚本")
print("=" * 60)


def get_main_board_stocks():
    """获取主板股票列表"""
    global STOCK_NAME_MAP
    print("📊 正在获取主板股票列表...")
    
    try:
        all_stocks = ak.stock_zh_a_spot_em()
        
        def is_main_board_stock(code, name):
            # 排除创业板和科创板
            if any(code.startswith(prefix) for prefix in ["300", "688"]):
                return False
            # 排除ST股票和退市股票
            if any(keyword in name for keyword in ["ST", "st", "退"]):
                return False
            # 主板股票代码
            main_board_prefixes = ["600", "601", "603", "605", "000", "001", "002"]
            return any(code.startswith(prefix) for prefix in main_board_prefixes)

        main_board_stocks = all_stocks[
            all_stocks.apply(
                lambda row: is_main_board_stock(row["代码"], row["名称"]), axis=1
            )
        ]

        # 创建股票代码到名称的映射
        for _, row in main_board_stocks.iterrows():
            STOCK_NAME_MAP[row["代码"]] = row["名称"]

        print(f"✅ 成功获取 {len(main_board_stocks)} 只主板股票")
        return main_board_stocks["代码"].tolist()
        
    except Exception as e:
        print(f"❌ 获取股票列表失败: {e}")
        return []


def get_stock_data(stock_code, target_date, days=60, debug=False, max_retries=3):
    """获取单只股票的历史数据，基于指定的目标日期"""
    for retry in range(max_retries):
        try:
            # 解析目标日期
            if isinstance(target_date, str):
                target_date = datetime.strptime(target_date, "%Y-%m-%d")
            
            # 计算开始日期（目标日期往前推days天）
            start_date = target_date - timedelta(days=days)
            
            if debug:
                print(f"   调试: 获取 {stock_code} 数据 (尝试 {retry+1}/{max_retries})")
                print(f"        开始日期: {start_date.strftime('%Y-%m-%d')}")
                print(f"        结束日期: {target_date.strftime('%Y-%m-%d')}")
            
            # 获取数据（到目标日期为止）
            data = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=target_date.strftime("%Y%m%d"),
                adjust="qfq",
            )
            
            if debug:
                print(f"        API返回数据: {len(data) if data is not None else 'None'} 行")
            
            if data is None:
                if debug:
                    print(f"        ❌ API返回None")
                if retry < max_retries - 1:
                    time.sleep(0.5 * (retry + 1))  # 递增延时
                    continue
                return None
                
            if data.empty:
                if debug:
                    print(f"        ❌ API返回空DataFrame")
                return None
                
            # 重命名列
            try:
                data = data.rename(
                    columns={
                        "日期": "date",
                        "开盘": "open",
                        "最高": "high",
                        "最低": "low",
                        "收盘": "close",
                        "成交量": "volume",
                        "涨跌幅": "pct_change",
                    }
                )
            except Exception as e:
                if debug:
                    print(f"        ❌ 列重命名失败: {e}")
                    print(f"        原始列名: {data.columns.tolist()}")
                return None
            
            data["date"] = pd.to_datetime(data["date"])
            data = data.sort_values("date").reset_index(drop=True)
            
            # 确保最后一天的数据是目标日期或之前
            data = data[data["date"] <= target_date]
            
            if debug:
                print(f"        ✅ 成功获取数据: {len(data)} 行")
                if len(data) > 0:
                    print(f"        日期范围: {data['date'].min()} 到 {data['date'].max()}")
            
            return data
            
        except Exception as e:
            error_msg = str(e)
            if debug:
                print(f"        ❌ 异常 (尝试 {retry+1}/{max_retries}): {type(e).__name__}: {error_msg}")
            
            # 如果是网络相关错误，等待后重试
            if any(keyword in error_msg.lower() for keyword in ['proxy', 'connection', 'timeout', 'network']):
                if retry < max_retries - 1:
                    wait_time = 1.0 * (retry + 1)  # 1秒、2秒、3秒递增等待
                    if debug:
                        print(f"        🔄 网络错误，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
            
            # 其他错误直接返回
            if retry == max_retries - 1:
                return None
                
    return None


def calculate_technical_indicators(data):
    """计算技术指标"""
    if len(data) < 30:  # 确保有足够数据
        return None
        
    try:
        # 转换为float类型
        close = data["close"].astype(float).values
        high = data["high"].astype(float).values
        low = data["low"].astype(float).values
        volume = data["volume"].astype(float).values
        
        # 计算移动平均线
        data["ma5"] = talib.SMA(close, timeperiod=5)
        data["ma20"] = talib.SMA(close, timeperiod=20)
        data["ma30"] = talib.SMA(close, timeperiod=30)
        
        # 计算成交量均线
        data["volume_ma20"] = talib.SMA(volume, timeperiod=20)
        data["volume_ma10"] = talib.SMA(volume, timeperiod=10)
        
        # 计算MACD
        macd_line, signal_line, _ = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
        data["macd_line"] = macd_line
        data["dea_line"] = signal_line
        
        # 计算KDJ
        k_values, d_values = talib.STOCH(
            high, low, close,
            fastk_period=9,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0
        )
        data["kdj_k"] = k_values
        data["kdj_d"] = d_values
        
        # 计算RSI
        data["rsi"] = talib.RSI(close, timeperiod=14)
        
        return data
        
    except Exception as e:
        return None


def check_doji_reversal_signal(data, symbol):
    """检查单只股票的十字星反转信号"""
    try:
        # 基本数据检查
        if len(data) < 22:
            return None
            
        # 计算技术指标
        data = calculate_technical_indicators(data)
        if data is None:
            return None
            
        # 获取最近两天的数据索引
        # -1: 确认日（当天，验证反转信号）
        # -2: 十字星日（前一日，出现十字星形态）
        
        if len(data) < 2:
            return None
            
        confirm_idx = -1  # 确认日（当天）
        doji_idx = -2     # 十字星日（前一日）
        
        # 获取确认日数据
        confirm_close = data["close"].iloc[confirm_idx]
        confirm_open = data["open"].iloc[confirm_idx]
        confirm_high = data["high"].iloc[confirm_idx]
        confirm_volume = data["volume"].iloc[confirm_idx]
        
        # 获取十字星日数据
        doji_close = data["close"].iloc[doji_idx]
        doji_open = data["open"].iloc[doji_idx]
        doji_high = data["high"].iloc[doji_idx]
        doji_low = data["low"].iloc[doji_idx]
        doji_volume = data["volume"].iloc[doji_idx]
        
        # 避免除零错误
        if doji_open <= 0 or doji_close <= 0:
            return None
            
        # === 第一步：判断十字星形态 ===
        # 1. 实体小于1个点
        body_size = abs(doji_close - doji_open) / doji_open * 100
        is_small_body = body_size < 1.0
        
        # 2. 判断十字星的上下影线条件
        is_valid_doji = False
        
        if doji_close >= doji_open:  # 收盘价大于等于开盘价
            upper_shadow = doji_high > doji_close
            lower_shadow = doji_low < doji_open
            is_valid_doji = upper_shadow and lower_shadow
        else:  # 收盘价小于开盘价
            upper_shadow = doji_high > doji_open
            lower_shadow = doji_low < doji_close
            is_valid_doji = upper_shadow and lower_shadow
            
        # 3. 缩量条件：十字星当天成交量低于20日平均成交量
        volume_ma20_value = data["volume_ma20"].iloc[doji_idx]
        if pd.isna(volume_ma20_value) or volume_ma20_value <= 0:
            return None
        is_low_volume = doji_volume < volume_ma20_value
        
        # === 第二步：验证反转信号 ===
        # 确认日收盘价高于十字星日最高价，确认反转
        is_reversal = confirm_close > doji_high
        
        # 确认日必须为阳线
        is_positive_candle = confirm_close > confirm_open
        
        # === 第三步：DEA 增大且相关条件 ===
        is_dea_conditions_met = False
        dea_doji_day = data["dea_line"].iloc[doji_idx]
        dea_confirm_day = data["dea_line"].iloc[confirm_idx]
        macd_confirm_day = data["macd_line"].iloc[confirm_idx]
        
        if not (pd.isna(dea_doji_day) or pd.isna(dea_confirm_day) or pd.isna(macd_confirm_day)):
            # 条件1：DEA增大
            is_dea_increasing = dea_confirm_day > dea_doji_day
            # 条件2：DEA小于0
            is_dea_negative = dea_confirm_day < 0
            # 条件3：MACD大于DEA
            is_macd_above_dea = macd_confirm_day > dea_confirm_day
            
            is_dea_conditions_met = is_dea_increasing and is_dea_negative and is_macd_above_dea
        
        # === 第四步：KDJ指标条件 ===
        is_kdj_conditions_met = False
        k_value = data["kdj_k"].iloc[confirm_idx]
        d_value = data["kdj_d"].iloc[confirm_idx]
        
        if not (pd.isna(k_value) or pd.isna(d_value)):
            j_value = 3 * k_value - 2 * d_value
            is_kdj_conditions_met = j_value < 90
        else:
            j_value = 0
            
        # === 综合判断 ===
        if (is_small_body and is_valid_doji and is_low_volume and 
            is_reversal and is_positive_candle and is_dea_conditions_met and is_kdj_conditions_met):
            
            # 计算评分
            score = 0
            reasons = []
            
            # 基础分：十字星质量
            doji_quality = 0
            if body_size < 0.5:
                doji_quality += 20
                reasons.append("极小实体")
            elif body_size < 1.0:
                doji_quality += 15
                reasons.append("小实体")
                
            # 上下影线长度评分
            upper_shadow_pct = (doji_high - max(doji_open, doji_close)) / max(doji_open, doji_close) * 100
            lower_shadow_pct = (min(doji_open, doji_close) - doji_low) / min(doji_open, doji_close) * 100
            
            if upper_shadow_pct > 2 and lower_shadow_pct > 2:
                doji_quality += 15
                reasons.append("明显上下影线")
            elif upper_shadow_pct > 1 or lower_shadow_pct > 1:
                doji_quality += 10
                reasons.append("有上下影线")
                
            score += doji_quality
            
            # 缩量程度评分
            volume_ratio = doji_volume / volume_ma20_value
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
            
            # 均线数据
            ma20_value = data["ma20"].iloc[confirm_idx]
            ma30_value = data["ma30"].iloc[confirm_idx]
            ma5_value = data["ma5"].iloc[confirm_idx]
            
            # 开盘价位置评分
            if not pd.isna(ma30_value) and confirm_open < ma30_value:
                tech_bonus += 20
                reasons.append("开盘价低于30日线")
            if not pd.isna(ma20_value) and confirm_open < ma20_value:
                tech_bonus += 10
                reasons.append("开盘价低于20日线")
                
            # 收盘价位置评分
            # 计算确认日收盘价超过30日线的幅度并给予相应评分
            if not pd.isna(ma30_value) and confirm_close > ma30_value:
                # 计算超过30日线的百分比
                exceed_ma30_pct = (confirm_close - ma30_value) / ma30_value * 100
                
                # 根据超过幅度给予不同分数，超过越多得分越高
                if exceed_ma30_pct > 10:
                    ma30_score = 25
                    reasons.append(f"收盘价大幅超过30日线({exceed_ma30_pct:.1f}%)")
                elif exceed_ma30_pct > 5:
                    ma30_score = 20
                    reasons.append(f"收盘价明显超过30日线({exceed_ma30_pct:.1f}%)")
                elif exceed_ma30_pct > 2:
                    ma30_score = 15
                    reasons.append(f"收盘价适度超过30日线({exceed_ma30_pct:.1f}%)")
                else:
                    ma30_score = 5
                    reasons.append(f"收盘价刚好突破30日线({exceed_ma30_pct:.1f}%)")
                    
                tech_bonus += ma30_score
            else:
                exceed_ma30_pct = 0
                
            if not pd.isna(ma20_value) and confirm_close > ma20_value:
                tech_bonus += 20
                reasons.append("收盘价突破20日线")
                
            # 均线多头排列
            if (not pd.isna(ma5_value) and not pd.isna(ma20_value) and not pd.isna(ma30_value) and
                ma5_value > ma20_value > ma30_value):
                tech_bonus += 20
                reasons.append("均线多头排列")
                
            # DEA改善加分
            dea_improvement = dea_confirm_day - dea_doji_day
            if dea_improvement > 0.02:
                tech_bonus += 15
                reasons.append("DEA明显改善")
            else:
                tech_bonus += 10
                reasons.append("DEA增大")
                
            # 确认日涨幅加分
            confirm_daily_gain_pct = (confirm_close - confirm_open) / confirm_open * 100
            if confirm_daily_gain_pct > 9:
                tech_bonus += 20
                reasons.append(f"确认日大涨({confirm_daily_gain_pct:.1f}%)")
            elif confirm_daily_gain_pct > 5:
                tech_bonus += 10
                reasons.append(f"确认日上涨({confirm_daily_gain_pct:.1f}%)")
                
            # 确认日成交量判断
            confirmation_to_doji_volume_ratio = confirm_volume / doji_volume if doji_volume > 0 else 0
            if confirmation_to_doji_volume_ratio > 6.0:
                tech_bonus += 10
                reasons.append(f"确认日大幅放量({confirmation_to_doji_volume_ratio:.1f}倍)")
                
            score += tech_bonus
            
            # 只返回评分大于100的股票
            if score > 100:
                return {
                    "symbol": symbol,
                    "score": score,
                    "doji_date": data["date"].iloc[doji_idx].strftime("%Y-%m-%d"),
                    "confirm_date": data["date"].iloc[confirm_idx].strftime("%Y-%m-%d"),
                    "doji_body_size": body_size,
                    "volume_ratio": volume_ratio,
                    "reversal_pct": reversal_pct,
                    "doji_high": doji_high,
                    "confirm_close": confirm_close,
                    "confirm_daily_gain_pct": confirm_daily_gain_pct,
                    "reasons": reasons,
                    "doji_quality": doji_quality,
                    "volume_score": volume_score,
                    "reversal_score": reversal_score,
                    "tech_bonus": tech_bonus,
                    "upper_shadow_pct": upper_shadow_pct,
                    "lower_shadow_pct": lower_shadow_pct,
                    "dea_doji_day": dea_doji_day,
                    "dea_confirm_day": dea_confirm_day,
                    "dea_improvement": dea_improvement,
                    "j_value": j_value,
                    "confirmation_to_doji_volume_ratio": confirmation_to_doji_volume_ratio,
                    "exceed_ma30_pct": exceed_ma30_pct,
                    "current_price": data["close"].iloc[-1],  # 最新价格
                }
                
        return None
        
    except Exception as e:
        return None


def run_daily_screening(target_date=None, debug_mode=False):
    """运行每日选股"""
    # 处理日期参数
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    elif isinstance(target_date, str):
        # 验证日期格式
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            print("❌ 日期格式错误，请使用 YYYY-MM-DD 格式")
            return []
    
    print(f"\n🎯 开始执行选股分析 (目标日期: {target_date})")
    print(f"   分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 先测试一只股票，看看数据获取是否正常
    print(f"\n🔍 预检查: 测试数据获取功能...")
    test_stocks = ["000001", "000002", "600000"]  # 测试几只知名股票
    test_success = False
    
    for test_code in test_stocks:
        print(f"   测试股票 {test_code}...")
        test_data = get_stock_data(test_code, target_date, days=30, debug=True)
        if test_data is not None and len(test_data) > 0:
            print(f"   ✅ 测试成功: {test_code} 获取到 {len(test_data)} 天数据")
            test_success = True
            break
        else:
            print(f"   ❌ 测试失败: {test_code}")
    
    if not test_success:
        print(f"\n❌ 预检查失败: 无法获取任何测试股票的数据")
        print(f"   可能原因:")
        print(f"   1. 指定日期 {target_date} 不是交易日")
        print(f"   2. akshare API 服务异常")
        print(f"   3. 网络连接问题")
        print(f"   4. 数据源维护中")
        
        # 检查是否为周末
        check_date = datetime.strptime(target_date, "%Y-%m-%d")
        weekday = check_date.weekday()
        if weekday >= 5:  # 周六(5)或周日(6)
            print(f"   ⚠️ 注意: {target_date} 是{'周六' if weekday == 5 else '周日'}，非交易日")
            
        return []
    
    print(f"✅ 预检查通过，开始正式分析...")
    
    # 1. 获取股票列表
    stock_codes = get_main_board_stocks()
    if not stock_codes:
        print("❌ 无法获取股票列表")
        return []
    
    # 处理所有股票，不再限制数量
    print(f"📈 开始筛选所有 {len(stock_codes)} 只主板股票...")
    print(f"🔄 同时进行市场情绪分析和十字星反转选股...")
    
    # 初始化变量
    current_date = target_date
    selected_stocks = []
    
    # 情绪分析变量
    hot_stocks = []
    max_7day_gain = 0.0
    
    # 统计变量
    checked_count = 0
    data_fetch_failed = 0
    data_insufficient_emotion = 0
    data_insufficient_doji = 0
    emotion_checked = 0
    doji_checked = 0
    
    # 错误统计
    api_none_count = 0
    api_empty_count = 0
    exception_count = 0
    
    for i, stock_code in enumerate(stock_codes):
        if i % 100 == 0:  # 更频繁的进度显示
            progress = (i + 1) / len(stock_codes) * 100
            print(f"   进度: {i+1}/{len(stock_codes)} ({progress:.1f}%) | "
                  f"成功: {checked_count} | 失败: {data_fetch_failed} | "
                  f"情绪: {emotion_checked} | 十字星: {doji_checked}")
            
            # 防风控机制：每100个股票休眠10秒
            if i > 0:  # 第一批不休眠
                print(f"   🛡️ 防风控休眠中...", end="", flush=True)
                for countdown in range(10, 0, -1):
                    print(f" {countdown}", end="", flush=True)
                    time.sleep(1)
                print(" ✅")  # 换行并显示完成
            
        try:
            # 获取股票数据（只获取一次）
            use_debug = debug_mode and i < 5  # 只对前5只股票开启调试
            data = get_stock_data(stock_code, target_date, days=60, debug=use_debug)
            
            if data is None:
                data_fetch_failed += 1
                api_none_count += 1
                time.sleep(0.05)  # 失败时稍微延时
                continue
                
            if len(data) == 0:
                data_fetch_failed += 1
                api_empty_count += 1
                continue
                
            checked_count += 1
            
            # === 1. 市场情绪分析 ===
            # 检查是否有足够数据进行情绪分析（需要至少8天）
            if len(data) >= 8:
                try:
                    emotion_checked += 1
                    
                    # 计算7日涨幅
                    current_price = data["close"].iloc[-1]  # 目标日期收盘价
                    price_7days_ago = data["close"].iloc[-8]  # 7天前收盘价
                    
                    if price_7days_ago > 0 and current_price > 0:
                        gain_7days = (current_price - price_7days_ago) / price_7days_ago * 100
                        
                        # 更新最大7日涨幅
                        if gain_7days > max_7day_gain:
                            max_7day_gain = gain_7days
                        
                        # 如果7日涨幅超过60%，记录为热门股票
                        if gain_7days > 60:
                            stock_name = STOCK_NAME_MAP.get(stock_code, stock_code)
                            hot_stocks.append({
                                "symbol": stock_code,
                                "name": stock_name,
                                "gain_7days": gain_7days,
                                "current_price": current_price,
                                "price_7days_ago": price_7days_ago,
                            })
                            
                except Exception as e:
                    pass  # 情绪分析失败不影响继续处理
            else:
                data_insufficient_emotion += 1
            
            # === 2. 十字星反转选股 ===
            # 检查是否有足够数据进行十字星分析（需要至少22天）
            if len(data) >= 22:
                try:
                    doji_checked += 1
                    signal = check_doji_reversal_signal(data, stock_code)
                    if signal:
                        selected_stocks.append(signal)
                except Exception as e:
                    pass  # 十字星分析失败不影响继续处理
            else:
                data_insufficient_doji += 1
                
        except Exception as e:
            data_fetch_failed += 1
            exception_count += 1
            if debug_mode and i < 5:
                print(f"   异常 {stock_code}: {e}")
            time.sleep(0.1)
            continue
            
        # 控制请求频率，防止被限制
        time.sleep(0.1)  # 调整为100ms间隔
    
    # === 3. 处理情绪分析结果 ===
    sentiment_active = len(hot_stocks) > 0
    
    # 更新全局情绪状态
    global MARKET_SENTIMENT
    MARKET_SENTIMENT.update({
        "date": current_date,
        "hot_stocks": hot_stocks,
        "sentiment_active": sentiment_active,
        "max_7day_gain": max_7day_gain,
    })
    
    # === 4. 按评分排序选股结果 ===
    selected_stocks = sorted(selected_stocks, key=lambda x: x["score"], reverse=True)
    
    # === 5. 输出结果 ===
    print(f"\n" + "="*80)
    print(f"📊 {current_date} 缩量十字星反转选股结果 (全市场扫描)")
    print(f"="*80)
    
    # 数据统计
    print(f"📊 数据统计:")
    print(f"   分析日期: {target_date}")
    print(f"   总计股票: {len(stock_codes)} 只")
    print(f"   成功获取数据: {checked_count} 只")
    print(f"   获取失败: {data_fetch_failed} 只")
    print(f"     - API返回None: {api_none_count} 只")
    print(f"     - API返回空: {api_empty_count} 只") 
    print(f"     - 异常错误: {exception_count} 只")
    print(f"   情绪分析有效: {emotion_checked} 只")
    print(f"   十字星分析有效: {doji_checked} 只")
    print(f"   数据获取成功率: {checked_count/len(stock_codes)*100:.1f}%")
    
    # 市场情绪结果
    print(f"\n📈 市场情绪分析:")
    print(f"   最大7日涨幅: {max_7day_gain:.1f}%")
    
    if sentiment_active:
        print(f"🔥 市场情绪: 活跃 ✅ (发现 {len(hot_stocks)} 只热门股票)")
        
        # 按涨幅排序显示前5只
        hot_stocks_sorted = sorted(hot_stocks, key=lambda x: x["gain_7days"], reverse=True)
        for i, stock in enumerate(hot_stocks_sorted[:5]):
            stock_display = f"{stock['name']}({stock['symbol']})"
            print(f"      {i+1}. {stock_display}: +{stock['gain_7days']:.1f}%")
            
        if len(hot_stocks) > 5:
            print(f"      ... 还有{len(hot_stocks)-5}只热门股票")
            
        print("   ✅ 情绪共振条件满足，可执行十字星反转选股")
    else:
        print("😴 市场情绪: 平淡 ⚠️ (不满足情绪共振条件，建议谨慎)")
        
    print(f"\n🎯 十字星选股结果: 共发现 {len(selected_stocks)} 只符合条件的股票")
    
    if selected_stocks:
        print(f"\n📈 推荐股票 (前10名):")
        print("-" * 80)
        
        for i, stock in enumerate(selected_stocks[:10]):
            symbol = stock["symbol"]
            name = STOCK_NAME_MAP.get(symbol, symbol)
            stock_display = f"{name}({symbol})"
            
            print(f"{i+1:2d}. {stock_display}")
            print(f"    💯 总评分: {stock['score']:.0f}分")
            
            # 显示各项得分详情
            print(f"    🔍 得分详情:")
            print(f"       • 十字星质量: {stock['doji_quality']:.0f}分")
            print(f"       • 缩量程度: {stock['volume_score']:.0f}分") 
            print(f"       • 反转强度: {stock['reversal_score']:.0f}分")
            print(f"       • 技术面加分: {stock['tech_bonus']:.0f}分")
            
            print(f"    📅 十字星日期: {stock['doji_date']} → 确认日期: {stock['confirm_date']}")
            print(f"    📊 十字星实体: {stock['doji_body_size']:.2f}% | 缩量比例: {stock['volume_ratio']:.2f}")
            print(f"    📈 反转幅度: {stock['reversal_pct']:.1f}% | 确认日涨幅: {stock['confirm_daily_gain_pct']:.1f}%")
            print(f"    💰 当前价格: ¥{stock['current_price']:.2f}")
            print(f"    🎯 DEA: {stock['dea_doji_day']:.4f} → {stock['dea_confirm_day']:.4f} (改善{stock['dea_improvement']:.4f})")
            print(f"    📊 KDJ-J值: {stock['j_value']:.1f} | 确认日放量: {stock['confirmation_to_doji_volume_ratio']:.1f}倍")
            # 显示确认日收盘价超过30日线的幅度
            if stock['exceed_ma30_pct'] > 0:
                print(f"    📈 超越30日线: +{stock['exceed_ma30_pct']:.1f}%")
            print(f"    ✨ 优势: {', '.join(stock['reasons'])}")
            print()
            
        # 保存结果到文件
        save_results_to_file(selected_stocks, current_date, sentiment_active)
        
    else:
        print("📝 该日期无符合条件的十字星反转信号")
    
    # 如果数据获取成功率太低，给出提示
    success_rate = checked_count / len(stock_codes) * 100
    if success_rate < 50:
        print(f"\n⚠️  警告: 数据获取成功率较低({success_rate:.1f}%)，可能原因:")
        print(f"   - 指定日期可能不是交易日")
        print(f"   - 存在较多停牌或新上市股票")
        print(f"   - 网络连接不稳定导致数据获取失败")
        print(f"   - 请求频率过高被数据源限制")
        print(f"   - akshare API 服务异常")
        print(f"   建议选择有效的交易日期")
        
    print("🎯 选股完成！")
    return selected_stocks


def save_results_to_file(selected_stocks, current_date, sentiment_active):
    """保存选股结果到文件"""
    try:
        # 保存到CSV文件
        if selected_stocks:
            df_results = pd.DataFrame(selected_stocks)
            csv_filename = f"daily_screening_{current_date.replace('-', '')}.csv"
            df_results.to_csv(csv_filename, index=False, encoding="utf-8-sig")
            print(f"📄 详细结果已保存到: {csv_filename}")
        
        # 保存到日志文件
        log_filename = "daily_screening.log"
        with open(log_filename, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"{current_date} 缩量十字星反转选股结果\n")
            f.write(f"{'='*80}\n")
            f.write(f"市场情绪: {'活跃' if sentiment_active else '平淡'}\n")
            f.write(f"筛选结果: {len(selected_stocks)} 只股票\n")
            f.write(f"最大7日涨幅: {MARKET_SENTIMENT['max_7day_gain']:.1f}%\n")
            
            if MARKET_SENTIMENT['hot_stocks']:
                f.write(f"热门股票: {len(MARKET_SENTIMENT['hot_stocks'])} 只\n")
                for stock in MARKET_SENTIMENT['hot_stocks'][:5]:
                    f.write(f"  {stock['name']}({stock['symbol']}): +{stock['gain_7days']:.1f}%\n")
            
            f.write("\n推荐股票:\n")
            for i, stock in enumerate(selected_stocks[:10]):
                symbol = stock["symbol"]
                name = STOCK_NAME_MAP.get(symbol, symbol)
                exceed_info = f" 超30日线:{stock['exceed_ma30_pct']:.1f}%" if stock['exceed_ma30_pct'] > 0 else ""
                f.write(f"{i+1:2d}. {name}({symbol}) - 评分:{stock['score']:.0f} 价格:¥{stock['current_price']:.2f}{exceed_info}\n")
                f.write(f"     得分详情: 十字星{stock['doji_quality']:.0f}分 + 缩量{stock['volume_score']:.0f}分 + 反转{stock['reversal_score']:.0f}分 + 技术{stock['tech_bonus']:.0f}分\n")
                
            f.write(f"\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
        print(f"📋 选股日志已保存到: {log_filename}")
        
    except Exception as e:
        print(f"❌ 保存文件失败: {e}")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='缩量十字星反转策略选股脚本')
    parser.add_argument('-d', '--date', type=str, help='指定分析日期 (格式: YYYY-MM-DD)', default=None)
    parser.add_argument('-i', '--interactive', action='store_true', help='交互式输入日期')
    parser.add_argument('--debug', action='store_true', help='开启调试模式，显示详细错误信息')
    return parser.parse_args()


def get_target_date(args):
    """获取目标日期"""
    if args.date:
        # 使用命令行指定的日期
        try:
            target_dt = datetime.strptime(args.date, "%Y-%m-%d")
            today = datetime.now()
            
            # 检查是否为未来日期
            if target_dt > today:
                print(f"❌ 指定日期 {args.date} 是未来日期，无法获取数据")
                print(f"   当前日期: {today.strftime('%Y-%m-%d')}")
                return None
                
            return args.date
        except ValueError:
            print("❌ 命令行日期格式错误，请使用 YYYY-MM-DD 格式")
            return None
    
    if args.interactive:
        # 交互式输入日期
        while True:
            try:
                date_input = input("📅 请输入分析日期 (格式: YYYY-MM-DD, 直接回车使用今日): ").strip()
                if not date_input:
                    return datetime.now().strftime("%Y-%m-%d")
                
                # 验证日期格式和是否为未来日期
                target_dt = datetime.strptime(date_input, "%Y-%m-%d")
                today = datetime.now()
                
                if target_dt > today:
                    print(f"❌ 指定日期 {date_input} 是未来日期，请选择今日或历史日期")
                    continue
                    
                return date_input
            except ValueError:
                print("❌ 日期格式错误，请使用 YYYY-MM-DD 格式")
            except KeyboardInterrupt:
                print("\n⚠️ 用户取消操作")
                return None
    
    # 默认使用今日
    return datetime.now().strftime("%Y-%m-%d")


if __name__ == "__main__":
    try:
        # 解析命令行参数
        args = parse_arguments()
        
        # 获取目标日期
        target_date = get_target_date(args)
        if target_date is None:
            sys.exit(1)
        
        # 显示使用说明
        print(f"\n📋 使用说明:")
        print(f"   目标日期: {target_date}")
        print(f"   十字星日: {target_date} 的前一日")
        print(f"   确认日: {target_date} (当天)")
        print(f"   📝 命令行用法:")
        print(f"      python {sys.argv[0]} -d 2024-01-15")
        print(f"      python {sys.argv[0]} -i")
        print(f"      python {sys.argv[0]}  (使用今日)")
        
        # 运行选股分析
        results = run_daily_screening(target_date, debug_mode=args.debug)
        
        print(f"\n📋 选股统计:")
        print(f"   分析日期: {target_date}")
        print(f"   市场情绪: {'🔥 活跃' if MARKET_SENTIMENT['sentiment_active'] else '😴 平淡'}")
        print(f"   热门股票: {len(MARKET_SENTIMENT['hot_stocks'])} 只")
        print(f"   最大7日涨幅: {MARKET_SENTIMENT['max_7day_gain']:.1f}%")
        print(f"   符合条件: {len(results)} 只")
        
        if MARKET_SENTIMENT['sentiment_active'] and results:
            print(f"\n✅ 建议关注评分前3名的股票")
        elif not MARKET_SENTIMENT['sentiment_active']:
            print(f"\n⚠️ 市场情绪平淡，建议等待更好时机")
        else:
            print(f"\n📝 该日期无符合条件的标的")
            
    except KeyboardInterrupt:
        print(f"\n⚠️ 用户中断执行")
    except Exception as e:
        print(f"\n❌ 执行出错: {e}")
        import traceback
        traceback.print_exc() 