#!/usr/bin/env python3
"""
高客秘书 - 数据库存储模块
使用 SQLite 存储行情和基本面数据
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

try:
    import pandas as pd
    import numpy as np
except ImportError:
    print("错误：缺少必要的依赖。请运行：pip install pandas numpy")
    sys.exit(1)


class QuantDatabase:
    """量化数据库管理类"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化数据库连接
        
        Args:
            db_path: 数据库文件路径，默认为 ~/.xiaohuo_quant/quant_data.db
        """
        if db_path is None:
            config_dir = Path.home() / '.xiaohuo_quant'
            config_dir.mkdir(parents=True, exist_ok=True)
            db_path = config_dir / 'quant_data.db'
        
        self.db_path = str(db_path)
        self.conn = None
        self._connect()
        self._init_tables()
    
    def _connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def _close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def _init_tables(self):
        """初始化数据库表"""
        cursor = self.conn.cursor()
        
        # 日线行情表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                pre_close REAL,
                change REAL,
                pct_chg REAL,
                vol REAL,
                amount REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ts_code, trade_date)
            )
        ''')
        
        # 股票基本信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_basic (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT NOT NULL UNIQUE,
                symbol TEXT,
                name TEXT,
                area TEXT,
                industry TEXT,
                market TEXT,
                list_date TEXT,
                is_hs TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 财务指标表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS financial_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT NOT NULL,
                ann_date TEXT,
                end_date TEXT,
                eps REAL,
                dt_eps REAL,
                total_revenue REAL,
                revenue REAL,
                operate_profit REAL,
                total_profit REAL,
                n_income REAL,
                total_assets REAL,
                total_hldr_eqy_exc_min_int REAL,
                diluted_roe REAL,
                roe_waa REAL,
                roa REAL,
                debt_to_assets REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ts_code, end_date)
            )
        ''')
        
        # 数据同步状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_type TEXT NOT NULL,
                ts_code TEXT,
                last_sync_date TEXT,
                last_sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(data_type, ts_code)
            )
        ''')
        
        # 持仓表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT NOT NULL,
                name TEXT,
                buy_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                buy_date TEXT NOT NULL,
                buy_time TEXT,
                status TEXT DEFAULT 'holding',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 自动升级：为已有表添加buy_time字段（兼容老用户）
        try:
            cursor.execute("ALTER TABLE portfolio ADD COLUMN buy_time TEXT")
        except Exception:
            # 字段已经存在，忽略错误
            pass
        
        # 收益跟踪表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS return_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_date TEXT NOT NULL,
                tracking_time TEXT NOT NULL,
                total_value REAL,
                total_cost REAL,
                total_return_pct REAL,
                daily_return_pct REAL,
                benchmark_return_pct REAL,
                attribution_data TEXT,
                quant_metrics TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tracking_date, tracking_time)
            )
        ''')
        # 自动升级：为已有表添加quant_metrics字段（兼容老用户）
        try:
            cursor.execute("ALTER TABLE return_tracking ADD COLUMN quant_metrics TEXT")
        except Exception:
            # 字段已经存在，忽略错误
            pass
        
        # 投资报告表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS investment_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                report_type TEXT NOT NULL,
                content TEXT,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(report_date, report_type)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_ts_code ON daily_quotes(ts_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_trade_date ON daily_quotes(trade_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_financial_ts_code ON financial_indicators(ts_code)')
        
        self.conn.commit()
    
    def save_daily_quotes(self, ts_code: str, df: pd.DataFrame) -> int:
        """
        保存日线行情数据
        
        Args:
            ts_code: 股票代码
            df: 包含行情数据的DataFrame
            
        Returns:
            保存的记录数
        """
        if df is None or df.empty:
            return 0
        
        cursor = self.conn.cursor()
        saved_count = 0
        
        for _, row in df.iterrows():
            try:
                trade_date = row['trade_date']
                if hasattr(trade_date, 'strftime'):
                    trade_date = trade_date.strftime('%Y-%m-%d')
                elif isinstance(trade_date, str) and len(trade_date) == 8:
                    trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
                
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_quotes 
                    (ts_code, trade_date, open, high, low, close, pre_close, 
                     change, pct_chg, vol, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ts_code,
                    trade_date,
                    float(row.get('open', 0)) if pd.notna(row.get('open')) else None,
                    float(row.get('high', 0)) if pd.notna(row.get('high')) else None,
                    float(row.get('low', 0)) if pd.notna(row.get('low')) else None,
                    float(row.get('close', 0)) if pd.notna(row.get('close')) else None,
                    float(row.get('pre_close', 0)) if pd.notna(row.get('pre_close')) else None,
                    float(row.get('change', 0)) if pd.notna(row.get('change')) else None,
                    float(row.get('pct_chg', 0)) if pd.notna(row.get('pct_chg')) else None,
                    float(row.get('vol', 0)) if pd.notna(row.get('vol')) else None,
                    float(row.get('amount', 0)) if pd.notna(row.get('amount')) else None
                ))
                saved_count += 1
            except Exception as e:
                print(f"保存 {ts_code} {trade_date} 数据时出错: {e}")
                continue
        
        # 更新同步状态
        if saved_count > 0:
            last_date = df['trade_date'].max()
            if hasattr(last_date, 'strftime'):
                last_date = last_date.strftime('%Y-%m-%d')
            elif isinstance(last_date, str) and len(last_date) == 8:
                last_date = f"{last_date[:4]}-{last_date[4:6]}-{last_date[6:8]}"
            
            cursor.execute('''
                INSERT OR REPLACE INTO sync_status (data_type, ts_code, last_sync_date)
                VALUES (?, ?, ?)
            ''', ('daily', ts_code, last_date))
        
        self.conn.commit()
        return saved_count
    
    def get_daily_quotes(self, ts_code: str, start_date: Optional[str] = None, 
                         end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取日线行情数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            DataFrame
        """
        query = "SELECT * FROM daily_quotes WHERE ts_code = ?"
        params = [ts_code]
        
        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)
        
        query += " ORDER BY trade_date ASC"
        
        df = pd.read_sql_query(query, self.conn, params=params)
        if not df.empty:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
        return df
    
    def save_stock_basic(self, df: pd.DataFrame) -> int:
        """
        保存股票基本信息
        
        Args:
            df: 包含股票基本信息的DataFrame
            
        Returns:
            保存的记录数
        """
        if df is None or df.empty:
            return 0
        
        cursor = self.conn.cursor()
        saved_count = 0
        
        for _, row in df.iterrows():
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_basic 
                    (ts_code, symbol, name, area, industry, market, list_date, is_hs)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row.get('ts_code'),
                    row.get('symbol'),
                    row.get('name'),
                    row.get('area'),
                    row.get('industry'),
                    row.get('market'),
                    row.get('list_date'),
                    row.get('is_hs')
                ))
                saved_count += 1
            except Exception as e:
                print(f"保存股票信息 {row.get('ts_code')} 时出错: {e}")
                continue
        
        self.conn.commit()
        return saved_count
    
    def get_stock_basic(self, ts_code: Optional[str] = None) -> pd.DataFrame:
        """
        获取股票基本信息
        
        Args:
            ts_code: 股票代码，None则获取所有
            
        Returns:
            DataFrame
        """
        if ts_code:
            query = "SELECT * FROM stock_basic WHERE ts_code = ?"
            df = pd.read_sql_query(query, self.conn, params=[ts_code])
        else:
            query = "SELECT * FROM stock_basic"
            df = pd.read_sql_query(query, self.conn)
        return df
    
    def save_financial_indicators(self, ts_code: str, df: pd.DataFrame) -> int:
        """
        保存财务指标数据
        
        Args:
            ts_code: 股票代码
            df: 包含财务指标的DataFrame
            
        Returns:
            保存的记录数
        """
        if df is None or df.empty:
            return 0
        
        cursor = self.conn.cursor()
        saved_count = 0
        
        for _, row in df.iterrows():
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO financial_indicators 
                    (ts_code, ann_date, end_date, eps, dt_eps, total_revenue, revenue, 
                     operate_profit, total_profit, n_income, total_assets, 
                     total_hldr_eqy_exc_min_int, diluted_roe, roe_waa, roa, debt_to_assets)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ts_code,
                    row.get('ann_date'),
                    row.get('end_date'),
                    float(row.get('eps', 0)) if pd.notna(row.get('eps')) else None,
                    float(row.get('dt_eps', 0)) if pd.notna(row.get('dt_eps')) else None,
                    float(row.get('total_revenue', 0)) if pd.notna(row.get('total_revenue')) else None,
                    float(row.get('revenue', 0)) if pd.notna(row.get('revenue')) else None,
                    float(row.get('operate_profit', 0)) if pd.notna(row.get('operate_profit')) else None,
                    float(row.get('total_profit', 0)) if pd.notna(row.get('total_profit')) else None,
                    float(row.get('n_income', 0)) if pd.notna(row.get('n_income')) else None,
                    float(row.get('total_assets', 0)) if pd.notna(row.get('total_assets')) else None,
                    float(row.get('total_hldr_eqy_exc_min_int', 0)) if pd.notna(row.get('total_hldr_eqy_exc_min_int')) else None,
                    float(row.get('diluted_roe', 0)) if pd.notna(row.get('diluted_roe')) else None,
                    float(row.get('roe_waa', 0)) if pd.notna(row.get('roe_waa')) else None,
                    float(row.get('roa', 0)) if pd.notna(row.get('roa')) else None,
                    float(row.get('debt_to_assets', 0)) if pd.notna(row.get('debt_to_assets')) else None
                ))
                saved_count += 1
            except Exception as e:
                print(f"保存财务指标 {ts_code} {row.get('end_date')} 时出错: {e}")
                continue
        
        # 更新同步状态
        if saved_count > 0:
            last_date = df['end_date'].max() if 'end_date' in df.columns else None
            if last_date:
                cursor.execute('''
                    INSERT OR REPLACE INTO sync_status (data_type, ts_code, last_sync_date)
                    VALUES (?, ?, ?)
                ''', ('financial', ts_code, last_date))
        
        self.conn.commit()
        return saved_count
    
    def get_financial_indicators(self, ts_code: str, limit: int = 10) -> pd.DataFrame:
        """
        获取财务指标数据
        
        Args:
            ts_code: 股票代码
            limit: 返回记录数限制
            
        Returns:
            DataFrame
        """
        query = "SELECT * FROM financial_indicators WHERE ts_code = ? ORDER BY end_date DESC LIMIT ?"
        df = pd.read_sql_query(query, self.conn, params=[ts_code, limit])
        return df
    
    def get_sync_status(self, data_type: str, ts_code: str) -> Optional[str]:
        """
        获取数据同步状态
        
        Args:
            data_type: 数据类型 ('daily', 'financial')
            ts_code: 股票代码
            
        Returns:
            最后同步日期
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT last_sync_date FROM sync_status 
            WHERE data_type = ? AND ts_code = ?
        ''', (data_type, ts_code))
        row = cursor.fetchone()
        return row['last_sync_date'] if row else None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息
        
        Returns:
            统计信息字典
        """
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM daily_quotes")
        daily_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM stock_basic")
        stock_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM financial_indicators")
        financial_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(DISTINCT ts_code) as count FROM daily_quotes")
        unique_stocks = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(DISTINCT ts_code) as count FROM financial_indicators")
        unique_financial = cursor.fetchone()['count']
        
        cursor.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_quotes")
        row = cursor.fetchone()
        date_range = (row[0], row[1]) if row[0] else (None, None)
        
        return {
            "daily_quotes_count": daily_count,
            "stock_basic_count": stock_count,
            "financial_indicators_count": financial_count,
            "unique_stocks": unique_stocks,
            "unique_financial_stocks": unique_financial,
            "date_range": date_range,
            "db_path": self.db_path
        }
    
    # ============================================================
    # 持仓管理方法
    # ============================================================
    
    def add_position(self, ts_code: str, name: str, buy_price: float, 
                    quantity: int, buy_date: str, buy_time: str = None, 
                    notes: str = None) -> int:
        """
        添加持仓
        
        Args:
            ts_code: 股票代码
            name: 股票名称
            buy_price: 买入价格
            quantity: 数量
            buy_date: 买入日期
            buy_time: 买入时间（可选）
            notes: 备注
            
        Returns:
            新记录ID
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO portfolio (ts_code, name, buy_price, quantity, buy_date, buy_time, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (ts_code, name, buy_price, quantity, buy_date, buy_time, notes))
        self.conn.commit()
        return cursor.lastrowid
    
    def update_position(self, position_id: int, **kwargs) -> bool:
        """
        更新持仓
        
        Args:
            position_id: 持仓ID
            **kwargs: 要更新的字段
            
        Returns:
            是否成功
        """
        allowed_fields = ['buy_price', 'quantity', 'buy_date', 'status', 'notes']
        updates = []
        params = []
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                params.append(value)
        
        if not updates:
            return False
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(position_id)
        
        cursor = self.conn.cursor()
        cursor.execute(f'''
            UPDATE portfolio SET {', '.join(updates)}
            WHERE id = ?
        ''', params)
        self.conn.commit()
        return cursor.rowcount > 0
    
    def remove_position(self, position_id: int) -> bool:
        """
        删除持仓
        
        Args:
            position_id: 持仓ID
            
        Returns:
            是否成功
        """
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM portfolio WHERE id = ?', (position_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_positions(self, status: str = 'holding') -> List[Dict[str, Any]]:
        """
        获取持仓列表
        
        Args:
            status: 持仓状态 ('holding', 'sold', 'all')
            
        Returns:
            持仓列表
        """
        cursor = self.conn.cursor()
        
        if status == 'all':
            cursor.execute('SELECT * FROM portfolio ORDER BY created_at DESC')
        else:
            cursor.execute('SELECT * FROM portfolio WHERE status = ? ORDER BY created_at DESC', (status,))
        
        positions = []
        for row in cursor.fetchall():
            positions.append(dict(row))
        
        return positions
    
    def get_position_by_id(self, position_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取持仓
        
        Args:
            position_id: 持仓ID
            
        Returns:
            持仓信息
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM portfolio WHERE id = ?', (position_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_position_by_code(self, ts_code: str, status: str = 'holding') -> List[Dict[str, Any]]:
        """
        根据股票代码获取持仓
        
        Args:
            ts_code: 股票代码
            status: 持仓状态
            
        Returns:
            持仓列表
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM portfolio WHERE ts_code = ? AND status = ?
            ORDER BY created_at DESC
        ''', (ts_code, status))
        
        positions = []
        for row in cursor.fetchall():
            positions.append(dict(row))
        
        return positions
    
    # ============================================================
    # 收益跟踪方法
    # ============================================================
    
    def save_return_tracking(self, tracking_date: str, tracking_time: str, 
                            total_value: float, total_cost: float,
                            total_return_pct: float, daily_return_pct: float,
                            benchmark_return_pct: float = None,
                            attribution_data: dict = None,
                            quant_metrics: dict = None) -> int:
        """
        保存收益跟踪数据
        
        Args:
            tracking_date: 跟踪日期
            tracking_time: 跟踪时间 ('midday', 'close')
            total_value: 总市值
            total_cost: 总成本
            total_return_pct: 总收益率
            daily_return_pct: 日收益率
            benchmark_return_pct: 基准收益率
            attribution_data: 归因分析数据
            quant_metrics: 量化指标数据（波动率、夏普率等）
            
        Returns:
            新记录ID
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO return_tracking 
            (tracking_date, tracking_time, total_value, total_cost, 
             total_return_pct, daily_return_pct, benchmark_return_pct, attribution_data, quant_metrics)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tracking_date, tracking_time, total_value, total_cost,
            total_return_pct, daily_return_pct, benchmark_return_pct,
            json.dumps(attribution_data) if attribution_data else None,
            json.dumps(quant_metrics) if quant_metrics else None
        ))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_return_tracking(self, tracking_date: str = None, 
                           tracking_time: str = None, limit: int = 30) -> List[Dict[str, Any]]:
        """
        获取收益跟踪数据
        
        Args:
            tracking_date: 跟踪日期
            tracking_time: 跟踪时间
            limit: 返回记录数限制
            
        Returns:
            收益跟踪列表
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM return_tracking"
        params = []
        conditions = []
        
        if tracking_date:
            conditions.append("tracking_date = ?")
            params.append(tracking_date)
        if tracking_time:
            conditions.append("tracking_time = ?")
            params.append(tracking_time)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY tracking_date DESC, tracking_time DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get('attribution_data'):
                data['attribution_data'] = json.loads(data['attribution_data'])
            results.append(data)
        
        return results
    
    # ============================================================
    # 投资报告方法
    # ============================================================
    
    def save_investment_report(self, report_date: str, report_type: str,
                              content: str, summary: str = None) -> int:
        """
        保存投资报告
        
        Args:
            report_date: 报告日期
            report_type: 报告类型 ('midday', 'daily', 'weekly')
            content: 报告内容
            summary: 报告摘要
            
        Returns:
            新记录ID
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO investment_reports 
            (report_date, report_type, content, summary)
            VALUES (?, ?, ?, ?)
        ''', (report_date, report_type, content, summary))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_investment_report(self, report_date: str, report_type: str) -> Optional[Dict[str, Any]]:
        """
        获取投资报告
        
        Args:
            report_date: 报告日期
            report_type: 报告类型
            
        Returns:
            报告内容
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM investment_reports 
            WHERE report_date = ? AND report_type = ?
        ''', (report_date, report_type))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_latest_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最新的投资报告
        
        Args:
            limit: 返回记录数限制
            
        Returns:
            报告列表
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM investment_reports 
            ORDER BY report_date DESC, created_at DESC LIMIT ?
        ''', (limit,))
        
        reports = []
        for row in cursor.fetchall():
            reports.append(dict(row))
        
        return reports
    
    def close(self):
        """关闭数据库连接"""
        self._close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================================
# 便捷函数
# ============================================================

def get_db(db_path: Optional[str] = None) -> QuantDatabase:
    """获取数据库连接"""
    return QuantDatabase(db_path)



