#!/usr/bin/env python3
"""
高客秘书模板引擎
负责加载、渲染MD模板文件
"""
import sys
import re
from pathlib import Path
from typing import Dict, Any, Optional

SCRIPT_DIR = Path(__file__).parent
TEMPLATES_DIR = SCRIPT_DIR.parent / 'templates'


class ReportTemplate:
    """报告模板类"""
    
    def __init__(self, template_name: str):
        self.template_name = template_name
        self.template_path = TEMPLATES_DIR / f"{template_name}.md"
        self.content = self._load_template()
    
    def _load_template(self) -> str:
        """加载模板文件"""
        if not self.template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {self.template_path}")
        
        with open(self.template_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def render(self, context: Dict[str, Any]) -> str:
        """
        渲染模板
        
        Args:
            context: 包含所有占位符值的字典
                    例如: {'股票代码': '600519', '日期': '2026-04-19'}
        
        Returns:
            渲染后的字符串
        """
        result = self.content
        
        # 1. 先扁平化嵌套字典，方便模板匹配
        flat_context = self._flatten_context(context)
        
        # 使用正则表达式替换所有 {变量名} 占位符
        # 支持中文和英文变量名
        def replace_placeholder(match):
            key = match.group(1)
            if key in flat_context:
                value = flat_context[key]
                # 处理None值
                if value is None:
                    return "-"
                # 转换为字符串
                return str(value)
            # 如果context中没有这个key，保留原样
            return match.group(0)
        
        # 替换 {xxx} 格式的占位符
        result = re.sub(r'\{([^}]+)\}', replace_placeholder, result)
        
        return result
    
    def _flatten_context(self, context: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
        """
        扁平化嵌套字典，方便模板匹配
        
        例如: {'最新行情': {'最新价': 100}} -> {'最新价': 100, '最新行情.最新价': 100}
        """
        flat = {}
        
        for key, value in context.items():
            new_key = f"{prefix}{key}" if prefix else key
            
            if isinstance(value, dict):
                # 递归处理嵌套字典
                nested_flat = self._flatten_context(value, f"{new_key}.")
                flat.update(nested_flat)
                # 同时也把子字典的直接key加入，方便匹配
                for nested_key, nested_value in value.items():
                    if nested_key not in flat:  # 避免覆盖更高级别的key
                        flat[nested_key] = nested_value
            else:
                flat[new_key] = value
        
        return flat


class StockAnalysisTemplate(ReportTemplate):
    """个股分析报告模板"""
    
    def __init__(self):
        super().__init__('stock_analysis')
    
    def get_parts(self, rendered_content: str) -> Dict[int, str]:
        """
        把个股分析分成4个部分（对应4种颜色卡片）
        
        Returns:
            {1: 第1部分内容, 2: 第2部分内容, ...}
        """
        parts = {}
        
        # 解析4个部分
        section_patterns = [
            (1, r'## 第1/4部分.*?```(.*?)```', re.DOTALL),
            (2, r'## 第2/4部分.*?```(.*?)```', re.DOTALL),
            (3, r'## 第3/4部分.*?```(.*?)```', re.DOTALL),
            (4, r'## 第4/4部分.*?```(.*?)```', re.DOTALL),
        ]
        
        for part_num, pattern, flags in section_patterns:
            match = re.search(pattern, rendered_content, flags)
            if match:
                parts[part_num] = match.group(1).strip()
        
        return parts


def load_template(template_name: str) -> ReportTemplate:
    """
    快捷加载模板函数
    
    Args:
        template_name: 模板名称（不带.md后缀）
                      例如: 'stock_analysis', 'midday_report'
    
    Returns:
        ReportTemplate实例
    """
    template_map = {
        'stock_analysis': StockAnalysisTemplate,
    }
    
    if template_name in template_map:
        return template_map[template_name]()
    
    return ReportTemplate(template_name)


def render_report(template_name: str, context: Dict[str, Any]) -> str:
    """
    快捷渲染报告函数
    
    Args:
        template_name: 模板名称
        context: 占位符数据字典
    
    Returns:
        渲染后的完整报告
    """
    template = load_template(template_name)
    return template.render(context)


def main():
    """测试模板引擎"""
    print("🎯 测试模板引擎")
    print(f"📁 模板目录: {TEMPLATES_DIR}")
    
    # 测试加载所有模板
    template_names = [
        'stock_analysis',
        'midday_report',
        'close_report',
        'investment_report',
        'opportunity_scan'
    ]
    
    for name in template_names:
        try:
            template = load_template(name)
            print(f"✅ 加载模板: {name}")
        except Exception as e:
            print(f"❌ 加载失败: {name}, 错误: {e}")
    
    # 测试简单渲染
    print("\n🎬 测试简单渲染...")
    test_context = {
        '股票代码': '600519',
        '股票名称': '贵州茅台',
        '日期': '2026-04-19',
        '分析时间': '2026-04-19 12:30'
    }
    
    try:
        result = render_report('midday_report', test_context)
        print(f"✅ 午盘报告渲染成功，长度: {len(result)} 字符")
    except Exception as e:
        print(f"❌ 渲染失败: {e}")
    
    print("\n🎉 模板引擎测试完成！")


if __name__ == "__main__":
    main()
