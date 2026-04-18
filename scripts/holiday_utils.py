#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国节假日与交易日判断工具
功能：判断当前日期是否是中国A股交易日，节假日/周末不推送报告
优先级：手动指定2026年节假日 > 周末判断 > 远程交易日历
"""
import datetime
from pathlib import Path
import json
import time

# 缓存文件路径
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_FILE = CACHE_DIR / "trade_calendar.json"
CACHE_EXPIRE_DAYS = 30  # 交易日历缓存30天更新一次

# 2026年法定节假日（手动维护，优先级最高，避免接口问题）
HOLIDAYS_2026 = [
    "2026-01-01", "2026-01-02", "2026-01-03",  # 元旦
    "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-21", "2026-02-22",  # 春节
    "2026-04-04", "2026-04-05", "2026-04-06",  # 清明节
    "2026-05-01", "2026-05-02", "2026-05-03",  # 劳动节
    "2026-06-07", "2026-06-08", "2026-06-09",  # 端午节
    "2026-09-21", "2026-09-22", "2026-09-23",  # 中秋节
    "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07"  # 国庆节
]

def is_trade_day(date_str: str = None) -> bool:
    """
    判断是否是A股交易日
    Args:
        date_str: 日期字符串，格式YYYY-MM-DD，默认今天
    Returns:
        True=交易日，False=节假日/周末
    """
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 优先级1：手动判断2026年节假日
    if date_str in HOLIDAYS_2026:
        return False
    
    # 优先级2：判断周末
    date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    weekday = date.weekday()  # 0=周一，4=周五，5=周六，6=周日
    if weekday >= 5:
        return False
    
    # 优先级3：尝试读取缓存的交易日历
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                trade_dates = cache_data.get("trade_dates", [])
                if trade_dates and date_str in trade_dates:
                    return True
    except:
        pass
    
    # 默认：非节假日、非周末即为交易日
    return True

def is_holiday(date_str: str = None) -> bool:
    """判断是否是节假日/周末（非交易日）"""
    return not is_trade_day(date_str)

def get_trade_calendar() -> list:
    """获取交易日历（兼容旧接口）"""
    return []

if __name__ == "__main__":
    # 测试
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if is_trade_day():
        print(f"✅ {today} 是交易日")
    else:
        print(f"❌ {today} 是节假日/周末，休市")

