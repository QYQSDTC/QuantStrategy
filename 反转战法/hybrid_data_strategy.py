#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
混合数据源策略脚本
结合qstock和其他数据源进行分析

数据源组合：
1. qstock: 实时数据、市场情绪、盘口数据
2. akshare/tushare: 历史数据、基本面数据
3. 本地缓存: 历史技术指标计算结果

使用场景：
- 历史回测：使用传统数据源
- 实时监控：使用qstock实时数据
- 选股筛选：结合多源数据优势
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import json
import os

warnings.filterwarnings("ignore")

try:
    import qstock as qs
    QSTOCK_AVAILABLE = True
    print("✅ qstock 已导入")
except ImportError:
    QSTOCK_AVAILABLE = False
    print("❌ qstock 未安装，部分功能将受限")

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
    print("✅ akshare 已导入")
except ImportError:
    AKSHARE_AVAILABLE = False
    print("❌ akshare 未安装，历史数据功能将受限")

print("🚀 混合数据源量化策略系统")
print("=" * 60)


class HybridDataStrategy:
    def __init__(self, cache_dir="data_cache"):
        self.cache_dir = cache_dir
        self.stock_name_map = {}
        self.create_cache_dir()
        
    def create_cache_dir(self):
        """创建缓存目录"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            print(f"📁 创建缓存目录: {self.cache_dir}")

    def get_realtime_data(self, market='沪深A', codes=None):
        """获取实时数据 - 优先使用qstock"""
        if not QSTOCK_AVAILABLE:
            print("⚠️  qstock不可用，无法获取实时数据")
            return None
            
        try:
            print(f"📡 正在获取实时数据...")
            
            if codes is None:
                # 获取整个市场的实时数据
                data = qs.realtime_data(market=market)
            else:
                # 获取指定股票的实时数据
                data = qs.realtime_data(code=codes)
            
            if data is not None and not data.empty:
                print(f"✅ 成功获取 {len(data)} 条实时数据")
                
                # 标准化列名
                column_mapping = {
                    '代码': 'code',
                    '名称': 'name', 
                    '最新价': 'price',
                    '涨跌幅': 'pct_change',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '总市值': 'market_cap'
                }
                
                for old_col, new_col in column_mapping.items():
                    if old_col in data.columns:
                        data = data.rename(columns={old_col: new_col})
                
                # 创建代码名称映射
                if 'code' in data.columns and 'name' in data.columns:
                    for _, row in data.iterrows():
                        self.stock_name_map[row['code']] = row['name']
                
                return data
            else:
                print("❌ 未获取到实时数据")
                return None
                
        except Exception as e:
            print(f"❌ 获取实时数据失败: {e}")
            return None

    def get_historical_data(self, stock_code, start_date, end_date, source='akshare'):
        """获取历史数据 - 支持多数据源"""
        cache_file = f"{self.cache_dir}/{stock_code}_{start_date}_{end_date}.csv"
        
        # 检查缓存
        if os.path.exists(cache_file):
            try:
                data = pd.read_csv(cache_file, parse_dates=['date'])
                print(f"📂 从缓存加载 {stock_code} 历史数据")
                return data
            except:
                pass
        
        # 获取新数据
        if source == 'akshare' and AKSHARE_AVAILABLE:
            data = self._get_akshare_hist(stock_code, start_date, end_date)
        elif source == 'qstock' and QSTOCK_AVAILABLE:
            data = self._get_qstock_hist(stock_code, start_date, end_date)
        else:
            print(f"⚠️  数据源 {source} 不可用")
            return None
        
        # 保存到缓存
        if data is not None and not data.empty:
            try:
                data.to_csv(cache_file, index=False)
                print(f"💾 已缓存 {stock_code} 历史数据")
            except Exception as e:
                print(f"⚠️  缓存保存失败: {e}")
        
        return data

    def _get_akshare_hist(self, stock_code, start_date, end_date):
        """使用akshare获取历史数据"""
        try:
            data = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq",
            )
            
            if not data.empty:
                # 标准化列名
                data = data.rename(columns={
                    "日期": "date",
                    "开盘": "open",
                    "最高": "high", 
                    "最低": "low",
                    "收盘": "close",
                    "成交量": "volume",
                    "涨跌幅": "pct_change",
                })
                data['date'] = pd.to_datetime(data['date'])
                data['symbol'] = stock_code
                return data
                
        except Exception as e:
            print(f"❌ akshare获取 {stock_code} 数据失败: {e}")
            
        return None

    def _get_qstock_hist(self, stock_code, start_date, end_date):
        """使用qstock获取历史数据 (如果有相关接口)"""
        # qstock主要提供实时数据，历史数据接口有限
        # 这里提供接口预留，等待qstock更新
        print(f"⚠️  qstock历史数据接口有限，建议使用其他数据源")
        return None

    def market_sentiment_analysis(self):
        """市场情绪分析 - 使用qstock实时数据"""
        if not QSTOCK_AVAILABLE:
            print("⚠️  qstock不可用，无法进行情绪分析")
            return False
            
        try:
            print("\n🔍 正在进行市场情绪分析...")
            
            # 获取实时市场数据
            market_data = self.get_realtime_data(market='沪深A')
            if market_data is None:
                return False
            
            # 情绪指标计算
            total_stocks = len(market_data)
            
            if 'pct_change' in market_data.columns:
                up_stocks = len(market_data[market_data['pct_change'] > 0])
                down_stocks = len(market_data[market_data['pct_change'] < 0])
                limit_up = len(market_data[market_data['pct_change'] >= 9.5])
                limit_down = len(market_data[market_data['pct_change'] <= -9.5])
                strong_stocks = len(market_data[market_data['pct_change'] > 6])
                
                up_ratio = up_stocks / total_stocks if total_stocks > 0 else 0
                
                # 情绪判断
                sentiment_active = (
                    up_ratio > 0.6 or  # 超60%股票上涨
                    limit_up > 10 or   # 涨停超10只
                    strong_stocks > 50  # 强势股超50只
                )
                
                print(f"📊 市场情绪分析结果:")
                print(f"   总股票数: {total_stocks}")
                print(f"   上涨比例: {up_ratio:.1%} ({up_stocks}只)")
                print(f"   下跌比例: {(down_stocks/total_stocks):.1%} ({down_stocks}只)")
                print(f"   涨停股票: {limit_up}只")
                print(f"   跌停股票: {limit_down}只")
                print(f"   强势股票: {strong_stocks}只 (涨幅>6%)")
                print(f"   情绪状态: {'🔥 活跃' if sentiment_active else '😴 平淡'}")
                
                return sentiment_active
            else:
                print("⚠️  涨跌幅数据不可用")
                return False
                
        except Exception as e:
            print(f"❌ 情绪分析失败: {e}")
            return False

    def hybrid_stock_screening(self, use_realtime=True, use_historical=True):
        """混合数据源选股"""
        print("\n🎯 开始混合数据源选股...")
        
        selected_stocks = []
        
        # 1. 实时数据筛选
        if use_realtime and QSTOCK_AVAILABLE:
            print("📡 第一阶段: 实时数据筛选")
            realtime_candidates = self._realtime_screening()
        else:
            realtime_candidates = []
            print("⚠️  跳过实时数据筛选")
        
        # 2. 历史数据验证
        if use_historical and AKSHARE_AVAILABLE and realtime_candidates:
            print("📊 第二阶段: 历史数据验证")
            for candidate in realtime_candidates[:20]:  # 只验证前20只
                if self._historical_validation(candidate):
                    selected_stocks.append(candidate)
        else:
            selected_stocks = realtime_candidates[:10]
            print("⚠️  跳过历史数据验证")
        
        return selected_stocks

    def _realtime_screening(self):
        """实时数据筛选"""
        market_data = self.get_realtime_data(market='沪深A')
        if market_data is None:
            return []
        
        candidates = []
        
        # 筛选主板股票
        if 'code' in market_data.columns:
            main_board_data = market_data[
                market_data['code'].str.match(r'^(600|601|603|605|000|001|002)')
            ]
            
            print(f"📈 筛选主板股票: {len(main_board_data)} 只")
            
            # 基本筛选条件
            for _, stock in main_board_data.iterrows():
                try:
                    code = stock.get('code', '')
                    name = stock.get('name', '')
                    price = stock.get('price', 0)
                    pct_change = stock.get('pct_change', 0)
                    volume = stock.get('volume', 0)
                    
                    # 过滤条件
                    if (
                        5 < price < 100 and  # 价格范围
                        -3 < pct_change < 8 and  # 涨跌幅范围
                        volume > 0 and  # 有成交量
                        'ST' not in name  # 非ST股票
                    ):
                        # 简单评分
                        score = 50
                        if 0 < pct_change <= 3:
                            score += 10  # 温和上涨
                        if 10 <= price <= 50:
                            score += 5   # 合理价位
                        
                        candidates.append({
                            'code': code,
                            'name': name,
                            'price': price,
                            'pct_change': pct_change,
                            'volume': volume,
                            'score': score,
                            'source': 'realtime'
                        })
                        
                except Exception as e:
                    continue
        
        # 按评分排序
        candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)
        
        print(f"✅ 实时筛选结果: {len(candidates)} 只候选股票")
        return candidates

    def _historical_validation(self, candidate):
        """历史数据验证"""
        code = candidate['code']
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        hist_data = self.get_historical_data(code, start_date, end_date)
        if hist_data is None or len(hist_data) < 10:
            return False
        
        try:
            # 简单的历史验证条件
            recent_data = hist_data.tail(10)
            
            # 检查是否有稳定的交易量
            avg_volume = recent_data['volume'].mean()
            current_volume = candidate['volume']
            
            # 检查价格趋势
            price_trend = recent_data['close'].iloc[-1] > recent_data['close'].iloc[0]
            
            # 验证通过条件
            validation_passed = (
                current_volume > avg_volume * 0.5 and  # 成交量不过低
                price_trend  # 近期价格呈上升趋势
            )
            
            if validation_passed:
                candidate['historical_validation'] = True
                candidate['avg_volume_30d'] = avg_volume
                return True
                
        except Exception as e:
            pass
            
        return False

    def generate_report(self, selected_stocks):
        """生成分析报告"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"\n📋 混合数据源选股报告")
        print(f"=" * 60)
        print(f"🕐 生成时间: {timestamp}")
        print(f"📊 数据源: qstock(实时) + akshare(历史)")
        
        if selected_stocks:
            print(f"✅ 选股结果: {len(selected_stocks)} 只股票")
            print(f"\n详细列表:")
            
            for i, stock in enumerate(selected_stocks[:10]):
                validation_status = "✅" if stock.get('historical_validation', False) else "⏳"
                print(f"  {i+1:2d}. {stock['name']}({stock['code']}) {validation_status}")
                print(f"      价格: ¥{stock['price']:.2f}")
                print(f"      涨幅: {stock['pct_change']:+.2f}%")
                print(f"      评分: {stock['score']}")
                if 'avg_volume_30d' in stock:
                    print(f"      30日均量: {stock['avg_volume_30d']:,.0f}")
                print()
        else:
            print("❌ 未选出符合条件的股票")
        
        # 保存报告
        report_data = {
            'timestamp': timestamp,
            'selected_stocks': selected_stocks,
            'data_sources': ['qstock', 'akshare'],
            'total_selected': len(selected_stocks)
        }
        
        report_file = f"{self.cache_dir}/hybrid_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)
            print(f"📁 报告已保存: {report_file}")
        except Exception as e:
            print(f"⚠️  报告保存失败: {e}")

    def run_strategy(self):
        """运行完整策略"""
        print(f"🚀 开始执行混合数据源策略")
        print(f"🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. 市场情绪分析
        sentiment_active = self.market_sentiment_analysis()
        
        # 2. 混合选股
        selected_stocks = self.hybrid_stock_screening()
        
        # 3. 生成报告
        self.generate_report(selected_stocks)
        
        # 4. 策略建议
        print(f"\n💡 策略建议:")
        if sentiment_active and selected_stocks:
            print("🔥 市场情绪活跃 + 发现优质标的 → 建议积极操作")
        elif sentiment_active and not selected_stocks:
            print("🔥 市场情绪活跃但无优质标的 → 建议谨慎观望")
        elif not sentiment_active and selected_stocks:
            print("😴 市场情绪平淡但有优质标的 → 建议轻仓试探")
        else:
            print("😴 市场情绪平淡且无优质标的 → 建议空仓观望")
        
        print(f"🕐 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    """主函数"""
    print("💡 混合数据源策略说明:")
    print("   - qstock: 实时数据获取和市场情绪分析")
    print("   - akshare: 历史数据验证和技术分析") 
    print("   - 本地缓存: 提高数据获取效率")
    print("   - 双重验证: 实时筛选 + 历史验证")
    print("")
    
    # 检查数据源可用性
    if not QSTOCK_AVAILABLE and not AKSHARE_AVAILABLE:
        print("❌ 错误: 没有可用的数据源，请安装 qstock 或 akshare")
        return
    
    if not QSTOCK_AVAILABLE:
        print("⚠️  警告: qstock不可用，实时功能受限")
    
    if not AKSHARE_AVAILABLE:
        print("⚠️  警告: akshare不可用，历史验证功能受限")
    
    try:
        strategy = HybridDataStrategy()
        strategy.run_strategy()
    except KeyboardInterrupt:
        print("\n👋 策略执行已停止")
    except Exception as e:
        print(f"❌ 策略执行失败: {e}")


if __name__ == "__main__":
    main() 