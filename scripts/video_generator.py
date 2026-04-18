#!/usr/bin/env python3
"""
视频生成模块
功能：调用视频生成API生成背景视频
可配置模型参数，支持后续切换其他视频生成模型
"""
import os
import time
import random
import urllib.request
import sys
import requests
import json
from pathlib import Path

# 添加当前目录到路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from config import DOUBAN_CONFIG

# 10组固定视频提示词，随机轮训
VIDEO_PROMPTS = [
    # 提示词1：蓝色金融主题，动态K线图
    "专业级中文财经早报背景视频，深蓝色渐变金融风格，动态滚动的上证指数、深证成指、创业板指K线图，红色阳线绿色阴线，配合实时数据图表展示，无任何英文，界面简洁大气，适合央视财经等专业财经节目",
    # 提示词2：金色奢华风格，数据矩阵
    "高端金色金融风格背景视频，金色渐变奢华背景，3D立体数据矩阵旋转动画，金色货币符号流动，股票价格实时刷新，配合柱状图、饼图、折线图组合展示，专业量化投资数据可视化",
    # 提示词3：科技深蓝风，3D走势图
    "科技深蓝风格财经背景，深邃太空蓝渐变，3D立体股票走势图动画，A股三大指数曲线实时滚动，配合粒子效果和数据流瀑布，专业量化投资数据展示，适合机构投资者",
    # 提示词4：红色经典风，大盘实时
    "红色经典金融风格，中国红渐变背景，动态展示A股大盘实时走势图，红色阳线绿色阴线交替，配合成交量柱状图，专业大气的财经新闻背景，适合新闻联播财经时段",
    # 提示词5：绿色增长风，板块轮动
    "清新绿色金融风格，自然绿渐变背景，A股板块轮动动画，新能源、科技、消费、金融、医药板块动态切换，绿色增长曲线实时攀升，配合行业数据图表，价值投资理念传播",
    # 提示词6：紫金色AI风，神经网络
    "紫金色AI科技风格，紫金渐变高端背景，神经网络可视化动画，股票预测数据实时展示，配合深度学习模型可视化，专业AI量化投资背景，未来感十足",
    # 提示词7：橙金色活力风，资金流向
    "橙金色活力风格，橙金渐变阳光背景，资金流向动态图，红色资金流入绿色资金流出，配合3D立体K线图，专业财经早间播报背景，充满活力与希望",
    # 提示词8：青灰色沉稳风，实时行情
    "青灰色沉稳专业风格，青灰渐变稳重背景，实时行情滚动屏动画，股票代码和价格快速刷新，数字矩阵背景配合数据瀑布，专业财经资讯展示，适合专业投资者",
    # 提示词9：香槟金轻奢风，全球市场
    "香槟金轻奢风格，香槟金渐变背景，全球市场联动图，中美欧股市数据实时联动，配合世界地图背景，专业全球化投资视角，高端大气上档次",
    # 提示词10：灰蓝色价值风，历史曲线
    "灰蓝色价值投资风格，灰蓝渐变稳重背景，A股历史走势图，十年上证指数、深证成指、创业板指曲线展示，配合价值投资理念数据，专业长期投资理念传播"
]

# 配置区域
CONFIG = {
    # 模型配置（可根据需要切换其他模型）
    "model": DOUBAN_CONFIG["video_model"],
    "api_key": DOUBAN_CONFIG["api_key"],
    "base_url": DOUBAN_CONFIG["api_base_url"],
    
    # 视频生成参数
    "video_duration": 12,  # 生成12秒背景视频，后续循环到1分钟
    "output_dir": os.path.join(SCRIPT_DIR.parent, "output", "videos"),
    "default_output_name": "background_video.mp4"
}

def generate_background_video(prompt=None, output_path=None):
    """生成背景视频
    Args:
        prompt: 自定义提示词，不填则随机从10组中选择
        output_path: 输出路径，不填则使用默认配置
    Returns:
        生成的视频本地路径
    """
    # 创建输出目录
    os.makedirs(CONFIG["output_dir"], exist_ok=True)
    
    # 使用默认值
    if not prompt:
        # 随机从10组提示词中选择
        prompt = random.choice(VIDEO_PROMPTS)
        print(f"🎲 随机选择提示词：{prompt[:50]}...")
    if not output_path:
        output_path = os.path.join(CONFIG["output_dir"], CONFIG["default_output_name"])
    
    api_key = CONFIG["api_key"]
    base_url = CONFIG["base_url"].rstrip("/")
    model = CONFIG["model"]
    
    print(f"开始生成背景视频，模型：{model}")
    
    try:
        # 1. 创建生成任务
        create_url = f"{base_url}/contents/generations/tasks"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "content": [
                {
                    "type": "text",
                    "text": f"{prompt} --duration 12 --watermark false"
                }
            ]
        }
        
        response = requests.post(create_url, headers=headers, json=payload)
        response.raise_for_status()
        task_data = response.json()
        task_id = task_data["id"]
        print(f"任务已创建，ID：{task_id}")
        
        # 2. 轮询任务状态
        get_url = f"{base_url}/contents/generations/tasks/{task_id}"
        while True:
            response = requests.get(get_url, headers=headers)
            response.raise_for_status()
            result = response.json()
            status = result["status"]
            
            if status == "succeeded":
                video_url = result["content"]["video_url"]
                print(f"视频生成成功，开始下载...")
                # 下载视频
                urllib.request.urlretrieve(video_url, output_path)
                print(f"视频已保存到：{output_path}")
                return output_path
            elif status == "failed":
                print(f"视频生成失败：{result.get('error', '未知错误')}")
                raise Exception(f"视频生成失败：{result.get('error', '未知错误')}")
            else:
                print(f"任务状态：{status}，等待中...")
                time.sleep(10)
                
    except Exception as e:
        print(f"视频生成出错：{e}")
        # 生成失败时返回默认背景视频，保证功能可用
        default_video = os.path.join(SCRIPT_DIR, "full_cn_morning.mp4")
        if os.path.exists(default_video):
            print(f"使用默认背景视频：{default_video}")
            return default_video
        raise e

if __name__ == "__main__":
    # 测试生成
    video_path = generate_background_video()
    print(f"生成的视频路径：{video_path}")
