#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于qstock的实时选股脚本
利用qstock的实时数据进行十字星反转策略选股

由于qstock主要提供实时数据，本脚本专注于：
1. 实时数据获取和分析
2. 当日市场情绪判断
3. 实时选股筛选
4. 盘中监控功能
"""

import pandas as pd
import qstock as qs
import numpy as np
from datetime import datetime, timedelta
import time
import warnings

warnings.filterwarnings("ignore")

print("🚀 qstock实时选股系统 - 十字星反转策略")
print("=" * 60)


class QstockRealtimeScreener:
    def __init__(self):
        self.stock_name_map = {}
        self.market_sentiment = {
            "date": None,
            "hot_stocks": [],
            "sentiment_active": False,
            "total_stocks": 0,
            "up_stocks": 0,
            "down_stocks": 0,
            "limit_up": 0,
            "limit_down": 0,
        }

    def get_stock_list(self):
        """获取股票列表"""
        print("📊 正在获取实时股票数据...")
        
        try:
            # 使用qstock获取沪深A股实时数据
            all_stocks = qs.realtime_data()
            print(f"✅ 成功获取 {len(all_stocks)} 只股票的实时数据")
            
            # 适配列名
            if "代码" in all_stocks.columns:
                code_col, name_col = "代码", "名称"
            elif "code" in all_stocks.columns:
                code_col, name_col = "code", "name"
            else:
                code_col, name_col = all_stocks.columns[0], all_stocks.columns[1]
            
            # 筛选主板股票
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
                    lambda row: is_main_board_stock(row[code_col], row[name_col]), axis=1
                )
            ]

            # 创建股票代码到名称的映射
            for _, row in main_board_stocks.iterrows():
                self.stock_name_map[row[code_col]] = row[name_col]

            print(f"📈 筛选出 {len(main_board_stocks)} 只主板股票")
            return main_board_stocks, code_col, name_col
            
        except Exception as e:
            print(f"❌ 获取股票数据失败: {e}")
            return None, None, None

    def analyze_market_sentiment(self, stocks_data, code_col):
        """分析市场情绪"""
        print("\n🔍 正在分析市场情绪...")
        
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # 适配涨跌幅列名
            pct_col = None
            for col in ["涨跌幅", "pct_change", "change_pct", "涨幅"]:
                if col in stocks_data.columns:
                    pct_col = col
                    break
            
            if pct_col is None:
                print("⚠️  未找到涨跌幅数据列，跳过情绪分析")
                return False
            
            # 市场统计
            total_stocks = len(stocks_data)
            up_stocks = len(stocks_data[stocks_data[pct_col] > 0])
            down_stocks = len(stocks_data[stocks_data[pct_col] < 0])
            limit_up = len(stocks_data[stocks_data[pct_col] >= 9.5])  # 涨停
            limit_down = len(stocks_data[stocks_data[pct_col] <= -9.5])  # 跌停
            
            # 强势股票（涨幅超过6%）
            strong_stocks = stocks_data[stocks_data[pct_col] > 6]
            
            # 更新市场情绪状态
            self.market_sentiment.update({
                "date": current_date,
                "total_stocks": total_stocks,
                "up_stocks": up_stocks,
                "down_stocks": down_stocks,
                "limit_up": limit_up,
                "limit_down": limit_down,
                "hot_stocks": [],
                "sentiment_active": False,
            })
            
            # 记录强势股票
            hot_stocks = []
            for _, stock in strong_stocks.iterrows():
                stock_name = self.stock_name_map.get(stock[code_col], stock[code_col])
                hot_stocks.append({
                    "symbol": stock[code_col],
                    "name": stock_name,
                    "gain_today": stock[pct_col],
                })
            
            self.market_sentiment["hot_stocks"] = hot_stocks
            
            # 判断市场情绪是否活跃
            up_ratio = up_stocks / total_stocks if total_stocks > 0 else 0
            sentiment_active = (
                up_ratio > 0.6 or  # 超过60%的股票上涨
                limit_up > 10 or   # 涨停股票超过10只
                len(strong_stocks) > 50  # 强势股票超过50只
            )
            
            self.market_sentiment["sentiment_active"] = sentiment_active
            
            # 输出情绪分析结果
            print(f"📊 市场情绪分析 ({current_date}):")
            print(f"   总股票数: {total_stocks}")
            print(f"   上涨股票: {up_stocks} ({up_ratio:.1%})")
            print(f"   下跌股票: {down_stocks} ({(down_stocks/total_stocks):.1%})")
            print(f"   涨停股票: {limit_up}")
            print(f"   跌停股票: {limit_down}")
            print(f"   强势股票: {len(strong_stocks)} (涨幅>6%)")
            
            if sentiment_active:
                print(f"🔥 市场情绪: 活跃 ✅")
                if len(hot_stocks) > 0:
                    print(f"   热门股票 (前5只):")
                    for i, stock in enumerate(hot_stocks[:5]):
                        print(f"     {i+1}. {stock['name']}({stock['symbol']}): +{stock['gain_today']:.2f}%")
            else:
                print(f"😴 市场情绪: 平淡 ❌")
            
            return sentiment_active
            
        except Exception as e:
            print(f"❌ 市场情绪分析失败: {e}")
            return False

    def realtime_screening(self):
        """实时选股筛选"""
        print("\n🎯 开始实时选股筛选...")
        
        # 获取股票数据
        stocks_data, code_col, name_col = self.get_stock_list()
        if stocks_data is None:
            return []
        
        # 市场情绪分析
        sentiment_active = self.analyze_market_sentiment(stocks_data, code_col)
        
        # 基于实时数据的简化选股条件
        selected_stocks = []
        
        try:
            # 适配数据列名
            price_col = None
            for col in ["最新价", "current_price", "price", "收盘"]:
                if col in stocks_data.columns:
                    price_col = col
                    break
            
            volume_col = None
            for col in ["成交量", "volume", "vol"]:
                if col in stocks_data.columns:
                    volume_col = col
                    break
            
            pct_col = None
            for col in ["涨跌幅", "pct_change", "change_pct", "涨幅"]:
                if col in stocks_data.columns:
                    pct_col = col
                    break
            
            if not all([price_col, volume_col, pct_col]):
                print("⚠️  数据列不完整，无法进行选股")
                return []
            
            print(f"📈 正在分析 {len(stocks_data)} 只股票...")
            
            # 简化的实时选股条件
            for _, stock in stocks_data.iterrows():
                try:
                    # 基本筛选条件
                    price = stock[price_col]
                    volume = stock[volume_col]
                    pct_change = stock[pct_col]
                    
                    # 过滤条件
                    if (
                        price > 5 and  # 价格大于5元
                        price < 100 and  # 价格小于100元
                        volume > 0 and  # 有成交量
                        -2 < pct_change < 8  # 涨跌幅在合理范围内
                    ):
                        
                        # 计算简单评分
                        score = 50  # 基础分
                        
                        # 价格位置评分
                        if 10 <= price <= 50:
                            score += 10
                        
                        # 涨跌幅评分
                        if 0 < pct_change <= 3:
                            score += 15  # 温和上涨
                        elif 3 < pct_change <= 6:
                            score += 10  # 适度上涨
                        
                        # 成交量评分（相对评分）
                        if volume > stocks_data[volume_col].median():
                            score += 10
                        
                        # 只选择评分较高的股票
                        if score > 60:
                            stock_name = self.stock_name_map.get(stock[code_col], stock[code_col])
                            selected_stocks.append({
                                "symbol": stock[code_col],
                                "name": stock_name,
                                "price": price,
                                "pct_change": pct_change,
                                "volume": volume,
                                "score": score,
                            })
                
                except Exception as e:
                    continue
            
            # 按评分排序
            selected_stocks = sorted(selected_stocks, key=lambda x: x["score"], reverse=True)
            
            # 输出选股结果
            print(f"\n📋 实时选股结果:")
            if selected_stocks:
                print(f"✅ 共选出 {len(selected_stocks)} 只潜力股票")
                
                if sentiment_active:
                    print("🔥 市场情绪活跃，可考虑操作")
                else:
                    print("😴 市场情绪平淡，建议观望")
                
                print(f"\n前10只股票:")
                for i, stock in enumerate(selected_stocks[:10]):
                    print(f"  {i+1:2d}. {stock['name']}({stock['symbol']}) - "
                          f"价格:¥{stock['price']:.2f} "
                          f"涨幅:{stock['pct_change']:+.2f}% "
                          f"评分:{stock['score']}")
            else:
                print("❌ 未发现符合条件的股票")
            
            return selected_stocks[:10]  # 返回前10只
            
        except Exception as e:
            print(f"❌ 选股分析失败: {e}")
            return []

    def monitor_selected_stocks(self, selected_stocks, monitor_duration=60):
        """监控选中的股票"""
        if not selected_stocks:
            print("📭 没有股票需要监控")
            return
        
        print(f"\n👀 开始监控 {len(selected_stocks)} 只股票 (持续{monitor_duration}秒)...")
        
        start_time = time.time()
        monitor_symbols = [stock["symbol"] for stock in selected_stocks]
        
        try:
            while time.time() - start_time < monitor_duration:
                try:
                    # 获取实时数据
                    current_data = qs.realtime_data(code=monitor_symbols)
                    
                    if current_data is not None and not current_data.empty:
                        print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')} 实时监控:")
                        
                        # 适配列名
                        code_col = "代码" if "代码" in current_data.columns else current_data.columns[0]
                        
                        for _, stock in current_data.iterrows():
                            symbol = stock[code_col]
                            stock_name = self.stock_name_map.get(symbol, symbol)
                            
                            # 获取价格和涨跌幅信息
                            try:
                                price = stock.get("最新价", stock.get("current_price", 0))
                                pct_change = stock.get("涨跌幅", stock.get("pct_change", 0))
                                print(f"   {stock_name}({symbol}): ¥{price:.2f} ({pct_change:+.2f}%)")
                            except:
                                print(f"   {stock_name}({symbol}): 数据获取异常")
                    
                    time.sleep(10)  # 每10秒更新一次
                    
                except Exception as e:
                    print(f"⚠️  监控更新失败: {e}")
                    time.sleep(5)
                    continue
                    
        except KeyboardInterrupt:
            print("\n⏹️  监控已停止")

    def run_full_analysis(self):
        """运行完整的实时分析"""
        print(f"🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. 实时选股
        selected_stocks = self.realtime_screening()
        
        # 2. 保存选股结果
        if selected_stocks:
            df = pd.DataFrame(selected_stocks)
            filename = f"qstock_selected_stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"📁 选股结果已保存到: {filename}")
        
        # 3. 询问是否开始监控
        if selected_stocks:
            try:
                monitor = input("\n🤔 是否开始实时监控选中的股票? (y/n): ").lower().strip()
                if monitor in ['y', 'yes', '是']:
                    duration = input("监控时长(秒，默认60): ").strip()
                    duration = int(duration) if duration.isdigit() else 60
                    self.monitor_selected_stocks(selected_stocks, duration)
            except KeyboardInterrupt:
                print("\n👋 程序已退出")


def main():
    """主函数"""
    screener = QstockRealtimeScreener()
    
    try:
        screener.run_full_analysis()
    except KeyboardInterrupt:
        print("\n👋 程序已手动停止")
    except Exception as e:
        print(f"❌ 程序运行出错: {e}")
    
    print(f"🕐 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    print("💡 使用说明:")
    print("   - 本脚本基于qstock实时数据进行选股")
    print("   - 适合盘中实时分析和监控")
    print("   - 使用Ctrl+C可随时停止程序")
    print("   - 确保在交易时间内运行以获得最佳效果")
    print("")
    
    main() 