#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询 GitHub 项目 star 数，并根据新增的 star 数量增加旅行资金。
"""

import os
import json
import urllib.request
import urllib.error
import ssl

def get_config_value(settings_path, key, default):
    if not os.path.exists(settings_path):
        return default
    with open(settings_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split('=', 1)[1]
    return default

def get_github_stars(repo_name):
    url = f"https://api.github.com/repos/{repo_name}"
    req = urllib.request.Request(url, headers={'User-Agent': 'TabiClaw-Bot'})
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('stargazers_count', 0)
    except Exception as e:
        print(f"[WARN] 无法获取 GitHub Star 数: {e}")
        return None

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    settings_path = os.path.join(project_root, 'config', 'settings.yaml')
    status_path = os.path.join(project_root, 'data', 'status.json')
    
    # 1. 读取配置
    repo_name = get_config_value(settings_path, 'github_repo_name', 'zrh091110225/TabiClaw')
    try:
        star_reward_n = float(get_config_value(settings_path, 'star_reward_n', '10'))
    except ValueError:
        star_reward_n = 10.0
        
    print(f"[{__file__}] 配置读取: Repo={repo_name}, N={star_reward_n}")

    # 2. 获取最新 Star 数量
    current_stars = get_github_stars(repo_name)
    if current_stars is None:
        print(f"[{__file__}] 终止处理: Star获取失败。")
        return

    print(f"[{__file__}] 当前 GitHub Stars: {current_stars}")

    # 3. 读取当前状态
    if not os.path.exists(status_path):
        print(f"[{__file__}] 状态文件 {status_path} 不存在，跳过 Star 检查。")
        return

    with open(status_path, 'r', encoding='utf-8') as f:
        try:
            status = json.load(f)
        except Exception as e:
            print(f"[{__file__}] 无法读取 status.json: {e}")
            return
    
    last_star_count = status.get('last_star_count')
    
    # 如果是首次运行，仅记录当前的 Star 数，不增加资金
    if last_star_count is None:
        print(f"[{__file__}] 首次运行，记录初始 Star 数: {current_stars}")
        status['last_star_count'] = current_stars
        with open(status_path, 'w', encoding='utf-8') as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
        return
        
    # 计算新增的 Star 数量
    new_stars = current_stars - last_star_count
    
    if new_stars > 0:
        reward = new_stars * star_reward_n
        old_wallet = status.get('current_wallet', 0.0)
        new_wallet = old_wallet + reward
        
        print(f"[{__file__}] 发现新增 {new_stars} 个 Star，增加 {reward} 元资金！")
        print(f"[{__file__}] 钱包余额从 {old_wallet} 更新为 {new_wallet}")
        
        status['current_wallet'] = new_wallet
        status['last_star_count'] = current_stars
        
        with open(status_path, 'w', encoding='utf-8') as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
            
    elif new_stars < 0:
        # 有人取消了 Star，我们只更新 last_star_count，但不扣钱
        print(f"[{__file__}] Star 数量减少了 {-new_stars} 个，更新记录，但不扣除资金。")
        status['last_star_count'] = current_stars
        with open(status_path, 'w', encoding='utf-8') as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
    else:
        print(f"[{__file__}] 没有新增 Star。")

if __name__ == '__main__':
    main()
