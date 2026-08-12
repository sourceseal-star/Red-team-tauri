#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-
"""
MIRAGE v1.0 — 数字诱饵部署系统
功能：生成虚假文件、伪造通话记录、伪造聊天日志，主动污染监控源
用途：合法数据保护与反监控测试
"""

import os
import sys
import json
import random
import time
import datetime
import shutil
from pathlib import Path

# ---------- 配置 ----------
HOME = str(Path.home())
BAIT_DIR = os.path.join(HOME, "storage", "downloads", ".mirage_bait")  # 诱饵暂存
TARGET_DIRS = [
    os.path.join(HOME, "storage", "downloads"),
    os.path.join(HOME, "storage", "documents"),
    os.path.join(HOME, "storage", "dcim", "Camera"),  # 假装是照片
]
REAL_VAULT = os.path.join(HOME, ".real_data")  # 真实数据藏身处（不暴露）

# ---------- 工具函数 ----------
def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

def random_name():
    """生成随机中文名"""
    family = ['张', '王', '李', '刘', '陈', '杨', '赵', '黄', '周', '吴']
    given = ['伟', '芳', '娜', '秀英', '敏', '静', '丽', '强', '磊', '洋']
    return random.choice(family) + random.choice(given) + random.choice(given)

def random_phone():
    return f"1{random.choice([3,5,7,8,9])}{''.join([str(random.randint(0,9)) for _ in range(9)])}"

def random_location():
    lat = 39.9 + random.uniform(-0.5, 0.5)
    lng = 116.3 + random.uniform(-0.5, 0.5)
    return f"{lat:.6f}, {lng:.6f}"

# ---------- 核心：生成诱饵文件 ----------
def generate_text_bait():
    """生成假文本文件（会议纪要/密报）"""
    content = f"""
【内部会议记录】 时间：{datetime.datetime.now().strftime('%Y-%m-%d')}
参会人：{random_name()}、{random_name()}、{random_name()}
议题：关于近期行动部署
决议：1. 明日{random.randint(8,20)}时在{random_location()}附近集合
2. 携带{random.choice(['红色背包','蓝色文件夹','黑色雨伞'])}
3. 备用联系频道：{random_phone()}
备注：此文件阅后即焚
"""
    fname = f"会议记录_{random.randint(100,999)}.txt"
    path = os.path.join(BAIT_DIR, fname)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path

def generate_chat_log():
    """生成假微信聊天记录（XML/JSON格式）"""
    msgs = []
    for _ in range(random.randint(5, 15)):
        msg = {
            "time": f"{random.randint(8,23)}:{random.randint(10,59)}",
            "sender": random.choice(["我", random_name()]),
            "text": random.choice([
                "到了吗？", "我在老地方", "注意安全", "东西带了吗", 
                "有人跟踪你", "换地点", "等我信号", "明天再说"
            ])
        }
        msgs.append(msg)
    # 生成一个类似微信缓存的JSON文件
    chat_data = {"group": random_name() + "的群聊", "messages": msgs}
    fname = f"wx_chat_{random.randint(1000,9999)}.json"
    path = os.path.join(BAIT_DIR, fname)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(chat_data, f, ensure_ascii=False, indent=2)
    return path

def generate_fake_audio_meta():
    """生成假的音频文件（只含元数据，无实际声音）"""
    fname = f"call_record_{random.randint(100,999)}.amr"
    path = os.path.join(BAIT_DIR, fname)
    # 伪造文件头，看起来像录音文件
    with open(path, 'wb') as f:
        # 写入一些随机字节模拟音频头
        f.write(b'\x23\x21\x41\x4d\x52\x0a')  # AMR头
        f.write(os.urandom(random.randint(1024, 4096)))  # 随机内容
    return path

def generate_contact_list():
    """生成假通讯录"""
    contacts = []
    for _ in range(10):
        contacts.append({
            "name": random_name(),
            "phone": random_phone(),
            "relation": random.choice(["同事", "线人", "朋友", "亲属", "上级"])
        })
    fname = f"contacts_backup_{random.randint(1,9)}.csv"
    path = os.path.join(BAIT_DIR, fname)
    with open(path, 'w', encoding='utf-8') as f:
        f.write("姓名,电话,关系\n")
        for c in contacts:
            f.write(f"{c['name']},{c['phone']},{c['relation']}\n")
    return path

# ---------- 部署诱饵到目标目录 ----------
def deploy_baits():
    """将诱饵文件分散到各个容易被扫描到的目录"""
    if not os.path.exists(BAIT_DIR):
        os.makedirs(BAIT_DIR)
    
    # 先清空旧诱饵（防止被分析规律）
    shutil.rmtree(BAIT_DIR, ignore_errors=True)
    os.makedirs(BAIT_DIR)
    
    log("🔄 正在生成新的诱饵群...")
    
    baits = []
    for _ in range(random.randint(3, 6)):
        baits.append(generate_text_bait())
    for _ in range(random.randint(2, 4)):
        baits.append(generate_chat_log())
    for _ in range(random.randint(1, 3)):
        baits.append(generate_fake_audio_meta())
    baits.append(generate_contact_list())
    
    log(f"✅ 已生成 {len(baits)} 个诱饵文件，存放在 {BAIT_DIR}")
    
    # 散布到各个公开目录
    for target in TARGET_DIRS:
        if not os.path.exists(target):
            continue
        # 每个目录复制 2-3 个诱饵
        chosen = random.sample(baits, min(len(baits), random.randint(2, 3)))
        for src in chosen:
            dst = os.path.join(target, os.path.basename(src))
            try:
                shutil.copy2(src, dst)
                log(f"   ↳ 投放至: {dst}")
            except Exception as e:
                log(f"   ✗ 投放失败: {e}")
    
    return baits

# ---------- 保护真实数据 ----------
def protect_real_data():
    """将真实数据藏入隐藏目录并伪装成系统缓存"""
    if not os.path.exists(REAL_VAULT):
        os.makedirs(REAL_VAULT)
    # 将真实文件移入此处（用户需提前把文件放入 ~/real_data_input）
    input_dir = os.path.join(HOME, "real_data_input")
    if os.path.exists(input_dir) and os.listdir(input_dir):
        log("📦 检测到真实数据，正在移动到隐藏保险库...")
        for f in os.listdir(input_dir):
            src = os.path.join(input_dir, f)
            dst = os.path.join(REAL_VAULT, f".{f}")  # 加前缀隐藏
            shutil.move(src, dst)
            log(f"   ↳ 已隐藏: {f}")
        os.rmdir(input_dir)  # 删除空目录
    else:
        log("ℹ️ 未发现真实数据（如需保护，请创建 ~/real_data_input 并放入文件）")

# ---------- 自动清理痕迹 ----------
def self_clean():
    """清除操作记录"""
    log("🧹 正在清除操作痕迹...")
    # 清空Python历史
    hist_file = os.path.join(HOME, ".python_history")
    if os.path.exists(hist_file):
        os.remove(hist_file)
    # 清空bash历史
    bash_hist = os.path.join(HOME, ".bash_history")
    if os.path.exists(bash_hist):
        open(bash_hist, 'w').close()
    log("✅ 痕迹已清理")

# ---------- 主菜单 ----------
def main_menu():
    os.system('clear')
    print("=" * 50)
    print("  🌀 MIRAGE 幻影诱饵系统 v1.0")
    print("  策略：让监控者淹没在虚假信息中")
    print("=" * 50)
    print("1. 🎯 完整欺骗部署（生成+投放+隐藏真实数据）")
    print("2. 📄 仅生成诱饵文件（存于暂存区）")
    print("3. 🚀 部署现有诱饵到扫描目录")
    print("4. 🛡️ 保护真实数据（移动至隐藏保险库）")
    print("5. 🧹 清理所有诱饵与痕迹")
    print("0. 退出")
    print("=" * 50)
    choice = input("请选择: ").strip()
    
    if choice == "1":
        log("🚀 启动完整欺骗流程...")
        protect_real_data()
        deploy_baits()
        self_clean()
        log("🎉 部署完成！监控者将被诱饵迷惑，真实数据安全。")
        log("⚠️ 请记住：真实数据在 ~/.real_data 中，诱饵在 storage/downloads 等处。")
    elif choice == "2":
        os.makedirs(BAIT_DIR, exist_ok=True)
        generate_text_bait()
        generate_chat_log()
        generate_fake_audio_meta()
        generate_contact_list()
        log(f"✅ 诱饵已生成在 {BAIT_DIR}，请手动投放。")
    elif choice == "3":
        deploy_baits()
    elif choice == "4":
        protect_real_data()
    elif choice == "5":
        shutil.rmtree(BAIT_DIR, ignore_errors=True)
        log("🧹 所有诱饵已清除。")
        self_clean()
    elif choice == "0":
        sys.exit(0)
    else:
        log("❌ 无效输入")
        time.sleep(1)
        main_menu()

# ---------- 入口 ----------
if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n用户中断")
        sys.exit(0)