#!//Users/qyq/miniconda3/envs/quant/bin/python


import pandas as pd
import akshare as ak
from datetime import datetime

today = datetime.now().strftime("%Y-%m-%d")


def get_market_overview():
    """获取大盘概况数据"""
    try:
        # 获取沪深京三个市场主要指数数据
        index_df = ak.stock_zh_index_spot_em(symbol="沪深重要指数")

        # 获取各指数行情数据
        sh_index = index_df[index_df["代码"] == "000001"].iloc[0]  # 上证指数
        sz_index = index_df[index_df["代码"] == "399001"].iloc[0]  # 深证成指
        kc_index = index_df[index_df["代码"] == "000688"].iloc[0]  # 科创板
        cy_index = index_df[index_df["代码"] == "399006"].iloc[0]  # 创业板
        bz_index = index_df[index_df["代码"] == "899050"].iloc[0]  # 北证50

        # 获取沪深两市的资金流数据（保留历史数据最后一条为最新）
        fund_flow = ak.stock_market_fund_flow().iloc[-1]

        # 计算沪深京三市总成交额（单位：万亿元）
        total_volume = (
            index_df[index_df["代码"].isin(["000001", "399001", "899050"])][
                "成交额"
            ].sum()
        ) / 1e12

        return (
            "## 📊 大盘实时行情\n"
            f"- 上证指数：{sh_index['最新价']} ({sh_index['涨跌幅']}%)\n"
            f"- 深证成指：{sz_index['最新价']} ({sz_index['涨跌幅']}%)\n"
            f"- 科创板：{kc_index['最新价']} ({kc_index['涨跌幅']}%)\n"
            f"- 创业板：{cy_index['最新价']} ({cy_index['涨跌幅']}%)\n"
            f"- 北证50：{bz_index['最新价']} ({bz_index['涨跌幅']}%)\n\n"
            "## 💰 资金流向\n"
            f"- 沪深主力净流入：{fund_flow['主力净流入-净额']/1e8:.2f}亿\n"
            f"- 沪深京总成交额：{total_volume:.2f}万亿\n"
        )
    except Exception as e:
        print(f"大盘数据获取失败: {str(e)}")
        return ""


def format_currency(value):
    """格式化金额显示（单位：亿元）"""
    return f"{float(value)/1e8:.2f}亿" if pd.notna(value) else "无数据"


def format_stock_info(row, is_zt=True):
    """格式化个股详细信息"""
    # 公共基础信息
    info = (
        f"**{row['名称']}（{row['代码']}）**\n"
        f"- 📈 当日涨幅：{row['涨跌幅']:.2f}%\n"
        f"- 💰 最新价：{row['最新价']}元\n"
        f"- 🏦 流通市值：{format_currency(row['流通市值'])}\n"
        f"- 🔄 换手率：{row['换手率']:.2f}%\n"
    )

    # 特殊字段处理
    if is_zt:
        info += (
            f"- 🛡️ 封板金额：{format_currency(row.get('封板资金', 0))}\n"
            f"- ⏰ 首次封板：{datetime.strptime(row['首次封板时间'], '%H%M%S').strftime('%H:%M:%S')}\n"
            f"- 🎯 连板数：{row.get('连板数', 0)}连板\n"
            f"- 📊 涨停统计：{row.get('涨停统计', '无统计')}\n"
        )
    else:
        info += (
            f"- 🧾 封单资金：{format_currency(row.get('封单资金', 0))}\n"
            f"- 💸 板上成交：{format_currency(row.get('板上成交额', 0))}\n"
        )

    # 行业信息
    info += f"- 🏭 行业板块：{row['所属行业']}\n"

    # 龙虎榜信息
    if pd.notna(row.get("龙虎榜净买额")):
        info += (
            "\n**🐉 龙虎榜数据**\n"
            f"- 🏛️ 净买额：{format_currency(row['龙虎榜净买额'])}\n"
            f"- 🏦 机构净买：{format_currency(row['机构买入净额'])}\n"
        )

    return info + "\n"


def generate_full_report(market_str, zt_df, dt_df):
    """生成完整分析报告"""
    report = f"# 🚀 {today} 市场全景分析报告\n\n"

    # 大盘概况
    report += "## 🌐 大盘全景\n"
    report += market_str + "\n"  # 直接插入格式化好的字符串

    # 新增热门股分析
    report += "## 🔥 热门股分析\n"
    total_hot = len(zt_df) + len(dt_df)
    sentiment = len(zt_df) / total_hot if total_hot > 0 else 0  # 情绪指数计算

    # 新增热门行业统计
    combined_df = pd.concat([zt_df, dt_df])
    if not combined_df.empty and "所属行业" in combined_df:
        industry_counts = combined_df["所属行业"].value_counts().head(3)
        report += "## 🏭 热门行业板块\n"
        report += "- 今日最活跃行业 TOP3：\n"
        for industry, count in industry_counts.items():
            report += f"  - 📌 {industry}（出现 {count} 次）\n"
    else:
        report += "## 🏭 热门行业板块\n- 今日无显著活跃行业数据\n"

    report += f"- 📈 涨停股数目：{len(zt_df)}家\n"
    report += f"- 📉 跌停股数目：{len(dt_df)}家\n"
    report += f"- 📊 市场情绪指数：{sentiment:.2%}（涨停/(涨停+跌停）\n\n"

    # 涨停股分析
    if not zt_df.empty:
        report += "## 📈 涨停股深度分析\n"
        for _, row in zt_df.iterrows():
            report += format_stock_info(row)

    # 跌停股分析
    if not dt_df.empty:
        report += "## 📉 跌停股监控预警\n"
        for _, row in dt_df.iterrows():
            report += format_stock_info(row, is_zt=False)

    return report


def get_enhanced_data():
    """获取增强数据集"""
    try:
        # 获取基础数据
        lhb_df = ak.stock_lhb_stock_statistic_em()
        date_str = datetime.now().strftime("%Y%m%d")

        # 获取并处理涨停数据
        zt_df = ak.stock_zt_pool_em(date=date_str)
        zt_df = pd.merge(
            zt_df,
            lhb_df[["代码", "龙虎榜净买额", "机构买入净额"]],
            on="代码",
            how="left",
        )
        zt_df["代码"] = zt_df["代码"].astype(str).str.zfill(6)

        # 获取并处理跌停数据
        dt_df = ak.stock_zt_pool_dtgc_em(date=date_str)
        dt_df = pd.merge(
            dt_df,
            lhb_df[["代码", "龙虎榜净买额", "机构买入净额"]],
            on="代码",
            how="left",
        )
        dt_df["代码"] = dt_df["代码"].astype(str).str.zfill(6)

        return zt_df, dt_df
    except Exception as e:
        print(f"数据获取失败: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()


if __name__ == "__main__":
    # 获取所有数据
    market_data = get_market_overview()
    zt_data, dt_data = get_enhanced_data()

    # 生成并保存报告
    if not market_data or not zt_data.empty or not dt_data.empty:
        report = generate_full_report(market_data, zt_data, dt_data)
        filename = f"{today}-市场全景分析报告.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"✅ 报告已生成：{filename}")
    else:
        print("❌ 数据获取失败，无法生成报告")
