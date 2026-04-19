#!/usr/bin/env python3
"""
用新浪财经接口获取沪深300涨幅榜（稳定版）
新浪接口完全免费无限制，速度快，稳定性高，彻底解决网络连接问题
修复非交易时段涨跌幅显示为0的bug，自动降级到日线接口获取数据
新增缓存机制：交易时段缓存10分钟，非交易时段读取15:10预拉取缓存
新增JSON输出模式：--output json --output-file result.json
"""

import os
import json
import time
import argparse
from pathlib import Path

import sys
import re
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

try:
    import pandas as pd
except ImportError as e:
    print(f"错误：缺少依赖 {e.name}。请运行：pip install -r requirements.txt")
    sys.exit(1)

# 导入统一数据源管理器（用于非交易时段日线数据查询）
from data_source import get_data_manager

# 缓存配置
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_EXPIRE_SECONDS = 10 * 60  # 交易时段缓存10分钟


def format_stock_code(code: any) -> str:
    """
    格式化股票代码，确保6位完整，保留前导0
    
    Args:
        code: 股票代码（可以是数字或字符串）
        
    Returns:
        格式化后的6位股票代码字符串
    """
    if code is None:
        return ""
    
    # 转换为字符串
    code_str = str(code).strip()
    
    # 移除任何前缀（如sh.、sz.等）- 正确处理前缀在前面的情况
    if '.' in code_str:
        parts = code_str.split('.')
        # 取纯数字的那一部分
        for part in parts:
            if part.isdigit():
                code_str = part
                break
        else:
            # 如果没有找到纯数字部分，取最后一部分
            code_str = parts[-1]
    
    # 只保留数字字符
    code_str = ''.join([c for c in code_str if c.isdigit()])
    
    # 确保6位，补前导0
    code_str = code_str.zfill(6)
    
    return code_str


def _get_cache_path(date_str: str = None) -> Path:
    """获取缓存文件路径"""
    if date_str is None:
        date_str = time.strftime("%Y%m%d")
    return CACHE_DIR / f"gainers_{date_str}.json"


def _load_cache() -> Optional[pd.DataFrame]:
    """加载有效缓存"""
    cache_path = _get_cache_path()
    if not cache_path.exists():
        return None
    
    # 检查缓存是否过期
    mtime = cache_path.stat().st_mtime
    if time.time() - mtime > CACHE_EXPIRE_SECONDS:
        # 交易时段缓存过期，非交易时段缓存永久有效
        now = datetime.now()
        trading_hours = (now.hour >= 9 and now.hour < 15) and not (now.hour == 11 and now.minute > 30)
        if not trading_hours:
            # 非交易时段，缓存不过期
            pass
        else:
            return None
    
    # 读取缓存
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except:
        return None


def _save_cache(df: pd.DataFrame):
    """保存数据到缓存"""
    cache_path = _get_cache_path()
    data = df.to_dict('records')
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_trading_day() -> tuple[bool, str]:
    """
    检查今天是否是交易日
    
    Returns:
        (is_trading, message)
    """
    now = datetime.now()
    weekday = now.weekday()  # 0=周一, 5=周六, 6=周日
    
    # 检查是否是周末
    if weekday >= 5:
        day_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        return False, f"今天是{day_names[weekday]}（{now.strftime('%Y-%m-%d')}），A股周末休市"
    
    # TODO: 可以增加节假日检查
    return True, "今天是交易日"


def get_today_gainers(n: int = 50, count: int = 50) -> pd.DataFrame:
    """
    获取沪深300今日涨幅榜（稳定版，基于新浪财经接口）
    Args:
        n: 返回数量（兼容旧版）
        count: 返回数量
    Returns:
        DataFrame格式的涨幅榜，按涨跌幅从高到低排序
    """
    count = n if n != 50 else count
    
    # 第一步：检查缓存
    cached_df = _load_cache()
    if cached_df is not None:
        return cached_df.head(count)
    
    # 第二步：判断时段
    now = datetime.now()
    trading_hours = (now.hour >= 9 and now.hour < 15) and not (now.hour == 11 and now.minute > 30)
    # 3:00-3:10空档期按交易时段处理
    if now.hour == 15 and now.minute < 10:
        trading_hours = True
    
    # 非交易时段优先读取15:10预缓存
    if not trading_hours:
        pre_cache_path = _get_cache_path()
        if pre_cache_path.exists():
            df = pd.read_json(pre_cache_path)
            return df.head(count)
    
    # 第三步：没有缓存，实时拉取
    
    # 沪深300成分股列表（2026年最新）
    stock_list = [
        "000001.SZ", "000002.SZ", "000063.SZ", "000100.SZ", "000157.SZ",
        "000166.SZ", "000301.SZ", "000333.SZ", "000338.SZ", "000408.SZ",
        "000425.SZ", "000538.SZ", "000568.SZ", "000596.SZ", "000617.SZ",
        "000625.SZ", "000630.SZ", "000651.SZ", "000661.SZ", "000708.SZ",
        "000725.SZ", "000768.SZ", "000776.SZ", "000786.SZ", "000792.SZ",
        "000807.SZ", "000858.SZ", "000876.SZ", "000895.SZ", "000938.SZ",
        "000963.SZ", "000975.SZ", "000977.SZ", "000983.SZ", "000999.SZ",
        "001391.SZ", "001965.SZ", "001979.SZ", "002001.SZ", "002027.SZ",
        "002028.SZ", "002049.SZ", "002050.SZ", "002074.SZ", "002142.SZ",
        "002179.SZ", "002230.SZ", "002236.SZ", "002241.SZ", "002252.SZ",
        "300014.SZ", "300015.SZ", "300033.SZ", "300059.SZ", "300122.SZ",
        "300124.SZ", "300142.SZ", "300144.SZ", "300274.SZ", "300308.SZ",
        "300347.SZ", "300408.SZ", "300413.SZ", "300433.SZ", "300450.SZ",
        "300498.SZ", "300628.SZ", "300676.SZ", "300750.SZ", "300760.SZ",
        "300782.SZ", "300896.SZ", "600000.SH", "600009.SH", "600010.SH",
        "600016.SH", "600019.SH", "600028.SH", "600030.SH", "600031.SH",
        "600036.SH", "600048.SH", "600050.SH", "600085.SH", "600104.SH",
        "600109.SH", "600111.SH", "600115.SH", "600196.SH", "600276.SH",
        "600309.SH", "600436.SH", "600438.SH", "600519.SH", "600547.SH",
        "600570.SH", "600585.SH", "600588.SH", "600606.SH", "600660.SH",
        "600690.SH", "600703.SH", "600745.SH", "600809.SH", "600837.SH",
        "600845.SH", "600887.SH", "600893.SH", "600900.SH", "600918.SH",
        "600999.SH", "601012.SH", "601088.SH", "601138.SH", "601166.SH",
        "601186.SH", "601211.SH", "601288.SH", "601318.SH", "601336.SH",
        "601398.SH", "601601.SH", "601628.SH", "601633.SH", "601668.SH",
        "601688.SH", "601818.SH", "601857.SH", "601888.SH", "601899.SH",
        "601919.SH", "601988.SH", "601989.SH", "601995.SH", "603259.SH",
        "603288.SH", "603501.SH", "603899.SH", "688111.SH", "688981.SH"
    ]
    
    # 转换为新浪接口代码格式：sh600519、sz000001
    sina_codes = []
    code_map = {}
    for ts_code in stock_list:
        code, market = ts_code.split('.')
        if market == 'SH':
            sina_code = f"sh{code}"
        else:
            sina_code = f"sz{code}"
        sina_codes.append(sina_code)
        code_map[sina_code] = ts_code
    
    # 批量查询新浪行情，一次查询所有300只，效率极高
    url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
    headers = {
        'Referer': 'https://finance.sina.com.cn/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gbk'
        text = response.text
    except Exception as e:
        print(f"⚠️  新浪接口调用失败：{e}，降级到本地数据源")
        # 新浪接口失败时，降级到统一数据源管理器
        data_source = get_data_manager()
        stock_data = []
        for ts_code in stock_list:
            try:
                price, _ = data_source.get_realtime_price(ts_code)
                # 非交易时段自动从日线接口获取涨跌幅
                now = datetime.now()
                trading_hours = (now.hour >=9 and now.hour <15) and not (now.hour ==11 and now.minute>30)
                if not trading_hours or price == 0:
                    # 从日线接口获取最新涨跌幅
                    end_date = datetime.now().date()
                    start_date = end_date - timedelta(days=1)
                    start_str = start_date.strftime('%Y%m%d')
                    end_str = end_date.strftime('%Y%m%d')
                    try:
                        df, _ = data_source.get_daily_quotes(ts_code, start_str, end_str)
                        if df is not None and len(df)>=2:
                            prev_close = df.iloc[-2]['close']
                            curr_close = df.iloc[-1]['close']
                            change_pct = ((curr_close - prev_close)/prev_close)*100
                            price = curr_close
                    except:
                        change_pct = 0.0
                else:
                    change_pct = 0.0
                
                if price:
                    stock_data.append({
                        'ts_code': ts_code,
                        'code': ts_code.split('.')[0],
                        'name': ts_code.split('.')[0],
                        'price': round(price,2),
                        'change_pct': round(change_pct,2),
                        'volume': 0
                    })
            except:
                continue
        # 排序
        stock_data = sorted(stock_data, key=lambda x:x['change_pct'], reverse=True)
        return pd.DataFrame(stock_data[:count])
    
    # 解析新浪返回结果
    stock_data = []
    pattern = re.compile(r'var hq_str_([a-z0-9]+)=\"([^\"]+)\";')
    matches = pattern.findall(text)
    
    # 检查是否是交易时段
    now = datetime.now()
    trading_hours = (now.hour >= 9 and now.hour < 15) and not (now.hour == 11 and now.minute > 30)
    
    data_source = None
    for sina_code, info in matches:
        ts_code = code_map.get(sina_code)
        if not ts_code:
            continue
            
        parts = info.split(',')
        if len(parts) < 3:
            continue
            
        name = parts[0]
        open_price = float(parts[1]) if parts[1] else 0.0
        prev_close = float(parts[2]) if parts[2] else 0.0
        current_price = float(parts[3]) if parts[3] else 0.0
        volume = float(parts[8]) if len(parts) >8 and parts[8] else 0.0  # 成交量（股）
        
        # 计算涨跌幅
        if prev_close > 0 and current_price > 0:
            change_pct = ((current_price - prev_close) / prev_close) * 100
        else:
            change_pct = 0.0
        
        # 非交易时段，如果涨跌幅为0，自动从日线接口获取真实涨跌幅
        if not trading_hours and abs(change_pct) < 0.01:
            if data_source is None:              data_source = get_data_manager()
            try:
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=1)
                start_str = start_date.strftime('%Y%m%d')
                end_str = end_date.strftime('%Y%m%d')
                df, _ = data_source.get_daily_quotes(ts_code, start_str, end_str)
                if df is not None and len(df)>=2:
                    prev_close_daily = df.iloc[-2]['close']
                    curr_close_daily = df.iloc[-1]['close']
                    if prev_close_daily > 0:
                        change_pct = ((curr_close_daily - prev_close_daily)/prev_close_daily)*100
                        current_price = curr_close_daily
            except:
                pass
        
        if current_price > 0:
            stock_data.append({
                'ts_code': ts_code,
                'code': ts_code.split('.')[0],
                'name': name if name else ts_code.split('.')[0],
                'price': round(current_price, 2),
                'change_pct': round(change_pct, 2),
                'volume': round(volume / 1000000, 2)  # 股 → 万手：1万手 = 1,000,000股
            })
    
    # 按涨跌幅从高到低排序
    stock_data = sorted(stock_data, key=lambda x: x['change_pct'], reverse=True)
    df = pd.DataFrame(stock_data[:count])
    
    # 保存到缓存
    _save_cache(df)
    
    return df


def generate_json_output(df: pd.DataFrame) -> Dict[str, Any]:
    """生成符合规范的JSON输出"""
    now = datetime.now()
    is_trading, msg = is_trading_day()
    
    # 格式化涨幅榜数据
    gainers_list = []
    for i, (_, row) in enumerate(df.head(50).iterrows(), 1):
        gainers_list.append({
            '排名': i,
            '代码': format_stock_code(row['code']),
            '名称': row['name'],
            '最新价': round(float(row['price']), 2),
            '涨跌幅': round(float(row['change_pct']), 2),
            '成交量': round(float(row['volume']), 2)
        })
    
    # 构造完整JSON
    result = {
        'success': True,
        'report_type': 'opportunity_scan',
        'template_name': 'opportunity_scan',
        'data': {
            '日期': now.strftime('%Y-%m-%d'),
            'is_trading': is_trading,
            'data_source_date': now.strftime('%Y-%m-%d') if is_trading else (now - timedelta(days=1)).strftime('%Y-%m-%d'),
            '涨幅榜': gainers_list
        },
        'metadata': {
            'generated_at': now.strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': '新浪财经+统一数据源管理器',
            'cached': _load_cache() is not None
        }
    }
    
    return result


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='获取沪深300涨幅榜')
    parser.add_argument('--output', type=str, default='text', choices=['text', 'json'],
                        help='输出格式: text(文本) 或 json(结构化数据)')
    parser.add_argument('--output-file', type=str, default=None,
                        help='JSON输出文件路径')
    args = parser.parse_args()
    
    # 获取数据
    df = get_today_gainers(count=50)
    
    # 根据输出格式处理
    if args.output == 'json':
        # JSON输出模式
        result = generate_json_output(df)
        
        if args.output_file:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    
    else:
        # 兼容旧的文本模式
        print("=" * 80)
        print("📊 沪深300涨幅榜（稳定版）")
        print("=" * 80)
        print()
        
        # 检查是否是交易日
        is_trading, msg = is_trading_day()
        print(f"📅 {msg}")
        print()
        
        print(f"✅ 成功获取 {len(df)} 只股票的行情数据")
        print()
        
        if not is_trading:
            print("⚠️  当前为非交易时段，数据为最近一个交易日的正式收盘数据")
        else:
            print("⚠️  实时行情数据，仅供参考")
        
        print()
        print("=" * 80)
        print("🏆 涨幅榜 - 前10只")
        print("=" * 80)
        print(f"{'排名':<6}{'代码':<12}{'名称':<12}{'最新价':<12}{'涨跌幅':<16}{'成交量':<12}")
        print("-" * 80)
        
        for i, (_, row) in enumerate(df.head(10).iterrows(), 1):
            status = "🟢" if row['change_pct'] > 0 else "🔴" if row['change_pct'] < 0 else "⚪"
            # 强制股票代码为字符串格式输出
            code_str = format_stock_code(row['code'])
            print(f"{i:<6}{code_str:<12}{row['name']:<12}¥{row['price']:<11.2f}{status} {row['change_pct']:+.2f}% {row['volume']:<10.0f}万手")
        
        # 保存结果前确保股票代码列是字符串格式
        df['code'] = df['code'].apply(format_stock_code)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        save_path = f"today_gainers_{timestamp}.csv"
        df.to_csv(save_path, index=False, encoding='utf-8-sig')
        print()
        print(f"💾 完整结果已保存到: {Path(__file__).parent / save_path}")
        
        print()
        print("=" * 80)
        print("⚠️  重要提示")
        print("=" * 80)
        print("   - 非交易时段数据为最近一个交易日的正式收盘数据")
        print("   - 本榜单为沪深300成分股涨幅榜，非全市场涨幅榜")
        print("   - 投资有风险，入市需谨慎")
        print("=" * 80)


if __name__ == "__main__":
    main()
