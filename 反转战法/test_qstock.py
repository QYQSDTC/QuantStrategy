#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qstock功能测试脚本
验证qstock的基本功能和数据获取能力
"""

import sys
import warnings
warnings.filterwarnings("ignore")

def test_qstock_installation():
    """测试qstock安装"""
    print("🔍 测试qstock安装...")
    try:
        import qstock as qs
        print("✅ qstock安装成功")
        return True
    except ImportError as e:
        print(f"❌ qstock未安装: {e}")
        print("💡 请运行: pip install qstock")
        return False

def test_realtime_data():
    """测试实时数据获取"""
    print("\n📡 测试实时数据获取...")
    try:
        import qstock as qs
        
        # 获取沪深A股实时数据
        data = qs.realtime_data()
        
        if data is not None and not data.empty:
            print(f"✅ 成功获取 {len(data)} 条实时数据")
            print(f"📊 数据列名: {list(data.columns)}")
            print(f"📋 前3行数据:")
            print(data.head(3))
            return True
        else:
            print("❌ 获取到空数据")
            return False
            
    except Exception as e:
        print(f"❌ 实时数据获取失败: {e}")
        return False

def test_specific_stocks():
    """测试特定股票数据获取"""
    print("\n🎯 测试特定股票数据获取...")
    try:
        import qstock as qs
        
        # 测试获取特定股票数据
        test_codes = ['000001', '000002', '600000']
        
        for code in test_codes:
            try:
                data = qs.realtime_data(code=code)
                if data is not None and not data.empty:
                    print(f"✅ {code}: 获取成功")
                else:
                    print(f"⚠️  {code}: 获取到空数据")
            except Exception as e:
                print(f"❌ {code}: 获取失败 - {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 特定股票数据测试失败: {e}")
        return False

def test_different_markets():
    """测试不同市场数据获取"""
    print("\n🌏 测试不同市场数据获取...")
    try:
        import qstock as qs
        
        markets = ['沪深A', '沪A', '深A']
        
        for market in markets:
            try:
                data = qs.realtime_data(market=market)
                if data is not None and not data.empty:
                    print(f"✅ {market}: 获取 {len(data)} 条数据")
                else:
                    print(f"⚠️  {market}: 获取到空数据")
            except Exception as e:
                print(f"❌ {market}: 获取失败 - {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 不同市场数据测试失败: {e}")
        return False

def test_data_structure():
    """测试数据结构和列名"""
    print("\n🔍 测试数据结构...")
    try:
        import qstock as qs
        
        data = qs.realtime_data()
        
        if data is not None and not data.empty:
            print(f"📊 数据形状: {data.shape}")
            print(f"📝 列名列表:")
            for i, col in enumerate(data.columns, 1):
                print(f"   {i:2d}. {col}")
            
            print(f"\n📋 数据类型:")
            print(data.dtypes)
            
            print(f"\n📈 数值列统计:")
            numeric_cols = data.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                print(data[numeric_cols].describe())
            
            return True
        else:
            print("❌ 无法获取数据进行结构分析")
            return False
            
    except Exception as e:
        print(f"❌ 数据结构测试失败: {e}")
        return False

def test_error_handling():
    """测试错误处理"""
    print("\n⚠️  测试错误处理...")
    try:
        import qstock as qs
        
        # 测试无效股票代码
        try:
            data = qs.realtime_data(code='INVALID')
            print(f"⚠️  无效代码测试: 返回数据 {len(data) if data is not None else 'None'}")
        except Exception as e:
            print(f"✅ 无效代码正确抛出异常: {type(e).__name__}")
        
        # 测试无效市场
        try:
            data = qs.realtime_data(market='无效市场')
            print(f"⚠️  无效市场测试: 返回数据 {len(data) if data is not None else 'None'}")
        except Exception as e:
            print(f"✅ 无效市场正确抛出异常: {type(e).__name__}")
        
        return True
        
    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}")
        return False

def generate_test_report(results):
    """生成测试报告"""
    print("\n" + "="*60)
    print("📋 qstock功能测试报告")
    print("="*60)
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    print(f"✅ 通过: {passed_tests}/{total_tests}")
    print(f"❌ 失败: {total_tests - passed_tests}/{total_tests}")
    print(f"📊 通过率: {passed_tests/total_tests*100:.1f}%")
    
    print(f"\n详细结果:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    if passed_tests == total_tests:
        print(f"\n🎉 所有测试通过！qstock功能正常")
    else:
        print(f"\n⚠️  部分测试失败，请检查qstock安装和网络连接")

def main():
    """主测试函数"""
    print("🚀 qstock功能测试开始")
    print("="*60)
    
    results = {}
    
    # 运行各项测试
    results['安装测试'] = test_qstock_installation()
    
    if results['安装测试']:
        results['实时数据测试'] = test_realtime_data()
        results['特定股票测试'] = test_specific_stocks()
        results['不同市场测试'] = test_different_markets()
        results['数据结构测试'] = test_data_structure()
        results['错误处理测试'] = test_error_handling()
    else:
        print("\n❌ qstock未安装，跳过其他测试")
        return
    
    # 生成测试报告
    generate_test_report(results)

if __name__ == "__main__":
    print("💡 qstock功能测试脚本")
    print("   - 检验qstock基本功能")
    print("   - 验证数据获取能力")
    print("   - 分析数据结构")
    print("")
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 测试已停止")
    except Exception as e:
        print(f"\n❌ 测试程序异常: {e}")
        import traceback
        traceback.print_exc() 