# akshare 到 qstock 数据接口迁移指南

## 📋 概述

本指南帮助您将现有的akshare数据接口迁移到qstock，同时提供最佳实践和解决方案。

## 🔄 接口映射对照表

### 1. 股票列表获取

**akshare:**
```python
import akshare as ak
all_stocks = ak.stock_zh_a_spot_em()
```

**qstock:**
```python
import qstock as qs
all_stocks = qs.realtime_data()  # 获取沪深A股实时数据
# 或者指定市场
all_stocks = qs.realtime_data(market='沪深A')
```

### 2. 个股历史数据

**akshare:**
```python
data = ak.stock_zh_a_hist(
    symbol="000001",
    period="daily", 
    start_date="20230101",
    end_date="20231231",
    adjust="qfq"
)
```

**qstock:**
```python
# qstock提供完整的历史数据接口
data = qs.get_data(
    code_list="000001",
    start="20230101",
    end="20231231", 
    freq='d',  # 日线频率
    fqt=1      # 前复权
)
# 或者获取多只股票的价格数据
price_data = qs.get_price(
    code_list=["000001", "000002"],
    start="20230101",
    end="20231231"
)
```

### 3. 指数数据

**akshare:**
```python
hs300_data = ak.index_zh_a_hist(
    symbol="000300",
    period="daily",
    start_date="20230101", 
    end_date="20231231"
)
```

**qstock:**
```python
# qstock提供完整的指数数据接口
hs300_data = qs.get_data(
    code_list="hs300",  # 沪深300简称
    start="20230101",
    end="20231231",
    freq='d'
)
# 也可以使用中文名称
index_data = qs.get_data(
    code_list="沪深300",
    start="20230101",
    end="20231231"
)
```

## 📊 列名标准化对照

### akshare 列名 → qstock 列名

| akshare | qstock | 说明 |
|---------|--------|------|
| 代码 | 代码 | 股票代码 |
| 名称 | 名称 | 股票名称 |
| 最新价 | 最新价 | 当前价格 |
| 涨跌幅 | 涨跌幅 | 涨跌百分比 |
| 成交量 | 成交量 | 交易量 |
| 成交额 | 成交额 | 交易金额 |
| 日期 | date | 历史数据中的日期 |
| 开盘 | open | 开盘价 |
| 最高 | high | 最高价 |
| 最低 | low | 最低价 |
| 收盘 | close | 收盘价 |
| 成交量 | vol | qstock使用vol列名 |

## 🔧 迁移策略

### 策略1: 混合数据源方案 (推荐)

```python
import qstock as qs
import akshare as ak

class HybridDataProvider:
    def get_realtime_data(self):
        """使用qstock获取实时数据"""
        return qs.realtime_data()
    
    def get_historical_data(self, symbol, start_date, end_date):
        """使用akshare获取历史数据"""
        return ak.stock_zh_a_hist(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
```

### 策略2: 渐进式迁移

1. **第一阶段**: 保留akshare，添加qstock实时功能
2. **第二阶段**: 使用qstock替换部分akshare功能
3. **第三阶段**: 完全迁移到qstock (当功能完善后)

### 策略3: 功能分离

- **qstock**: 实时数据、市场情绪分析、盘中监控
- **akshare**: 历史回测、技术指标计算、基本面分析

## 🚀 最佳实践

### 1. 数据缓存机制

```python
import os
import pandas as pd

class DataCache:
    def __init__(self, cache_dir="data_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def get_cached_data(self, key):
        cache_file = f"{self.cache_dir}/{key}.csv"
        if os.path.exists(cache_file):
            return pd.read_csv(cache_file)
        return None
    
    def save_to_cache(self, key, data):
        cache_file = f"{self.cache_dir}/{key}.csv"
        data.to_csv(cache_file, index=False)
```

### 2. 错误处理和重试

```python
import time

def robust_data_fetch(fetch_func, max_retries=3, delay=1):
    for attempt in range(max_retries):
        try:
            return fetch_func()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))
                continue
            else:
                raise e
```

### 3. 列名标准化

```python
def standardize_columns(df, source='qstock'):
    """标准化不同数据源的列名"""
    if source == 'qstock':
        column_mapping = {
            '代码': 'code',
            '名称': 'name',
            '最新价': 'price',
            '涨跌幅': 'pct_change',
            '成交量': 'volume'
        }
    elif source == 'akshare':
        column_mapping = {
            '代码': 'code',
            '名称': 'name', 
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume'
        }
    
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns:
            df = df.rename(columns={old_col: new_col})
    
    return df
```

## ⚠️ 注意事项

### 1. qstock历史数据功能
- ✅ 提供完整的历史K线数据接口 (get_data)
- ✅ 支持多只股票价格数据获取 (get_price)
- ✅ 支持多种频率: 日线、周线、月线、分钟线
- ✅ 支持前复权、后复权、不复权
- ✅ 支持指数数据获取

### 2. 兼容性考虑
- qstock可能与不同版本的pandas有兼容性问题
- 建议在虚拟环境中测试

### 3. 数据更新频率
- qstock实时数据更新频率较高
- 注意API调用限制，避免过于频繁的请求

## 📝 迁移检查清单

- [ ] 安装qstock: `pip install qstock`
- [ ] 测试基本数据获取功能
- [ ] 实现列名标准化
- [ ] 添加错误处理机制
- [ ] 实施数据缓存策略
- [ ] 更新现有代码中的数据获取逻辑
- [ ] 全面测试迁移后的功能
- [ ] 性能对比和优化

## 🔍 示例代码

### 完整的迁移示例

```python
import qstock as qs
import akshare as ak
import pandas as pd
from datetime import datetime

class StockDataProvider:
    def __init__(self):
        self.qstock_available = True
        self.akshare_available = True
        
        try:
            qs.realtime_data(market='沪深A')[:1]  # 测试连接
        except:
            self.qstock_available = False
            
        try:
            ak.stock_zh_a_spot_em()[:1]  # 测试连接
        except:
            self.akshare_available = False
    
    def get_stock_list(self, source='auto'):
        """获取股票列表"""
        if source == 'auto':
            source = 'qstock' if self.qstock_available else 'akshare'
            
        if source == 'qstock' and self.qstock_available:
            data = qs.realtime_data()
            return self.standardize_realtime_data(data)
        elif source == 'akshare' and self.akshare_available:
            data = ak.stock_zh_a_spot_em()
            return self.standardize_spot_data(data)
        else:
            raise Exception(f"数据源 {source} 不可用")
    
    def get_historical_data(self, symbol, start_date, end_date):
        """获取历史数据 - 优先使用akshare"""
        if self.akshare_available:
            return ak.stock_zh_a_hist(
                symbol=symbol,
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust='qfq'
            )
        else:
            raise Exception("akshare不可用，无法获取历史数据")
    
    def get_realtime_quote(self, symbols):
        """获取实时行情 - 优先使用qstock"""
        if self.qstock_available:
            return qs.realtime_data(code=symbols)
        elif self.akshare_available:
            # 使用akshare的实时数据作为备选
            return ak.stock_zh_a_spot_em()
        else:
            raise Exception("无可用的实时数据源")
    
    def standardize_realtime_data(self, df):
        """标准化qstock实时数据"""
        return df.rename(columns={
            '代码': 'code',
            '名称': 'name',
            '最新价': 'price',
            '涨跌幅': 'pct_change'
        })
    
    def standardize_spot_data(self, df):
        """标准化akshare现货数据"""
        return df.rename(columns={
            '代码': 'code', 
            '名称': 'name',
            '最新价': 'price',
            '涨跌幅': 'pct_change'
        })

# 使用示例
provider = StockDataProvider()

# 获取股票列表
stock_list = provider.get_stock_list()
print(f"获取到 {len(stock_list)} 只股票")

# 获取实时行情
realtime_data = provider.get_realtime_quote(['000001', '000002'])
print("实时行情数据:", realtime_data.head())

# 获取历史数据
hist_data = provider.get_historical_data('000001', '2023-01-01', '2023-12-31')
print("历史数据:", hist_data.head())
```

## 📚 相关资源

- [qstock GitHub仓库](https://github.com/tkfy920/qstock)
- [qstock PyPI页面](https://pypi.org/project/qstock/)
- [akshare官方文档](https://akshare.akfamily.xyz/)

## 🎯 结论

qstock作为新兴的量化数据库，在实时数据获取方面具有优势，但历史数据功能仍在完善中。建议采用混合数据源策略，发挥各数据源的优势，逐步完成迁移。 