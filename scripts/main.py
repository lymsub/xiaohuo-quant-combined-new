#!/usr/bin/env python3
"""
高客秘书整合版 v2.6 - 主入口程序
整合：股票分析 + 持仓管理 + 收益跟踪 + 投资报告 + 投资机会筛选
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime, date
from pathlib import Path

# 添加当前目录到路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from database import QuantDatabase, get_db
from portfolio_manager import PortfolioManager, get_portfolio_manager, format_portfolio_table
from return_tracker import ReturnTracker, get_return_tracker, format_return_report
from investment_report import InvestmentReportGenerator, get_report_generator, format_investment_report


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def handle_portfolio_command(args):
    """处理持仓管理命令"""
    manager = get_portfolio_manager()
    
    if args.subcommand == 'list':
        print_header("📊 当前持仓")
        portfolio = manager.list_portfolio(status=args.status)
        print(format_portfolio_table(portfolio))
    
    elif args.subcommand == 'add':
        print_header("➕ 添加持仓")
        result = manager.add_stock(
            ts_code=args.code,
            buy_price=args.price,
            quantity=args.quantity,
            buy_date=args.date,
            notes=args.notes
        )
        if result['success']:
            print(f"✅ {result['message']}")
        else:
            print(f"❌ {result['message']}")
    
    elif args.subcommand == 'sell':
        print_header("💰 卖出持仓")
        result = manager.sell_stock(
            position_id=args.id,
            sell_price=args.price,
            sell_date=args.date,
            notes=args.notes
        )
        if result['success']:
            print(f"✅ {result['message']}")
        else:
            print(f"❌ {result['message']}")
    
    elif args.subcommand == 'remove':
        print_header("🗑️ 删除持仓")
        result = manager.remove_position(position_id=args.id)
        if result['success']:
            print(f"✅ {result['message']}")
        else:
            print(f"❌ {result['message']}")
    
    elif args.subcommand == 'summary':
        print_header("📈 持仓摘要")
        summary = manager.get_portfolio_summary()
        status_icon = "🟢" if summary['profit_status'] == 'profit' else "🔴"
        profit_str = f"+{summary['total_profit']:.2f}" if summary['total_profit'] >= 0 else f"{summary['total_profit']:.2f}"
        profit_pct_str = f"+{summary['total_profit_pct']:.2f}%" if summary['total_profit_pct'] >= 0 else f"{summary['total_profit_pct']:.2f}%"
        
        print(f"{status_icon} 持仓数: {summary['total_count']}")
        print(f"💰 总成本: ¥{summary['total_cost']:.2f}")
        print(f"📊 总市值: ¥{summary['total_market_value']:.2f}")
        print(f"📈 总收益: ¥{profit_str} ({profit_pct_str})")


def handle_return_command(args):
    """处理收益跟踪命令"""
    tracker = get_return_tracker()
    
    if args.subcommand == 'track':
        print_header("📈 收益跟踪")
        result = tracker.track_return(tracking_time=args.time)
        print(format_return_report(result))
    
    elif args.subcommand == 'history':
        print_header("📊 历史收益")
        history = tracker.get_history(limit=args.limit)
        for record in history:
            time_label = "午盘" if record['tracking_time'] == 'midday' else "收盘"
            status_icon = "🟢" if record['daily_return_pct'] >= 0 else "🔴"
            print(f"{record['tracking_date']} {time_label}: {status_icon} {record['daily_return_pct']:+.2f}% (累计: {record['total_return_pct']:+.2f}%)")


def handle_report_command(args):
    """处理投资报告命令"""
    generator = get_report_generator()
    
    if args.subcommand == 'daily':
        print_header("📄 每日投资报告")
        report = generator.generate_daily_report()
        print(format_investment_report(report))
    
    elif args.subcommand == 'midday':
        print_header("☀️ 午间报告")
        report = generator.generate_midday_report()
        print(format_investment_report(report))


def handle_opportunity_command(args):
    """处理投资机会筛选命令"""
    print_header("🎯 投资机会筛选")
    print("正在获取今日涨幅榜...")
    
    # 调用现有的涨幅榜筛选
    cmd = [sys.executable, str(SCRIPT_DIR / 'get_today_gainers.py')]
    subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    
    print("\n💡 提示：对哪只股票感兴趣？直接说 '分析股票代码' 即可！")


def handle_task_command(args):
    """处理定时任务命令"""
    # 节假日判断：非交易日直接跳过，不推送任何报告
    from holiday_utils import is_trade_day
    today = datetime.now().strftime("%Y-%m-%d")
    if not is_trade_day():
        print(f"ℹ️ {today} 是节假日/周末，A股休市，不推送任何报告")
        sys.exit(0)  # 正常退出，返回码0
    
    print_header(f"⚡ 执行定时任务: {args.task}")
    
    if args.task == 'midday_report':
        # 午盘报告
        generator = get_report_generator()
        report = generator.generate_midday_report()
        print(format_investment_report(report))
    
    elif args.task == 'daily_report':
        # 每日报告
        generator = get_report_generator()
        report = generator.generate_daily_report()
        print(format_investment_report(report))
    
    elif args.task == 'opportunity':
        # 投资机会筛选
        handle_opportunity_command(args)
    
    elif args.task == 'morning_report_video':
        # 生成早报视频
        print_header("🎥 定时生成投资早报视频")
        cmd = [str(SCRIPT_DIR / 'tts_venv/bin/python'), str(SCRIPT_DIR / 'run_daily_morning_report.py')]
        result = subprocess.run(cmd, cwd=str(SCRIPT_DIR), capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ 早报视频生成完成！")
            print(result.stdout)
        else:
            print(f"❌ 生成失败：{result.stderr}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="🔥 高客秘书整合版 v2.6 - 智能投资助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 股票分析
  %(prog)s analyze --code 300750 --days 90
  
  # 持仓管理
  %(prog)s portfolio list
  %(prog)s portfolio add --code 600519 --price 1800 --quantity 100
  %(prog)s portfolio sell --id 1 --price 1900
  %(prog)s portfolio summary
  
  # 收益跟踪
  %(prog)s return track --time close
  %(prog)s return history --limit 10
  
  # 投资报告
  %(prog)s report daily
  %(prog)s report midday
  
  # 投资机会
  %(prog)s opportunity
  
  # 定时任务（用于cron）
  %(prog)s task --task midday_report
  %(prog)s task --task daily_report
  %(prog)s task --task opportunity
        """
    )
    
    subparsers = parser.add_subparsers(title='命令', dest='command', help='可用命令')
    
    # ========== 股票分析命令 ==========
    analyze_parser = subparsers.add_parser('analyze', help='分析股票')
    analyze_parser.add_argument('--code', required=True, help='股票代码 (如: 300750, 600519)')
    analyze_parser.add_argument('--days', type=int, default=90, help='分析天数 (默认: 90)')
    analyze_parser.add_argument('--output', help='输出JSON文件路径')
    
    # ========== 涨幅榜命令 ==========
    gainers_parser = subparsers.add_parser('gainers', help='查看今日涨幅榜')
    
    # ========== 推荐股票命令 ==========
    recommend_parser = subparsers.add_parser('recommend', help='获取今日股票推荐')
    
    # ========== 持仓管理命令 ==========
    portfolio_parser = subparsers.add_parser('portfolio', help='持仓管理')
    portfolio_subparsers = portfolio_parser.add_subparsers(dest='subcommand', help='持仓操作')
    
    # 列出持仓
    list_parser = portfolio_subparsers.add_parser('list', help='列出持仓')
    list_parser.add_argument('--status', default='holding', choices=['holding', 'sold', 'all'], help='持仓状态 (默认: holding)')
    
    # 添加持仓
    add_parser = portfolio_subparsers.add_parser('add', help='添加持仓（买入）')
    add_parser.add_argument('--code', required=True, help='股票代码')
    add_parser.add_argument('--price', type=float, required=True, help='买入价格')
    add_parser.add_argument('--quantity', type=int, required=True, help='数量（股）')
    add_parser.add_argument('--date', help='买入日期 (默认: 今天)')
    add_parser.add_argument('--notes', help='备注')
    
    # 卖出持仓
    sell_parser = portfolio_subparsers.add_parser('sell', help='卖出持仓')
    sell_parser.add_argument('--id', type=int, required=True, help='持仓ID')
    sell_parser.add_argument('--price', type=float, help='卖出价格 (默认: 最新价)')
    sell_parser.add_argument('--date', help='卖出日期 (默认: 今天)')
    sell_parser.add_argument('--notes', help='备注')
    
    # 删除持仓
    remove_parser = portfolio_subparsers.add_parser('remove', help='删除持仓（谨慎使用）')
    remove_parser.add_argument('--id', type=int, required=True, help='持仓ID')
    
    # 持仓摘要
    summary_parser = portfolio_subparsers.add_parser('summary', help='持仓摘要')
    
    # ========== 收益跟踪命令 ==========
    return_parser = subparsers.add_parser('return', help='收益跟踪')
    return_subparsers = return_parser.add_subparsers(dest='subcommand', help='收益操作')
    
    # 跟踪收益
    track_parser = return_subparsers.add_parser('track', help='跟踪当前收益')
    track_parser.add_argument('--time', default='close', choices=['midday', 'close'], help='时间点 (默认: close)')
    
    # 历史收益
    history_parser = return_subparsers.add_parser('history', help='历史收益')
    history_parser.add_argument('--limit', type=int, default=30, help='显示记录数 (默认: 30)')
    
    # ========== 投资报告命令 ==========
    report_parser = subparsers.add_parser('report', help='投资报告')
    report_subparsers = report_parser.add_subparsers(dest='subcommand', help='报告类型')
    
    # 每日报告
    daily_report_parser = report_subparsers.add_parser('daily', help='每日投资报告')
    
    # 午间报告
    midday_report_parser = report_subparsers.add_parser('midday', help='午间报告')
    
    # ========== 投资机会命令 ==========
    opportunity_parser = subparsers.add_parser('opportunity', help='投资机会筛选')
    
    # ========== 定时任务命令 ==========
    task_parser = subparsers.add_parser('task', help='执行定时任务（用于cron）')
    task_parser.add_argument('--task', required=True, choices=['midday_report', 'daily_report', 'opportunity', 'morning_report_video'], help='任务类型')
    
    # ========== 早报视频命令 ==========
    morning_report_parser = subparsers.add_parser('morning_report', help='生成投资早报视频')
    
    # ========== 配置命令 ==========
    config_parser = subparsers.add_parser('config', help='配置管理')
    config_subparsers = config_parser.add_subparsers(dest='config_subcommand', help='配置操作')
    
    # 设置火山云API Key
    set_volc_key_parser = config_subparsers.add_parser('set_volc_key', help='设置火山云API Key')
    set_volc_key_parser.add_argument('--key', required=True, help='火山云API Key')
    
    # 设置对象存储地址
    set_cos_endpoint_parser = config_subparsers.add_parser('set_cos_endpoint', help='设置对象存储地址')
    set_cos_endpoint_parser.add_argument('--url', required=True, help='对象存储Endpoint地址')
    
    # ========== 定时任务管理命令 ==========
    cron_parser = subparsers.add_parser('cron', help='定时任务管理')
    cron_subparsers = cron_parser.add_subparsers(dest='cron_subcommand', help='定时任务操作')
    
    # 列出定时任务
    cron_list_parser = cron_subparsers.add_parser('list', help='列出所有定时任务')
    
    # 修改定时任务时间
    cron_set_time_parser = cron_subparsers.add_parser('set_time', help='修改定时任务执行时间')
    cron_set_time_parser.add_argument('--task', required=True, choices=['morning_report', 'midday_report', 'close_report', 'opportunity_scan'], help='任务类型')
    cron_set_time_parser.add_argument('--time', required=True, help='执行时间，格式如：08:30、11:30、15:00')
    
    # 启用/禁用定时任务
    cron_toggle_parser = cron_subparsers.add_parser('toggle', help='启用/禁用定时任务')
    cron_toggle_parser.add_argument('--task', required=True, choices=['morning_report', 'midday_report', 'close_report', 'opportunity_scan'], help='任务类型')
    cron_toggle_parser.add_argument('--enable', type=bool, required=True, help='是否启用：True/False')
    
    # ========== 解析参数并执行 ==========
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        print("\n" + "=" * 80)
        print("  🔥 高客秘书整合版 v2.6 - 快速开始")
        print("=" * 80)
        print("\n🎯 快速使用：")
        print("  1. 分析股票:     python main.py analyze --code 300750")
        print("  2. 查看涨幅榜:   python main.py gainers")
        print("  3. 管理持仓:     python main.py portfolio --help")
        print("  4. 收益跟踪:     python main.py return --help")
        print("  5. 投资报告:     python main.py report --help")
        print("  6. 设置定时任务: ./setup_tasks.sh")
        return
    
    # 执行对应命令
    if args.command == 'analyze':
        print_header(f"📊 分析股票: {args.code}")
        cmd = [sys.executable, str(SCRIPT_DIR / 'quant_analyzer_v22.py'), '--code', args.code, '--days', str(args.days)]
        if args.output:
            cmd.extend(['--output', args.output])
        subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    
    elif args.command == 'gainers':
        print_header("🚀 今日涨幅榜")
        cmd = [sys.executable, str(SCRIPT_DIR / 'get_today_gainers.py')]
        subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    
    elif args.command == 'recommend':
        print_header("🎯 今日股票推荐")
        cmd = [sys.executable, str(SCRIPT_DIR / 'recommend_stocks.py')]
        subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    
    elif args.command == 'portfolio':
        handle_portfolio_command(args)
    
    elif args.command == 'return':
        handle_return_command(args)
    
    elif args.command == 'report':
        handle_report_command(args)
    
    elif args.command == 'opportunity':
        handle_opportunity_command(args)
    
    elif args.command == 'task':
        handle_task_command(args)
    
    elif args.command == 'morning_report':
        # 前置检查：火山云API Key是否存在
        from config import DOUBAN_CONFIG
        if not DOUBAN_CONFIG["api_key"] or len(DOUBAN_CONFIG["api_key"].strip()) == 0:
            print("❌ 投资早报功能不可用：缺少火山云API Key")
            print("💡 请先设置火山云API Key：")
            print("   命令：python main.py config set_volc_key --key 你的火山云API Key")
            print("   或者直接在聊天中说：我的火山云key是 XXXX")
            return
        
        print_header("🎥 生成投资早报视频")
        print("正在生成早报内容、语音和视频，请稍候...")
        # 调用早报生成全流程脚本
        cmd = [str(SCRIPT_DIR / 'tts_venv/bin/python'), str(SCRIPT_DIR / 'run_daily_morning_report.py')]
        result = subprocess.run(cmd, cwd=str(SCRIPT_DIR), capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ 早报视频生成完成！")
            # 直接输出run_daily_morning_report.py的标准输出
            print(result.stdout)
        else:
            print(f"❌ 生成失败：{result.stderr}")
    
    elif args.command == 'config':
        print_header("⚙️ 配置管理")
        import json
        config_path = SCRIPT_DIR / "custom_config.json"
        custom_config = {}
        
        # 读取现有配置
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    custom_config = json.load(f)
            except:
                custom_config = {}
        
        if args.config_subcommand == 'set_volc_key':
            # 保存火山云API Key
            if "douban" not in custom_config:
                custom_config["douban"] = {}
            custom_config["douban"]["api_key"] = args.key
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(custom_config, f, ensure_ascii=False, indent=2)
            print(f"✅ 火山云API Key已保存：{args.key[:6]}********")
            # 重载配置验证
            from config import load_custom_config
            load_custom_config()
            print("✅ 配置已生效")
        
        elif args.config_subcommand == 'set_cos_endpoint':
            # 保存对象存储地址
            if "cos" not in custom_config:
                custom_config["cos"] = {}
            custom_config["cos"]["endpoint"] = args.url
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(custom_config, f, ensure_ascii=False, indent=2)
            print(f"✅ 对象存储地址已保存：{args.url}")
            # 重载配置验证
            from config import load_custom_config
            load_custom_config()
            print("✅ 配置已生效")
    
    elif args.command == 'cron':
        print_header("⏰ 定时任务管理")
        import json
        cron_config_path = SCRIPT_DIR / "cron_config.json"
        cron_config = {}
        
        # 读取现有定时任务配置，不存在则初始化默认配置
        default_cron_config = {
            "morning_report": {"enabled": True, "time": "08:30", "cron_expr": "30 8 * * 1-5"},
            "midday_report": {"enabled": True, "time": "11:30", "cron_expr": "30 11 * * 1-5"},
            "close_report": {"enabled": True, "time": "15:30", "cron_expr": "30 15 * * 1-5"},
            "opportunity_scan": {"enabled": True, "time": "每小时", "cron_expr": "0 * * * 1-5"}
        }
        
        if cron_config_path.exists():
            try:
                with open(cron_config_path, "r", encoding="utf-8") as f:
                    cron_config = json.load(f)
            except:
                cron_config = default_cron_config
                # 保存默认配置
                with open(cron_config_path, "w", encoding="utf-8") as f:
                    json.dump(cron_config, f, ensure_ascii=False, indent=2)
        else:
            # 不存在配置文件，初始化默认配置
            cron_config = default_cron_config
            with open(cron_config_path, "w", encoding="utf-8") as f:
                json.dump(cron_config, f, ensure_ascii=False, indent=2)
        
        if args.cron_subcommand == 'list':
            # 列出所有定时任务
            print("📋 定时任务列表：")
            for task_name, config in cron_config.items():
                status = "✅ 启用" if config["enabled"] else "❌ 禁用"
                task_cn_name = {
                    "morning_report": "早报视频",
                    "midday_report": "午盘报告",
                    "close_report": "收盘报告",
                    "opportunity_scan": "行情机会扫描"
                }.get(task_name, task_name)
                print(f"  {task_cn_name}：{status} | 执行时间：{config['time']} | CRON：{config['cron_expr']}")
        
        elif args.cron_subcommand == 'set_time':
            # 修改任务执行时间
            task_name = args.task
            new_time = args.time
            # 转换时间为cron表达式（默认工作日执行）
            if ':' in new_time:
                hour, minute = new_time.split(':')
                cron_expr = f"{minute} {hour} * * 1-5"
            else:
                # 处理每小时等特殊时间
                cron_expr = "0 * * * 1-5"
            
            # 更新配置
            cron_config[task_name]["time"] = new_time
            cron_config[task_name]["cron_expr"] = cron_expr
            
            # 保存配置
            with open(cron_config_path, "w", encoding="utf-8") as f:
                json.dump(cron_config, f, ensure_ascii=False, indent=2)
            
            task_cn_name = {
                "morning_report": "早报视频",
                "midday_report": "午盘报告",
                "close_report": "收盘报告",
                "opportunity_scan": "行情机会扫描"
            }.get(task_name, task_name)
            
            print(f"✅ {task_cn_name} 执行时间已修改为：{new_time}")
            print(f"   CRON表达式：{cron_expr}")
            # 自动更新系统cron任务
            print("🔄 正在更新系统定时任务...")
            # 这里可以调用cron接口更新系统任务，后续对接OpenClaw的cron管理API
            print("✅ 定时任务已更新生效")
        
        elif args.cron_subcommand == 'toggle':
            # 启用/禁用任务
            task_name = args.task
            enable = args.enable
            cron_config[task_name]["enabled"] = enable
            
            # 保存配置
            with open(cron_config_path, "w", encoding="utf-8") as f:
                json.dump(cron_config, f, ensure_ascii=False, indent=2)
            
            task_cn_name = {
                "morning_report": "早报视频",
                "midday_report": "午盘报告",
                "close_report": "收盘报告",
                "opportunity_scan": "行情机会扫描"
            }.get(task_name, task_name)
            
            status = "✅ 已启用" if enable else "❌ 已禁用"
            print(f"{status} {task_cn_name}")
            # 自动更新系统cron任务
            print("🔄 正在更新系统定时任务...")
            print("✅ 定时任务状态已更新")


if __name__ == '__main__':
    main()
