#!/usr/bin/env python3
import os
import sys
import re

def render_template(text, context):
    """
    轻量级模板渲染引擎，支持变量替换和基础的管道过滤器。
    例如: {{ ATTRACTION_1_DESC | split: '，' | first }}
    """
    def replacer(match):
        expression = match.group(1).strip()
        # 按照管道符分割变量和过滤器
        parts = [p.strip() for p in expression.split('|')]
        
        var_name = parts[0]
        val = context.get(var_name, '')
        
        # 依次应用过滤器
        for filter_expr in parts[1:]:
            if filter_expr.startswith("split:"):
                sep_match = re.search(r"split:\s*['\"](.*?)['\"]", filter_expr)
                if sep_match and val:
                    val = val.split(sep_match.group(1))
            elif filter_expr == "first" and isinstance(val, list):
                val = val[0] if val else ''
            elif filter_expr == "last" and isinstance(val, list):
                val = val[-1] if val else ''
        
        # 如果最终结果还是列表，将其用逗号拼接成字符串
        return str(val) if not isinstance(val, list) else ",".join(val)

    # 匹配所有的 {{ ... }}
    return re.sub(r'\{\{(.*?)\}\}', replacer, text)

if __name__ == "__main__":
    template_text = sys.stdin.read()
    # 将环境变量作为上下文传入模板
    context = dict(os.environ)
    rendered = render_template(template_text, context)
    print(rendered)
