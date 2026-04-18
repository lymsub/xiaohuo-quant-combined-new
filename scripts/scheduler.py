#!/usr/bin/env python3
"""
高客秘书 v2.7 统一调度器
安装 Skill 后自动注册，所有定时任务内置，无需手动配置
只需注册 1 条 cron：每分钟执行 python scheduler.py

错误处理原则：
1. 缺配置 → 输出友好提示到 IM，提醒用户录入
2. 用户不录入 → 核心功能（涨幅榜/机会扫描）照常运行，依赖持仓的功能静默跳过
3. 任务执行失败 → 输出错误摘要到 IM，让用户知道哪里有问题
4. scheduler 本身永不崩溃
"""
import os
import sys
import json
import subprocess
import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
LOG_DIR = SCRIPT_DIR / "cache" / "logs"
LOCK_DIR = SCRIPT_DIR / "cache" / "locks"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOCK_DIR.mkdir(parents=True, exist_ok=True)


def _is_trade_day() -> bool:
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from config import is_trade_day
        return is_trade_day()
    except Exception:
        return datetime.datetime.now().weekday() < 5


def _has_tushare_token() -> bool:
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from config import get_tushare_token
        return bool(get_tushare_token())
    except Exception:
        return bool(os.getenv("TUSHARE_API_KEY")) or (Path.home() / '.xiaohuo_quant' / 'token.txt').exists()


def _has_portfolio() -> bool:
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from database import QuantDatabase
        db = QuantDatabase()
        portfolio = db.list_portfolio(status='holding')
        db.close()
        return portfolio is not None and len(portfolio) > 0
    except Exception:
        return False


def _has_video_api_key() -> bool:
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from config import DOUBAN_CONFIG
        return bool(DOUBAN_CONFIG.get("api_key"))
    except Exception:
        return False


SCHEDULE = [
    {
        "name": "早报背景预生成",
        "time": "08:00",
        "command": [sys.executable, str(SCRIPT_DIR / "run_daily_morning_report.py"), "--pre-generate-bg"],
        "push": False,
        "requires": ["video_api"],
        "missing_hint": "⚠️ 早报视频需要配置火山引擎API Key。请设置环境变量 ARK_API_KEY 后重试。",
        "enabled": True,  # 核心任务：默认启用
    },
    {
        "name": "早报生成推送",
        "time": "08:30",
        "command": [sys.executable, str(SCRIPT_DIR / "run_daily_morning_report.py")],
        "push": True,
        "requires": ["video_api"],
        "missing_hint": "⚠️ 早报视频需要配置火山引擎API Key。请设置环境变量 ARK_API_KEY 后重试。",
        "enabled": True,  # 核心任务：默认启用
    },
    {
        "name": "上午市场机会扫描",
        "time": "10:00",
        "command": [sys.executable, str(SCRIPT_DIR / "scheduled_investment_scanner.py")],
        "push": True,
        "requires": [],
        "missing_hint": "",
        "enabled": False,  # 推荐任务：默认不启用
    },
    {
        "name": "上午市场机会扫描",
        "time": "11:00",
        "command": [sys.executable, str(SCRIPT_DIR / "scheduled_investment_scanner.py")],
        "push": True,
        "requires": [],
        "missing_hint": "",
        "enabled": False,  # 推荐任务：默认不启用
    },
    {
        "name": "午盘收益报告推送",
        "time": "11:35",
        "command": [sys.executable, str(SCRIPT_DIR / "main.py"), "task", "--task", "midday_report"],
        "push": True,
        "requires": ["portfolio"],
        "missing_hint": "⚠️ 午盘报告需要先添加持仓。请对我说「买入 股票代码 数量股」来添加持仓。",
        "enabled": False,  # 推荐任务：默认不启用
    },
    {
        "name": "下午市场机会扫描",
        "time": "13:30",
        "command": [sys.executable, str(SCRIPT_DIR / "scheduled_investment_scanner.py")],
        "push": True,
        "requires": [],
        "missing_hint": "",
        "enabled": False,  # 推荐任务：默认不启用
    },
    {
        "name": "下午市场机会扫描",
        "time": "14:30",
        "command": [sys.executable, str(SCRIPT_DIR / "scheduled_investment_scanner.py")],
        "push": True,
        "requires": [],
        "missing_hint": "",
        "enabled": False,  # 推荐任务：默认不启用
    },
    {
        "name": "收盘收益报告推送",
        "time": "15:10",
        "command": [sys.executable, str(SCRIPT_DIR / "main.py"), "return", "track", "--time", "close"],
        "push": True,
        "requires": ["portfolio"],
        "missing_hint": "⚠️ 收盘报告需要先添加持仓。请对我说「买入 股票代码 数量股」来添加持仓。",
        "enabled": False,  # 推荐任务：默认不启用
    },
    {
        "name": "沪深300收盘数据缓存",
        "time": "15:10",
        "command": [sys.executable, str(SCRIPT_DIR / "sync_data.py"), "--cache-hs300"],
        "push": False,
        "requires": ["tushare"],
        "missing_hint": "⚠️ 数据缓存需要Tushare Token。请设置环境变量 TUSHARE_API_KEY。",
        "enabled": True,  # 核心任务：默认启用
    },
    {
        "name": "每日深度投资报告推送",
        "time": "15:30",
        "command": [sys.executable, str(SCRIPT_DIR / "main.py"), "report", "daily"],
        "push": True,
        "requires": ["portfolio"],
        "missing_hint": "⚠️ 投资报告需要先添加持仓。请对我说「买入 股票代码 数量股」来添加持仓。",
        "enabled": False,  # 推荐任务：默认不启用
    },
    {
        "name": "每日股票数据同步",
        "time": "16:00",
        "command": [sys.executable, str(SCRIPT_DIR / "sync_data.py"), "--portfolio", "--days", "30"],
        "push": False,
        "requires": ["tushare", "portfolio"],
        "missing_hint": "⚠️ 数据同步需要Tushare Token和持仓数据。请设置环境变量 TUSHARE_API_KEY 并添加持仓。",
        "enabled": True,  # 核心任务：默认启用
    },
]

REQUIREMENT_CHECKERS = {
    "tushare": _has_tushare_token,
    "portfolio": _has_portfolio,
    "video_api": _has_video_api_key,
}

_missing_hint_cache = {}

# 任务配置文件
TASK_CONFIG_FILE = SCRIPT_DIR.parent / "task_config.json"


def _load_task_config():
    """加载任务配置"""
    if TASK_CONFIG_FILE.exists():
        try:
            with open(TASK_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_task_config(config: dict):
    """保存任务配置"""
    try:
        with open(TASK_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存任务配置失败: {e}")


def _apply_task_config():
    """应用任务配置到 SCHEDULE"""
    config = _load_task_config()
    for task in SCHEDULE:
        task_key = f"{task['name']}_{task['time']}"
        if task_key in config:
            task_config = config[task_key]
            if "enabled" in task_config:
                task["enabled"] = task_config["enabled"]
            if "time" in task_config:
                task["time"] = task_config["time"]


# 启动时应用配置
_apply_task_config()


# ==========================================
# 任务管理函数
# ==========================================
def toggle_task(task_name: str, enabled: bool):
    """启用/禁用任务"""
    config = _load_task_config()
    
    for task in SCHEDULE:
        if task["name"] == task_name:
            task["enabled"] = enabled
            task_key = f"{task['name']}_{task['time']}"
            config[task_key] = {"enabled": enabled, "time": task["time"]}
            _save_task_config(config)
            print(f"✅ {task_name} 已{'启用' if enabled else '禁用'}")
            return True
    
    print(f"❌ 任务 '{task_name}' 不存在")
    return False


def set_task_time(task_name: str, new_time: str):
    """修改任务时间"""
    config = _load_task_config()
    
    for task in SCHEDULE:
        if task["name"] == task_name:
            old_time = task["time"]
            old_key = f"{task['name']}_{old_time}"
            
            # 更新任务
            task["time"] = new_time
            task_key = f"{task['name']}_{new_time}"
            
            # 更新配置
            if old_key in config:
                config[task_key] = config.pop(old_key)
            else:
                config[task_key] = {}
            config[task_key]["enabled"] = task.get("enabled", True)
            config[task_key]["time"] = new_time
            
            _save_task_config(config)
            print(f"✅ {task_name} 时间已修改为 {new_time}")
            return True
    
    print(f"❌ 任务 '{task_name}' 不存在")
    return False


def _get_lock_file(task_name: str, time_str: str) -> Path:
    today = datetime.datetime.now().strftime("%Y%m%d")
    safe_name = task_name.replace(" ", "_")
    return LOCK_DIR / f"{safe_name}_{time_str.replace(':', '')}_{today}.lock"


def _is_already_run(task_name: str, time_str: str) -> bool:
    return _get_lock_file(task_name, time_str).exists()


def _mark_as_run(task_name: str, time_str: str):
    _get_lock_file(task_name, time_str).write_text(datetime.datetime.now().isoformat())


def _cleanup_old_locks():
    today = datetime.datetime.now().strftime("%Y%m%d")
    for f in LOCK_DIR.glob("*.lock"):
        if today not in f.name:
            f.unlink(missing_ok=True)


def _check_requirements(task: dict) -> tuple:
    """
    检查任务前置条件
    Returns: (通过?, 缺失项列表)
    """
    missing = []
    for req in task.get("requires", []):
        checker = REQUIREMENT_CHECKERS.get(req)
        if checker and not checker():
            missing.append(req)
    return len(missing) == 0, missing


def _write_log(task_name: str, time_str: str, level: str, message: str):
    today = datetime.datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"scheduler_{today}.log"
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] [{level}] {task_name} - {message}\n"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def run_pending_tasks():
    """
    执行当前时间匹配的待运行任务
    - 缺配置：输出友好提示到 IM，提醒用户录入
    - 用户不录入：核心功能照常运行，依赖持仓的功能静默跳过（每天只提示一次）
    - 任务失败：输出错误摘要到 IM
    """
    try:
        if not _is_trade_day():
            return
    except Exception:
        pass

    now = datetime.datetime.now()
    current_time = now.strftime("%H:%M")
    _cleanup_old_locks()

    for task in SCHEDULE:
        if task["time"] != current_time:
            continue

        # 检查任务是否启用（默认 True）
        if not task.get("enabled", True):
            _write_log(task["name"], task["time"], "SKIP", "任务未启用")
            continue

        if _is_already_run(task["name"], task["time"]):
            continue

        passed, missing = _check_requirements(task)

        if not passed:
            hint = task.get("missing_hint", "")
            hint_key = f"{task['name']}_{'+'.join(sorted(missing))}"
            if hint and hint_key not in _missing_hint_cache:
                _missing_hint_cache[hint_key] = True
                print(hint)
            _write_log(task["name"], task["time"], "SKIP", f"前置条件不满足: {missing}")
            _mark_as_run(task["name"], task["time"])
            continue

        _write_log(task["name"], task["time"], "START", "开始执行")

        try:
            result = subprocess.run(
                task["command"],
                cwd=str(SCRIPT_DIR),
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode == 0:
                _mark_as_run(task["name"], task["time"])
                _write_log(task["name"], task["time"], "OK", "执行成功")
                if task["push"] and result.stdout:
                    output = result.stdout.strip()
                    if output:
                        print(output)
            else:
                stderr = (result.stderr or "")[:500]
                _write_log(task["name"], task["time"], "FAIL", f"退出码{result.returncode}: {stderr}")
                if task["push"]:
                    print(f"❌ {task['name']}执行失败，请检查日志：python scheduler.py --logs")
        except subprocess.TimeoutExpired:
            _write_log(task["name"], task["time"], "TIMEOUT", "执行超时(600s)")
            _mark_as_run(task["name"], task["time"])
            if task["push"]:
                print(f"⏰ {task['name']}执行超时，请稍后重试")
        except Exception as e:
            _write_log(task["name"], task["time"], "ERROR", str(e)[:200])
            _mark_as_run(task["name"], task["time"])
            if task["push"]:
                print(f"❌ {task['name']}执行异常：{str(e)[:100]}")


def list_tasks():
    """列出所有内置定时任务"""
    print("=" * 80)
    print("  高客秘书 v2.7 内置定时任务清单")
    print("=" * 80)
    
    # 核心任务：默认启用
    core_tasks = ["早报背景预生成", "早报生成推送", "沪深300收盘数据缓存", "每日股票数据同步"]
    
    print("\n📢 推送到群任务：")
    shown_push = set()
    for task in SCHEDULE:
        if task["push"]:
            key = task["name"]
            if key in shown_push:
                continue
            shown_push.add(key)
            
            enabled = task.get("enabled", True)
            status = "✅ 启用" if enabled else "❌ 禁用"
            core_label = " [核心]" if key in core_tasks else ""
            
            # 收集所有时间
            times = sorted(set(t["time"] for t in SCHEDULE if t["name"] == key and t["push"]))
            print(f"  {key:<24} {', '.join(times):<12} {status}{core_label}")

    print("\n⚙️ 后台自动运行任务：")
    shown_bg = set()
    for task in SCHEDULE:
        if not task["push"]:
            key = task["name"]
            if key in shown_bg:
                continue
            shown_bg.add(key)
            
            enabled = task.get("enabled", True)
            status = "✅ 启用" if enabled else "❌ 禁用"
            core_label = " [核心]" if key in core_tasks else ""
            
            # 收集所有时间
            times = sorted(set(t["time"] for t in SCHEDULE if t["name"] == key and not t["push"]))
            print(f"  {key:<24} {', '.join(times):<12} {status}{core_label}")

    print("\n" + "=" * 80)
    print("  核心任务默认启用 | 节假日/周末自动跳过 | 缺配置友好提示")
    print("=" * 80)
    print("\n💡 使用方法：")
    print("  列出任务: python scheduler.py list")
    print("  启用任务: python scheduler.py toggle --task \"早报生成推送 --enable true")
    print("  禁用任务: python scheduler.py toggle --task \"上午市场机会扫描 --enable false")
    print("  修改时间: python scheduler.py set_time --task \"早报生成推送 --time 08:30")


def show_status():
    """显示今日任务执行状态"""
    if not _is_trade_day():
        print("📅 今日非交易日，所有任务自动跳过")
        return

    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_minutes = now.hour * 60 + now.minute

    print(f"\n📅 {today} 任务执行状态：\n")

    for task in SCHEDULE:
        h, m = map(int, task["time"].split(":"))
        task_minutes = h * 60 + m

        lock = _get_lock_file(task["name"], task["time"])
        if lock.exists():
            icon = "✅"
        elif current_minutes >= task_minutes:
            icon = "⏳"
        else:
            icon = "🕐"
        push_tag = "📢" if task["push"] else "⚙️"

        reqs = task.get("requires", [])
        req_tag = ""
        if reqs:
            req_names = {"tushare": "Token", "portfolio": "持仓", "video_api": "视频API"}
            req_str = "+".join([req_names.get(r, r) for r in reqs])
            req_tag = f" [需{req_str}]"

        print(f"  {icon} {push_tag} {task['time']} {task['name']}{req_tag}")

    print()


def show_logs(lines: int = 50):
    """显示最近的调度日志"""
    today = datetime.datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"scheduler_{today}.log"
    if not log_file.exists():
        print("📋 今日暂无调度日志")
        return
    try:
        content = log_file.read_text(encoding="utf-8")
        all_lines = content.strip().split("\n")
        recent = all_lines[-lines:]
        print(f"📋 最近 {len(recent)} 条调度日志：\n")
        for line in recent:
            print(line)
    except Exception as e:
        print(f"读取日志失败: {e}")


if __name__ == "__main__":
    try:
        import argparse
        parser = argparse.ArgumentParser(description="高客秘书统一调度器")
        
        subparsers = parser.add_subparsers(title="命令", dest="command", help="可用命令")
        
        # 默认命令：执行待运行任务
        parser.add_argument("--run", action="store_true", help="执行当前时间的待运行任务")
        parser.add_argument("--list", action="store_true", help="列出所有定时任务")
        parser.add_argument("--status", action="store_true", help="显示今日任务执行状态")
        parser.add_argument("--logs", action="store_true", help="查看调度日志")
        parser.add_argument("--log-lines", type=int, default=50, help="日志行数")
        
        # 子命令：列出任务
        list_parser = subparsers.add_parser("list", help="列出所有定时任务")
        
        # 子命令：启用/禁用任务
        toggle_parser = subparsers.add_parser("toggle", help="启用/禁用定时任务")
        toggle_parser.add_argument("--task", required=True, help="任务名称")
        toggle_parser.add_argument("--enable", type=str, required=True, help="是否启用: true/false")
        
        # 子命令：修改任务时间
        set_time_parser = subparsers.add_parser("set_time", help="修改定时任务执行时间")
        set_time_parser.add_argument("--task", required=True, help="任务名称")
        set_time_parser.add_argument("--time", required=True, help="执行时间，格式如：08:30")
        
        args = parser.parse_args()

        if args.command == "list" or args.list:
            list_tasks()
        elif args.command == "toggle":
            enabled = args.enable.lower() in ("true", "1", "yes", "on")
            toggle_task(args.task, enabled)
        elif args.command == "set_time":
            set_task_time(args.task, args.time)
        elif args.status:
            show_status()
        elif args.logs:
            show_logs(args.log_lines)
        elif args.run:
            run_pending_tasks()
        elif not args.command:
            # 默认执行待运行任务
            run_pending_tasks()
    except Exception as e:
        print(f"调度器错误: {e}")
        pass
