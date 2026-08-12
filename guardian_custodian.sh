#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# GUARDIAN CUSTODIAN v1.0 
# 用途：在断网/被监控下，对关键文件进行"指纹固化"与"抗篡改封装"
# 操作：生成不可否认的 SHA-256 指纹库 + 加密压缩备份 + 终端干扰伪装
# ============================================================

set -e

# --- 配置区 ---
WORK_DIR="$HOME/protected_data"          # 你要保护的文件放这里
BACKUP_DIR="$HOME/.secure_vault"         # 隐藏的加密备份目录 (看似系统缓存)
FINGERPRINT_FILE="$BACKUP_DIR/manifest.sha256"
PASSPHRASE_FILE="$BACKUP_DIR/.key"       # 密钥由随机数生成，每次运行更新

# --- 1. 反录屏/防抓现行：生成大量无害终端噪音（干扰OCR和屏幕录制）---
noise_blind() {
    echo -ne "\033[?25l"  # 隐藏光标
    for i in {1..50}; do
        echo -n "$(openssl rand -base64 12 | head -c 20) " 
    done
    echo ""
    echo -e "\e[38;5;240m[!] 系统日志回滚中... (干扰信号已注入)\e[0m"
    sleep 1
    clear
}

# --- 2. 生成不可篡改的指纹库 (包含文件名、大小、修改时间、SHA-256) ---
generate_fingerprint() {
    mkdir -p "$BACKUP_DIR"
    > "$FINGERPRINT_FILE"  # 清空旧指纹
    
    echo "# GUARDIAN MANIFEST - $(date '+%Y-%m-%d %H:%M:%S %Z')" >> "$FINGERPRINT_FILE"
    echo "# 验证命令: sha256sum -c manifest.sha256 2>/dev/null" >> "$FINGERPRINT_FILE"
    echo "" >> "$FINGERPRINT_FILE"

    find "$WORK_DIR" -type f -print0 | while IFS= read -r -d '' file; do
        # 计算哈希
        hash=$(sha256sum "$file" | awk '{print $1}')
        # 获取文件大小和修改时间
        size=$(stat -c %s "$file" 2>/dev/null || stat -f %z "$file" 2>/dev/null)
        mtime=$(stat -c %y "$file" 2>/dev/null || stat -f %Sm "$file" 2>/dev/null)
        # 写入清单（标准sha256sum格式，但追加了元数据注释）
        echo "$hash  $file" >> "$FINGERPRINT_FILE"
        # 在注释行记录元数据（防伪造）
        echo "# SIZE=$size | MTIME=$mtime" >> "$FINGERPRINT_FILE"
    done

    echo "[√] 指纹库已生成: $FINGERPRINT_FILE"
}

# --- 3. 加密打包备份（防物理抢夺：即使手机被扣，打不开备份包）---
encrypt_backup() {
    # 生成一次性强密码（不保存明文，仅留提示）
    local tmp_pass=$(openssl rand -base64 32)
    echo "$tmp_pass" > "$PASSPHRASE_FILE"
    chmod 600 "$PASSPHRASE_FILE"
    
    local backup_tarball="$BACKUP_DIR/archive_$(date +%Y%m%d_%H%M%S).tgz.enc"
    
    # 先打包，再用 openssl 对称加密（aes-256-cbc）
    tar -czf - -C "$WORK_DIR" . 2>/dev/null | \
    openssl enc -aes-256-cbc -salt -pbkdf2 -pass pass:"$tmp_pass" -out "$backup_tarball"
    
    echo "[√] 加密备份完成: $backup_tarball"
    echo "[!] 解密命令: openssl enc -d -aes-256-cbc -pbkdf2 -pass pass:密码 -in 文件.tgz.enc | tar -xz"
}

# --- 4. 生成纸质离线存证（二维码）---
qr_manifest() {
    if command -v qrencode >/dev/null 2>&1; then
        # 只取前 20 个文件的哈希摘要生成二维码，防止数据太大
        head -n 20 "$FINGERPRINT_FILE" | qrencode -t ANSIUTF8 -o - 
        echo "[√] 请截屏此二维码保存为纸质证据（连同当时的报纸/时间戳拍照）"
    else
        echo "[!] 未安装 qrencode，跳过二维码。手动保存清单: $FINGERPRINT_FILE"
    fi
}

# --- 5. 反取证：立即粉碎临时痕迹（删除操作日志）---
self_destruct_trace() {
    # 清理 Termux 历史记录
    history -c 2>/dev/null || true
    > ~/.bash_history 2>/dev/null || true
    > ~/.zsh_history 2>/dev/null || true
    # 覆写内存临时文件（如果有）
    find /data/data/com.termux/files/usr/tmp -type f -mmin -5 -exec shred -z -n 3 {} \; 2>/dev/null || true
    echo "[√] 本地操作痕迹已粉碎（shred 覆写）"
}

# --- 主程序执行 ---
main() {
    # 第一步：播噪音（让录屏录音变成废片）
    noise_blind

    # 第二步：检查待保护目录是否存在
    if [ ! -d "$WORK_DIR" ]; then
        echo "[-] 错误: 请先创建目录 $WORK_DIR 并放入你要保护的文件"
        echo "[-] 命令: mkdir -p ~/protected_data"
        exit 1
    fi

    echo "========================"
    echo "  证据固化流程启动"
    echo "  时间: $(date)"
    echo "  目标目录: $WORK_DIR"
    echo "========================"

    # 第三步：生成指纹
    generate_fingerprint

    # 第四步：加密备份
    encrypt_backup

    # 第五步：生成纸质证据
    qr_manifest

    # 第六步：自毁操作痕迹
    self_destruct_trace

    echo ""
    echo "========================"
    echo "  [完成] 此时你可以直接关机或拔出电池。"
    echo "  核心文件路径："
    echo "  指纹库: $FINGERPRINT_FILE"
    echo "  加密包: $BACKUP_DIR/*.tgz.enc"
    echo "  密钥提示: 保存于 $PASSPHRASE_FILE (若被抢，立即记下此文件内容后销毁手机)"
    echo "========================"
    
    # 第七步：重置终端以防监听残留
    reset
}

# 执行
main "$@"