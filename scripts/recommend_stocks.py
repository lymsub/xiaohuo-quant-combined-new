#!/usr/bin/env python3
"""
高客秘书 - 今日最佳股票推荐核心算法
综合多维度评分，推荐今日最佳股票

评分维度：
1. 涨跌幅（30%）- 涨幅越大越好
2. 成交量（20%）- 放量上涨更健康
3. 成交额（15%）- 资金关注度
4. 技术指标（25%）- MA、MACD、RSI 综合判断
5. 价格位置（10%）- 相对均线位置
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Tuple

sys.path.insert(0, str(Path(__file__).parent))

# 导入配置模块
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


# 检查是否是第一次运行
# 跳过首次运行检查，已手动配置完成
# if _check_first_run():
#     print("\n" + "="*80)
#     print(" " * 20 + "🚀 检测到首次使用，正在运行安装向导...")
#     print("="*80)
#     SetupWizard.run()
#     print("\n" + "="*80)
#     print(" " * 25 + "✅ 安装配置完成！")
#     print("="*80)
    print("\n现在开始推荐股票...\n")

# 确保依赖已安装（已注释，修复Config.ensure_dependencies不存在问题）
# if not Config.ensure_dependencies():
#     sys.exit(1)

# 现在可以安全导入了
import pandas as pd
import numpy as np

from get_today_gainers import get_today_gainers, is_trading_day


class StockRecommender:
    """股票推荐器"""
    
    def __init__(self):
        self.weights = {
            'pct_change': 0.30,      # 涨跌幅权重
            'volume': 0.20,          # 成交量权重
            'amount': 0.15,          # 成交额权重
            'technical': 0.25,       # 技术指标权重
            'price_position': 0.10    # 价格位置权重
        }
    
    def calculate_score(self, stock: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
        """
        计算单只股票的综合评分
        
        Args:
            stock: 股票数据字典
            
        Returns:
            (total_score, dimension_scores) - 总分和各维度评分
        """
        scores = {}
        
        # 1. 涨跌幅评分（0-100分）
        pct_change = self._safe_float(stock.get('change_pct', 0))
        scores['pct_change'] = self._score_pct_change(pct_change)
        
        # 2. 成交量评分（0-100分）
        volume = self._safe_float(stock.get('volume', 0))
        scores['volume'] = self._score_volume(volume)
        
        # 3. 成交额评分（0-100分）
        amount = self._safe_float(stock.get('amount', 0) if 'amount' in stock else 0)
        scores['amount'] = self._score_amount(amount)
        
        # 4. 技术指标评分（0-100分）
        # 如果有详细技术数据，使用技术数据；否则用涨跌幅和成交量估算
        if '技术指标' in stock:
            scores['technical'] = self._score_technical(stock['技术指标'])
        else:
            scores['technical'] = self._score_technical_simple(pct_change, volume)
        
        # 5. 价格位置评分（0-100分）
        # 如果有均线数据，使用均线；否则用估算
        if '均线' in stock:
            latest_price = self._safe_float(stock.get('最新价', 0))
            scores['price_position'] = self._score_price_position(latest_price, stock['均线'])
        else:
            scores['price_position'] = 50  # 中性评分
        
        # 计算加权总分
        total_score = sum(
            scores[dim] * self.weights[dim]
            for dim in self.weights
        )
        
        return total_score, scores
    
    def _safe_float(self, value) -> float:
        """安全转换为float"""
        if value is None:
            return 0.0
        try:
            if isinstance(value, str):
                value = value.replace('%', '').replace(',', '').strip()
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def _score_pct_change(self, pct_change: float) -> float:
        """
        涨跌幅评分
        - 涨幅 > 5%: 100分
        - 涨幅 3-5%: 80-100分
        - 涨幅 1-3%: 60-80分
        - 涨幅 0-1%: 40-60分
        - 跌幅 0-2%: 20-40分
        - 跌幅 > 2%: 0-20分
        """
        if pct_change >= 5:
            return 100
        elif pct_change >= 3:
            return 80 + (pct_change - 3) * 10
        elif pct_change >= 1:
            return 60 + (pct_change - 1) * 10
        elif pct_change >= 0:
            return 40 + pct_change * 20
        elif pct_change >= -2:
            return 40 + pct_change * 10
        else:
            return max(0, 20 + (pct_change + 2) * 10)
    
    def _score_volume(self, volume: float) -> float:
        """
        成交量评分（归一化到0-100）
        使用对数缩放，避免大数值垄断
        """
        if volume <= 0:
            return 0
        
        # 对数缩放
        log_volume = np.log1p(volume)
        
        # 归一化到0-100（假设100万手是很高的成交量）
        max_log_volume = np.log1p(1000000)  # 100万手
        score = (log_volume / max_log_volume) * 100
        
        return min(100, max(0, score))
    
    def _score_amount(self, amount: float) -> float:
        """
        成交额评分（归一化到0-100）
        """
        if amount <= 0:
            return 0
        
        # 对数缩放
        log_amount = np.log1p(amount)
        
        # 归一化到0-100（假设100亿是很高的成交额）
        max_log_amount = np.log1p(1000000)  # 100亿
        score = (log_amount / max_log_amount) * 100
        
        return min(100, max(0, score))
    
    def _score_technical(self, technical: Dict[str, Any]) -> float:
        """
        技术指标评分（基于详细技术数据）
        
        Args:
            technical: 技术指标字典，包含 MA、MACD、RSI 等
        """
        score = 50  # 基础分
        
        # 均线评分
        if '均线' in technical:
            ma = technical['均线']
            latest_price = technical.get('最新价', 0)
            
            # 价格在均线上方加分
            above_count = 0
            for ma_key in ['MA5', 'MA10', 'MA20', 'MA60']:
                if ma_key in ma and latest_price > self._safe_float(ma[ma_key]):
                    above_count += 1
            
            score += above_count * 5
        
        # MACD评分
        if 'MACD' in technical:
            macd = technical['MACD']
            dif = self._safe_float(macd.get('DIF', 0))
            dea = self._safe_float(macd.get('DEA', 0))
            macd_bar = self._safe_float(macd.get('MACD', 0))
            
            # DIF和DEA在零轴上方加分
            if dif > 0:
                score += 5
            if dea > 0:
                score += 5
            
            # MACD柱状线为正加分
            if macd_bar > 0:
                score += 5
            
            # 金叉加分
            if dif > dea and dif > 0:
                score += 10
        
        # RSI评分
        if 'RSI' in technical:
            rsi = self._safe_float(technical.get('RSI', 50))
            
            # RSI在30-70之间是健康的
            if 30 <= rsi <= 70:
                score += 5
            # RSI在50-60之间偏强但不超买
            elif 50 <= rsi <= 60:
                score += 10
        
        return min(100, max(0, score))
    
    def _score_technical_simple(self, pct_change: float, volume: float) -> float:
        """
        技术指标评分（简化版，基于涨跌幅和成交量估算）
        """
        score = 50
        
        # 放量上涨加分
        if pct_change > 0 and volume > 0:
            score += min(20, pct_change * 2 + volume * 0.0001)
        
        # 大涨但不放量减分
        elif pct_change > 3 and volume < 10000:
            score -= 10
        
        return min(100, max(0, score))
    
    def _score_price_position(self, latest_price: float, ma_data: Dict[str, float]) -> float:
        """
        价格位置评分（基于均线位置）
        """
        if latest_price <= 0:
            return 50
        
        score = 50
        
        # 计算在均线上方的数量
        above_count = 0
        total_count = 0
        
        for ma_key in ['MA5', 'MA10', 'MA20', 'MA60']:
            if ma_key in ma_data:
                total_count += 1
                ma_value = self._safe_float(ma_data[ma_key])
                if ma_value > 0 and latest_price > ma_value:
                    above_count += 1
        
        if total_count > 0:
            # 在均线上方的比例
            ratio = above_count / total_count
            score += ratio * 40  # 最高加40分
        
        return min(100, max(0, score))
    
    def recommend(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        推荐今日最佳股票
        
        Args:
            n: 推荐数量
            
        Returns:
            推荐的股票列表，按评分降序排列
        """
        # 检查是否是交易日
        is_trading, message = is_trading_day()
        if not is_trading:
            print(f"⚠️  {message}")
            print("返回最近一个交易日的数据...")
        
        # 获取今日涨幅榜（自动复用缓存，无需重复拉取）
        print("📊 正在获取今日涨幅榜（优先读取缓存）...")
        df = get_today_gainers(n=50)  # 先获取50只，再从中筛选，自动使用缓存
        
        if df is None or df.empty:
            print("❌  获取涨幅榜失败，请检查网络连接或数据源配置...")
            return []
        
        # 计算每只股票的评分
        print("🔢 正在计算股票评分...")
        scored_stocks = []
        
        for _, row in df.iterrows():
            stock = row.to_dict()
            
            # 计算评分
            total_score, dimension_scores = self.calculate_score(stock)
            
            scored_stocks.append({
                '排名': len(scored_stocks) + 1,
                '股票代码': stock.get('code', ''),
                '股票名称': stock.get('name', ''),
                '最新价': stock.get('price', 0),
                '涨跌幅': stock.get('change_pct', 0),
                '成交量': stock.get('volume', 0),
                '成交额': stock.get('amount', 0) if 'amount' in stock else 0,
                '综合评分': round(total_score, 2),
                '各维度评分': {
                    '涨跌幅': round(dimension_scores['pct_change'], 2),
                    '成交量': round(dimension_scores['volume'], 2),
                    '成交额': round(dimension_scores['amount'], 2),
                    '技术指标': round(dimension_scores['technical'], 2),
                    '价格位置': round(dimension_scores['price_position'], 2)
                }
            })
        
        # 按综合评分降序排列
        scored_stocks.sort(key=lambda x: x['综合评分'], reverse=True)
        
        # 返回前n只
        return scored_stocks[:n]


def print_recommendations(recommendations: List[Dict[str, Any]]):
    """格式化打印推荐结果"""
    if not recommendations:
        print("\n" + "="*100)
        print(" " * 35 + "❌ 获取股票推荐失败")
        print("="*100)
        print("\n请检查网络连接或数据源配置...")
        print("="*100 + "\n")
        return
    
    # 检查是否是交易日
    is_trading, message = is_trading_day()
    
    print("\n" + "="*100)
    if is_trading:
        print(" " * 35 + "🔥 今日最佳股票推荐")
    else:
        print(" " * 30 + "🔥 最近一个交易日股票推荐")
    print("="*100)
    print(f"\n📅 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 推荐数量: {len(recommendations)} 只")
    if not is_trading:
        print(f"📌 说明: {message}")
    print("\n" + "-"*100)
    
    # 打印表头
    print(f"{'排名':<4} {'股票代码':<10} {'股票名称':<10} {'最新价':<10} {'涨跌幅':<10} {'成交量':<12} {'成交额':<12} {'综合评分':<10}")
    print("-"*100)
    
    # 打印每只股票
    for stock in recommendations:
        pct_str = f"{stock['涨跌幅']:.2f}%"
        volume_str = stock['成交量'] if stock['成交量'] != '-' else '0'
        amount_str = f"{stock['成交额']:,.0f}"
        
        # 根据涨跌幅添加颜色标记
        pct_display = f"🟢 {pct_str}" if stock['涨跌幅'] >= 0 else f"🔴 {pct_str}"
        
        print(f"{stock['排名']:<4} {stock['股票代码']:<10} {stock['股票名称']:<10} "
              f"{stock['最新价']:<10.2f} {pct_display:<15} {volume_str:<12} {amount_str:<12} {stock['综合评分']:<10.2f}")
    
    print("-"*100)
    print("\n📝 评分说明:")
    print("  • 综合评分 = 涨跌幅(30%) + 成交量(20%) + 成交额(15%) + 技术指标(25%) + 价格位置(10%)")
    print("  • 评分范围: 0-100分，越高越好")
    print("  • 仅供参考，不构成投资建议")
    print("="*100 + "\n")


def save_recommendations(recommendations: List[Dict[str, Any]], output_file: str = None):
    """保存推荐结果到JSON文件"""
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"recommendations_{timestamp}.json"
    
    result = {
        '生成时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '推荐数量': len(recommendations),
        '推荐列表': recommendations
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"💾 推荐结果已保存到: {output_file}")
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description='高客秘书 - 今日最佳股票推荐',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python recommend_stocks.py                    # 推荐前10只（文本模式）
  python recommend_stocks.py --n 20            # 推荐前20只
  python recommend_stocks.py --output rec.json  # 保存到指定文件（文本模式）
  python recommend_stocks.py --output json     # 输出JSON格式
  python recommend_stocks.py --output json --output-file rec.json  # 保存JSON到文件
        """
    )
    
    parser.add_argument('--n', type=int, default=5, 
                        help='推荐数量（默认5只）')
    parser.add_argument('--output', type=str, 
                        help='输出方式（默认文本，json为JSON格式）')
    parser.add_argument('--output-file', type=str, 
                        help='JSON输出文件路径')
    
    args = parser.parse_args()
    
    # 创建推荐器
    recommender = StockRecommender()
    
    # 获取推荐
    recommendations = recommender.recommend(n=args.n)
    
    # 检查是否是交易日
    is_trading, message = is_trading_day()
    
    # JSON输出模式
    if args.output == 'json':
        # 构建标准化JSON
        if not recommendations:
            result = {
                'success': False,
                'error': '获取股票推荐失败，请检查网络连接或数据源配置',
                'metadata': {
                    'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
        else:
            result = {
                'success': True,
                'report_type': 'opportunity_scan',
                'template_name': 'opportunity_scan',
                'data': {
                    '日期': datetime.now().strftime('%Y-%m-%d'),
                    'is_trading': is_trading,
                    'data_source_date': datetime.now().strftime('%Y-%m-%d') if is_trading 
                                   else (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                    '推荐列表': recommendations
                },
                'metadata': {
                    'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'data_source': '新浪财经 + 本地缓存',
                    'cached': True
                }
            }
        
        output_json = json.dumps(result, ensure_ascii=False, indent=2)
        
        if args.output_file:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                f.write(output_json)
            print(f"✅ 推荐结果已保存到: {args.output_file}")
        
        print(output_json)
        return
    
    # 兼容旧的文本模式
    print_recommendations(recommendations)
    
    # 保存结果
    if args.output and recommendations:
        save_recommendations(recommendations, args.output)
    elif recommendations:
        save_recommendations(recommendations)


if __name__ == '__main__':
    import argparse
    main()
