#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OSINT STRUCT MAPPER v1.0 - 组织实体抽取与关联引擎
适用于安全研究人员、记者，用于从公开文本中提取结构化情报。
仅处理用户提供的本地文本，不主动联网，不留存网络痕迹。
"""

import re
import json
import hashlib
import sys
import os
from datetime import datetime
from collections import defaultdict, Counter

# ---------- 配置区 (可自定义扩充) ----------
# 针对特定政权的职位关键词库（可无限扩充）
POSITION_KEYWORDS = [
    "司令", "副司令", "总参谋", "队长", "副队长", "支队长", "政委", "书记",
    "部长", "副部长", "处长", "科长", "主任", "秘书", "助理", "特别行动组",
    "内卫", "警卫", "司机班", "通讯科", "情报处", "后勤部", "机要局"
]

# 电话号码正则（适应中国/南美格式）
PHONE_PATTERN = r'\+?\d{1,4}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}'

# 身份证/军官证号模式（模糊匹配）
ID_PATTERN = r'[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]?'

# ---------- 核心提取类 ----------
class EntityExtractor:
    def __init__(self, raw_text):
        self.raw_text = raw_text
        self.paragraphs = [p for p in re.split(r'\n\s*\n', raw_text) if len(p) > 10]
        self.entities = {
            "persons": [],
            "positions": [],
            "phones": [],
            "ids": [],
            "orgs": []
        }
        self.cooccurrence = defaultdict(Counter)  # 关联矩阵

    def extract_all(self):
        """执行所有提取"""
        self._extract_persons_and_positions()
        self._extract_phones()
        self._extract_ids()
        self._build_cooccurrence()
        return self._build_graph()

    def _extract_persons_and_positions(self):
        """抽取姓名+职位（基于职位关键词前/后的名字）"""
        # 策略：捕获"职位 + 空格 + 两到四个汉字（姓名）"
        for pos in POSITION_KEYWORDS:
            # 模式1：职位在前，姓名在后（如：队长 张三）
            pattern1 = rf'({pos})\s*([\u4e00-\u9fa5]{{2,4}})'
            matches = re.findall(pattern1, self.raw_text)
            for p, name in matches:
                self.entities["positions"].append(p)
                self.entities["persons"].append(name)
                # 记录关联
                self.cooccurrence[name][p] += 1

            # 模式2：姓名在前，职位在后（如：张三 队长）
            pattern2 = rf'([\u4e00-\u9fa5]{{2,4}})\s*({pos})'
            matches = re.findall(pattern2, self.raw_text)
            for name, p in matches:
                self.entities["positions"].append(p)
                self.entities["persons"].append(name)
                self.cooccurrence[name][p] += 1

        # 额外：抓取单独提及的姓名（用于扩大关联网）
        # 此处用简单启发式：捕获"同志"、"先生"、"女士"前的两到四个汉字
        honorifics = re.findall(r'([\u4e00-\u9fa5]{2,4})\s*(?:同志|先生|女士|上校|中校)', self.raw_text)
        for name in honorifics:
            if name not in self.entities["persons"]:
                self.entities["persons"].append(name)

    def _extract_phones(self):
        """提取电话/手机号"""
        phones = re.findall(PHONE_PATTERN, self.raw_text)
        for p in phones:
            clean_p = re.sub(r'[\s\-\(\)]', '', p)
            if len(clean_p) > 7:
                self.entities["phones"].append(clean_p)

    def _extract_ids(self):
        """提取身份证/证件号"""
        ids = re.findall(ID_PATTERN, self.raw_text)
        for i in ids:
            self.entities["ids"].append(i.upper())

    def _build_cooccurrence(self):
        """构建共现矩阵：如果同一段落里出现两个姓名，则他们可能认识或同一派系"""
        names = list(set(self.entities["persons"]))
        if len(names) < 2:
            return
        
        for para in self.paragraphs:
            # 找出该段落中出现的所有姓名
            found_names = []
            for name in names:
                if name in para:
                    found_names.append(name)
            # 两两关联加权重
            if len(found_names) >= 2:
                for i in range(len(found_names)):
                    for j in range(i+1, len(found_names)):
                        n1, n2 = found_names[i], found_names[j]
                        self.cooccurrence[n1][n2] += 1
                        self.cooccurrence[n2][n1] += 1

    def _build_graph(self):
        """构建最终图谱结构"""
        # 去重
        unique_persons = list(set(self.entities["persons"]))
        unique_positions = list(set(self.entities["positions"]))
        unique_phones = list(set(self.entities["phones"]))
        unique_ids = list(set(self.entities["ids"]))

        # 构建关联边（用于图形化展示）
        edges = []
        for name, counter in self.cooccurrence.items():
            for target, weight in counter.items():
                if target in unique_persons:
                    edges.append({
                        "source": name,
                        "target": target,
                        "weight": weight,
                        "relation": "同派系/共事" if weight > 2 else "关联"
                    })

        # 汇总个人信息（把手机号和身份证挂到人名下，此处模拟贪心匹配）
        person_profiles = []
        for p in unique_persons:
            profile = {
                "name": p,
                "positions": [pos for pos in unique_positions if pos in self.raw_text and p in self.raw_text],
                "phones": [ph for ph in unique_phones if ph in self.raw_text],
                "ids": [id_ for id_ in unique_ids if id_ in self.raw_text]
            }
            person_profiles.append(profile)

        return {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "source_length": len(self.raw_text),
                "note": "此数据仅用于防御性情报分析，证明特定时间点已知信息的Hash。"
            },
            "entities": {
                "total_persons": len(unique_persons),
                "total_phones": len(unique_phones),
                "total_ids": len(unique_ids),
                "list": person_profiles
            },
            "relationships": {
                "total_links": len(edges),
                "edges": edges[:30]  # 防止输出过大，截断
            }
        }

# ---------- 主程序：无痕执行与证据锚定 ----------
def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else "raw_data.txt"
    
    print("[*] 正在读取原始情报文本...")
    if not os.path.exists(input_file):
        print(f"[-] 错误: 找不到文件 {input_file}")
        print("[*] 用法: python3 osint_struct_mapper.py <你的文本文件>")
        sys.exit(1)

    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()

    print("[+] 文本读取成功，长度: {} 字符".format(len(text)))
    extractor = EntityExtractor(text)
    
    print("[*] 正在执行实体抽取与关联分析（纯本地运算，无网络请求）...")
    result = extractor.extract_all()
    
    # 生成报告文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_json = json.dumps(result, ensure_ascii=False, indent=2)
    report_file = f"struct_report_{timestamp}.json"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_json)
    
    print(f"[+] 结构化报告已保存至: {report_file}")

    # ---------- 防篡改锚定（核心！） ----------
    # 计算报告自身的SHA-256
    sha256_hash = hashlib.sha256(report_json.encode('utf-8')).hexdigest()
    
    # 提取关键人物的指纹作为附加锚点（防止他们将人员从名单中抹去）
    persons_hash = hashlib.sha256(
        json.dumps(result["entities"]["list"], ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    
    # 写入审计日志（不可变的证明）
    audit_log = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "report_file": report_file,
        "report_hash_sha256": sha256_hash,
        "persons_snapshot_hash": persons_hash,
        "total_persons": result["entities"]["total_persons"],
        "total_links": result["relationships"]["total_links"],
        "warning": "若此哈希与数据库记录不符，则证明证据已被篡改。"
    }
    
    audit_file = f"audit_anchor_{timestamp}.json"
    with open(audit_file, 'w', encoding='utf-8') as f:
        json.dump(audit_log, f, ensure_ascii=False, indent=2)

    # ---------- 终端输出（直接打印可锚定的Hash供SourceSeal使用）----------
    print("\n" + "="*60)
    print(" ⚡ 证据锚定信息 (请将此Hash录入SourceSeal/区块链) ⚡")
    print("="*60)
    print(f" 报告指纹 (SHA-256): {sha256_hash}")
    print(f" 人员快照指纹:      {persons_hash}")
    print(f" 查获总人数:         {result['entities']['total_persons']}")
    print(f" 关联边数:           {result['relationships']['total_links']}")
    print("="*60)
    print("[*] 若今后有人篡改此报告，以上哈希将完全不匹配。")
    print("[*] 审计日志已保存，请物理保管好 .json 文件。")
    print("\n[!] 操作完成。日志未上传，未联网。你的身份在此次操作中未暴露。")

if __name__ == "__main__":
    main()