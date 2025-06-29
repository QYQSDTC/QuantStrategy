#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票评分查询工具使用示例

本脚本展示如何使用 stock_score_query.py 工具查询特定股票在特定日期的评分
"""

import subprocess
import sys


def run_query(stock_input, date_input, use_code=False):
    """运行股票评分查询"""
    print(f"\n{'='*60}")
    if use_code:
        print(f"查询股票代码: {stock_input} 在 {date_input} 的评分")
        cmd = [
            sys.executable,
            "stock_score_query.py",
            "--code",
            stock_input,
            "--date",
            date_input,
        ]
    else:
        print(f"查询股票名称: {stock_input} 在 {date_input} 的评分")
        cmd = [
            sys.executable,
            "stock_score_query.py",
            "--stock",
            stock_input,
            "--date",
            date_input,
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

        if result.returncode == 0:
            print("查询成功！")
            print(result.stdout)
        else:
            print("查询失败！")
            print("错误信息:", result.stderr)

    except Exception as e:
        print(f"执行查询时出错: {e}")


def main():
    """主函数 - 展示多个查询示例"""

    print("📋 股票评分查询工具使用示例")
    print("=" * 60)

    # 示例1: 使用股票名称查询
    print("\n示例1: 使用股票名称查询大众交通")
    run_query("大众交通", "2024-07-09", use_code=False)

    input("\n按回车键继续下一个示例...")

    # 示例2: 使用股票代码查询
    print("\n示例2: 使用股票代码查询600611")
    run_query("600611", "2024-07-09", use_code=True)

    input("\n按回车键继续下一个示例...")

    # 示例3: 查询其他股票
    print("\n示例3: 查询贵州茅台")
    run_query("贵州茅台", "2023-06-15", use_code=False)

    input("\n按回车键继续下一个示例...")

    # 示例4: 查询平安银行
    print("\n示例4: 查询平安银行")
    run_query("000001", "2023-08-20", use_code=True)

    print("\n✅ 所有示例查询完成！")

    # 使用说明
    print("\n" + "=" * 60)
    print("💡 使用说明:")
    print("=" * 60)
    print("1. 命令行直接使用:")
    print("   python stock_score_query.py --stock '大众交通' --date '2023-07-08'")
    print("   python stock_score_query.py --code '600611' --date '2023-07-08'")
    print("")
    print("2. 参数说明:")
    print("   --stock: 股票名称（支持模糊匹配）")
    print("   --code:  股票代码（6位数字）")
    print("   --date:  查询日期（YYYY-MM-DD格式）")
    print("")
    print("3. 评分说明:")
    print("   - 总评分 > 100: 符合买入条件")
    print("   - 总评分 > 85:  接近买入条件")
    print("   - 总评分 ≤ 85:  不符合买入条件")
    print("")
    print("4. 评分组成:")
    print("   - 十字星质量: 最高35分（实体大小+影线长度）")
    print("   - 缩量程度: 最高20分（成交量相对20日均量）")
    print("   - 反转强度: 最高20分（确认日收盘vs十字星最高）")
    print("   - 技术面加分: 最高100分（均线位置+DEA+确认日涨幅+放量确认等）")


if __name__ == "__main__":
    main()
