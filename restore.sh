#!/bin/sh
# 一键恢复: 把备份的 tg-checkin 文件夹放回 /root/ 后, 跑这个脚本即可
# 用法: sh /root/tg-checkin/restore.sh
# 做: 装 python3/pip -> 装 telethon 依赖 -> 补 cron 定时任务 -> 验证账号
DIR=/root/tg-checkin

# 1. python3 / pip (新固件自带则跳过)
if ! command -v python3 >/dev/null 2>&1; then
  echo "[1/4] 安装 python3..."
  apk update >/dev/null 2>&1
  apk add python3 py3-pip || { echo "python3 安装失败, 请检查网络"; exit 1; }
else
  echo "[1/4] python3 已存在, 跳过"
fi

# 2. 权限修正
[ -f "$DIR/env.sh" ] && chmod 600 "$DIR/env.sh"
[ -f "$DIR/run.sh" ] && chmod +x "$DIR/run.sh"
echo "[2/4] 权限已修正"

# 3. telethon 等依赖
if ! python3 -c "import telethon" 2>/dev/null; then
  echo "[3/4] 安装 telethon 等依赖..."
  PIP_ROOT_USER_ACTION=ignore python3 -m pip install --quiet telethon pysocks python-socks || { echo "依赖安装失败, 请检查网络"; exit 1; }
else
  echo "[3/4] telethon 已存在, 跳过"
fi

# 4. cron 定时任务 (默认每天 10:00, 改时间用 setup.py)
if grep -q "tg-checkin/run.sh" /etc/crontabs/root 2>/dev/null; then
  echo "[4/4] 定时任务已存在, 跳过"
else
  echo "0 10 * * * $DIR/run.sh" >> /etc/crontabs/root
  /etc/init.d/cron restart >/dev/null 2>&1
  echo "[4/4] 已添加每天 10:00 打卡定时任务"
fi

# 5. 验证: 账号能列出来 = 恢复成功
echo "=== 验证账号 ==="
[ -f "$DIR/env.sh" ] && . "$DIR/env.sh"
python3 "$DIR/checkin.py" status 2>&1 | head -20
