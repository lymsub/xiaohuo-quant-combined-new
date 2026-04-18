#!/usr/bin/env python3
"""
高客秘书 - 数据同步脚本
定时从 Tushare 获取行情和基本面数据并存储到 SQLite 数据库
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    import pandas as pd
    import numpy as np
except ImportError:
    print("错误：缺少必要的依赖。请运行：pip install pandas numpy")
    sys.exit(1)

try:
    import tushare as ts
except ImportError:
    print("错误：缺少 tushare。请运行：pip install tushare")
    sys.exit(1)

from database import QuantDatabase


def get_hs300_stock_list() -> list:
    """
    获取沪深300成分股列表
    与 get_today_gainers.py 保持一致
    """
    return [
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


class DataSyncer:
    """数据同步器"""
    
    def __init__(self, tushare_token: str):
        self.token = tushare_token
        ts.set_token(tushare_token)
        self.pro = ts.pro_api()
        self.db = QuantDatabase()
    
    def sync_stock_list(self) -> int:
        """同步股票列表"""
        print("📋 正在同步股票列表...")
        try:
            df = self.pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,market,list_date,is_hs')
            if df is not None and not df.empty:
                count = self.db.save_stock_basic(df)
                print(f"✅ 同步了 {count} 只股票信息")
                return count
            return 0
        except Exception as e:
            print(f"❌ 同步股票列表失败: {e}")
            return 0
    
    def sync_daily_quotes(self, ts_code: str, days: int = 365) -> int:
        """
        同步单只股票的日线数据
        
        Args:
            ts_code: 股票代码
            days: 同步天数
            
        Returns:
            保存的记录数
        """
        try:
            # 获取上次同步日期
            last_sync = self.db.get_sync_status('daily', ts_code)
            
            end_date = datetime.now()
            if last_sync:
                # 从上次同步日期的下一天开始
                start_date = datetime.strptime(last_sync, '%Y-%m-%d') + timedelta(days=1)
                # 最多同步指定天数
                if (end_date - start_date).days > days:
                    start_date = end_date - timedelta(days=days)
            else:
                # 首次同步，获取指定天数的数据
                start_date = end_date - timedelta(days=days)
            
            # 格式化日期
            start_str = start_date.strftime('%Y%m%d')
            end_str = end_date.strftime('%Y%m%d')
            
            # 如果开始日期大于结束日期，说明已经是最新的了
            if start_date > end_date:
                print(f"⏭️  {ts_code} 已经是最新数据")
                return 0
            
            # 获取数据
            df = self.pro.daily(ts_code=ts_code, start_date=start_str, end_date=end_str)
            
            if df is not None and not df.empty:
                df = df.sort_values('trade_date')
                df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
                count = self.db.save_daily_quotes(ts_code, df)
                print(f"✅ {ts_code}: 同步了 {count} 条日线数据 ({start_str} 至 {end_str})")
                return count
            else:
                print(f"ℹ️  {ts_code}: 没有新数据 ({start_str} 至 {end_str})")
                return 0
                
        except Exception as e:
            print(f"❌ {ts_code}: 同步失败 - {e}")
            return 0
    
    def sync_portfolio_stocks(self, days: int = 365) -> dict:
        """
        只同步持仓股票的数据
        这个方法不会遍历所有缓存的股票，避免非交易日卡死

        Args:
            days: 同步天数

        Returns:
            同步统计字典
        """
        # 获取当前持仓的股票
        positions = self.db.get_positions(status='holding')
        ts_codes = [p['ts_code'] for p in positions]
        
        if not ts_codes:
            print("⚠️  当前没有持仓，跳过数据同步")
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'total_records': 0
            }

        # 只同步持仓的股票
        return self.sync_multiple_stocks(ts_codes, days)

    def sync_multiple_stocks(self, ts_codes: list, days: int = 365) -> dict:
        """
        同步多只股票的数据

        Args:
            ts_codes: 股票代码列表
            days: 同步天数

        Returns:
            同步统计字典
        """
        stats = {
            'total': len(ts_codes),
            'success': 0,
            'failed': 0,
            'total_records': 0
        }

        print(f"\n🚀 开始同步 {len(ts_codes)} 只股票的数据...\n")

        for i, ts_code in enumerate(ts_codes, 1):
            print(f"[{i}/{len(ts_codes)}] ", end="")
            count = self.sync_daily_quotes(ts_code, days)
            if count >= 0:
                stats['success'] += 1
                stats['total_records'] += count
            else:
                stats['failed'] += 1

        return stats
    
    def sync_financial_indicators(self, ts_code: str, periods: int = 10) -> int:
        """
        同步单只股票的财务指标
        
        Args:
            ts_code: 股票代码
            periods: 获取的期数（默认10期）
            
        Returns:
            保存的记录数
        """
        try:
            print(f"📊 同步 {ts_code} 财务指标...")
            
            # 获取财务指标
            df = self.pro.fina_indicator(ts_code=ts_code)
            
            if df is not None and not df.empty:
                # 只保留最近的 periods 期
                if len(df) > periods:
                    df = df.head(periods)
                
                count = self.db.save_financial_indicators(ts_code, df)
                print(f"✅ {ts_code}: 同步了 {count} 条财务指标")
                return count
            else:
                print(f"ℹ️  {ts_code}: 没有财务指标数据")
                return 0
                
        except Exception as e:
            print(f"❌ {ts_code}: 同步财务指标失败 - {e}")
            return -1
    
    def sync_multiple_financial(self, ts_codes: list, periods: int = 10) -> dict:
        """
        同步多只股票的财务指标
        
        Args:
            ts_codes: 股票代码列表
            periods: 每只股票获取的期数
            
        Returns:
            同步统计字典
        """
        stats = {
            'total': len(ts_codes),
            'success': 0,
            'failed': 0,
            'total_records': 0
        }
        
        print(f"\n🚀 开始同步 {len(ts_codes)} 只股票的财务指标...\n")
        
        for i, ts_code in enumerate(ts_codes, 1):
            print(f"[{i}/{len(ts_codes)}] ", end="")
            count = self.sync_financial_indicators(ts_code, periods)
            if count >= 0:
                stats['success'] += 1
                stats['total_records'] += count
            else:
                stats['failed'] += 1
        
        return stats
    
    def sync_hs300_data(self, days: int = 30) -> dict:
        """
        同步沪深300成分股的数据（用于15:10定时任务）
        
        Args:
            days: 同步天数
            
        Returns:
            同步统计字典
        """
        print("📊 开始同步沪深300成分股数据...")
        
        # 获取沪深300成分股列表
        ts_codes = get_hs300_stock_list()
        
        if not ts_codes:
            print("❌ 没有沪深300成分股数据")
            return {'total': 0, 'success': 0, 'failed': 0, 'total_records': 0}
        
        # 同步数据
        stats = self.sync_multiple_stocks(ts_codes, days)
        
        # 同时调用 get_today_gainers.py 来生成涨幅榜缓存
        print("\n📋 正在生成涨幅榜缓存...")
        try:
            from get_today_gainers import get_today_gainers
            # 调用一次来触发生成缓存
            get_today_gainers(count=50)
            print("✅ 涨幅榜缓存生成成功")
        except Exception as e:
            print(f"⚠️  涨幅榜缓存生成失败: {e}")
        
        return stats
    
    def sync_all_stocks(self, days: int = 30, batch_size: int = 100) -> dict:
        """
        同步所有股票的数据（慎用，API调用次数多）
        
        Args:
            days: 同步天数
            batch_size: 每批处理的股票数
            
        Returns:
            同步统计字典
        """
        # 先同步股票列表
        self.sync_stock_list()
        
        # 获取所有股票代码
        stock_df = self.db.get_stock_basic()
        if stock_df.empty:
            print("❌ 没有股票数据")
            return {'total': 0, 'success': 0, 'failed': 0, 'total_records': 0}
        
        ts_codes = stock_df['ts_code'].tolist()
        return self.sync_multiple_stocks(ts_codes, days)
    
    def close(self):
        """关闭数据库连接"""
        self.db.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def _load_token_from_store() -> str:
    """从存储中加载 Token"""
    token = os.getenv('TUSHARE_TOKEN')
    if token:
        return token
    
    config_dir = Path.home() / '.xiaohuo_quant'
    env_file = config_dir / 'token.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if 'TUSHARE_TOKEN' in line and '=' in line:
                value = line.split('=', 1)[1].strip().strip('"').strip("'")
                if value:
                    os.environ['TUSHARE_TOKEN'] = value
                    return value
    
    token_file = config_dir / 'token.txt'
    if token_file.exists():
        value = token_file.read_text().strip()
        if value:
            os.environ['TUSHARE_TOKEN'] = value
            return value
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description='高客秘书 - 数据同步工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 同步单只股票最近一年的数据
  python sync_data.py --code 300919
  
  # 同步多只股票
  python sync_data.py --codes 300919,600519,000001
  
  # 同步所有股票最近30天的数据（慎用）
  python sync_data.py --all --days 30
  
  # 同步股票列表
  python sync_data.py --stock-list
  
  # 同步单只股票的财务指标
  python sync_data.py --financial --code 300919
  
  # 同步多只股票的财务指标
  python sync_data.py --financial --codes 300919,600519
        """
    )
    
    parser.add_argument('--token', type=str, 
                        help='Tushare Token（也可设置TUSHARE_TOKEN环境变量）')
    parser.add_argument('--code', type=str, 
                        help='单只股票代码')
    parser.add_argument('--codes', type=str, 
                        help='多只股票代码，用逗号分隔')
    parser.add_argument('--portfolio', action='store_true',
                        help='只同步持仓的股票（推荐，避免遍历所有缓存股票）')
    parser.add_argument('--cache-hs300', action='store_true',
                        help='同步沪深300成分股数据并生成涨幅榜缓存（15:10定时任务用）')
    parser.add_argument('--all', action='store_true',
                        help='同步所有股票（慎用，API调用次数多）')
    parser.add_argument('--stock-list', action='store_true',
                        help='只同步股票列表')
    parser.add_argument('--days', type=int, default=365,
                        help='同步天数（默认365天）')
    parser.add_argument('--stats', action='store_true',
                        help='显示数据库统计信息')
    parser.add_argument('--financial', action='store_true',
                        help='同步财务指标（而非日线行情）')
    parser.add_argument('--periods', type=int, default=10,
                        help='财务指标期数（默认10期）')
    
    args = parser.parse_args()
    
    # 获取token
    token = args.token or _load_token_from_store()
    if not token and not args.stats:
        print("❌ 错误：请提供Tushare Token（--token参数或TUSHARE_TOKEN环境变量）")
        print("获取Token：https://tushare.pro/register")
        sys.exit(1)
    
    # 只显示统计信息
    if args.stats:
        with QuantDatabase() as db:
            stats = db.get_stats()
            print("\n" + "="*60)
            print("📊 数据库统计信息")
            print("="*60)
            print(f"📈 日线数据量: {stats['daily_quotes_count']:,} 条")
            print(f"📋 股票信息数: {stats['stock_basic_count']:,} 只")
            print(f"📊 财务指标数: {stats['financial_indicators_count']:,} 条")
            print(f"🔢 唯一股票数（行情）: {stats['unique_stocks']:,} 只")
            print(f"🔢 唯一股票数（财务）: {stats['unique_financial_stocks']:,} 只")
            print(f"📅 日期范围: {stats['date_range'][0]} 至 {stats['date_range'][1]}")
            print(f"📁 数据库路径: {stats['db_path']}")
            print("="*60 + "\n")
        return
    
    # 执行同步
    with DataSyncer(token) as syncer:
        if args.stock_list:
            syncer.sync_stock_list()
        
        elif args.financial:
            # 同步财务指标
            if args.code:
                # 标准化股票代码
                ts_code = args.code
                if not ts_code.endswith(('.SZ', '.SH', '.BJ')):
                    if ts_code.startswith('6'):
                        ts_code = ts_code + '.SH'
                    elif ts_code.startswith(('8', '4')):
                        ts_code = ts_code + '.BJ'
                    else:
                        ts_code = ts_code + '.SZ'
                
                syncer.sync_financial_indicators(ts_code, args.periods)
            
            elif args.codes:
                code_list = args.codes.split(',')
                ts_codes = []
                for code in code_list:
                    code = code.strip()
                    if not code.endswith(('.SZ', '.SH', '.BJ')):
                        if code.startswith('6'):
                            code = code + '.SH'
                        elif code.startswith(('8', '4')):
                            code = code + '.BJ'
                        else:
                            code = code + '.SZ'
                    ts_codes.append(code)
                
                stats = syncer.sync_multiple_financial(ts_codes, args.periods)
                print(f"\n📊 财务指标同步完成: {stats['success']}/{stats['total']} 成功, "
                      f"共 {stats['total_records']} 条记录")
        
        else:
            # 同步日线行情（默认）
            if args.cache_hs300:
                # 同步沪深300成分股数据并生成涨幅榜缓存
                stats = syncer.sync_hs300_data(args.days)
                if stats['total'] > 0:
                    print(f"\n📊 沪深300同步完成: {stats['success']}/{stats['total']} 成功, "
                          f"共 {stats['total_records']} 条记录")
            
            elif args.code:
                # 标准化股票代码
                ts_code = args.code
                if not ts_code.endswith(('.SZ', '.SH', '.BJ')):
                    if ts_code.startswith('6'):
                        ts_code = ts_code + '.SH'
                    elif ts_code.startswith(('8', '4')):
                        ts_code = ts_code + '.BJ'
                    else:
                        ts_code = ts_code + '.SZ'
                
                syncer.sync_daily_quotes(ts_code, args.days)
            
            elif args.codes:
                code_list = args.codes.split(',')
                ts_codes = []
                for code in code_list:
                    code = code.strip()
                    if not code.endswith(('.SZ', '.SH', '.BJ')):
                        if code.startswith('6'):
                            code = code + '.SH'
                        elif code.startswith(('8', '4')):
                            code = code + '.BJ'
                        else:
                            code = code + '.SZ'
                    ts_codes.append(code)
                
                stats = syncer.sync_multiple_stocks(ts_codes, args.days)
                print(f"\n📊 同步完成: {stats['success']}/{stats['total']} 成功, "
                      f"共 {stats['total_records']} 条记录")
            
            elif args.portfolio:
                # 只同步持仓股票（推荐）
                stats = syncer.sync_portfolio_stocks(args.days)
                if stats['total'] > 0:
                    print(f"\n📊 同步完成: {stats['success']}/{stats['total']} 成功, "
                          f"共 {stats['total_records']} 条记录")
            
            elif args.all:
                confirm = input(f"⚠️  警告：同步所有股票会调用大量API，确定继续吗？(yes/no): ")
                if confirm.lower() == 'yes':
                    stats = syncer.sync_all_stocks(args.days)
                    print(f"\n📊 同步完成: {stats['success']}/{stats['total']} 成功, "
                          f"共 {stats['total_records']} 条记录")
                else:
                    print("❌ 已取消")


if __name__ == '__main__':
    main()
