#!/usr/bin/env python3
"""
早报生成全流程入口脚本
功能：一键执行早报生成→视频生成→语音合成→视频合并全流程
适合定时任务每天自动调用
支持参数：
--pre-generate-bg: 仅预生成12秒背景视频，保存到缓存，不生成完整早报
"""
import datetime
import os
import sys
import json
from pathlib import Path

# 加载配置
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from config import DOUBAN_CONFIG, COS_CONFIG, FEISHU_CONFIG, load_custom_config
# 新逻辑：使用精简版250字早报，无冗余内容
from generate_short_report import generate_short_report as generate_report
from video_generator import generate_background_video
import video_generator
# 新逻辑：强制使用Seedance 2.0模型生成15秒背景模版
video_generator.CONFIG["model"] = "doubao-seedance-2-0-260128"
video_generator.CONFIG["video_duration"] = 15
from tts_composer import text_to_speech, compose_video
import tts_composer
# 新逻辑：语速250字/分钟，总时长65秒预留缓冲
tts_composer.CONFIG["speech_rate"] = "+25%"
tts_composer.CONFIG["target_duration"] = 65

# 全局配置
CONFIG = {
    "upload_to_cos": COS_CONFIG["upload_enabled"],  # 是否上传到对象存储
    "cos_path": COS_CONFIG["endpoint"],
    "save_local": True,  # 是否保存本地文件
    "local_save_dir": os.path.join(SCRIPT_DIR.parent, "history/"),
    "generate_new_background": True,  # 是否每天生成新背景视频，False则复用现有背景
    "default_background": os.path.join(SCRIPT_DIR, "full_cn_morning.mp4"),  # 兜底背景视频路径，生成失败自动用这个
    "feishu_send_video": FEISHU_CONFIG["send_video_directly"],  # 无COS时直接发飞书
    "background_cache_dir": os.path.join(SCRIPT_DIR, "cache", "video")  # 背景视频缓存目录
}

# 显示配置信息
print("=" * 80)
print("📋 当前配置:")
print(f"   对象存储上传: {'✅ 已启用' if CONFIG['upload_to_cos'] else '❌ 未启用'}")
if CONFIG['cos_path']:
    print(f"   对象存储 endpoint: {CONFIG['cos_path']}")
print(f"   飞书推送: {'✅ 已启用' if FEISHU_CONFIG['push_enabled'] else '❌ 未启用'}")
print(f"   飞书直接发送视频: {'✅ 已启用' if CONFIG['feishu_send_video'] else '❌ 未启用'}")
print("=" * 80)

def upload_to_cos(local_path, remote_name):
    """上传文件到对象存储"""
    # 先检查配置
    if not CONFIG.get("cos_path") or not CONFIG.get("cos_path").strip():
        print("⚠️ 对象存储 endpoint 未配置，跳过上传")
        return None
    
    # 检查文件是否存在
    if not os.path.exists(local_path):
        print(f"⚠️ 文件不存在，无法上传：{local_path}")
        return None
    
    try:
        print(f"🚀 开始上传到对象存储...")
        print(f"   本地文件: {local_path}")
        print(f"   目标路径: {CONFIG['cos_path']}{remote_name}")
        
        cmd = f"curl -T {local_path} {CONFIG['cos_path']}{remote_name}"
        result = os.popen(cmd).read()
        
        if result:
            print(f"   上传结果: {result.strip()}")
        
        uploaded_url = f"{CONFIG['cos_path']}{remote_name}"
        print(f"✅ 文件已上传：{uploaded_url}")
        return uploaded_url
        
    except Exception as e:
        print(f"❌ 对象存储上传失败：{e}")
        print("\n💡 提示：")
        print("   1. 请检查 endpoint 配置是否正确（需要包含 https:// 和结尾的 /）")
        print("   2. 火山引擎 TOS 需要 SDK 签名上传，简单的 curl PUT 方式不支持")
        print("   3. 可以使用支持匿名上传的对象存储服务")
        return None

def upload_to_feishu_drive(local_path, file_name):
    """上传文件到飞书云盘，返回飞书内链"""
    try:
        import json
        # 新版OpenClaw调用工具方式
        cmd = f'''openclaw agent --local --message '{{"name": "feishu_drive_file", "parameters": {{"action": "upload", "file_path": "{local_path}", "file_name": "{file_name}"}}}}' --json'''
        result = os.popen(cmd).read()
        
        # 尝试解析 JSON 响应
        try:
            data = json.loads(result)
            if "file_token" in data.get("result", {}):
                return f"https://bytedance.feishu.cn/file/{data['result']['file_token']}"
            elif "file_token" in data:
                return f"https://bytedance.feishu.cn/file/{data['file_token']}"
        except:
            pass
        
        # 如果 JSON 解析失败或者没有返回 file_token，也没关系
        print(f"📝 飞书云盘上传响应: {result[:100]}...")
        
        # 只要不报错就继续，上传可能通过 OpenClaw 自动处理
        # 这里不强制要求返回 file_token
        
    except Exception as e:
        print(f"⚠️ 飞书云盘上传可能遇到问题：{e}")
        # 不抛出异常，继续执行
        pass
    
    return None

def main(force_regenerate=False):
    """主函数"""
    # 生成日期目录
    today = datetime.datetime.now().strftime("%Y%m%d")
    save_dir = os.path.join(CONFIG["local_save_dir"], today)
    os.makedirs(save_dir, exist_ok=True)
    
    # 检查当天是否已经生成过早报，优先复用缓存
    final_video_path = os.path.join(save_dir, f"final_report_{today}.mp4")
    link_cache_path = os.path.join(save_dir, "link_cache.json")
    if not force_regenerate and os.path.exists(final_video_path) and os.path.exists(link_cache_path):
        try:
            with open(link_cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            print("="*80)
            print("✅ 发现已生成的今日早报，直接复用缓存结果")
            print("="*80)
            print(f"飞书内链：{cache_data.get('feishu_link')}")
            print(f"COS链接：{cache_data.get('cos_link')}")
            return cache_data
        except Exception as e:
            print(f"读取缓存失败，重新生成：{e}")
    
    print("="*80)
    print("🚀 开始执行每日早报生成全流程")
    print("="*80)
    
    # Step 1：生成早报内容
    print("\n📝 Step 1/5：生成早报内容...")
    try:
        report_content = generate_report()
        report_path = os.path.join(save_dir, f"morning_report_{today}.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"早报内容已保存到：{report_path}")
    except Exception as e:
        print(f"早报生成失败，使用默认内容：{e}")
        report_content = "各位投资者早上好，今日市场整体平稳，建议关注优质蓝筹标的投资机会，投资有风险，入市需谨慎。"
    
    # Step 2：获取背景视频
    print("\n🎬 Step 2/5：获取背景视频...")
    background_path = None
    # 优先使用缓存的背景视频
    if not CONFIG["generate_new_background"]:
        cache_files = sorted(Path(CONFIG["background_cache_dir"]).glob("*.mp4"), key=os.path.getmtime, reverse=True)
        if cache_files:
            background_path = str(cache_files[0])
            print(f"复用缓存背景视频：{background_path}")
    
    # 没有缓存则生成新背景
    if not background_path:
        try:
            print("未找到预生成背景，实时生成中...")
            background_path = generate_background_video()
            # 缓存新生成的背景
            os.makedirs(CONFIG["background_cache_dir"], exist_ok=True)
            cache_path = os.path.join(CONFIG["background_cache_dir"], f"bg_{today}.mp4")
            os.system(f"cp {background_path} {cache_path}")
            print(f"背景视频已缓存到：{cache_path}")
        except Exception as e:
            # 兜底逻辑：生成失败使用默认背景
            print(f"背景视频生成失败，使用兜底模版：{e}")
            background_path = CONFIG["default_background"]
    
    # Step 3：生成语音播报
    print("\n🎤 Step 3/5：生成语音播报...")
    try:
        result = text_to_speech(report_content)
        # 处理返回值：如果是tuple，取第一个元素作为路径
        if isinstance(result, tuple):
            audio_path = result[0]
        else:
            audio_path = result
        print(f"语音生成成功，路径：{audio_path}")
    except Exception as e:
        print(f"语音生成失败，退出：{e}")
        sys.exit(1)
    
    # Step 4：合成最终视频
    print("\n🎞️ Step 4/5：合成最终视频...")
    try:
        final_video_path = compose_video(background_path, audio_path)
        # 保存到历史目录
        save_video_path = os.path.join(save_dir, f"final_report_{today}.mp4")
        os.system(f"cp {final_video_path} {save_video_path}")
        print(f"最终视频已保存到：{save_video_path}")
        # 输出到环境变量供后续调用
        print(f"VIDEO_PATH={save_video_path}")
    except Exception as e:
        print(f"视频合成失败，退出：{e}")
        sys.exit(1)
    
    # Step 5：发布早报
    print("\n☁️ Step 5/5：发布早报视频...")
    feishu_link = None
    cos_link = None
    
    # 先上传到COS
    if CONFIG["upload_to_cos"]:
        try:
            cos_file_name = f"morning_report_{today}.mp4"
            cos_link = upload_to_cos(save_video_path, cos_file_name)
            if cos_link:
                print(f"COS链接：{cos_link}")
        except Exception as e:
            print(f"COS上传失败：{e}")
    
    # 再上传到飞书云盘
    if CONFIG["feishu_send_video"]:
        try:
            feishu_link = upload_to_feishu_drive(save_video_path, f"投资早报_{today}.mp4")
            if feishu_link:
                print(f"飞书内链：{feishu_link}")
        except Exception as e:
            print(f"飞书上传失败：{e}")
    
    print("\n" + "="*80)
    print("✅ 早报视频生成完成！")
    print("="*80)
    
    # 保存缓存
    try:
        with open(link_cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"缓存链接失败：{e}")
    
    # 返回结果
    return cache_data

if __name__ == "__main__":
    # 处理参数
    force_regenerate = False
    if len(sys.argv) > 1:
        if sys.argv[1] == "--pre-generate-bg":
            print("🔧 预生成背景视频模式...")
            try:
                path = generate_background_video()
                os.makedirs(CONFIG["background_cache_dir"], exist_ok=True)
                cache_path = os.path.join(CONFIG["background_cache_dir"], f"bg_pre_{datetime.datetime.now().strftime('%Y%m%d%H%M')}.mp4")
                os.system(f"cp {path} {cache_path}")
                print(f"✅ 背景视频预生成完成，缓存到：{cache_path}")
            except Exception as e:
                print(f"❌ 预生成失败：{e}")
            sys.exit(0)
        elif sys.argv[1] == "--force":
            force_regenerate = True
            print("🔧 强制重新生成早报模式，忽略缓存...")
    
    # 正常执行全流程
    result = main(force_regenerate=force_regenerate)
