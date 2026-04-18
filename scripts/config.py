#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局配置文件
支持命令行参数：
  --install: 安装依赖
  --check: 检查配置
  --setup: 配置向导
"""
import os
import json
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any

# 脚本目录
SCRIPT_DIR = Path(__file__).parent

# 基础配置
BASE_CONFIG = {
    "data_dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
    "cache_db": os.path.join(os.path.dirname(os.path.abspath(__file__)), "quant_data.db"),
    "log_level": "INFO",
}

# 数据源配置
DATA_SOURCES = [
    # 内置数据源，优先级从高到低
    {
        "name": "sqlite_cache",
        "type": "sqlite",
        "enabled": True,
        "priority": 1,
        "config": {
            "db_path": BASE_CONFIG["cache_db"]
        }
    },
    {
        "name": "tushare",
        "type": "api",
        "enabled": True,
        "priority": 2,
        "config": {
            "api_key": os.getenv("TUSHARE_API_KEY", ""),
            "endpoint": "http://api.tushare.pro"
        }
    },
    {
        "name": "akshare",
        "type": "lib",
        "enabled": True,
        "priority": 3,
        "config": {}
    }
    # 用户自定义数据源可以在这里添加，或者从配置文件动态加载
]

# 自定义算法配置
CUSTOM_ALGORITHMS = [
    # 示例配置，用户可以在这里添加自己的算法
    # {
    #     "name": "my_custom_strategy",
    #     "type": "http_api",
    #     "enabled": True,
    #     "config": {
    #         "url": "http://your-server/api/generate_signals",
    #         "api_key": "your-api-key",
    #         "timeout": 10
    #     }
    # }
]

# 豆包API配置
DOUBAN_CONFIG = {
    "api_key": os.getenv("ARK_API_KEY", os.getenv("VOLC_ARK_API_KEY", os.getenv("DOUBAO_API_KEY", ""))),
    # 强制使用公网地址，内网地址在服务器上无法解析
    "api_base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "video_api": "https://ark.cn-beijing.volces.com/api/v3/videos/generations",
    "video_model": "doubao-seedance-2-0-260128",
    "video_duration": 15
}

# 对象存储配置（可选）
COS_CONFIG = {
    "endpoint": os.getenv("COS_ENDPOINT", ""),
    "upload_enabled": os.getenv("COS_UPLOAD_ENABLED", "false").lower() == "true"
}

# 飞书配置
FEISHU_CONFIG = {
    "webhook": os.getenv("FEISHU_WEBHOOK", ""),
    "push_enabled": os.getenv("FEISHU_PUSH_ENABLED", "false").lower() == "true",
    "send_video_directly": os.getenv("FEISHU_SEND_VIDEO", "true").lower() == "true"
}

# 早报配置
MORNING_REPORT_CONFIG = {
    "enabled": True,
    "run_time": "08:30",
    "video_enabled": os.getenv("MORNING_REPORT_VIDEO_ENABLED", "false").lower() == "true",
    "push_enabled": FEISHU_CONFIG["push_enabled"]
}

def load_custom_config(config_path: str = None) -> Dict[str, Any]:
    """加载用户自定义配置文件"""
    if config_path is None:
        # 优先级1: 当前目录
        current_dir_config = "custom_config.json"
        if os.path.exists(current_dir_config):
            config_path = current_dir_config
        else:
            # 优先级2: 上级目录 (针对 scripts/ 目录下的脚本)
            config_path = str(SCRIPT_DIR.parent / "custom_config.json")
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                custom_config = json.load(f)
                # 合并配置
                if "data_sources" in custom_config:
                    DATA_SOURCES.extend(custom_config["data_sources"])
                if "custom_algorithms" in custom_config:
                    CUSTOM_ALGORITHMS.extend(custom_config["custom_algorithms"])
                if "douban" in custom_config:
                    DOUBAN_CONFIG.update(custom_config["douban"])
                if "cos" in custom_config:
                    COS_CONFIG.update(custom_config["cos"])
                if "feishu" in custom_config:
                    FEISHU_CONFIG.update(custom_config["feishu"])
                if "morning_report" in custom_config:
                    MORNING_REPORT_CONFIG.update(custom_config["morning_report"])
                print(f"已加载自定义配置文件: {config_path}")
                return custom_config
        except Exception as e:
            print(f"加载自定义配置失败: {e}")
    return {}

def install_dependencies():
    """安装项目依赖"""
    print("📦 正在安装依赖...")
    requirements_file = SCRIPT_DIR.parent / "requirements.txt"
    if requirements_file.exists():
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)])
            print("✅ 依赖安装完成")
        except subprocess.CalledProcessError as e:
            print(f"❌ 依赖安装失败: {e}")
            return False
    else:
        print(f"❌ 未找到 requirements.txt: {requirements_file}")
        return False
    return True

def check_config():
    """检查配置状态"""
    print("🔍 检查配置状态...")
    print()
    
    # 检查数据目录
    print(f"📁 数据目录: {BASE_CONFIG['data_dir']}")
    if os.path.exists(BASE_CONFIG['data_dir']):
        print("   ✅ 存在")
    else:
        print("   ❌ 不存在")
    
    # 检查配置文件
    config_file = SCRIPT_DIR.parent / "custom_config.json"
    print(f"📝 配置文件: {config_file}")
    if config_file.exists():
        print("   ✅ 存在")
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                print(f"   火山云API Key: {'✅ 已配置' if config.get('douban', {}).get('api_key') else '❌ 未配置'}")
                print(f"   Tushare Token: {'✅ 已配置' if config.get('tushare', {}).get('api_key') else '❌ 未配置'}")
        except:
            print("   ⚠️  配置文件格式错误")
    else:
        print("   ❌ 不存在")
    
    # 检查关键依赖
    print()
    print("📦 检查依赖库:")
    libs = [("akshare", "数据获取"), ("pandas", "数据处理"), ("requests", "HTTP请求")]
    for lib, desc in libs:
        try:
            __import__(lib)
            print(f"   ✅ {lib}: {desc}")
        except ImportError:
            print(f"   ❌ {lib}: {desc} (未安装)")
    
    print()
    print("✅ 检查完成")

def setup_wizard():
    """配置向导"""
    print("🚀 高客秘书配置向导")
    print("=" * 50)
    print()
    
    # 检查配置文件是否存在
    config_file = SCRIPT_DIR.parent / "custom_config.json"
    if config_file.exists():
        print("✅ 配置文件已存在")
        print()
        show_config = input("是否显示当前配置? (y/n): ").strip().lower()
        if show_config == 'y':
            check_config()
        return
    
    # 创建默认配置
    default_config = {
        "douban": {"api_key": ""},
        "tushare": {"api_key": ""},
        "feishu": {"group_id": "", "push_enabled": False, "webhook": "", "send_video_directly": True}
    }
    
    print("📝 创建默认配置文件...")
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        print(f"✅ 配置文件已创建: {config_file}")
    except Exception as e:
        print(f"❌ 创建配置文件失败: {e}")
        return
    
    print()
    print("💡 提示:")
    print("   1. 编辑 custom_config.json 填入你的API Key")
    print("   2. 或者通过IM对话直接设置: '我的火山云key是 xxx'")
    print()

# 兼容旧版本导入
class Config:
    """兼容旧版本配置类"""
    CONFIG_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = Path(BASE_CONFIG["data_dir"])
    TOKEN_FILE = CONFIG_DIR / "tushare.token"
    TOKEN_ENV_FILE = CONFIG_DIR / ".env"
    DB_FILE = CONFIG_DIR / "quant_data.db"
    pass

class SetupWizard:
    """兼容旧版本配置向导类"""
    pass

# 初始化创建数据目录
os.makedirs(BASE_CONFIG["data_dir"], exist_ok=True)

# 加载自定义配置
load_custom_config()

if __name__ == "__main__":
    if "--install" in sys.argv:
        install_dependencies()
    elif "--check" in sys.argv:
        check_config()
    elif "--setup" in sys.argv:
        setup_wizard()
    else:
        print("高客秘书 - 配置管理")
        print()
        print("使用方法:")
        print("  python config.py --install   安装依赖")
        print("  python config.py --check     检查配置")
        print("  python config.py --setup     配置向导")
        print()
