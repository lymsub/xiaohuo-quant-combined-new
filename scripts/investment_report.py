#!/usr/bin/env python3
"""
高客秘书 - 投资报告生成模块
结合收益跟踪、归因分析、财经资讯，生成当日投资报告
"""

import os
import sys
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

try:
    import pandas as pd
    import numpy as np
except ImportError:
    print("错误：缺少必要的依赖。请运行：pip install pandas numpy")
    sys.exit(1)

from database import QuantDatabase, get_db
from portfolio_manager import PortfolioManager, get_portfolio_manager, format_portfolio_table
from return_tracker import ReturnTracker, get_return_tracker, format_return_report
from data_source import DataSourceManager


class InvestmentReportGenerator:
    """投资报告生成器"""
    
    def __init__(self, db: QuantDatabase = None,
                 portfolio_manager: PortfolioManager = None,
                 return_tracker: ReturnTracker = None,
                 data_source: DataSourceManager = None):
        """
        初始化报告生成器
        
        Args:
            db: 数据库连接
            portfolio_manager: 持仓管理器
            return_tracker: 收益跟踪器
            data_source: 数据源管理器
        """
        self.db = db or get_db()
        self.portfolio_manager = portfolio_manager or get_portfolio_manager()
        self.return_tracker = return_tracker or get_return_tracker()
        
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
    
    def generate_daily_report(self) -> Dict[str, Any]:
        """
        生成每日投资报告
        
        Returns:
            报告内容
        """
        today = date.today().strftime('%Y-%m-%d')
        
        # 1. 获取持仓数据
        portfolio = self.portfolio_manager.list_portfolio(status='holding')
        
        # 2. 获取收益跟踪数据
        return_data = self.return_tracker.track_return(tracking_time='close')
        
        # 3. 获取相关财经资讯
        news = self._get_relevant_news(portfolio)
        
        # 4. 生成市场点评
        market_commentary = self._generate_market_commentary(return_data, portfolio)
        
        # 5. 生成操作建议
        recommendations = self._generate_recommendations(portfolio, return_data)
        
        # 6. 组合报告
        report_content = {
            "date": today,
            "report_type": "daily",
            "portfolio": portfolio,
            "return_tracking": return_data,
            "news": news,
            "market_commentary": market_commentary,
            "recommendations": recommendations
        }
        
        # 7. 保存到数据库
        report_json = json.dumps(report_content, ensure_ascii=False)
        summary = self._generate_summary(report_content)
        
        self.db.save_investment_report(
            report_date=today,
            report_type="daily",
            content=report_json,
            summary=summary
        )
        
        return report_content
    
    def generate_midday_report(self) -> Dict[str, Any]:
        """
        生成午间报告
        
        Returns:
            报告内容
        """
        today = date.today().strftime('%Y-%m-%d')
        
        # 1. 获取持仓数据
        portfolio = self.portfolio_manager.list_portfolio(status='holding')
        
        # 2. 获取收益跟踪数据（午盘）
        return_data = self.return_tracker.track_return(tracking_time='midday')
        
        # 3. 生成简要点评
        commentary = self._generate_midday_commentary(return_data, portfolio)
        
        # 组合报告
        report_content = {
            "date": today,
            "report_type": "midday",
            "portfolio": portfolio,
            "return_tracking": return_data,
            "commentary": commentary
        }
        
        # 保存到数据库
        report_json = json.dumps(report_content, ensure_ascii=False)
        summary = f"{today} 午盘报告：收益 {return_data['daily_return_pct']:+.2f}%"
        
        self.db.save_investment_report(
            report_date=today,
            report_type="midday",
            content=report_json,
            summary=summary
        )
        
        return report_content
    
    def _get_relevant_news(self, portfolio: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        获取持仓相关的财经资讯
        
        Args:
            portfolio: 持仓数据
            
        Returns:
            相关新闻列表
        """
        # 简化实现 - 实际生产环境应对接新闻API
        # 这里返回一些示例数据
        
        positions = portfolio['positions']
        if not positions:
            return []
        
        news = []
        
        # 为每只持仓股票生成一条相关新闻（示例）
        for pos in positions[:3]:  # 只取前3只
            news.append({
                "title": f"{pos['name']}：{self._get_random_news_title()}",
                "source": "财经资讯",
                "time": date.today().strftime('%Y-%m-%d'),
                "relevance": "高",
                "related_stock": pos['ts_code'],
                "summary": self._get_random_news_summary()
            })
        
        # 添加市场新闻
        news.append({
            "title": "今日股市概览：市场整体表现",
            "source": "市场分析",
            "time": date.today().strftime('%Y-%m-%d'),
            "relevance": "中",
            "related_stock": None,
            "summary": "今日市场整体呈现震荡态势，板块轮动明显。"
        })
        
        return news
    
    def _generate_market_commentary(self, return_data: Dict[str, Any], 
                                   portfolio: Dict[str, Any]) -> str:
        """
        生成市场点评
        
        Args:
            return_data: 收益数据
            portfolio: 持仓数据
            
        Returns:
            市场点评
        """
        commentary = []
        
        daily_return = return_data['daily_return_pct']
        total_return = return_data['total_return_pct']
        
        # 收益情况分析
        if daily_return >= 0:
            commentary.append(f"📈 今日表现：账户盈利 {daily_return:+.2f}%，整体表现稳健。")
        else:
            commentary.append(f"📉 今日表现：账户回撤 {daily_return:+.2f}%，属于正常波动范围。")
        
        commentary.append(f"📊 累计收益：{total_return:+.2f}%，{'表现优秀' if total_return >= 10 else '稳步增长' if total_return >= 0 else '需要关注'}。")
        
        # 持仓分析
        positions = portfolio['positions']
        if positions:
            profit_count = sum(1 for p in positions if p.get('profit', 0) >= 0)
            commentary.append(f"🎯 持仓质量：{profit_count}/{len(positions)} 只股票盈利，胜率 {profit_count/len(positions)*100:.1f}%。")
            
            # 最大贡献者
            attribution = return_data.get('attribution', {})
            if attribution.get('top_contributor'):
                top = attribution['top_contributor']
                commentary.append(f"🏆 最大亮点：{top['name']}贡献了主要收益。")
        
        commentary.append("💡 投资观点：保持耐心，关注持仓股票的基本面变化，避免频繁操作。")
        
        return "\n".join(commentary)
    
    def _generate_midday_commentary(self, return_data: Dict[str, Any], 
                                     portfolio: Dict[str, Any]) -> str:
        """
        生成午间点评
        
        Args:
            return_data: 收益数据
            portfolio: 持仓数据
            
        Returns:
            午间点评
        """
        commentary = []
        
        daily_return = return_data['daily_return_pct']
        
        if daily_return >= 0:
            commentary.append(f"🌞 午盘简评：上午时段盈利 {daily_return:+.2f}%，开局不错！")
        else:
            commentary.append(f"☁️ 午盘简评：上午时段回撤 {daily_return:+.2f}%，下午有望回升。")
        
        commentary.append("⏰ 提示：下午关注市场量能变化，若无重大变化，可继续持有。")
        
        return "\n".join(commentary)
    
    def _generate_recommendations(self, portfolio: Dict[str, Any], 
                                 return_data: Dict[str, Any]) -> List[str]:
        """
        生成操作建议
        
        Args:
            portfolio: 持仓数据
            return_data: 收益数据
            
        Returns:
            操作建议列表
        """
        recommendations = []
        
        positions = portfolio['positions']
        
        if not positions:
            recommendations.append("💡 空仓建议：关注今日涨幅榜，寻找优质标的。")
            return recommendations
        
        # 针对持仓的建议
        for pos in positions:
            profit_pct = pos.get('profit_pct', 0)
            
            if profit_pct >= 15:
                recommendations.append(f"🎯 {pos['name']}：已盈利 {profit_pct:.1f}%，可考虑部分止盈。")
            elif profit_pct >= 5:
                recommendations.append(f"✅ {pos['name']}：盈利 {profit_pct:.1f}%，继续持有，设好止盈。")
            elif profit_pct >= -5:
                recommendations.append(f"⏸️ {pos['name']}：小幅波动 {profit_pct:.1f}%，耐心持有。")
            else:
                recommendations.append(f"⚠️ {pos['name']}：回撤 {profit_pct:.1f}%，关注支撑位，考虑是否止损。")
        
        # 通用建议
        recommendations.append("📋 总体策略：多看少动，持有优质标的，避免追涨杀跌。")
        
        return recommendations
    
    def _generate_summary(self, report_content: Dict[str, Any]) -> str:
        """
        生成报告摘要
        
        Args:
            report_content: 报告内容
            
        Returns:
            摘要
        """
        return_data = report_content['return_tracking']
        daily_return = return_data['daily_return_pct']
        total_return = return_data['total_return_pct']
        
        return f"{report_content['date']} 投资报告：日收益 {daily_return:+.2f}%，累计收益 {total_return:+.2f}%"
    
    def _get_random_news_title(self) -> str:
        """获取随机新闻标题（示例用）"""
        titles = [
            "最新公告：业务进展顺利",
            "行业利好：政策支持持续",
            "机构评级：维持买入评级",
            "业绩预告：预计稳定增长",
            "技术突破：新产品发布在即"
        ]
        import random
        return random.choice(titles)
    
    def _get_random_news_summary(self) -> str:
        """获取随机新闻摘要（示例用）"""
        summaries = [
            "公司业务进展顺利，市场前景看好。",
            "行业政策利好，有助于公司长期发展。",
            "机构投资者看好公司未来表现。",
            "业绩稳步增长，基本面良好。",
            "技术创新能力强，产品竞争力提升。"
        ]
        import random
        return random.choice(summaries)


def format_investment_report(report_content: Dict[str, Any]) -> str:
    """
    格式化投资报告
    
    Args:
        report_content: 报告内容
        
    Returns:
        格式化的报告
    """
    output = []
    
    report_type = "午间" if report_content['report_type'] == 'midday' else "每日"
    
    output.append(f"📄 高客秘书 - {report_content['date']} {report_type}投资报告")
    output.append("=" * 100)
    
    # 1. 收益概览
    return_data = report_content['return_tracking']
    output.append(format_return_report(return_data))
    output.append("")
    
    # 2. 持仓情况
    portfolio = report_content['portfolio']
    output.append("📊 持仓详情")
    output.append("-" * 80)
    output.append(format_portfolio_table(portfolio))
    output.append("")
    
    # 3. 市场点评
    if 'market_commentary' in report_content:
        output.append("💭 市场点评")
        output.append("-" * 80)
        output.append(report_content['market_commentary'])
        output.append("")
    
    # 4. 相关资讯
    if 'news' in report_content and report_content['news']:
        output.append("📰 相关资讯")
        output.append("-" * 80)
        for news in report_content['news'][:5]:  # 只显示前5条
            relevance_icon = "🔴" if news['relevance'] == '高' else "🟡"
            output.append(f"{relevance_icon} {news['title']}")
            output.append(f"   来源：{news['source']} | 时间：{news['time']}")
            output.append(f"   {news['summary']}")
            output.append("")
    
    # 5. 操作建议
    if 'recommendations' in report_content:
        output.append("🎯 操作建议")
        output.append("-" * 80)
        for rec in report_content['recommendations']:
            output.append(rec)
        output.append("")
    
    output.append("=" * 100)
    output.append("⚠️ 风险提示：本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。")
    
    return "\n".join(output)


# ============================================================
# 便捷函数
# ============================================================

def get_report_generator() -> InvestmentReportGenerator:
    """获取报告生成器"""
    return InvestmentReportGenerator()



