#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
# WATCHER v1.0 — 极端环境下的个人数据保护与反监控工具箱
# 仅供合法测试与个人数据安全研究使用。严禁用于非法活动。
# ================================================================

set -e

# ---------- 颜色定义 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; BLUE='\033[0;34m'; NC='\033[0m'

# ---------- 配置 ----------
DATA_DIR="$HOME/data_to_protect"      # 需要保护的文件放这里
BACKUP_DIR="$HOME/.watcher_vault"     # 加密备份存放处（隐藏）
MANIFEST_FILE="$BACKUP_DIR/manifest.sha256"
LOG_FILE="$BACKUP_DIR/run.log"
PASSPHRASE_FILE="$BACKUP_DIR/.last_key"

# ---------- 辅助函数 ----------
log() { echo -e "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
die() { log "${RED}错误: $*${NC}"; exit 1; }

# ---------- 0. 环境净化与噪音注入 ----------
noise_blind() {
    echo -e "${YELLOW}>>> 正在注入终端干扰信号 (抗录屏) ...${NC}"
    echo -ne "\033[?25l"  # 隐藏光标
    for i in {1..80}; do
        echo -n "$(openssl rand -base64 16 | head -c 24) "
    done
    echo -e "\n${BLUE}*** 模拟系统日志滚动 ***${NC}"
    sleep 1
    clear
    echo -e "${GREEN}[√] 干扰完成。${NC}"
}

# ---------- 1. 生成文件指纹清单 ----------
generate_manifest() {
    mkdir -p "$BACKUP_DIR"
    echo -e "${YELLOW}>>> 正在为 $DATA_DIR 生成指纹清单 ...${NC}"
    > "$MANIFEST_FILE"
    echo "# WATCHER MANIFEST - $(date '+%Y-%m-%d %H:%M:%S %Z')" >> "$MANIFEST_FILE"
    echo "# 验证: sha256sum -c manifest.sha256 2>/dev/null" >> "$MANIFEST_FILE"
    find "$DATA_DIR" -type f -print0 2>/dev/null | while IFS= read -r -d '' file; do
        hash=$(sha256sum "$file" | awk '{print $1}')
        size=$(stat -c %s "$file" 2>/dev/null || stat -f %z "$file" 2>/dev/null)
        mtime=$(stat -c %y "$file" 2>/dev/null || stat -f %Sm "$file" 2>/dev/null)
        echo "$hash  $file" >> "$MANIFEST_FILE"
        echo "# SIZE=$size | MTIME=$mtime" >> "$MANIFEST_FILE"
    done
    log "${GREEN}[√] 清单生成: $MANIFEST_FILE (共 $(grep -c '^[0-9a-f]' "$MANIFEST_FILE") 个文件)${NC}"
}

# ---------- 2. 加密备份 ----------
encrypt_backup() {
    echo -e "${YELLOW}>>> 创建加密备份 ...${NC}"
    local pass=$(openssl rand -base64 32)
    echo "$pass" > "$PASSPHRASE_FILE"
    chmod 600 "$PASSPHRASE_FILE"
    local tarball="$BACKUP_DIR/archive_$(date +%Y%m%d_%H%M%S).tgz.enc"
    tar -czf - -C "$DATA_DIR" . 2>/dev/null | \
        openssl enc -aes-256-cbc -salt -pbkdf2 -pass pass:"$pass" -out "$tarball"
    echo -e "${GREEN}[√] 加密备份: $tarball${NC}"
    echo -e "${RED}⚠️ 本次密钥（请抄在纸上，之后立即删除此文件）: ${pass}${NC}"
    echo "密钥已存入 $PASSPHRASE_FILE (请务必手动记录并立即删除该文件)"
}

# ---------- 3. 生成二维码（需 qrencode） ----------
qr_manifest() {
    if command -v qrencode >/dev/null 2>&1; then
        echo -e "${YELLOW}>>> 生成二维码摘要 ...${NC}"
        head -n 30 "$MANIFEST_FILE" | qrencode -t ANSIUTF8 -o -
        echo -e "${GREEN}[√] 请截图此二维码保存为纸质证据。${NC}"
    else
        echo -e "${YELLOW}[!] 未安装 qrencode，跳过二维码。手动保存清单。${NC}"
    fi
}

# ---------- 4. 假情报生成器 ----------
fake_data_feed() {
    echo -e "${YELLOW}>>> 生成假情报数据 (污染监控源) ...${NC}"
    local fake_dir="$DATA_DIR/.fake"
    mkdir -p "$fake_dir"
    for i in {1..5}; do
        echo "2026-08-$(printf '%02d' $((RANDOM%30+1))) 14:$((RANDOM%60)) 坐标: 45.${RANDOM:0:4}N 12.${RANDOM:0:4}E" >> "$fake_dir/log_$i.txt"
        echo "联系人: $(openssl rand -base64 6 | tr -d '/+=')" >> "$fake_dir/contacts_$i.txt"
        dd if=/dev/urandom of="$fake_dir/dummy_$i.bin" bs=1K count=$((RANDOM%5+1)) 2>/dev/null
    done
    log "${GREEN}[√] 已生成 $fake_dir 下的假数据。${NC}"
}

# ---------- 5. 进程与连接检查 ----------
check_threats() {
    echo -e "${YELLOW}>>> 检查可疑进程和连接 ...${NC}"
    echo "--- Top CPU 进程 ---"
    ps -eo pid,%cpu,args 2>/dev/null | sort -k2 -rn | head -8 || echo "ps 不可用"
    echo "--- 已知间谍软件名称检测 ---"
    local spy_names="mSpy|FlexiSpy|Pegasus|NSO|Hoverwatch|Cerberus|Spyera"
    ps -eo args 2>/dev/null | grep -iE "$spy_names" | head -5 && echo "${RED}⚠️ 发现可疑进程！${NC}" || echo "未发现常见间谍名。"
    echo "--- 活跃网络连接 ---"
    ss -tunap 2>/dev/null | grep ESTAB | head -5 || netstat -tunap 2>/dev/null | grep ESTABLISHED | head -5 || echo "无 netstat/ss"
}

# ---------- 6. 自毁痕迹 ----------
self_destruct() {
    echo -e "${YELLOW}>>> 清除操作痕迹 ...${NC}"
    history -c 2>/dev/null || true
    > ~/.bash_history 2>/dev/null || true
    > ~/.zsh_history 2>/dev/null || true
    find /data/data/com.termux/files/usr/tmp -type f -mmin -5 -exec shred -z -n 2 {} \; 2>/dev/null || true
    echo -e "${GREEN}[√] 本地痕迹已粉碎。${NC}"
}

# ---------- 主菜单 ----------
main_menu() {
    clear
    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}    WATCHER 守望者 v1.0${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo "1. 完整保护流程（指纹+备份+假情报+检查）"
    echo "2. 仅生成指纹清单"
    echo "3. 仅加密备份"
    echo "4. 注入假情报数据"
    echo "5. 检查进程与网络"
    echo "6. 自毁痕迹（不生成报告）"
    echo "0. 退出"
    echo -e "${BLUE}========================================${NC}"
    read -p "选择 [0-6]: " opt
    case $opt in
        1) noise_blind; mkdir -p "$DATA_DIR"; generate_manifest; encrypt_backup; qr_manifest; fake_data_feed; check_threats; self_destruct; echo -e "${GREEN}完成！${NC}";;
        2) generate_manifest; cat "$MANIFEST_FILE";;
        3) encrypt_backup;;
        4) fake_data_feed;;
        5) check_threats;;
        6) self_destruct;;
        0) exit 0;;
        *) echo "无效选项"; sleep 1; main_menu;;
    esac
}

# 检查是否在 Termux 中
if [ -z "$PREFIX" ] && [ ! -d "/data/data/com.termux" ]; then
    echo -e "${RED}警告: 此脚本专为 Termux (Android) 设计，在其他环境可能无法完全运行。${NC}"
fi

# 运行
main_menu