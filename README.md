# 🔥 高客秘书整合版 v2.8

> 智能投资助手 - 股票筛选、个股分析、收益跟踪、投资报告、早报视频五大能力
> 
> 📦 新仓库：[lymsub/xiaohuo-quant-combined-new](https://github.com/lymsub/xiaohuo-quant-combined-new)

---

## 📋 目录

- [功能介绍](#功能介绍)
- [安装指南](#安装指南)
- [快速开始](#快速开始)
- [功能详解](#功能详解)
- [IM对话配置](#im对话配置)
- [定时任务](#定时任务)
- [强制规则](#强制规则)
- [常见问题](#常见问题)

---

## 📦 安装指南

### 方式一：一键安装（推荐）

```bash
# 克隆项目
git clone https://github.com/lymsub/xiaohuo-quant-combined-2.git
cd xiaohuo-quant-combined-2

# 运行安装脚本
cd scripts
chmod +x install.sh
./install.sh
```

安装脚本会自动完成以下操作：
- ✅ 检查 Python 环境
- ✅ 创建独立虚拟环境
- ✅ 安装所有依赖库
- ✅ 初始化配置文件
- ✅ 显示快速开始指南

---

### 方式二：手动安装

```bash
# 1. 创建虚拟环境
cd scripts
python3 -m venv venv

# 2. 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows

# 3. 安装依赖
cd ..
pip install -r requirements.txt

# 4. 初始化配置
cd scripts
python config.py --setup

# 5. 检查配置
python config.py --check
```

---

### 配置项说明

安装后，编辑 `custom_config.json` 配置你的API Key：

```json
{
  "douban": {
    "api_key": "你的火山云API Key"
  },
  "tushare": {
    "api_key": "你的Tushare Token"
  },
  "feishu": {
    "group_id": "",
    "push_enabled": false,
    "webhook": "",
    "send_video_directly": true
  }
}
```

---

## 🚀 功能介绍

高客秘书是一款专业的量化投资助手，整合了五大核心能力：

| 能力 | 说明 |
|------|------|
| 📊 **股票筛选** | 实时涨幅榜、智能推荐、投资机会扫描 |
| 📈 **个股分析** | 深度量化分析、技术指标、策略信号、AI诊断 |
| 💰 **收益跟踪** | 午盘/收盘收益跟踪、历史记录、归因分析 |
| 📄 **投资报告** | 午间报告、每日投资报告、专业深度分析 |
| 🎬 **早报视频** | 自动生成视频早报、飞书云盘推送 |

---

## 💡 快速开始

### 基础使用

直接在IM中与高客秘书对话即可：

```
启动高客秘书
分析股票 000617
查看今日涨幅榜
生成早报视频
```

### 命令行使用

```bash
cd scripts

# 查看帮助
python main.py --help

# 分析股票
python main.py analyze --code 000617 --days 90

# 查看涨幅榜
python main.py gainers

# 生成早报视频
python main.py morning_report
```

---

## 📖 功能详解

### 1️⃣ 股票筛选

#### 今日涨幅榜
```
查看今日涨幅榜
今日涨幅榜
```

#### 股票推荐
```
推荐股票
今天最推荐的股票
```

#### 投资机会筛选
```
筛选股票
投资机会
```

---

### 2️⃣ 个股分析

```
分析股票 000617
分析个股 000617
分析股票代码 000617
```

**分析内容包括：**
- 股票基本信息 + 最新行情
- 技术指标分析（MA、MACD、RSI等）
- 策略信号 + 历史回测
- 综合诊断 + AI深度分析

---

### 3️⃣ 收益跟踪

#### 午盘报告
```
午盘报告
查看午盘
午盘收益
```

#### 收盘报告
```
收盘报告
查看收盘
收盘收益
```

#### 历史收益
```
查看历史收益
收益历史
```

---

### 4️⃣ 投资报告

```
投资报告
今日投资报告
生成投资报告
```

**报告内容包括：**
- 收益概览
- 持仓明细
- 收益归因
- 市场点评
- 相关资讯
- 操作建议

---

### 5️⃣ 早报视频

```
早报视频
生成早报
投资早报
```

**早报视频特点：**
- 240-260字精简内容
- Seedance 2.0模型生成背景
- 语速+25%，250字/分钟
- 总时长65秒预留缓冲
- 优先推送飞书云盘链接

---

## 🎛️ 配置说明

### 方式一：通过IM对话配置（推荐）

直接在IM中与高客秘书对话即可配置：

#### 配置火山云API Key（用于视频生成）

```
我的火山云key是 xxxxxxxx
设置火山云key xxxxxxxx
配置火山引擎API Key xxxxxxxx
```

或使用命令行：

```bash
cd scripts
python main.py config set_volc_key --key 你的火山云API Key
```

---

#### 配置对象存储（COS）

```
我的COS地址是 https://xxx.cos.com
设置对象存储地址 https://xxx.cos.com
```

或使用命令行：

```bash
cd scripts
python main.py config set_cos_endpoint --url https://your-cos-endpoint.com
```

---

#### 配置Tushare Token（可选，用于高级数据源）

```
我的Tushare token是 xxxxxxxx
设置Tushare token xxxxxxxx
```

---

#### 配置飞书Webhook（可选，用于自动推送）

```
我的飞书webhook是 https://open.feishu.cn/xxx
设置飞书推送地址 https://open.feishu.cn/xxx
```

---

### 方式二：通过配置文件配置

编辑项目根目录下的 `custom_config.json` 文件：

```json
{
  "douban": {
    "api_key": "你的火山云API Key"
  },
  "tushare": {
    "api_key": "你的Tushare Token"
  },
  "cos": {
    "endpoint": "https://your-cos-endpoint.com",
    "upload_enabled": true
  },
  "feishu": {
    "group_id": "",
    "push_enabled": false,
    "webhook": "https://open.feishu.cn/your-webhook",
    "send_video_directly": true
  }
}
```

#### 配置项说明：

| 配置项 | 说明 | 必填 |
|--------|------|------|
| `douban.api_key` | 火山引擎API Key，用于生成早报视频 | 是 |
| `tushare.api_key` | Tushare Token，用于高级数据源 | 否 |
| `cos.endpoint` | 对象存储上传地址 | 否 |
| `cos.upload_enabled` | 是否开启COS上传 | 否 |
| `feishu.webhook` | 飞书Webhook地址 | 否 |
| `feishu.push_enabled` | 是否开启飞书自动推送 | 否 |
| `feishu.send_video_directly` | 是否直接发送视频文件 | 否 |

---

### 获取配置信息

#### 火山引擎API Key
1. 访问 [火山引擎官网](https://www.volcengine.com/)
2. 注册/登录账号
3. 进入「控制台」→「API访问」→「API密钥管理」
4. 创建新的API Key，复制保存

#### Tushare Token
1. 访问 [Tushare官网](https://tushare.pro/)
2. 注册/登录账号
3. 进入「个人中心」→「接口Token」
4. 复制你的Token

#### 对象存储（COS）
可以使用任意对象存储服务（阿里云OSS、腾讯云COS、七牛云等）
1. 在对象存储服务商创建存储空间（Bucket）
2. 获取上传地址和访问权限
3. 配置到 `cos.endpoint`

---

## ⏰ 定时任务

高客秘书内置了完整的定时任务系统，安装后自动生效：

| 任务 | 时间 | 说明 |
|------|------|------|
| 早报背景预生成 | 08:00 | 预生成15秒背景视频 |
| 早报生成推送 | 08:30 | 生成并推送早报视频 |
| 上午市场机会扫描 | 10:00, 11:00 | 每天2次扫描 |
| 午盘收益报告推送 | 11:35 | 推送午盘收益报告 |
| 下午市场机会扫描 | 13:30, 14:30 | 每天2次扫描 |
| 收盘收益报告推送 | 15:10 | 推送收盘收益报告 |
| 沪深300收盘数据缓存 | 15:10 | 缓存收盘数据 |
| 每日深度投资报告推送 | 15:30 | 推送投资报告 |
| 每日股票数据同步 | 16:00 | 同步历史数据 |

---

### 修改定时任务时间

```
把早报时间改成8点
修改推送时间到08:00
```

或使用命令行：

```bash
cd scripts
python main.py cron set_time --task morning_report --time 08:00
```

---

### 启用/禁用定时任务

```
关闭早报推送
禁用午盘报告
启用投资机会扫描
```

或使用命令行：

```bash
cd scripts
python main.py cron toggle --task morning_report --enable False
```

---

### 列出定时任务

```
查看定时任务
列出所有任务
```

或使用命令行：

```bash
cd scripts
python main.py cron list
```

---

## 🔴 强制规则（永久固化）

### 数据真实性规则
1. ❌ **绝对禁止编造任何数据**：所有行情、指标、收益必须从真实接口拉取
2. ✅ **空值统一标注**：接口失败标注「获取失败」，数据不足标注「暂未同步基准净值与区间数据，后续接入数据源自动补齐」

### 报告格式规则
1. 所有报告必须完整输出模板中定义的所有模块
2. 个股分析报告飞书平台分4色卡片发送（绿/蓝/橙/紫）
3. 所有表格使用标准Markdown格式
4. 所有报告末尾添加标准风险提示：
   ```
   ⚠️ 本分析仅供参考，不构成投资建议。股市有风险，投资需谨慎！
   ```

### 早报视频强制返回规则
- **优先返回飞书云盘内链**：
  ```
  ✅ 今日早报视频已生成：<https://bytedance.feishu.cn/file/xxx>
  💡 点击链接即可直接在飞书内观看/下载，无需额外权限。
  ```

- **云盘失败返回COS链接**：
  ```
  ⚠️ 飞书云盘临时上传失败，已为你生成公网可访问链接：<https://xxx.cos.com>
  💡 链接24小时内有效，可直接下载观看。
  ```

- **生成失败统一返回**：
  ```
  ❌ 今日早报视频生成失败，请稍后重试。
  ```

- **绝对禁止**：提及任何服务器本地路径、引导用户从服务器获取文件

---

## 💼 持仓管理

### 查看持仓
```
查看持仓
我的持仓
持仓列表
```

### 添加持仓（买入）
```
买入贵州茅台1000股
以235元买入比亚迪1000股
```

### 卖出持仓
```
卖出持仓1
卖出贵州茅台
```

### 删除持仓
```
删除持仓1
移除持仓
```

### 持仓摘要
```
持仓摘要
查看总收益
```

---

## 🎨 状态指示器标准

### 涨跌状态
- 🟢 上涨/正值/零轴上方/多头
- 🔴 下跌/负值/零轴下方/空头/超买/超卖
- ⚪ 持平/中性/震荡

### 量能状态
- 放量（成交量≥10000000）
- 缩量（成交量≤2000000）
- 平量（其他）

---

## ❌ 禁止行为

1. 禁止编造大盘数据、板块涨跌幅
2. 禁止虚增当日收益，不得把累计收益冒充当日收益
3. 禁止隐瞒高仓位风险，不得修改仓位集中度数值
4. 禁止编造风控指标
5. 禁止编造荐股逻辑、目标价位、买卖点位
6. 禁止编造任何没有真实计算依据的指标
7. 禁止虚构公司公告、行业新闻、政策信息
8. 禁止混淆累计收益和当日收益概念
9. 禁止使用未经核实的专业术语

---

## 📁 项目结构

```
xiaohuo-quant-combined/
├── scripts/                    # 核心功能脚本
│   ├── config.py              # 配置管理
│   ├── data_source.py         # 五数据源管理
│   ├── database.py            # 数据库管理
│   ├── generate_short_report.py # 精简早报生成
│   ├── get_today_gainers.py   # 涨幅榜获取
│   ├── holiday_utils.py       # 节假日判断
│   ├── install.sh             # 安装脚本
│   ├── investment_report.py   # 投资报告生成
│   ├── main.py                # 主入口程序
│   ├── morning_report_generator.py # 完整早报生成
│   ├── portfolio_manager.py   # 持仓管理
│   ├── quant_analyzer_v22.py # 个股分析
│   ├── recommend_stocks.py    # 股票推荐
│   ├── return_tracker.py      # 收益跟踪
│   ├── run_daily_morning_report.py # 早报视频全流程
│   ├── scheduled_investment_scanner.py # 定时投资扫描
│   ├── scheduler.py           # 统一调度器
│   ├── sync_data.py          # 数据同步
│   ├── tts_composer.py       # TTS语音合成
│   └── video_generator.py    # 视频生成
├── templates/                  # 报告模板
│   ├── close_report.md
│   ├── investment_report.md
│   ├── midday_report.md
│   ├── opportunity_scan.md
│   └── stock_analysis.md
├── SKILL.md                   # Skill定义
├── FORCED_RULES.md            # 强制规则
└── custom_config.json         # 自定义配置
```

---

## 🤝 常见问题

### Q: 如何开始使用？
A: 直接在IM中说「启动高客秘书」即可！

### Q: 视频生成需要什么配置？
A: 需要配置火山云API Key，在IM中说「我的火山云key是 xxx」即可。

### Q: 节假日会推送吗？
A: 不会！系统内置2026全年法定节假日，节假日/周末自动休市不推送。

### Q: 数据来源是什么？
A: 统一五数据源管理（新浪/腾讯/AkShare/Tushare/Baostock），主数据源失败自动降级。

### Q: 如何查看所有功能？
A: 说「启动高客秘书」即可看到完整功能菜单。

---

## 📄 许可证

本项目仅供学习研究使用，不构成投资建议。股市有风险，投资需谨慎！

---

**🎉 高客秘书 - 您的专业量化投资助手！**
