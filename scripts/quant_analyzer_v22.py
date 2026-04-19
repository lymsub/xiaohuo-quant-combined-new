#!/usr/bin/env python3
"""
商业量化分析系统 v2.5
- 数据源：SQLite 本地数据库 + (Tushare Pro ↔ AkShare) 双数据源互补
- 策略：双均线交叉、MACD金叉死叉、RSI超买超卖
- 功能：技术分析 + 回测引擎
- 优化：优先使用本地数据库，双数据源自动互补，提升速度和稳定性
- 新特性：首次使用自动运行完整安装向导，用户无感知

使用方法:
    python quant_analyzer_v22.py --code 300919 --days 90
    python quant_analyzer_v22.py --code 300919 --token your_token
    python quant_analyzer_v22.py --code 300919 --source tushare  # 指定Tushare
    python quant_analyzer_v22.py --code 300919 --source akshare  # 指定AkShare
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from pathlib import Path

# 导入配置模块
sys.path.insert(0, str(Path(__file__).parent))
from config import Config, SetupWizard


def _check_first_run() -> bool:
    """
    检查是否是第一次运行
    
    Returns:
        是否是第一次运行
    """
    # 检查配置目录是否存在
    if not Config.CONFIG_DIR.exists():
        return True
    
    # 检查是否有任何配置文件
    config_files = [
        Config.TOKEN_FILE,
        Config.TOKEN_ENV_FILE,
        Config.DB_FILE,
    ]
    
    # 如果所有配置文件都不存在，认为是第一次运行
    all_missing = all(not f.exists() for f in config_files)
    return all_missing


# 检查是否是第一次运行（已注释，修复SetupWizard.run不存在问题）
# if _check_first_run():
#     print("\n" + "="*80)
#     print(" " * 20 + "🚀 检测到首次使用，正在运行安装向导...")
#     print("="*80)
#     SetupWizard.run()
#     print("\n" + "="*80)
#     print(" " * 25 + "✅ 安装配置完成！")
#     print("="*80)
#     print("\n现在开始分析股票...\n")

# 确保依赖已安装（已注释，修复Config.ensure_dependencies不存在问题）
# if not Config.ensure_dependencies():
#     sys.exit(1)

# 现在可以安全导入了
import pandas as pd
import numpy as np

# 导入双数据源管理器
try:
    from data_source import DataSourceManager, get_data_manager
    DATA_SOURCE_MANAGER_AVAILABLE = True
except ImportError:
    DATA_SOURCE_MANAGER_AVAILABLE = False
    print("⚠️  双数据源管理器不可用，将使用传统方式")
    try:
        import tushare as ts
    except ImportError:
        print("错误：缺少 tushare。请运行：pip install tushare")
        sys.exit(1)

# 导入数据库模块
try:
    from database import QuantDatabase
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    print("⚠️  数据库模块不可用，将仅使用 API")


# ============================================================
# 1. 数据获取模块（支持三数据源：数据库 + Tushare + AkShare 互补
# ============================================================

class UnifiedDataSource:
    """统一数据源管理器：SQLite 本地数据库 + (Tushare ↔ AkShare) 双数据源互补"""
    
    def __init__(self, token: str, use_database: bool = True, 
                 force_source: Optional[str] = None,
                 preferred_source: str = 'tushare',
                 enable_fallback: bool = True):
        """
        初始化统一数据源
        
        Args:
            token: Tushare Token
            use_database: 是否使用本地数据库
            force_source: 强制使用指定数据源 ('tushare'/'akshare'/None)
            preferred_source: 首选数据源 ('tushare'/'akshare')
            enable_fallback: 是否启用备用数据源
        """
        self.token = token
        self.use_database = use_database and DATABASE_AVAILABLE
        self.force_source = force_source
        self.preferred_source = preferred_source
        self.enable_fallback = enable_fallback
        
        # 初始化数据库
        self.db = None
        if self.use_database:
            try:
                self.db = QuantDatabase()
                print("📊 使用本地数据库作为优先数据源")
            except Exception as e:
                print(f"⚠️  数据库初始化失败，将不使用数据库: {e}")
                self.use_database = False
        
        # 初始化双数据源管理器
        self.data_mgr = None
        self.using_data_mgr = False
        self.pro = None
        
        if DATA_SOURCE_MANAGER_AVAILABLE:
            try:
                self.data_mgr = get_data_manager(
                    token, 
                    enable_fallback=enable_fallback,
                    retry_count=2,
                    retry_delay=0.5
                )
                self.using_data_mgr = True
                print("🔄 四数据源管理器已启用（新浪/腾讯/Tushare/AkShare自动互补）")
            except Exception as e:
                print(f"⚠️  四数据源管理器初始化失败: {e}")
                self.using_data_mgr = False
                # 降级到传统 Tushare 方式
                import tushare as ts
                ts.set_token(token)
                self.pro = ts.pro_api()
        else:
            self.using_data_mgr = False
            import tushare as ts
            ts.set_token(token)
            self.pro = ts.pro_api()
    
    def get_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取日线数据（优先从数据库获取，没有则从双数据源获取并缓存
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
        """
        # 格式化日期
        def format_date(s: str) -> str:
            if len(s) == 8:
                return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
            return s
        
        start_formatted = format_date(start_date)
        end_formatted = format_date(end_date)
        
        # 智能获取最近交易日（避免周末/节假日导致查询失败）
        from datetime import datetime, timedelta
        def get_latest_trading_day():
            today = datetime.now().date()
            check_date = today
            for i in range(7):
                if check_date.weekday() >= 5:
                    check_date = check_date - timedelta(days=1)
                    continue
                return check_date
            return today
        
        latest_trading_day = get_latest_trading_day()
        latest_trading_day_str = latest_trading_day.strftime('%Y-%m-%d')
        
        # 调整 end_date 到最近交易日（避免周末/节假日问题）
        if end_formatted > latest_trading_day_str:
            print(f"ℹ️  调整查询结束日期: {end_formatted} → {latest_trading_day_str}（最近交易日）")
            end_formatted = latest_trading_day_str
        
        # 尝试从数据库获取
        if self.use_database and self.db:
            try:
                print(f"🔍 从数据库查询 {ts_code} ({start_formatted} 至 {end_formatted})...")
                df_db = self.db.get_daily_quotes(ts_code, start_formatted, end_formatted)
                
                if df_db is not None and not df_db.empty:
                    # 检查数据覆盖范围
                    db_start = df_db['trade_date'].min().strftime('%Y-%m-%d')
                    db_end = df_db['trade_date'].max().strftime('%Y-%m-%d')
                    print(f"✅ 数据库中有数据: {db_start} 至 {db_end}")
                    
                    # 灵活判断：只要数据库中已经有数据，并且覆盖了我们需要的开始日期就用
                    # 不要求 db_end 必须等于 end_formatted（因为可能是周末/节假日）
                    if db_start <= start_formatted:
                        print("📊 使用数据库数据")
                        return df_db
                    else:
                        print("⚠️  数据库数据不完整，将从 API 补充")
            except Exception as e:
                print(f"⚠️  数据库查询失败: {e}")
        
        # 从数据源获取
        df = None
        source_used = None
        
        if self.using_data_mgr and self.data_mgr:
            # 使用双数据源管理器
            try:
                print(f"🌐 从双数据源管理器获取 {ts_code} 数据...")
                df, source_used = self.data_mgr.get_daily_quotes(
                    ts_code, start_date, end_date, 
                    source=self.force_source
                )
                print(f"✅ 从 {source_used} 获取了 {len(df)} 条数据")
            except Exception as e:
                print(f"⚠️  双数据源管理器失败: {e}")
                # 降级
                if self.force_source != 'akshare' and self.pro:
                    print(f"🌐 从 Tushare API 获取 {ts_code} 数据...")
                    df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                    source_used = 'tushare (fallback)'
        elif self.pro:
            # 传统方式
            print(f"🌐 从 Tushare API 获取 {ts_code} 数据...")
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            source_used = 'tushare'
        
        if df is not None and not df.empty:
            # 确保 trade_date 列格式正确
            if 'trade_date' in df.columns:
                if not pd.api.types.is_datetime64_any_dtype(df['trade_date']):
                    # 尝试自动解析
                    try:
                        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
                    except:
                        try:
                            df['trade_date'] = pd.to_datetime(df['trade_date'])
                        except:
                            pass
            elif 'date' in df.columns:
                # AkShare 格式
                df = df.rename(columns={'date': 'trade_date'})
                if not pd.api.types.is_datetime64_any_dtype(df['trade_date']):
                    df['trade_date'] = pd.to_datetime(df['trade_date'])
            
            # 保存到数据库（如果启用）
            if self.use_database and self.db:
                try:
                    print(f"💾 保存数据到数据库...")
                    count = self.db.save_daily_quotes(ts_code, df)
                    print(f"✅ 保存了 {count} 条数据")
                except Exception as e:
                    print(f"⚠️  保存到数据库失败: {e}")
        
        return df
    
    def get_stock_basic(self, ts_code: str) -> str:
        """
        获取股票名称（优先从数据库获取）
        """
        # 尝试从数据库获取
        if self.use_database and self.db:
            try:
                df = self.db.get_stock_basic(ts_code)
                if df is not None and not df.empty:
                    return df.iloc[0]['name']
            except Exception as e:
                print(f"⚠️  从数据库获取股票信息失败: {e}")
        
        # 尝试从数据源获取
        if self.using_data_mgr and self.data_mgr:
            try:
                df, _ = self.data_mgr.get_stock_list(source=self.force_source)
                if df is not None and not df.empty:
                    match = df[df['ts_code'] == ts_code]
                    if not match.empty:
                        return match.iloc[0]['name']
            except Exception as e:
                print(f"⚠️  从数据源获取股票信息失败: {e}")
        
        # 从 Tushare API 获取（兜底）
        try:
            if self.pro:
                df = self.pro.stock_basic(ts_code=ts_code)
                if df is not None and not df.empty:
                    return df.iloc[0]['name']
        except:
            pass
        return "未知"
    
    def close(self):
        """关闭数据库连接"""
        if self.db:
            try:
                self.db.close()
            except:
                pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================================
# 2. 技术指标计算模块
# ============================================================

class TechnicalIndicators:
    """技术指标计算"""
    
    @staticmethod
    def sma(close: pd.Series, n: int) -> pd.Series:
        """简单移动平均线"""
        return close.rolling(window=n, min_periods=1).mean()
    
    @staticmethod
    def ema(close: pd.Series, n: int) -> pd.Series:
        """指数移动平均线"""
        return close.ewm(span=n, adjust=False).mean()
    
    @staticmethod
    def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD指标：返回 DIF, DEA, MACD柱状线"""
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd_hist = dif - dea
        return dif, dea, macd_hist
    
    @staticmethod
    def rsi(close: pd.Series, n: int = 14) -> pd.Series:
        """RSI相对强弱指标"""
        diff = close.diff(1)
        gain = diff.where(diff > 0, 0)
        loss = -diff.where(diff < 0, 0)
        avg_gain = gain.rolling(window=n, min_periods=1).mean()
        avg_loss = loss.rolling(window=n, min_periods=1).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi


# ============================================================
# 3. 策略模块
# ============================================================

@dataclass
class Signal:
    """交易信号"""
    date: datetime
    type: str  # 'buy', 'sell', 'hold'
    strategy: str
    price: float
    reason: str


class Strategy:
    """策略基类"""
    
    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        raise NotImplementedError


class DoubleMACrossStrategy(Strategy):
    """双均线交叉策略"""
    
    def __init__(self, fast: int = 5, slow: int = 20):
        self.fast = fast
        self.slow = slow
    
    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        """生成双均线交叉信号"""
        signals = []
        
        # 计算均线
        df['ma_fast'] = df['close'].rolling(self.fast).mean()
        df['ma_slow'] = df['close'].rolling(self.slow).mean()
        
        # 生成信号
        for i in range(1, len(df)):
            curr_fast = df['ma_fast'].iloc[i]
            curr_slow = df['ma_slow'].iloc[i]
            prev_fast = df['ma_fast'].iloc[i-1]
            prev_slow = df['ma_slow'].iloc[i-1]
            
            # 金叉：快线上穿慢线
            if curr_fast > curr_slow and prev_fast <= prev_slow:
                signals.append(Signal(
                    date=df['trade_date'].iloc[i],
                    type='buy',
                    strategy='双均线交叉',
                    price=df['close'].iloc[i],
                    reason=f'MA{self.fast}上穿MA{self.slow}形成金叉'
                ))
            
            # 死叉：快线下穿慢线
            elif curr_fast < curr_slow and prev_fast >= prev_slow:
                signals.append(Signal(
                    date=df['trade_date'].iloc[i],
                    type='sell',
                    strategy='双均线交叉',
                    price=df['close'].iloc[i],
                    reason=f'MA{self.fast}下穿MA{self.slow}形成死叉'
                ))
        
        return signals


class MACDStrategy(Strategy):
    """MACD金叉死叉策略"""
    
    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        """生成MACD信号"""
        signals = []
        
        # 计算MACD
        ti = TechnicalIndicators()
        df['dif'], df['dea'], df['macd_hist'] = ti.macd(df['close'])
        
        # 生成信号
        for i in range(1, len(df)):
            curr_hist = df['macd_hist'].iloc[i]
            prev_hist = df['macd_hist'].iloc[i-1]
            
            # MACD金叉：柱状线由负转正
            if curr_hist > 0 and prev_hist <= 0:
                signals.append(Signal(
                    date=df['trade_date'].iloc[i],
                    type='buy',
                    strategy='MACD金叉死叉',
                    price=df['close'].iloc[i],
                    reason='DIF上穿DEA形成MACD金叉'
                ))
            
            # MACD死叉：柱状线由正转负
            elif curr_hist < 0 and prev_hist >= 0:
                signals.append(Signal(
                    date=df['trade_date'].iloc[i],
                    type='sell',
                    strategy='MACD金叉死叉',
                    price=df['close'].iloc[i],
                    reason='DIF下穿DEA形成MACD死叉'
                ))
        
        return signals


class RSIStrategy(Strategy):
    """RSI超买超卖策略"""
    
    def __init__(self, overbought: int = 70, oversold: int = 30):
        self.overbought = overbought
        self.oversold = oversold
    
    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        """生成RSI信号"""
        signals = []
        
        # 计算RSI
        ti = TechnicalIndicators()
        df['rsi'] = ti.rsi(df['close'])
        
        # 生成信号
        for i in range(1, len(df)):
            curr_rsi = df['rsi'].iloc[i]
            prev_rsi = df['rsi'].iloc[i-1]
            
            # RSI从超卖区上穿30：买入信号
            if curr_rsi > self.oversold and prev_rsi <= self.oversold:
                signals.append(Signal(
                    date=df['trade_date'].iloc[i],
                    type='buy',
                    strategy='RSI超买超卖',
                    price=df['close'].iloc[i],
                    reason=f'RSI从超卖区({prev_rsi:.1f})突破{self.oversold}，买入信号'
                ))
            
            # RSI从超买区下穿70：卖出信号
            elif curr_rsi < self.overbought and prev_rsi >= self.overbought:
                signals.append(Signal(
                    date=df['trade_date'].iloc[i],
                    type='sell',
                    strategy='RSI超买超卖',
                    price=df['close'].iloc[i],
                    reason=f'RSI从超买区({prev_rsi:.1f})跌破{self.overbought}，卖出信号'
                ))
        
        return signals


# ============================================================
# 4. 回测引擎模块
# ============================================================

class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, initial_capital: float = 100000, 
                 commission: float = 0.0003, slippage: float = 0.001):
        self.initial_capital = initial_capital
        self.commission = commission  # 手续费（默认万3）
        self.slippage = slippage  # 滑点
        
        self.cash = initial_capital
        self.position = 0  # 持仓股数
        self.trades = []  # 交易记录
        self.daily_values = []  # 每日资产价值
    
    def run(self, df: pd.DataFrame, signals: List[Signal]) -> dict:
        """运行回测"""
        # 合并信号到数据
        df['signal'] = 'hold'
        for signal in signals:
            idx = df[df['trade_date'] == signal.date].index
            if len(idx) > 0:
                df.loc[idx[0], 'signal'] = signal.type
                df.loc[idx[0], 'signal_price'] = signal.price
        
        # 回测循环
        for i, row in df.iterrows():
            date = row['trade_date']
            price = row['close']
            signal = row['signal']
            
            # 处理交易信号
            if signal == 'buy' and self.cash > 0:
                # 全仓买入
                shares = int(self.cash / (price * (1 + self.commission + self.slippage)))
                if shares > 0:
                    cost = shares * price * (1 + self.commission + self.slippage)
                    self.cash -= cost
                    self.position += shares
                    self.trades.append({
                        'date': date,
                        'type': 'buy',
                        'price': price,
                        'shares': shares,
                        'cost': cost
                    })
            
            elif signal == 'sell' and self.position > 0:
                # 全仓卖出
                revenue = self.position * price * (1 - self.commission - self.slippage)
                self.cash += revenue
                self.trades.append({
                    'date': date,
                    'type': 'sell',
                    'price': price,
                    'shares': self.position,
                    'revenue': revenue
                })
                self.position = 0
            
            # 计算当前资产价值
            total_value = self.cash + self.position * price
            self.daily_values.append({
                'date': date,
                'price': price,
                'cash': self.cash,
                'position': self.position,
                'total_value': total_value
            })
        
        return self._generate_report()
    
    def _generate_report(self) -> dict:
        """生成回测报告"""
        if not self.daily_values:
            return {"error": "没有回测数据"}
        
        df_values = pd.DataFrame(self.daily_values)
        
        # 计算收益率
        final_value = self.daily_values[-1]['total_value']
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100
        
        # 计算最大回撤
        peak = df_values['total_value'].expanding().max()
        drawdown = (df_values['total_value'] - peak) / peak
        max_drawdown = drawdown.min() * 100
        
        # 计算交易统计
        buy_trades = [t for t in self.trades if t['type'] == 'buy']
        sell_trades = [t for t in self.trades if t['type'] == 'sell']
        
        # 胜率计算
        winning_trades = 0
        for i, sell in enumerate(sell_trades):
            if i < len(buy_trades):
                buy = buy_trades[i]
                if sell['price'] > buy['price']:
                    winning_trades += 1
        
        win_rate = (winning_trades / len(sell_trades) * 100) if sell_trades else 0
        
        # 格式化交易记录，确保可以JSON序列化
        formatted_trades = []
        for trade in self.trades[-10:]:
            formatted_trade = {}
            for key, value in trade.items():
                if hasattr(value, 'strftime'):
                    formatted_trade[key] = value.strftime('%Y-%m-%d')
                elif hasattr(value, 'item'):
                    formatted_trade[key] = float(value.item())
                else:
                    formatted_trade[key] = value
            formatted_trades.append(formatted_trade)
        
        return {
            "initial_capital": float(self.initial_capital),
            "final_value": round(float(final_value), 2),
            "total_return_pct": round(float(total_return), 2),
            "max_drawdown_pct": round(float(abs(max_drawdown)), 2),
            "total_trades": int(len(self.trades)),
            "buy_trades": int(len(buy_trades)),
            "sell_trades": int(len(sell_trades)),
            "win_rate_pct": round(float(win_rate), 2),
            "trades": formatted_trades
        }


# ============================================================
# 5. 主分析器类
# ============================================================

class QuantAnalyzer:
    """商业量化分析器"""
    
    def __init__(self, tushare_token: str, use_database: bool = True,
                 force_source: Optional[str] = None,
                 preferred_source: str = 'tushare',
                 enable_fallback: bool = True):
        self.data_source = UnifiedDataSource(
            tushare_token, 
            use_database=use_database,
            force_source=force_source,
            preferred_source=preferred_source,
            enable_fallback=enable_fallback
        )
        self.indicators = TechnicalIndicators()
    
    def analyze(self, ts_code: str, days: int = 90) -> dict:
        """完整分析流程"""
        
        # 1. 获取数据
        # 智能获取最近交易日（避免周末/节假日导致查询失败）
        from datetime import datetime, timedelta
        def get_latest_trading_day():
            today = datetime.now().date()
            check_date = today
            for i in range(7):
                if check_date.weekday() >= 5:
                    check_date = check_date - timedelta(days=1)
                    continue
                return check_date
            return today
        
        latest_trading_day = get_latest_trading_day()
        
        # 使用最近交易日作为结束日期
        end_date = latest_trading_day
        start_date = end_date - timedelta(days=days + 30)
        
        print(f"📅 查询日期范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
        
        df = self.data_source.get_daily(
            ts_code, 
            start_date.strftime('%Y%m%d'),
            end_date.strftime('%Y%m%d')
        )
        
        if df is None or df.empty:
            return {"error": f"无法获取 {ts_code} 的数据"}
        
        # 2. 计算技术指标
        df['ma5'] = self.indicators.sma(df['close'], 5)
        df['ma10'] = self.indicators.sma(df['close'], 10)
        df['ma20'] = self.indicators.sma(df['close'], 20)
        df['ma60'] = self.indicators.sma(df['close'], 60)
        
        df['macd_dif'], df['macd_dea'], df['macd_hist'] = self.indicators.macd(df['close'])
        df['rsi'] = self.indicators.rsi(df['close'])
        
        # 3. 生成策略信号
        strategies = [
            DoubleMACrossStrategy(fast=5, slow=20),
            MACDStrategy(),
            RSIStrategy(overbought=70, oversold=30)
        ]
        
        all_signals = []
        for strategy in strategies:
            signals = strategy.generate_signals(df)
            all_signals.extend(signals)
        
        # 按日期排序
        all_signals.sort(key=lambda x: x.date)
        
        # 4. 运行回测
        backtest = BacktestEngine(
            initial_capital=100000,
            commission=0.0003,
            slippage=0.001
        )
        backtest_result = backtest.run(df, all_signals)
        
        # 5. 获取最新行情
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # 6. 组装报告（确保所有数据都可JSON序列化）
        def format_date(d):
            if hasattr(d, 'strftime'):
                return d.strftime('%Y-%m-%d')
            return str(d)[:10]
        
        def format_value(v):
            if v is None:
                return 0.0
            if hasattr(v, 'item'):
                try:
                    val = float(v.item())
                    return val if val == val else 0.0  # 检查NaN
                except:
                    return 0.0
            elif isinstance(v, (np.integer, np.floating)):
                try:
                    val = float(v)
                    return val if val == val else 0.0  # 检查NaN
                except:
                    return 0.0
            elif isinstance(v, float):
                return v if v == v else 0.0  # 检查NaN
            return v
        
        report = {
            "股票代码": ts_code,
            "股票名称": self.data_source.get_stock_basic(ts_code),
            "分析时间": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "数据范围": f"{format_date(df['trade_date'].min())} 至 {format_date(df['trade_date'].max())}",
            
            "最新行情": {
                "最新价": round(format_value(latest['close']), 2),
                "涨跌额": round(format_value(latest['close'] - prev['close']), 2),
                "涨跌幅": round(format_value((latest['close'] - prev['close']) / prev['close'] * 100), 2),
                "成交量": int(format_value(latest['vol'])) if 'vol' in latest and latest['vol'] is not None and not (isinstance(latest['vol'], float) and latest['vol'] != latest['vol']) else 0,
                "成交额": round(format_value(latest['amount']) / 10000, 2) if 'amount' in latest else None
            },
            
            "技术指标": {
                "均线": {
                    "MA5": round(format_value(latest['ma5']), 2),
                    "MA10": round(format_value(latest['ma10']), 2),
                    "MA20": round(format_value(latest['ma20']), 2),
                    "MA60": round(format_value(latest['ma60']), 2)
                },
                "MACD": {
                    "DIF": round(format_value(latest['macd_dif']), 3),
                    "DEA": round(format_value(latest['macd_dea']), 3),
                    "MACD": round(format_value(latest['macd_hist']), 3)
                },
                "RSI(14)": round(format_value(latest['rsi']), 2)
            },
            
            "策略信号": {
                "信号总数": len(all_signals),
                "买入信号": len([s for s in all_signals if s.type == 'buy']),
                "卖出信号": len([s for s in all_signals if s.type == 'sell']),
                "最近10条信号": [
                    {
                        "日期": format_date(s.date),
                        "类型": "买入" if s.type == 'buy' else "卖出",
                        "策略": s.strategy,
                        "价格": round(format_value(s.price), 2),
                        "原因": s.reason
                    }
                    for s in all_signals[-10:]
                ]
            },
            
            "回测结果": backtest_result
        }
        
        return report
    
    def close(self):
        """关闭数据源"""
        if hasattr(self.data_source, 'close'):
            self.data_source.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================================
# 6. 命令行接口
# ============================================================

def _prompt_for_token() -> Tuple[Optional[str], bool]:
    """
    无感知默认配置：自动使用免费数据源，无需用户交互
    """
    return None, False


def main():
    parser = argparse.ArgumentParser(
        description='商业量化分析系统 v2.2 - 专业级A股量化分析工具（双数据源互补）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python quant_analyzer_v22.py --code 300919
  python quant_analyzer_v22.py --code 600519 --days 180
  python quant_analyzer_v22.py --code 300919 --output result.json
  python quant_analyzer_v22.py --code 300919 --source tushare  # 强制使用Tushare
  python quant_analyzer_v22.py --code 300919 --source akshare  # 强制使用AkShare
        """
    )
    
    parser.add_argument('--code', type=str, required=True, 
                        help='股票代码（如：300919、600519）')
    parser.add_argument('--token', type=str, 
                        help='Tushare Token（也可设置TUSHARE_TOKEN环境变量）')
    parser.add_argument('--days', type=int, default=90, 
                        help='分析天数（默认90天）')
    parser.add_argument('--output', type=str, 
                        help='输出文件路径（JSON格式）')
    parser.add_argument('--source', type=str, choices=['tushare', 'akshare'],
                        help='强制使用指定数据源')
    parser.add_argument('--preferred-source', type=str, choices=['tushare', 'akshare'], 
                        help='首选数据源（如果有配置tushare token则默认tushare）')
    parser.add_argument('--no-fallback', action='store_true',
                        help='禁用备用数据源')
    parser.add_argument('--no-database', action='store_true',
                        help='禁用本地数据库功能')
    
    args = parser.parse_args()
    
    # 读取 custom_config.json
    actual_token = None
    preferred_source = 'akshare'
    custom_config = {}
    try:
        import os
        from pathlib import Path
        script_dir = Path(__file__).parent
        config_path = script_dir.parent / "custom_config.json"
        if config_path.exists():
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                custom_config = json.load(f)
    except Exception as e:
        print(f"⚠️  读取配置文件失败: {e}")
    
    # 如果有 tushare token，优先使用 tushare
    if custom_config and custom_config.get("tushare", {}).get("api_key"):
        actual_token = custom_config["tushare"]["api_key"]
        preferred_source = 'tushare'
        print(f"✅ 已配置Tushare Token，优先使用Tushare数据源")
    else:
        print(f"ℹ️  未配置Tushare Token，使用AkShare数据源")
    
    # 如果命令行指定了首选数据源，以命令行为准
    if args.preferred_source:
        preferred_source = args.preferred_source
    
    # 标准化股票代码
    ts_code = args.code
    if not ts_code.endswith(('.SZ', '.SH', '.BJ')):
        if ts_code.startswith('6'):
            ts_code = ts_code + '.SH'
        elif ts_code.startswith(('8', '4')):
            ts_code = ts_code + '.BJ'
        else:
            ts_code = ts_code + '.SZ'
    
    # 执行分析
    print(f"\n🔍 正在分析 {ts_code}，请稍候...\n")
    
    try:
        with QuantAnalyzer(
            actual_token, 
            use_database=not args.no_database,
            force_source=args.source,
            preferred_source=preferred_source,
            enable_fallback=not args.no_fallback
        ) as analyzer:
            result = analyzer.analyze(ts_code, args.days)
        
        if 'error' in result:
            print(f"❌ 分析失败：{result['error']}")
            sys.exit(1)
        
        # 输出结果（按新架构规范格式化）
        formatted_result = {
            "success": True,
            "report_type": "stock_analysis",
            "template_name": "stock_analysis",
            "data": result,
            "metadata": {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "本地数据库+新浪/腾讯/AkShare",
                "cached": False
            }
        }
        
        output = json.dumps(formatted_result, ensure_ascii=False, indent=2)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"✅ 分析结果已保存到：{args.output}")
        else:
            print("="*80)
            print(" "*30 + "📊 量化分析报告")
            print("="*80)
            print(output)
            print("="*80)
            
    except Exception as e:
        print(f"\n❌ 分析失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
