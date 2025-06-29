#!/Users/qyq/miniconda3/envs/quant/bin/python

# import necessary packages
import numpy as np
import pandas as pd
import qstock as qs
import matplotlib.pyplot as plt
import mplfinance as mpl
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta
from tqdm import tqdm

# 设置中文字体
plt.rcParams["font.sans-serif"] = [
    "Noto Sans CJK SC",
    "SimHei",
    "Arial Unicode MS",
    "Microsoft YaHei",
]
plt.rcParams["axes.unicode_minus"] = False  # 用来正常显示负号


# 获取A股股票池（排除创业板、科创板、北交所、ST和退市股票）
def get_stock_pool():
    all_stock = qs.realtime_data()
    # 剔除创业板（300开头）、科创板（688开头）、北交所（8开头）、ST和退市股票
    all_stock = all_stock[
        ~(
            all_stock["代码"].str.startswith(("300", "688", "301", "8"))
            | all_stock["名称"].str.contains("ST")
            | all_stock["名称"].str.contains("退市")
            | all_stock["名称"].str.contains("退")
        )
    ]
    return all_stock[["代码", "名称"]].values.tolist()


# 计算单个股票的7日预测收益率
def calculate_7day_return(stock_code, stock_name, N=29):
    try:
        # 获取最近2N天的数据
        start_date = (datetime.now() - timedelta(days=2 * N)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        recent_data = qs.get_data(stock_code, start=start_date, end=end_date)

        if len(recent_data) < N:
            print(f"{stock_name} 数据少于 {N} 天，跳过")
            return None

        # 只使用最近N天的数据
        recent_data = recent_data.tail(N)

        # 准备数据
        recent_data["log_price"] = np.log(recent_data["close"])
        X = np.arange(1, N + 1).reshape(-1, 1)
        y = recent_data["log_price"].values

        # 拟合对数线性回归模型
        model = LinearRegression()
        model.fit(X, y)

        # 预测7天后的收益率
        last_price = recent_data["close"].iloc[-1]
        future_log_price = model.predict([[N + 7]])[0]
        future_price = np.exp(future_log_price)
        returns = (future_price - last_price) / last_price * 100

        return returns
    except Exception as e:
        print(f"计算 {stock_code} ({stock_name}) 的收益率时出错: {str(e)}")
        return None


# 主函数
def main():
    stock_pool = get_stock_pool()
    results = []

    # 使用tqdm创建进度条
    for stock_code, stock_name in tqdm(stock_pool, desc="Processing stocks"):
        # print(f"Processing: {stock_code} ({stock_name})")
        returns = calculate_7day_return(
            stock_code, stock_name, N=29
        )  # 使用 29 天数据进行估计
        if returns is not None:
            # print(f'{stock_name} 7 days return is {returns}')
            results.append((stock_code, stock_name, returns))

    # 按收益率排序
    results.sort(key=lambda x: x[2], reverse=True)

    # 打印结果
    print("\n股票代码\t股票名称\t预测7日收益率")
    for stock_code, stock_name, returns in results[:20]:  # 打印前20个结果
        print(f"{stock_code}\t{stock_name}\t{returns:.2f}%")


# 运行主函数
if __name__ == "__main__":
    main()
