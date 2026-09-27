#!/bin/sh
# TG 每日自动打卡 - 服务器一键安装 (Debian / Ubuntu)
# 用法 (root 用户执行):
#   wget -qO- https://raw.githubusercontent.com/yiyewudao/tg-checkin/main/install-server.sh | sh
set -e

if [ "$(id -u)" -ne 0 ]; then
  echo "请用 root 用户运行此脚本 (如: sudo sh)"
  exit 1
fi

REPO="yiyewudao/tg-checkin"
BRANCH="main"
DIR=/root/tg-checkin
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH"

dl() {
  # $1=url $2=dest : 先尝试免认证下载, 失败(私有仓库)再要 token
  if curl -sfL -o "$2" "$1" 2>/dev/null; then
    return 0
  fi
  if [ -z "$GITHUB_TOKEN" ]; then
    printf "仓库是私有的, 请输入 GitHub Personal Access Token (需 repo 权限, 输入不回显): "
    read -s GITHUB_TOKEN
    echo ""
  fi
  curl -sfL -H "Authorization: Bearer $GITHUB_TOKEN" -o "$2" "$1"
}

echo "== 1/4 安装系统依赖 =="
apt-get update -qq
apt-get install -y -qq python3 python3-pip curl ca-certificates cron

echo "== 2/4 安装 Python 依赖 =="
PIP_ROOT_USER_ACTION=ignore pip3 install --quiet telethon pysocks python-socks 2>/dev/null \
  || PIP_ROOT_USER_ACTION=ignore pip3 install --quiet --break-system-packages telethon pysocks python-socks

echo "== 3/4 下载脚本到 $DIR =="
mkdir -p "$DIR"
cd "$DIR"
for f in checkin.py add_account.py setup.py run.sh env.sh.example; do
  echo "  下载 $f"
  dl "$RAW/$f" "$f"
done
chmod 600 checkin.py add_account.py setup.py env.sh.example
chmod 700 run.sh
[ -f env.sh ] || cp env.sh.example env.sh
chmod 600 env.sh

echo "== 4/4 设置定时任务 =="
# 打卡时间: 可用环境变量 CHECKIN_TIME 预设 (如 9:30), 否则交互询问, 默认 10:00
if [ -z "$CHECKIN_TIME" ]; then
  printf "每天几点打卡? (默认 10:00, 格式如 9:30, 直接回车用默认): "
  read CHECKIN_TIME < /dev/tty 2>/dev/null || CHECKIN_TIME=""
fi
CHECKIN_TIME="${CHECKIN_TIME:-10:00}"
CRON_H="${CHECKIN_TIME%%:*}"
CRON_M="${CHECKIN_TIME##*:}"
[ "$CRON_H" = "$CRON_M" ] && CRON_M=0
CRON_H=$(echo "$CRON_H" | tr -cd '0-9')
CRON_M=$(echo "$CRON_M" | tr -cd '0-9')
[ -z "$CRON_H" ] && CRON_H=10
[ -z "$CRON_M" ] && CRON_M=0
if [ "$CRON_H" -gt 23 ] || [ "$CRON_M" -gt 59 ]; then CRON_H=10; CRON_M=0; fi
( crontab -l 2>/dev/null | grep -v "tg-checkin/run.sh"; echo "$CRON_M $CRON_H * * * /root/tg-checkin/run.sh" ) | crontab -
service cron start 2>/dev/null || systemctl start cron 2>/dev/null || true
echo "已设置为每天 $CRON_H:$(printf %02d $CRON_M) 打卡 (以后可用 setup.py 修改)"

echo ""
echo "== 安装完成 =="
echo "运行下面这个命令开始配置 (加号/打卡时间/打卡目标/推送机器人):"
echo "  python3 /root/tg-checkin/setup.py"
