#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qstock历史数据功能演示脚本
展示qstock的get_data和get_price接口使用方法

主要功能：
1. 单只股票历史K线数据
2. 多只股票历史价格数据
3. 指数历史数据
4. 不同频率的数据获取
5. 复权处理演示
"""

import pandas as pd
import qstock as qs
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings("ignore")

# 设置matplotlib中文字体
plt.rcParams["font.sans-serif"] = [
    "SimHei",
    "Microsoft YaHei", 
    "DejaVu Sans",
    "Arial Unicode MS",
]
plt.rcParams["axes.unicode_minus"] = False

print("🚀 qstock历史数据功能演示")
print("=" * 60)


def demo_single_stock_data():
    """演示单只股票历史数据获取"""
    print("\n📊 1. 单只股票历史数据演示")
    print("-" * 40)
    
    try:
        # 获取中国平安的历史数据
        print("📈 获取中国平安(601318)最近1年的日线数据...")
        
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        
        data = qs.get_data(
            code_list='601318',  # 中国平安
            start=start_date,
            end=end_date,
            freq='d',  # 日线
            fqt=1  # 前复权
        )
        
        if data is not None and not data.empty:
            print(f"✅ 成功获取数据: {len(data)} 条记录")
            print(f"📅 时间范围: {data.index.min()} 到 {data.index.max()}")
            print(f"📋 数据列: {list(data.columns)}")
            print("\n📋 前5行数据:")
            print(data.head())
            print("\n📊 基本统计:")
            print(data.describe())
            
            return data
        else:
            print("❌ 未获取到数据")
            return None
            
    except Exception as e:
        print(f"❌ 获取数据失败: {e}")
        return None


def demo_multiple_stocks_price():
    """演示多只股票价格数据获取"""
    print("\n📊 2. 多只股票价格数据演示")
    print("-" * 40)
    
    try:
        # 获取多只股票的收盘价数据
        code_list = ['中国平安', '贵州茅台', '工业富联', '招商银行', '五粮液']
        print(f"📈 获取以下股票的历史价格数据: {code_list}")
        
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d')
        
        price_data = qs.get_price(
            code_list=code_list,
            start=start_date,
            end=end_date,
            freq='d',
            fqt=1
        )
        
        if price_data is not None and not price_data.empty:
            print(f"✅ 成功获取价格数据: {price_data.shape}")
            print(f"📅 时间范围: {price_data.index.min()} 到 {price_data.index.max()}")
            print("\n📋 最近5天的价格数据:")
            print(price_data.tail())
            
            # 计算收益率
            returns = price_data.pct_change().dropna()
            print("\n📊 最近收益率统计:")
            print(returns.describe())
            
            return price_data
        else:
            print("❌ 未获取到价格数据")
            return None
            
    except Exception as e:
        print(f"❌ 获取价格数据失败: {e}")
        return None


def demo_index_data():
    """演示指数数据获取"""
    print("\n📊 3. 指数历史数据演示")
    print("-" * 40)
    
    try:
        # 获取多个指数的历史数据
        index_list = ['sh', 'sz', 'hs300', 'sz50', 'cyb']  # 上证、深证、沪深300、上证50、创业板
        index_names = ['上证指数', '深证综指', '沪深300', '上证50', '创业板指']
        
        print(f"📈 获取指数数据: {dict(zip(index_list, index_names))}")
        
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
        
        index_data = qs.get_data(
            code_list=index_list,
            start=start_date,
            end=end_date,
            freq='d'
        )
        
        if index_data is not None and not index_data.empty:
            print(f"✅ 成功获取指数数据")
            print(f"📊 数据形状: {index_data.shape}")
            print("\n📋 最近指数数据:")
            print(index_data.tail())
            
            return index_data
        else:
            print("❌ 未获取到指数数据")
            return None
            
    except Exception as e:
        print(f"❌ 获取指数数据失败: {e}")
        return None


def demo_different_frequencies():
    """演示不同频率数据获取"""
    print("\n📊 4. 不同频率数据演示")
    print("-" * 40)
    
    frequencies = {
        'd': '日线',
        'w': '周线', 
        'm': '月线'
    }
    
    results = {}
    
    for freq_code, freq_name in frequencies.items():
        try:
            print(f"📈 获取中国平安{freq_name}数据...")
            
            if freq_code == 'd':
                days = 30
            elif freq_code == 'w':
                days = 180
            else:  # 月线
                days = 365
                
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
            
            data = qs.get_data(
                code_list='601318',
                start=start_date,
                end=end_date,
                freq=freq_code,
                fqt=1
            )
            
            if data is not None and not data.empty:
                print(f"   ✅ {freq_name}: {len(data)} 条记录")
                results[freq_name] = data
            else:
                print(f"   ❌ {freq_name}: 获取失败")
                
        except Exception as e:
            print(f"   ❌ {freq_name}: {e}")
    
    return results


def demo_adjustment_types():
    """演示不同复权类型"""
    print("\n📊 5. 复权类型演示")
    print("-" * 40)
    
    adjustment_types = {
        0: '不复权',
        1: '前复权',
        2: '后复权'
    }
    
    results = {}
    
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
    
    for fqt_code, fqt_name in adjustment_types.items():
        try:
            print(f"📈 获取中国平安{fqt_name}数据...")
            
            data = qs.get_data(
                code_list='601318',
                start=start_date,
                end=end_date,
                freq='d',
                fqt=fqt_code
            )
            
            if data is not None and not data.empty:
                latest_price = data['close'].iloc[-1]
                print(f"   ✅ {fqt_name}: 最新收盘价 ¥{latest_price:.2f}")
                results[fqt_name] = data
            else:
                print(f"   ❌ {fqt_name}: 获取失败")
                
        except Exception as e:
            print(f"   ❌ {fqt_name}: {e}")
    
    return results


def create_visualization(price_data):
    """创建数据可视化"""
    if price_data is None or price_data.empty:
        print("⚠️  无数据可用于绘图")
        return
    
    print("\n📊 6. 数据可视化")
    print("-" * 40)
    
    try:
        # 创建图表
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # 价格走势图
        for column in price_data.columns[:5]:  # 最多显示5只股票
            ax1.plot(price_data.index, price_data[column], label=column, linewidth=1.5)
        
        ax1.set_title('股票价格走势对比', fontsize=14, fontweight='bold')
        ax1.set_ylabel('价格 (元)', fontsize=12)
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3)
        
        # 收益率走势图
        returns = price_data.pct_change().dropna() * 100
        for column in returns.columns[:5]:
            ax2.plot(returns.index, returns[column].cumsum(), label=column, linewidth=1.5)
        
        ax2.set_title('累计收益率对比', fontsize=14, fontweight='bold')
        ax2.set_ylabel('累计收益率 (%)', fontsize=12)
        ax2.set_xlabel('日期', fontsize=12)
        ax2.legend(fontsize=10)
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('qstock_historical_data_demo.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print("✅ 图表已保存为: qstock_historical_data_demo.png")
        
    except Exception as e:
        print(f"❌ 绘图失败: {e}")


def generate_summary_report(results):
    """生成演示总结报告"""
    print("\n📋 演示总结报告")
    print("=" * 60)
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"🕐 报告生成时间: {timestamp}")
    
    print(f"\n✅ qstock历史数据功能验证结果:")
    
    feature_status = {
        '单只股票数据': results.get('single_stock') is not None,
        '多只股票价格': results.get('multiple_price') is not None, 
        '指数数据': results.get('index_data') is not None,
        '不同频率': len(results.get('frequencies', {})) > 0,
        '复权类型': len(results.get('adjustments', {})) > 0
    }
    
    for feature, status in feature_status.items():
        status_icon = "✅" if status else "❌"
        print(f"   {status_icon} {feature}")
    
    success_rate = sum(feature_status.values()) / len(feature_status) * 100
    print(f"\n📊 功能成功率: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("🎉 qstock历史数据功能良好，可以完全替代akshare进行历史数据获取！")
    elif success_rate >= 60:
        print("👍 qstock历史数据功能基本可用，建议与其他数据源结合使用")
    else:
        print("⚠️  qstock历史数据功能有限，建议继续使用akshare作为主要数据源")
    
    print(f"\n💡 使用建议:")
    print("   1. qstock的get_data()可获取完整的K线数据")
    print("   2. qstock的get_price()适合多股票价格对比")
    print("   3. 支持多种频率: 日线、周线、月线")
    print("   4. 支持前复权、后复权、不复权")
    print("   5. 可直接获取指数数据，无需特殊处理")


def main():
    """主函数"""
    print("💡 演示说明:")
    print("   - 验证qstock的历史数据获取能力")
    print("   - 展示get_data和get_price接口使用")
    print("   - 对比不同参数设置的效果")
    print("")
    
    results = {}
    
    try:
        # 1. 单只股票数据
        results['single_stock'] = demo_single_stock_data()
        
        # 2. 多只股票价格数据
        results['multiple_price'] = demo_multiple_stocks_price()
        
        # 3. 指数数据
        results['index_data'] = demo_index_data()
        
        # 4. 不同频率数据
        results['frequencies'] = demo_different_frequencies()
        
        # 5. 复权类型演示
        results['adjustments'] = demo_adjustment_types()
        
        # 6. 数据可视化
        if results['multiple_price'] is not None:
            create_visualization(results['multiple_price'])
        
        # 7. 生成总结报告
        generate_summary_report(results)
        
    except KeyboardInterrupt:
        print("\n👋 演示已停止")
    except Exception as e:
        print(f"\n❌ 演示程序异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🎯 目标: 全面测试qstock历史数据功能")
    print("📚 涵盖: K线数据、价格数据、指数数据、频率选择、复权处理")
    print("")
    
    main() 