#!/usr/bin/env python3
"""
语音合成与视频合成模块
功能：生成中文语音，将语音和背景视频合并为完整早报视频
输出视频时长控制在1分钟左右，不超过65秒
"""
import os
import subprocess
import math

def check_ffmpeg():
    """检查ffmpeg和ffprobe是否可用"""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
        return True
    except:
        return False

# 配置区域
def get_edge_tts_path():
    """获取edge-tts路径，按优先级查找"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 1. 先尝试项目venv
    venv_path = os.path.join(script_dir, "venv/bin/edge-tts")
    if os.path.exists(venv_path):
        return venv_path
    # 2. 再尝试系统PATH中的edge-tts
    try:
        result = subprocess.run(["which", "edge-tts"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    # 3. 最后尝试直接调用edge-tts
    return "edge-tts"

CONFIG = {
    # TTS配置
    "voice": "zh-CN-XiaoxiaoNeural",  # 中文女声，可切换其他音色
    "tts_output_dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", "audio"),
    "default_audio_name": "report_voice.mp3",
    "speech_rate": "+0%",  # 语速调整
    
    # 视频合成配置
    "target_duration": 60,  # 目标视频时长：60秒（1分钟）
    "output_dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", "final"),
    "default_final_name": "morning_report_final.mp4",
    
    # Edge TTS路径（自动查找）
    "edge_tts_path": get_edge_tts_path()
}

def init_dirs():
    """初始化输出目录"""
    os.makedirs(CONFIG["tts_output_dir"], exist_ok=True)
    os.makedirs(CONFIG["output_dir"], exist_ok=True)

def text_to_speech(text, output_path=None):
    """文本转语音
    Args:
        text: 要合成的文本
        output_path: 输出音频路径，不填则使用默认
    Returns:
        生成的音频路径和音频时长（秒）
    """
    init_dirs()
    if not output_path:
        output_path = os.path.join(CONFIG["tts_output_dir"], CONFIG["default_audio_name"])
    
    # 调用Edge TTS生成语音
    cmd = [
        CONFIG["edge_tts_path"],
        "--voice", CONFIG["voice"],
        "--text", text,
        "--write-media", output_path
    ]
    
    if CONFIG["speech_rate"] != "+0%":
        cmd.extend(["--rate", CONFIG["speech_rate"]])
    
    print(f"正在使用 {CONFIG['edge_tts_path']} 生成语音...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            error_msg = f"TTS生成失败：{result.stderr}"
            print(error_msg)
            print("\n💡 提示：请确保已安装edge-tts")
            print("   方法1: 在项目venv中安装: scripts/venv/bin/pip install edge-tts")
            print("   方法2: 使用系统安装: pip install edge-tts")
            raise Exception(error_msg)
    except FileNotFoundError:
        error_msg = f"找不到edge-tts命令，路径: {CONFIG['edge_tts_path']}"
        print(error_msg)
        print("\n💡 请先安装edge-tts:")
        print("   方法1: 在项目venv中安装: scripts/venv/bin/pip install edge-tts")
        print("   方法2: 使用系统安装: pip install edge-tts")
        raise Exception(error_msg)
    
    # 获取音频时长
    duration_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        output_path
    ]
    duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
    duration = float(duration_result.stdout.strip())
    
    # 控制音频时长不超过60秒，如果太长自动截断
    if duration > CONFIG["target_duration"]:
        print(f"音频时长{duration:.1f}秒，截断到{CONFIG['target_duration']}秒")
        truncated_path = output_path.replace(".mp3", "_truncated.mp3")
        truncate_cmd = [
            "ffmpeg", "-y", "-i", output_path,
            "-t", str(CONFIG["target_duration"]),
            "-c:a", "copy", truncated_path
        ]
        subprocess.run(truncate_cmd, capture_output=True)
        output_path = truncated_path
        duration = CONFIG["target_duration"]
    
    print(f"语音生成成功，时长：{duration:.1f}秒，路径：{output_path}")
    return output_path, duration

def compose_video(video_path, audio_path, output_path=None, target_duration=None):
    """合并背景视频和音频，生成最终视频
    Args:
        video_path: 背景视频路径（短片段，会自动循环）
        audio_path: 音频路径
        output_path: 输出视频路径，不填则使用默认
        target_duration: 目标视频时长，不填则使用音频时长
    Returns:
        最终视频路径
    """
    # 先检查ffmpeg是否可用
    if not check_ffmpeg():
        error_msg = "找不到ffmpeg或ffprobe，无法合成视频"
        print(error_msg)
        print("\n💡 请先安装ffmpeg:")
        print("   macOS: brew install ffmpeg")
        print("   Ubuntu/Debian: sudo apt-get install ffmpeg")
        print("   CentOS: sudo yum install ffmpeg")
        print("   Windows: 下载 https://ffmpeg.org/download.html")
        raise Exception(error_msg)
    
    init_dirs()
    if not output_path:
        output_path = os.path.join(CONFIG["output_dir"], CONFIG["default_final_name"])
    
    # 使用音频时长作为目标时长
    if not target_duration:
        # 获取音频时长
        duration_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
        target_duration = float(duration_result.stdout.strip())
    
    # 循环背景视频并合并音频
    print(f"正在使用ffmpeg合成视频，目标时长：{target_duration:.1f}秒...")
    # 输入顺序：第一个输入是视频（索引0），第二个输入是音频（索引1）
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",  # 从视频文件（输入0）获取视频流
        "-map", "1:a:0",  # 从音频文件（输入1）获取音频流
        "-t", str(math.ceil(target_duration)),  # 取整，避免音画不同步
        "-shortest",  # 以较短的流为准
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            error_msg = f"视频合成失败：{result.stderr}"
            print(error_msg)
            raise Exception(error_msg)
    except FileNotFoundError:
        error_msg = "找不到ffmpeg命令"
        print(error_msg)
        print("\n💡 请先安装ffmpeg:")
        print("   macOS: brew install ffmpeg")
        print("   Ubuntu/Debian: sudo apt-get install ffmpeg")
        print("   CentOS: sudo yum install ffmpeg")
        print("   Windows: 下载 https://ffmpeg.org/download.html")
        raise Exception(error_msg)
    
    print(f"视频合成成功，路径：{output_path}")
    return output_path

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TTS语音合成与视频合成工具")
    parser.add_argument("--text", type=str, required=True, help="要合成的文本内容")
    parser.add_argument("--video", type=str, required=True, help="背景视频路径")
    parser.add_argument("--output", type=str, help="输出视频路径（可选）")
    parser.add_argument("--duration", type=float, help="目标视频时长（可选，默认使用音频时长）")
    args = parser.parse_args()
    
    # 生成语音
    audio_path, duration = text_to_speech(args.text)
    # 合成视频
    final_path = compose_video(args.video, audio_path, args.output, args.duration)
    print(f"最终视频路径：{final_path}")
