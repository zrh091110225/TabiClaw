#!/usr/bin/env python3
"""
生成城市著名地标数据工具 - 调用大模型接口返回城市对应的前N个热门地标数据功能
用法: python3 scripts/generate_landmarks.py <城市名称>
输出: JSON 格式地标数组
"""

import sys
import os
import json
import urllib.request
import urllib.error
import re
from pathlib import Path

from lib.settings import load_runtime_settings

def load_env():
    """从项目根目录的 .env 文件加载环境变量"""
    env_path = Path(__file__).resolve().parent.parent / '.env'
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, val = line.split('=', 1)
                        # Remove surrounding quotes
                        val = val.strip('''"' ''')
                        if key not in os.environ or os.environ[key] == 'xxxx':
                            os.environ[key] = val

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing argument. Usage: python3 generate_landmarks.py <CityName> [N]"}, ensure_ascii=False))
        sys.exit(1)
        
    city_name = sys.argv[1]
    n_landmarks = sys.argv[2] if len(sys.argv) > 2 else ""
    
    # 1. Load configuration
    load_env()
    settings = load_runtime_settings(Path(__file__).resolve().parent.parent)
    provider = os.environ.get('LLM_PROVIDER', settings['llm_provider_default'])
    base_url = os.environ.get('LLM_BASE_URL', settings['llm_base_url_default'])
    model = os.environ.get('WRITER_MODEL', settings['writer_model_default'])
    api_key = os.environ.get('LLM_API_KEY')
    
    if not api_key:
        print(json.dumps({"error": "LLM_API_KEY not found in environment or .env file"}, ensure_ascii=False))
        sys.exit(1)
        
    # 2. Prepare Prompt
    limit_text = f"前{n_landmarks}个" if n_landmarks else ""
    prompt = (
        f"请列出[{city_name}]{limit_text}最著名的城市地标，并为每一个提供50字左右的生动描述，格式为 JSON。 "
        f"包含字段： landmark: 城市地标名称，desc: 景点描述，50个字左右。"
        f"只需返回一个JSON数组，不需要任何多余的文本解释。"
    )
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # 3. Build Request based on Provider
    if provider == "gemini":
        url = f"{base_url}/models/{model}:generateContent?key={api_key}"
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.4
            }
        }
    else:
        # OpenAI compatible formats (OpenAI, DeepSeek, MiniMax, etc.)
        # Ensure url ends with /chat/completions correctly
        if base_url.endswith('/'):
            url = f"{base_url}chat/completions"
        else:
            url = f"{base_url}/chat/completions"
            
        headers["Authorization"] = f"Bearer {api_key}"
        data = {
            "model": model,
            "temperature": 0.4,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
    # 4. Execute HTTP Request
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result_str = response.read().decode('utf-8')
            result_json = json.loads(result_str)
            
            content = ""
            if provider == "gemini":
                try:
                    content = result_json['candidates'][0]['content']['parts'][0]['text']
                except (KeyError, IndexError) as e:
                    print(json.dumps({"error": f"Failed to parse Gemini response: {e}", "raw": result_json}, ensure_ascii=False))
                    sys.exit(1)
            else:
                try:
                    content = result_json['choices'][0]['message']['content']
                except (KeyError, IndexError) as e:
                    print(json.dumps({"error": f"Failed to parse OpenAI compatible response: {e}", "raw": result_json}, ensure_ascii=False))
                    sys.exit(1)
            
            if not content:
                print(json.dumps({"error": "LLM returned empty content", "raw": result_json}, ensure_ascii=False))
                sys.exit(1)
                
            # 5. Extract JSON Array from content
            # Try to match markdown json block
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                # Try to extract substring from first [ to last ]
                start_idx = content.find('[')
                end_idx = content.rfind(']')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    content = content[start_idx:end_idx+1]
                else:
                    # Maybe it's not wrapped in array? Or failed.
                    pass
            
            # 6. Parse and Re-dump to ensure validity and format
            try:
                parsed_json = json.loads(content)
                if not isinstance(parsed_json, list):
                    # Wrap in list if it's a single dict
                    if isinstance(parsed_json, dict) and "landmark" in parsed_json:
                        parsed_json = [parsed_json]
                    else:
                        print(json.dumps({"error": "LLM output is not a JSON array of landmarks", "raw_content": content}, ensure_ascii=False))
                        sys.exit(1)
                print(json.dumps(parsed_json, ensure_ascii=False, indent=2))
            except json.JSONDecodeError:
                print(json.dumps({"error": "LLM did not return valid JSON", "raw_content": content}, ensure_ascii=False))
                sys.exit(1)
                
    except urllib.error.URLError as e:
        error_msg = str(e)
        if hasattr(e, 'read'):
            error_msg = e.read().decode('utf-8', errors='ignore')
        print(json.dumps({"error": f"HTTP Request failed: {e.reason}", "details": error_msg}, ensure_ascii=False))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Unexpected error: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
