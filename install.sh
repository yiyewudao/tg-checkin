#!/bin/sh
# TG 每日自动打卡 - 一键安装脚本 (OpenWrt / ImmortalWrt)
# 用法 (在软路由 SSH 里执行):
#   wget -qO- https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/tg-checkin/main/install.sh | sh
set -e

REPO="YOUR_GITHUB_USERNAME/tg-checkin"
BRANCH="main"
DIR=/root/tg-checkin
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH"

echo "== 1/4 安装系统依赖 =="
apk update
apk add python3 py3-pip wget ca-certificates

echo "== 2/4 安装 Python 依赖 =="
pip3 install --quiet telethon pysocks python-socks 2>/dev/null \
  || pip3 install --quiet --break-system-packages telethon pysocks python-socks

echo "== 3/4 下载脚本到 $DIR =="
mkdir -p "$DIR"
cd "$DIR"
for f in checkin.py add_account.py setup.py run.sh env.sh.example; do
  echo "  下载 $f"
  wget -q -O "$f" "$RAW/$f"
done
chmod 600 checkin.py add_account.py setup.py env.sh.example
chmod 700 run.sh
[ -f env.sh ] || cp env.sh.example env.sh
chmod 600 env.sh

echo "== 4/4 设置定时任务 (默认每天 10:00, 可用 setup.py 修改) =="
grep -q "tg-checkin/run.sh" /etc/crontabs/root 2>/dev/null \
  || echo "0 10 * * * /root/tg-checkin/run.sh" >> /etc/crontabs/root
/etc/init.d/cron restart

echo ""
echo "== 安装完成 =="
echo "运行下面这个命令开始配置 (加号/打卡时间/打卡目标/推送机器人):"
echo "  python3 /root/tg-checkin/setup.py"
