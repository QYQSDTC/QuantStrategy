#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票评分查询工具
用于查询特定股票在特定日期的缩量十字星反转策略评分

使用方法:
python stock_score_query.py --stock "大众交通" --date "2023-07-08"
或
python stock_score_query.py --code "600611" --date "2023-07-08"
"""

import pandas as pd
import akshare as ak
from datetime import datetime, timedelta
import argparse
import talib
import warnings

warnings.filterwarnings("ignore")

# 设置matplotlib中文字体
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = [
    "SimHei",
    "Microsoft YaHei",
    "DejaVu Sans",
    "Arial Unicode MS",
]
plt.rcParams["axes.unicode_minus"] = False


class StockScoreQuery:
    def __init__(self):
        self.stock_name_map = {}
        self.code_name_map = {}

    def get_stock_list(self):
        """获取股票列表，建立代码和名称的映射关系"""
        print("正在获取股票列表...")
        try:
            all_stocks = ak.stock_zh_a_spot_em()

            def is_main_board_stock(code, name):
                if any(code.startswith(prefix) for prefix in ["300", "688"]):
                    return False
                if any(keyword in name for keyword in ["ST", "st", "退"]):
                    return False
                main_board_prefixes = ["600", "601", "603", "605", "000", "001", "002"]
                return any(code.startswith(prefix) for prefix in main_board_prefixes)

            main_board_stocks = all_stocks[
                all_stocks.apply(
                    lambda row: is_main_board_stock(row["代码"], row["名称"]), axis=1
                )
            ]

            # 创建双向映射
            for _, row in main_board_stocks.iterrows():
                code = row["代码"]
                name = row["名称"]
                self.stock_name_map[name] = code
                self.code_name_map[code] = name

            print(f"成功获取 {len(main_board_stocks)} 只主板股票信息")
            return True

        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return False

    def find_stock_code(self, stock_input):
        """根据股票名称或代码查找对应的代码"""
        # 如果输入的是6位数字，直接当作代码
        if stock_input.isdigit() and len(stock_input) == 6:
            if stock_input in self.code_name_map:
                return stock_input, self.code_name_map[stock_input]
            else:
                return None, None

        # 否则当作名称查找
        for name, code in self.stock_name_map.items():
            if stock_input in name or name in stock_input:
                return code, name

        return None, None

    def get_stock_data(self, stock_code, target_date):
        """获取股票历史数据"""
        try:
            # 计算数据获取范围（需要足够的历史数据计算技术指标）
            target_dt = datetime.strptime(target_date, "%Y-%m-%d")
            start_date = (target_dt - timedelta(days=100)).strftime("%Y%m%d")
            end_date = (target_dt + timedelta(days=5)).strftime("%Y%m%d")

            print(f"正在获取股票数据: {stock_code}")
            data = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )

            if data.empty:
                print("未获取到股票数据")
                return None

            # 重命名列
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

            data["date"] = pd.to_datetime(data["date"])
            data.set_index("date", inplace=True)

            print(f"成功获取数据，时间范围: {data.index.min()} 到 {data.index.max()}")
            return data

        except Exception as e:
            print(f"获取股票数据失败: {e}")
            return None

    def calculate_indicators(self, data):
        """计算技术指标"""
        try:
            # 计算均线
            data["ma5"] = talib.SMA(data.close.astype(float), timeperiod=5)
            data["ma20"] = talib.SMA(data.close.astype(float), timeperiod=20)
            data["ma30"] = talib.SMA(data.close.astype(float), timeperiod=30)

            # 计算成交量均线
            data["volume_ma20"] = talib.SMA(data.volume.astype(float), timeperiod=20)

            # 计算MACD
            macd_line, dea_line, _ = talib.MACD(
                data.close.astype(float), fastperiod=12, slowperiod=26, signalperiod=9
            )
            data["macd_line"] = macd_line
            data["dea_line"] = dea_line

            # 计算KDJ
            kdj_k, kdj_d = talib.STOCH(
                data.high.astype(float),
                data.low.astype(float),
                data.close.astype(float),
                fastk_period=9,
                slowk_period=3,
                slowk_matype=0,
                slowd_period=3,
                slowd_matype=0,
            )
            data["kdj_k"] = kdj_k
            data["kdj_d"] = kdj_d
            data["kdj_j"] = 3 * kdj_k - 2 * kdj_d  # J = 3K - 2D

            return data

        except Exception as e:
            print(f"计算技术指标失败: {e}")
            return None

    def score_stock(self, data, target_date_str):
        """计算特定日期的股票评分"""
        target_date = pd.to_datetime(target_date_str)

        # 检查目标日期是否在数据范围内
        if target_date not in data.index:
            print(f"目标日期 {target_date_str} 不在数据范围内")
            available_dates = data.index.strftime("%Y-%m-%d").tolist()
            print(f"可用日期范围: {available_dates[0]} 到 {available_dates[-1]}")
            return None

        try:
            # 获取目标日期在数据中的位置
            date_idx = data.index.get_loc(target_date)

            # 需要至少3天数据（十字星日、确认日、策略执行日）
            if date_idx < 2:
                print("数据不足，需要至少3天历史数据")
                return None

            # 确定三个关键日期的索引
            strategy_day_idx = date_idx  # 策略执行日（目标日期）
            confirm_day_idx = date_idx - 1  # 确认日（目标日期前一天）
            doji_day_idx = date_idx - 2  # 十字星日（目标日期前两天）

            # 获取各日期的数据
            doji_data = data.iloc[doji_day_idx]
            confirm_data = data.iloc[confirm_day_idx]
            strategy_data = data.iloc[strategy_day_idx]

            print(f"\n=== 分析日期设定 ===")
            print(f"十字星日: {data.index[doji_day_idx].strftime('%Y-%m-%d')}")
            print(f"确认日: {data.index[confirm_day_idx].strftime('%Y-%m-%d')}")
            print(f"策略执行日: {data.index[strategy_day_idx].strftime('%Y-%m-%d')}")

            # 开始评分计算
            return self._calculate_detailed_score(
                doji_data, confirm_data, strategy_data
            )

        except Exception as e:
            print(f"评分计算失败: {e}")
            return None

    def _calculate_detailed_score(self, doji_data, confirm_data, strategy_data):
        """详细评分计算"""
        score_details = {
            "total_score": 0,
            "doji_quality": 0,
            "volume_score": 0,
            "reversal_score": 0,
            "tech_bonus": 0,
            "volume_bonus": 0,
            "reasons": [],
            "conditions_met": [],
            "conditions_failed": [],
        }

        # 基本数据
        doji_open = doji_data["open"]
        doji_high = doji_data["high"]
        doji_low = doji_data["low"]
        doji_close = doji_data["close"]
        doji_volume = doji_data["volume"]

        confirm_open = confirm_data["open"]
        confirm_high = confirm_data["high"]
        confirm_close = confirm_data["close"]
        confirm_volume = confirm_data["volume"]

        # 检查基本条件
        if doji_open <= 0 or doji_close <= 0:
            score_details["conditions_failed"].append("十字星日价格数据异常")
            return score_details

        print(f"\n=== 十字星形态分析 ===")
        print(
            f"十字星日: 开盘{doji_open:.2f}, 最高{doji_high:.2f}, 最低{doji_low:.2f}, 收盘{doji_close:.2f}"
        )
        print(
            f"确认日: 开盘{confirm_open:.2f}, 最高{confirm_high:.2f}, 收盘{confirm_close:.2f}"
        )

        # === 1. 十字星质量评分 ===
        body_size = abs(doji_close - doji_open) / doji_open * 100
        print(f"实体大小: {body_size:.3f}%")

        doji_quality = 0
        if body_size < 0.5:
            doji_quality += 20
            score_details["reasons"].append("极小实体")
        elif body_size < 1.0:
            doji_quality += 15
            score_details["reasons"].append("小实体")
        else:
            score_details["conditions_failed"].append(f"实体过大({body_size:.2f}%)")

        # 上下影线长度评分
        upper_shadow_pct = (
            (doji_high - max(doji_open, doji_close)) / max(doji_open, doji_close) * 100
        )
        lower_shadow_pct = (
            (min(doji_open, doji_close) - doji_low) / min(doji_open, doji_close) * 100
        )

        print(f"上影线: {upper_shadow_pct:.2f}%, 下影线: {lower_shadow_pct:.2f}%")

        if upper_shadow_pct > 2 and lower_shadow_pct > 2:
            doji_quality += 15
            score_details["reasons"].append("明显上下影线")
        elif upper_shadow_pct > 1 or lower_shadow_pct > 1:
            doji_quality += 10
            score_details["reasons"].append("有上下影线")
        else:
            score_details["conditions_failed"].append("影线不足")

        score_details["doji_quality"] = doji_quality

        # 十字星形态验证
        is_valid_doji = False
        if doji_close >= doji_open:
            upper_shadow = doji_high > doji_close
            lower_shadow = doji_low < doji_open
            is_valid_doji = upper_shadow and lower_shadow
        else:
            upper_shadow = doji_high > doji_open
            lower_shadow = doji_low < doji_close
            is_valid_doji = upper_shadow and lower_shadow

        if not is_valid_doji:
            score_details["conditions_failed"].append("不符合十字星形态要求")

        # === 2. 缩量程度评分 ===
        volume_ma20_value = doji_data["volume_ma20"]
        volume_ratio = doji_volume / volume_ma20_value if volume_ma20_value > 0 else 999

        print(f"\n=== 成交量分析 ===")
        print(f"十字星日成交量: {doji_volume:,.0f}")
        print(f"20日平均成交量: {volume_ma20_value:,.0f}")
        print(f"缩量比例: {volume_ratio:.3f}")

        volume_score = 0
        if volume_ratio < 0.5:
            volume_score = 20
            score_details["reasons"].append("大幅缩量")
        elif volume_ratio < 0.8:
            volume_score = 15
            score_details["reasons"].append("明显缩量")
        elif volume_ratio < 1.0:
            volume_score = 10
            score_details["reasons"].append("缩量")
        else:
            score_details["conditions_failed"].append(f"未缩量(量比{volume_ratio:.2f})")

        score_details["volume_score"] = volume_score

        # === 3. 反转强度评分 ===
        reversal_pct = (confirm_close - doji_high) / doji_high * 100
        print(f"\n=== 反转确认分析 ===")
        print(
            f"反转幅度: {reversal_pct:.2f}% (确认日收盘 {confirm_close:.2f} vs 十字星最高 {doji_high:.2f})"
        )

        reversal_score = 0
        is_reversal = confirm_close > doji_high
        if is_reversal:
            if reversal_pct > 3:
                reversal_score = 20
                score_details["reasons"].append("强势反转")
            elif reversal_pct > 1:
                reversal_score = 15
                score_details["reasons"].append("有效反转")
            else:
                reversal_score = 10
                score_details["reasons"].append("反转确认")
        else:
            score_details["conditions_failed"].append("未突破十字星最高价")

        score_details["reversal_score"] = reversal_score

        # 确认日必须为阳线
        is_positive_candle = confirm_close > confirm_open
        if is_positive_candle:
            score_details["conditions_met"].append("确认日为阳线")
        else:
            score_details["conditions_failed"].append("确认日非阳线")

        # === 4. 技术面加分 ===
        print(f"\n=== 技术面分析 ===")
        tech_bonus = 0

        # 均线数据
        ma5_confirm = confirm_data["ma5"]
        ma20_confirm = confirm_data["ma20"]
        ma30_confirm = confirm_data["ma30"]

        print(
            f"确认日均线: MA5={ma5_confirm:.2f}, MA20={ma20_confirm:.2f}, MA30={ma30_confirm:.2f}"
        )

        # 开盘价位置评分
        if confirm_open < ma30_confirm:
            tech_bonus += 20
            score_details["reasons"].append("开盘价低于30日线")
        if confirm_open < ma20_confirm:
            tech_bonus += 10
            score_details["reasons"].append("开盘价低于20日线")

        # 收盘价位置评分
        if confirm_close > ma30_confirm:
            tech_bonus += 10
            score_details["reasons"].append("收盘价突破30日线")
        if confirm_close > ma20_confirm:
            tech_bonus += 20
            score_details["reasons"].append("收盘价突破20日线")

        # 均线多头排列
        if ma5_confirm > ma20_confirm > ma30_confirm:
            tech_bonus += 20
            score_details["reasons"].append("均线多头排列")
            score_details["conditions_met"].append("均线多头排列")
        else:
            score_details["conditions_failed"].append("均线非多头排列")

        # DEA条件
        dea_doji = doji_data["dea_line"]
        dea_confirm = confirm_data["dea_line"]
        macd_confirm = confirm_data["macd_line"]

        print(
            f"MACD指标: 十字星日DEA={dea_doji:.4f}, 确认日DEA={dea_confirm:.4f}, 确认日MACD={macd_confirm:.4f}"
        )

        if pd.notna(dea_doji) and pd.notna(dea_confirm) and pd.notna(macd_confirm):
            is_dea_increasing = dea_confirm > dea_doji
            is_dea_negative = dea_confirm < 0
            is_macd_above_dea = macd_confirm > dea_confirm

            if is_dea_increasing and is_dea_negative and is_macd_above_dea:
                dea_improvement = dea_confirm - dea_doji
                if dea_improvement > 0.02:
                    tech_bonus += 15
                    score_details["reasons"].append("DEA明显改善")
                else:
                    tech_bonus += 10
                    score_details["reasons"].append("DEA增大")
                score_details["conditions_met"].append("DEA条件满足")
            else:
                score_details["conditions_failed"].append("DEA条件不满足")
        else:
            score_details["conditions_failed"].append("DEA数据缺失")

        # 确认日涨幅加分
        confirm_daily_gain_pct = (confirm_close - confirm_open) / confirm_open * 100
        print(f"确认日涨幅: {confirm_daily_gain_pct:.2f}%")

        if confirm_daily_gain_pct > 9:
            tech_bonus += 20
            score_details["reasons"].append(
                f"确认日大涨({confirm_daily_gain_pct:.1f}%)"
            )
        elif confirm_daily_gain_pct > 5:
            tech_bonus += 10
            score_details["reasons"].append(
                f"确认日上涨({confirm_daily_gain_pct:.1f}%)"
            )

        # KDJ条件
        j_value = confirm_data["kdj_j"]
        print(f"KDJ指标: J值={j_value:.1f}")

        if pd.notna(j_value):
            if j_value < 90:
                score_details["conditions_met"].append("J值<90(避免超买)")
            else:
                score_details["conditions_failed"].append(f"J值过高({j_value:.1f})")
        else:
            score_details["conditions_failed"].append("KDJ数据缺失")

        # === 5. 成交量加分 ===
        volume_bonus = 0
        confirmation_to_doji_volume_ratio = (
            confirm_volume / doji_volume if doji_volume > 0 else 999
        )
        print(f"\n=== 成交量加分检查 ===")
        print(f"确认日成交量比例: {confirmation_to_doji_volume_ratio:.2f}")

        if confirmation_to_doji_volume_ratio > 6.0:
            volume_bonus = 10
            tech_bonus += volume_bonus
            score_details["reasons"].append(
                f"确认日大幅放量({confirmation_to_doji_volume_ratio:.1f}倍)"
            )
            score_details["conditions_met"].append("确认日大幅放量确认")

        score_details["volume_bonus"] = volume_bonus

        # === 总分计算 ===
        total_score = doji_quality + volume_score + reversal_score + tech_bonus
        score_details["total_score"] = total_score

        # 额外信息
        score_details.update(
            {
                "body_size": body_size,
                "volume_ratio": volume_ratio,
                "reversal_pct": reversal_pct,
                "confirm_daily_gain_pct": confirm_daily_gain_pct,
                "upper_shadow_pct": upper_shadow_pct,
                "lower_shadow_pct": lower_shadow_pct,
                "confirmation_to_doji_volume_ratio": confirmation_to_doji_volume_ratio,
                "j_value": j_value,
            }
        )

        return score_details

    def print_score_report(self, stock_name, stock_code, target_date, score_details):
        """打印详细的评分报告"""
        if not score_details:
            print("无法生成评分报告")
            return

        print(f"\n{'='*80}")
        print(
            f"🎯 {stock_name}({stock_code}) - {target_date} 缩量十字星反转策略评分报告"
        )
        print(f"{'='*80}")

        print(f"\n📊 【总评分】: {score_details['total_score']:.0f}分")

        # 分项评分
        print(f"\n📋 【分项评分明细】:")
        print(f"├─ 十字星质量: {score_details['doji_quality']}分")
        print(f"├─ 缩量程度: {score_details['volume_score']}分")
        print(f"├─ 反转强度: {score_details['reversal_score']}分")
        print(f"├─ 技术面加分: {score_details['tech_bonus']}分")
        print(f"└─ 成交量加分: {score_details['volume_bonus']}分")

        # 关键数据
        print(f"\n📈 【关键数据】:")
        print(f"├─ 实体大小: {score_details['body_size']:.3f}%")
        print(f"├─ 缩量比例: {score_details['volume_ratio']:.3f}")
        print(f"├─ 反转幅度: {score_details['reversal_pct']:.2f}%")
        print(f"├─ 确认日涨幅: {score_details['confirm_daily_gain_pct']:.2f}%")
        print(f"├─ 上影线: {score_details['upper_shadow_pct']:.2f}%")
        print(f"├─ 下影线: {score_details['lower_shadow_pct']:.2f}%")
        print(
            f"├─ 确认日量比: {score_details['confirmation_to_doji_volume_ratio']:.2f}"
        )
        print(f"└─ KDJ J值: {score_details['j_value']:.1f}")

        # 加分原因
        if score_details["reasons"]:
            print(f"\n✅ 【得分原因】:")
            for reason in score_details["reasons"]:
                print(f"├─ {reason}")

        # 满足的条件
        if score_details["conditions_met"]:
            print(f"\n✅ 【满足条件】:")
            for condition in score_details["conditions_met"]:
                print(f"├─ {condition}")

        # 未满足的条件
        if score_details["conditions_failed"]:
            print(f"\n❌ 【未满足条件】:")
            for condition in score_details["conditions_failed"]:
                print(f"├─ {condition}")

        # 策略判断
        print(f"\n🎯 【策略判断】:")
        if score_details["total_score"] > 100:
            print("✅ 符合买入条件 (评分>100)")
        elif score_details["total_score"] > 85:
            print("⚠️  接近买入条件 (评分>85)")
        else:
            print("❌ 不符合买入条件")

        print(f"\n{'='*80}")

    def query_stock_score(self, stock_input, date_input):
        """主查询函数"""
        # 获取股票列表
        if not self.get_stock_list():
            return False

        # 查找股票代码
        stock_code, stock_name = self.find_stock_code(stock_input)
        if not stock_code:
            print(f"未找到股票: {stock_input}")
            return False

        print(f"找到股票: {stock_name}({stock_code})")

        # 获取股票数据
        data = self.get_stock_data(stock_code, date_input)
        if data is None:
            return False

        # 计算技术指标
        data = self.calculate_indicators(data)
        if data is None:
            return False

        # 计算评分
        score_details = self.score_stock(data, date_input)
        if score_details is None:
            return False

        # 打印报告
        self.print_score_report(stock_name, stock_code, date_input, score_details)

        return True


def main():
    parser = argparse.ArgumentParser(description="股票评分查询工具")
    parser.add_argument("--stock", "--name", help="股票名称(如: 大众交通)")
    parser.add_argument("--code", help="股票代码(如: 600611)")
    parser.add_argument("--date", required=True, help="查询日期(格式: 2023-07-08)")

    args = parser.parse_args()

    # 验证参数
    if not args.stock and not args.code:
        print("请提供股票名称(--stock)或股票代码(--code)")
        return

    stock_input = args.stock or args.code

    # 验证日期格式
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print("日期格式错误，请使用 YYYY-MM-DD 格式")
        return

    # 执行查询
    query_tool = StockScoreQuery()
    success = query_tool.query_stock_score(stock_input, args.date)

    if not success:
        print("查询失败")


if __name__ == "__main__":
    main()
