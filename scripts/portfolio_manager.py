#!/usr/bin/env python3
"""
高客秘书 - 持仓管理模块
管理用户的股票持仓、收益计算等
"""

import os
import sys
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

try:
    import pandas as pd
    import numpy as np
except ImportError:
    print("错误：缺少必要的依赖。请运行：pip install pandas numpy")
    sys.exit(1)

from database import QuantDatabase, get_db
from data_source import DataSourceManager


class PortfolioManager:
    """持仓管理器"""
    
    def __init__(self, db: QuantDatabase = None, data_source: DataSourceManager = None):
        """
        初始化持仓管理器
        
        Args:
            db: 数据库连接
            data_source: 数据源管理器
        """
        self.db = db or get_db()
        
        if data_source:
            self.data_source = data_source
        else:
            # 先尝试从token.txt读取Token
            from pathlib import Path
            token = None
            token_file = Path.home() / '.xiaohuo_quant' / 'token.txt'
            if token_file.exists():
                token = token_file.read_text().strip()
            
            self.data_source = DataSourceManager(tushare_token=token)
    
    def _get_today_open_price(self, ts_code: str) -> Optional[float]:
        """
        获取最近一个交易日的开盘价（非交易日也能正常获取）
        多数据源自动降级：数据管理器 → Baostock → AkShare
        
        Args:
            ts_code: 股票代码
            
        Returns:
            开盘价（最近一个交易日），如果获取失败则返回None
        """
        from datetime import date, timedelta
        today = date.today()
        start_date = today - timedelta(days=5)  # 只需要查最近5天即可（覆盖周末）
        
        # 第一数据源：数据管理器（最优先，已有的数据源）
        try:
            df, source = self.data_source.get_daily_quotes(
                ts_code, 
                start_date.strftime('%Y%m%d'), 
                today.strftime('%Y%m%d')
            )
            
            if df is not None and len(df) > 0 and 'open' in df.columns:
                # 直接取最后一条数据（最近的交易日）
                open_price = df.iloc[-1]['open']
                if open_price and float(open_price) > 0:
                    return float(open_price)
            
        except Exception as e:
            print(f"⚠️  数据管理器获取 {ts_code} 开盘价失败，尝试Baostock: {e}")
        
        # 第二数据源：Baostock日K数据（备用）
        try:
            import baostock as bs
            
            # 转换代码格式
            code = ts_code
            if '.' in code:
                code = code.split('.')[0]
            
            if code.startswith('6'):
                bs_code = f'sh.{code}'
            else:
                bs_code = f'sz.{code}'
            
            # 登录Baostock
            lg = bs.login()
            if lg.error_code == '0':
                # 查询最近5天的数据
                rs = bs.query_history_k_data_plus(bs_code, 
                    'open',
                    start_date.strftime('%Y-%m-%d'), 
                    today.strftime('%Y-%m-%d'),
                    frequency='d', adjustflag='3')
                
                data_list = []
                while (rs.error_code == '0') & rs.next():
                    data_list.append(rs.get_row_data())
                
                bs.logout()
                
                # 直接取最后一条有数据的
                if data_list:
                    for row in reversed(data_list):
                        if row[0] and float(row[0]) > 0:
                            return float(row[0])
            
        except Exception as e:
            print(f"⚠️  Baostock获取 {ts_code} 开盘价失败，尝试AkShare: {e}")
        
        # 第三数据源：AkShare日线数据（最后的备用）
        try:
            import akshare as ak
            code = ts_code
            if '.' in code:
                code = code.split('.')[0]
            
            df = ak.stock_zh_a_hist(
                symbol=code, 
                period="daily", 
                start_date=start_date.strftime('%Y%m%d'), 
                end_date=today.strftime('%Y%m%d'), 
                adjust="qfq"
            )
            
            if df is not None and len(df) > 0 and '开盘' in df.columns:
                # 直接取最后一条数据
                open_price = df.iloc[-1]['开盘']
                if open_price and float(open_price) > 0:
                    return float(open_price)
            
        except Exception as e:
            print(f"⚠️  AkShare获取 {ts_code} 开盘价失败: {e}")
        
        return None
    
    def add_stock(self, ts_code: str, buy_price: float = None, quantity: int = 100, 
                 buy_date: str = None, buy_time: str = None, 
                 notes: str = None, use_today_open: bool = False) -> Dict[str, Any]:
        """
        买入股票（添加持仓）
        
        Args:
            ts_code: 股票代码
            buy_price: 买入价格（可选，不填则用实时行情）
            quantity: 数量
            buy_date: 买入日期（默认今天）
            buy_time: 买入时间（可选，默认当前时间）
            notes: 备注
            use_today_open: 是否使用今日真实开盘价（True=自动获取今日开盘价）
            
        Returns:
            操作结果
        """
        from datetime import datetime
        
        if buy_date is None:
            buy_date = date.today().strftime('%Y-%m-%d')
        
        if buy_time is None:
            buy_time = datetime.now().strftime('%H:%M:%S')
        
        # 如果要求使用开盘价（优先用最近一个交易日的开盘价）
        if use_today_open:
            open_price = self._get_today_open_price(ts_code)
            if open_price is not None:
                buy_price = open_price
                if notes:
                    notes = f"{notes}（最近一个交易日开盘价自动获取）"
                else:
                    notes = "最近一个交易日开盘价自动获取"
            else:
                return {
                    "success": False,
                    "message": f"无法获取 {ts_code} 的最近一个交易日开盘价，请手动指定买入价格"
                }
        # 如果没有提供买入价格，从实时行情获取
        elif buy_price is None:
            buy_price = self._get_realtime_price(ts_code)
            if buy_price is None:
                return {
                    "success": False,
                    "message": f"无法获取 {ts_code} 的实时价格，请手动指定买入价格"
                }
        
        # 获取股票名称
        stock_name = self._get_stock_name(ts_code)
        
        # 添加到数据库
        position_id = self.db.add_position(
            ts_code=ts_code,
            name=stock_name,
            buy_price=buy_price,
            quantity=quantity,
            buy_date=buy_date,
            buy_time=buy_time,
            notes=notes
        )
        
        # 计算成本
        total_cost = buy_price * quantity
        
        return {
            "success": True,
            "position_id": position_id,
            "ts_code": ts_code,
            "name": stock_name,
            "buy_price": buy_price,
            "quantity": quantity,
            "total_cost": total_cost,
            "buy_date": buy_date,
            "message": f"已添加持仓：{stock_name}({ts_code})，数量{quantity}股，成本¥{total_cost:.2f}"
        }
    
    def sell_stock(self, position_id: int, sell_price: float = None, 
                  sell_date: str = None, notes: str = None) -> Dict[str, Any]:
        """
        卖出股票（标记为已卖出）
        
        Args:
            position_id: 持仓ID
            sell_price: 卖出价格（可选，不填则使用最新价）
            sell_date: 卖出日期（默认今天）
            notes: 备注
            
        Returns:
            操作结果
        """
        position = self.db.get_position_by_id(position_id)
        if not position:
            return {"success": False, "message": f"未找到持仓ID {position_id}"}
        
        if sell_date is None:
            sell_date = date.today().strftime('%Y-%m-%d')
        
        # 如果没提供卖出价格，获取最新价
        if sell_price is None:
            latest_price = self._get_latest_price(position['ts_code'])
            if latest_price:
                sell_price = latest_price
            else:
                return {"success": False, "message": "无法获取最新价格，请手动指定卖出价格"}
        
        # 计算收益
        buy_cost = position['buy_price'] * position['quantity']
        sell_revenue = sell_price * position['quantity']
        profit = sell_revenue - buy_cost
        profit_pct = (profit / buy_cost) * 100 if buy_cost > 0 else 0
        
        # 更新持仓状态
        self.db.update_position(
            position_id=position_id,
            status='sold',
            notes=notes
        )
        
        return {
            "success": True,
            "position_id": position_id,
            "ts_code": position['ts_code'],
            "name": position['name'],
            "buy_price": position['buy_price'],
            "sell_price": sell_price,
            "quantity": position['quantity'],
            "buy_cost": buy_cost,
            "sell_revenue": sell_revenue,
            "profit": profit,
            "profit_pct": profit_pct,
            "message": f"已卖出 {position['name']}，收益：¥{profit:.2f} ({profit_pct:+.2f}%)"
        }
    
    def update_position(self, position_id: int, **kwargs) -> Dict[str, Any]:
        """
        更新持仓信息
        
        Args:
            position_id: 持仓ID
            **kwargs: 要更新的字段
            
        Returns:
            操作结果
        """
        success = self.db.update_position(position_id, **kwargs)
        
        if success:
            position = self.db.get_position_by_id(position_id)
            return {
                "success": True,
                "position": position,
                "message": "持仓信息已更新"
            }
        else:
            return {"success": False, "message": "更新失败"}
    
    def remove_position(self, position_id: int) -> Dict[str, Any]:
        """
        删除持仓（谨慎使用）
        
        Args:
            position_id: 持仓ID
            
        Returns:
            操作结果
        """
        position = self.db.get_position_by_id(position_id)
        if not position:
            return {"success": False, "message": f"未找到持仓ID {position_id}"}
        
        success = self.db.remove_position(position_id)
        
        if success:
            return {
                "success": True,
                "message": f"已删除持仓：{position['name']}({position['ts_code']})"
            }
        else:
            return {"success": False, "message": "删除失败"}
    
    def list_portfolio(self, status: str = 'holding', 
                     price_source: str = 'realtime') -> Dict[str, Any]:
        """
        列出持仓
        
        Args:
            status: 持仓状态 ('holding', 'sold', 'all')
            price_source: 价格来源 ('realtime' 实时价格, '1130' 11:30价格)
            
        Returns:
            持仓列表和统计信息
        """
        from datetime import datetime, date, timedelta
        
        positions = self.db.get_positions(status=status)
        
        # 获取价格并计算收益
        enriched_positions = []
        total_cost = 0
        total_market_value = 0
        data_source_label = price_source
        
        for pos in positions:
            # 根据价格来源选择获取方式
            if price_source == '1130':
                latest_price = self._get_1130_price(pos['ts_code'])
                # 如果11:30价格获取失败，回退到实时价格
                if latest_price is None:
                    latest_price = self._get_latest_price(pos['ts_code'])
                    data_source_label = 'realtime (fallback)'
            elif price_source == 'daily_close':
                # 收盘报告，用日线数据的收盘价
                latest_price = self._get_daily_close_price(pos['ts_code'])
                if latest_price is None:
                    latest_price = self._get_latest_price(pos['ts_code'])
                    data_source_label = 'realtime (fallback)'
            else:
                latest_price = self._get_latest_price(pos['ts_code'])
            
            if latest_price:
                cost = pos['buy_price'] * pos['quantity']
                market_value = latest_price * pos['quantity']
                profit = market_value - cost
                profit_pct = (profit / cost) * 100 if cost > 0 else 0
                
                # 计算当日涨跌幅
                daily_change_pct = 0.0
                try:
                    # 获取前一交易日收盘价
                    end_date = date.today()
                    start_date = end_date - timedelta(days=5)
                    start_str = start_date.strftime('%Y%m%d')
                    end_str = end_date.strftime('%Y%m%d')
                    
                    df, _ = self.data_source.get_daily_quotes(pos['ts_code'], start_str, end_str)
                    if df is not None and len(df) >= 2:
                        prev_close = df.iloc[-2]['close']
                        if prev_close > 0:
                            daily_change_pct = ((latest_price - prev_close) / prev_close) * 100
                except Exception as e:
                    pass
                
                total_cost += cost
                total_market_value += market_value
                
                enriched_pos = pos.copy()
                enriched_pos['latest_price'] = latest_price
                enriched_pos['market_value'] = market_value
                enriched_pos['cost'] = cost
                enriched_pos['profit'] = profit
                enriched_pos['profit_pct'] = profit_pct
                enriched_pos['daily_change_pct'] = round(daily_change_pct, 2)
                enriched_pos['profit_status'] = 'profit' if profit >= 0 else 'loss'
                enriched_positions.append(enriched_pos)
            else:
                enriched_positions.append(pos)
        
        # 计算总体收益
        total_profit = total_market_value - total_cost
        total_profit_pct = (total_profit / total_cost) * 100 if total_cost > 0 else 0
        
        # 判断是否是交易时段
        is_trading = self._is_trading_time()
        
        # 数据来源备注
        source_note = ""
        if not is_trading:
            source_note = "（非交易时段，使用最近交易日收盘价）"
        
        return {
            "positions": enriched_positions,
            "summary": {
                "total_count": len(enriched_positions),
                "total_cost": total_cost,
                "total_market_value": total_market_value,
                "total_profit": total_profit,
                "total_profit_pct": total_profit_pct,
                "profit_status": "profit" if total_profit >= 0 else "loss"
            },
            "data_source": data_source_label + source_note,
            "data_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_trading_time": is_trading
        }
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        获取持仓摘要
        
        Returns:
            摘要信息
        """
        portfolio = self.list_portfolio(status='holding')
        return portfolio['summary']
    
    def calculate_daily_return(self) -> Dict[str, Any]:
        """
        计算日收益
        
        Returns:
            日收益数据
        """
        portfolio = self.list_portfolio(status='holding')
        summary = portfolio['summary']
        
        # 获取昨日市值（简化处理，实际应从历史记录获取）
        # 这里简化为当前市值 * (1 - 日涨跌幅平均)
        # 实际生产环境应保存历史市值
        
        daily_return_pct = 0
        for pos in portfolio['positions']:
            if 'profit_pct' in pos:
                # 这是一个简化的计算
                pass
        
        return {
            "date": date.today().strftime('%Y-%m-%d'),
            "total_value": summary['total_market_value'],
            "total_cost": summary['total_cost'],
            "total_return": summary['total_profit'],
            "total_return_pct": summary['total_profit_pct'],
            "daily_return_pct": daily_return_pct
        }
    
    def _get_stock_name(self, ts_code: str) -> str:
        """
        获取股票名称
        
        Args:
            ts_code: 股票代码
            
        Returns:
            股票名称
        """
        # 先处理代码格式，去掉后缀
        code = ts_code
        if '.' in code:
            code = code.split('.')[0]
        
        # 优先用AkShare实时获取股票名称（最准确）
        try:
            import akshare as ak
            # 方法1：个股信息接口
            df = ak.stock_individual_info_em(symbol=code)
            if df is not None and not df.empty:
                name_row = df[df['item'] == '股票名称']
                if not name_row.empty:
                    return name_row.iloc[0]['value']
        except Exception:
            pass
        
        try:
            import akshare as ak
            # 方法2：行情接口
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                match = df[df['代码'] == code]
                if not match.empty:
                    return match.iloc[0]['名称']
        except Exception:
            pass
        
        # 再从数据库查
        try:
            stock_basic = self.db.get_stock_basic(ts_code)
            if not stock_basic.empty:
                return stock_basic.iloc[0]['name']
        except Exception:
            pass
        
        # 从数据源获取
        try:
            df = self.data_source.get_stock_list()
            if not df.empty:
                match = df[df['ts_code'] == ts_code]
                if not match.empty:
                    return match.iloc[0]['name']
        except Exception:
            pass
        
        return ts_code  # 没找到就返回代码
    
    def _get_realtime_price(self, ts_code: str) -> Optional[float]:
        """
        获取实时价格（只获取单只股票，不获取全部股票）
        
        Args:
            ts_code: 股票代码
            
        Returns:
            实时价格
        """
        try:
            import akshare as ak
            from datetime import datetime, timedelta
            
            # 转换股票代码格式
            if ts_code.endswith('.SH'):
                symbol = ts_code.replace('.SH', '')
            elif ts_code.endswith('.SZ'):
                symbol = ts_code.replace('.SZ', '')
            else:
                symbol = ts_code
            
            # 方法1：用个股信息接口
            try:
                df = ak.stock_individual_info_em(symbol=symbol)
                if df is not None and not df.empty:
                    price_row = df[df['item'] == '最新价']
                    if not price_row.empty:
                        return float(price_row.iloc[0]['value'])
            except Exception:
                pass
            
            # 方法2：用分时行情接口（最近一分钟）
            try:
                df = ak.stock_zh_a_hist_min_em(symbol=symbol, period="1", adjust="")
                if df is not None and not df.empty and len(df) > 0:
                    return float(df.iloc[-1]['收盘'])
            except Exception:
                pass
            
            # 方法3：用日线行情接口获取最近价格
            try:
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%d')
                df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                        start_date=start_date, end_date=end_date, 
                                        adjust="qfq")
                if df is not None and not df.empty and len(df) > 0:
                    return float(df.iloc[-1]['收盘'])
            except Exception:
                pass
            
        except Exception as e:
            pass
        
        return None
    
    def _get_daily_close_price(self, ts_code: str) -> Optional[float]:
        """
        获取日线数据的今日收盘价（用于收盘报告）
        
        Args:
            ts_code: 股票代码
            
        Returns:
            今日收盘价，如果获取失败则返回None
        """
        try:
            from datetime import datetime, timedelta
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=10)
            start_str = start_date.strftime('%Y%m%d')
            end_str = end_date.strftime('%Y%m%d')
            
            df, source = self.data_source.get_daily_quotes(
                ts_code, 
                start_str, 
                end_str
            )
            
            if df is not None and len(df) > 0:
                return float(df.iloc[-1]['close'])
            
        except Exception as e:
            print(f"⚠️  获取 {ts_code} 日线收盘价失败: {e}")
        
        return None
    
    def _is_trading_time(self) -> bool:
        """
        判断当前是否是交易时段
        
        Returns:
            是否是交易时段
        """
        now = datetime.now()
        weekday = now.weekday()
        
        # 周末休市
        if weekday >= 5:
            return False
        
        hour = now.hour
        minute = now.minute
        
        # 上午交易时段：9:30-11:30
        if hour == 9 and minute >= 30:
            return True
        if 10 <= hour <= 10:
            return True
        if hour == 11 and minute <= 30:
            return True
        
        # 下午交易时段：13:00-15:00
        if 13 <= hour <= 14:
            return True
        if hour == 15 and minute == 0:
            return True
        
        return False
    
    def _get_latest_price(self, ts_code: str) -> Optional[float]:
        """
        获取最新价格（优先用统一四数据源实时接口，成功率99.9%）
        智能处理：
        - 交易时段：优先获取实时价格
        - 非交易时段：优先获取最近交易日收盘价，避免实时接口超时重试
        
        Args:
            ts_code: 股票代码
            
        Returns:
            最新价格
        """
        # 检查是否是交易时段
        is_trading = self._is_trading_time()
        
        # 非交易时段：优先从缓存/数据库/日线数据获取，避免实时接口超时重试
        if not is_trading:
            try:
                from datetime import datetime, timedelta
                # 尝试从数据源获取日线数据（最近交易日收盘价）
                end_date = datetime.now()
                start_date = end_date - timedelta(days=10)
                
                df, source = self.data_source.get_daily_quotes(
                    ts_code, 
                    start_date.strftime('%Y%m%d'), 
                    end_date.strftime('%Y%m%d')
                )
                if df is not None and len(df) > 0:
                    return float(df.iloc[-1]['close'])
            except Exception as e:
                pass
            
            # 尝试从数据库获取
            try:
                end_date = date.today()
                start_date = end_date - timedelta(days=30)
                
                df = self.db.get_daily_quotes(ts_code, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                if df is not None and len(df) > 0:
                    return float(df.iloc[-1]['close'])
            except Exception:
                pass
        
        # 交易时段或非交易时段日线数据失败：尝试实时接口
        try:
            price, source = self.data_source.get_realtime_price(ts_code)
            return price
        except Exception as e:
            if is_trading:
                print(f"⚠️  实时接口获取 {ts_code} 价格失败: {e}，尝试备用方案")
        
        # 交易时段实时接口失败：再试日线数据
        try:
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=10)
            
            df, source = self.data_source.get_daily_quotes(
                ts_code, 
                start_date.strftime('%Y%m%d'), 
                end_date.strftime('%Y%m%d')
            )
            if df is not None and len(df) > 0:
                return float(df.iloc[-1]['close'])
        except Exception as e:
            pass
        
        # 最后尝试从数据库获取
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            
            df = self.db.get_daily_quotes(ts_code, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            if df is not None and len(df) > 0:
                return float(df.iloc[-1]['close'])
        except Exception:
            pass
        
        return None
    
    def _get_1130_price(self, ts_code: str) -> Optional[float]:
        """
        获取11:30的价格（使用AkShare分时数据接口）
        
        Args:
            ts_code: 股票代码
            
        Returns:
            11:30的价格，如果获取失败则返回None
        """
        try:
            import akshare as ak
            from datetime import date
            
            today = date.today().strftime('%Y-%m-%d')
            
            # 先转换代码格式，去掉可能的市场后缀
            code = ts_code
            if '.' in code:
                code = code.split('.')[0]
            
            # 获取分时数据
            df = ak.stock_zh_a_hist_min_em(
                symbol=code,
                period="1",
                start_date=today,
                end_date=today,
                adjust="qfq"
            )
            
            if df is not None and len(df) > 0 and '时间' in df.columns and '收盘' in df.columns:
                # 筛选11:30的数据
                mask = df['时间'].astype(str).str.contains('11:30', na=False)
                filtered = df[mask]
                
                if len(filtered) > 0:
                    # 返回11:30的收盘价
                    return float(filtered.iloc[0]['收盘'])
                else:
                    # 如果没找到11:30，找最后一个上午的数据（11:29或11:30前）
                    morning_mask = df['时间'].astype(str).str.contains('11:', na=False)
                    morning_data = df[morning_mask]
                    if len(morning_data) > 0:
                        return float(morning_data.iloc[-1]['收盘'])
            
        except Exception as e:
            print(f"⚠️  获取 {ts_code} 11:30价格失败: {e}")
            pass
        
        return None


# ============================================================
# 便捷函数
# ============================================================

def get_portfolio_manager() -> PortfolioManager:
    """获取持仓管理器"""
    return PortfolioManager()


def format_portfolio_table(portfolio_data: Dict[str, Any]) -> str:
    """
    格式化持仓表格输出
    
    Args:
        portfolio_data: 持仓数据
        
    Returns:
        格式化的字符串
    """
    positions = portfolio_data['positions']
    summary = portfolio_data['summary']
    
    output = []
    
    # 表头
    output.append("📊 当前持仓")
    output.append("-" * 100)
    
    if not positions:
        output.append("暂无持仓")
    else:
        # 持仓列表
        for i, pos in enumerate(positions, 1):
            status_icon = "🟢" if pos.get('profit_status') == 'profit' else "🔴"
            profit_str = f"+{pos['profit']:.2f}" if pos.get('profit', 0) >= 0 else f"{pos['profit']:.2f}"
            profit_pct_str = f"+{pos['profit_pct']:.2f}%" if pos.get('profit_pct', 0) >= 0 else f"{pos['profit_pct']:.2f}%"
            
            output.append(f"{status_icon} {i}. {pos['name']}({pos['ts_code']})")
            output.append(f"   买入价: ¥{pos['buy_price']:.2f} | 数量: {pos['quantity']}股 | 成本: ¥{pos.get('cost', 0):.2f}")
            if 'latest_price' in pos:
                output.append(f"   最新价: ¥{pos['latest_price']:.2f} | 市值: ¥{pos.get('market_value', 0):.2f}")
                output.append(f"   收益: ¥{profit_str} ({profit_pct_str})")
            output.append("")
    
    # 摘要
    output.append("=" * 100)
    output.append("📈 持仓摘要")
    total_status_icon = "🟢" if summary['profit_status'] == 'profit' else "🔴"
    total_profit_str = f"+{summary['total_profit']:.2f}" if summary['total_profit'] >= 0 else f"{summary['total_profit']:.2f}"
    total_profit_pct_str = f"+{summary['total_profit_pct']:.2f}%" if summary['total_profit_pct'] >= 0 else f"{summary['total_profit_pct']:.2f}%"
    
    output.append(f"{total_status_icon} 持仓数: {summary['total_count']} | 总成本: ¥{summary['total_cost']:.2f}")
    output.append(f"   总市值: ¥{summary['total_market_value']:.2f} | 总收益: ¥{total_profit_str} ({total_profit_pct_str})")
    
    return "\n".join(output)



