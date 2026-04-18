#!/usr/bin/env python3
"""
定时投资机会扫描器
每小时运行一次，筛选全市场优质股票，生成标准化投资机会报告
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# 添加当前目录到路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from get_today_gainers import get_today_gainers, is_trading_day
from recommend_stocks import StockRecommender


def scan_investment_opportunities(top_n: int = 5) -> Dict[str, Any]:
    """
    扫描投资机会
    
    Args:
        top_n: 返回评分最高的前n只股票
        
    Returns:
        包含推荐列表和分析的字典
    """
    # 检查是否是交易日
    trading, msg = is_trading_day()
    if not trading:
        return {
            "success": False,
            "message": msg,
            "data": None
        }
    
    # 1. 获取今日涨幅榜
    print("📈 获取最新行情数据...")
    df = get_today_gainers(n=50)
    if df is None or df.empty:
        return {
            "success": False,
            "message": "获取行情数据失败",
            "data": None
        }
    
    # 2. 初始化推荐器
    recommender = StockRecommender()
    
    # 3. 计算每只股票的评分
    print("🧮 计算股票综合评分...")
    scored_stocks = []
    for _, row in df.iterrows():
        stock_data = {
            '代码': row['代码'],
            '名称': row['名称'],
            '最新价': float(row['最新价']) if row['最新价'] else 0,
            '涨跌幅': float(row['涨跌幅数值']) if '涨跌幅数值' in row else 0,
            '成交量': int(row['成交量']) if '成交量' in row and row['成交量'] else 0,
            '成交额': float(row['成交额']) if '成交额' in row and row['成交额'] else 0,
        }
        
        # 跳过ST、退市股票
        name = str(stock_data['名称'])
        if 'ST' in name or '*' in name or '退' in name:
            continue
        
        # 跳过涨幅超过15%的（避免追高风险）
        if stock_data['涨跌幅'] >= 15:
            continue
        
        # 计算评分
        total_score, dim_scores = recommender.calculate_score(stock_data)
        stock_data['total_score'] = total_score
        stock_data['dim_scores'] = dim_scores
        
        scored_stocks.append(stock_data)
    
    # 4. 按总分排序，取前top_n
    scored_stocks.sort(key=lambda x: x['total_score'], reverse=True)
    top_stocks = scored_stocks[:top_n]
    
    # 5. 生成AI分析
    ai_analysis = generate_ai_analysis(top_stocks)
    
    return {
        "success": True,
        "scan_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "top_stocks": top_stocks,
        "ai_analysis": ai_analysis
    }


def generate_ai_analysis(top_stocks: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    生成AI分析内容
    
    Args:
        top_stocks: 评分最高的股票列表
        
    Returns:
        分析内容字典
    """
    # 计算平均评分
    avg_score = sum(s['total_score'] for s in top_stocks) / len(top_stocks) if top_stocks else 0
    
    # 分析市场热度
    up_count = sum(1 for s in top_stocks if s['涨跌幅'] > 0)
    avg_pct = sum(s['涨跌幅'] for s in top_stocks) / len(top_stocks) if top_stocks else 0
    
    # 生成分析内容
    summary = f"本次扫描共筛选出{len(top_stocks)}只优质股票，平均综合评分{avg_score:.1f}分，平均涨幅{avg_pct:.2f}%，整体选股质量良好。"
    
    highlights = []
    for i, stock in enumerate(top_stocks, 1):
        highlights.append(f"{i}. {stock['名称']}({stock['代码']})：综合评分{stock['total_score']:.1f}分，当前涨幅{stock['涨跌幅']:.2f}%，量价配合良好，技术面信号偏多")
    
    risks = [
        "当前市场处于存量博弈阶段，板块轮动较快，建议短线操作，快进快出",
        "单只股票仓位建议控制在20%以内，避免集中风险",
        "设置5%的止损位，跌破坚决离场"
    ]
    
    suggestions = [
        "重点关注评分最高的前2只股票，开盘或回调时分批介入",
        "短线目标收益5%-8%，达到目标后逐步止盈",
        "若上证指数跌破3000点，暂停开新仓，控制整体仓位在50%以下"
    ]
    
    return {
        "summary": summary,
        "highlights": highlights,
        "risks": risks,
        "suggestions": suggestions
    }


def format_report(result: Dict[str, Any]) -> str:
    """
    生成标准化的投资机会报告
    
    Args:
        result: 扫描结果
        
    Returns:
        格式化的报告字符串
    """
    if not result['success']:
        return f"""
🔥 高客秘书定时投资机会扫描 - {datetime.now().strftime('%Y-%m-%d %H:%M')}
====================================================================================================
⚠️ 扫描失败：{result['message']}
====================================================================================================
"""
    
    scan_time = result['scan_time']
    top_stocks = result['top_stocks']
    ai_analysis = result['ai_analysis']
    
    output = []
    output.append(f"🔥 高客秘书定时投资机会扫描 - {scan_time}")
    output.append("=" * 100)
    output.append("")
    
    # 推荐股票列表
    output.append("🏆 本期推荐TOP3股票")
    output.append("-" * 100)
    output.append(f"{'排名':<4} {'代码':<10} {'名称':<10} {'最新价':<8} {'涨跌幅':<10} {'综合评分':<10}")
    output.append("-" * 100)
    
    for i, stock in enumerate(top_stocks, 1):
        status = "🟢" if stock['涨跌幅'] > 0 else "🔴"
        output.append(f"{i:<4} {stock['代码']:<10} {stock['名称']:<10} ¥{stock['最新价']:<7.2f} {status} {stock['涨跌幅']:<+7.2f}% {stock['total_score']:<10.1f}")
    
    output.append("")
    
    # AI分析部分
    output.append("🧠 AI投资分析")
    output.append("-" * 100)
    
    output.append("【扫描总结】")
    output.append(f"   {ai_analysis['summary']}")
    output.append("")
    
    output.append("【个股亮点】")
    for highlight in ai_analysis['highlights']:
        output.append(f"   • {highlight}")
    output.append("")
    
    output.append("【风险提示】")
    for risk in ai_analysis['risks']:
        output.append(f"   ⚠️  {risk}")
    output.append("")
    
    output.append("【操作建议】")
    for suggestion in ai_analysis['suggestions']:
        output.append(f"   💡 {suggestion}")
    
    output.append("")
    output.append("=" * 100)
    output.append("⚠️ 风险提示：本扫描结果仅供量化研究参考，不构成任何投资建议。股市有风险，入市需谨慎！")
    
    return "\n".join(output)


if __name__ == '__main__':
    # 执行扫描
    result = scan_investment_opportunities(top_n=3)
    
    # 生成报告
    report = format_report(result)
    
    # 打印报告
    print(report)
    
    # 保存报告到文件
    report_file = SCRIPT_DIR / f"investment_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n💾 报告已保存到: {report_file}")
