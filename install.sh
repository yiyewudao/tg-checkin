#!/bin/sh
# TG 每日自动打卡 - 一键安装脚本 (OpenWrt / ImmortalWrt)
# 公开仓库:
#   wget -qO- https://raw.githubusercontent.com/GITHUB_USER/tg-checkin/main/install.sh | sh
# 私有仓库 (先下载再运行, 按提示输入 token):
#   curl -sfL -H "Authorization: Bearer 你的TOKEN" \
#     -o /tmp/install.sh https://raw.githubusercontent.com/GITHUB_USER/tg-checkin/main/install.sh \
#     && sh /tmp/install.sh
#   (想跳过手动输入可先执行: export GITHUB_TOKEN=你的TOKEN)
set -e

REPO="GITHUB_USER/tg-checkin"
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
apk update
apk add python3 py3-pip curl ca-certificates wget

echo "== 2/4 安装 Python 依赖 =="
pip3 install --quiet telethon pysocks python-socks 2>/dev/null \
  || pip3 install --quiet --break-system-packages telethon pysocks python-socks

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

echo "== 4/4 设置定时任务 (默认每天 10:00, 可用 setup.py 修改) =="
grep -q "tg-checkin/run.sh" /etc/crontabs/root 2>/dev/null \
  || echo "0 10 * * * /root/tg-checkin/run.sh" >> /etc/crontabs/root
/etc/init.d/cron restart

echo ""
echo "== 安装完成 =="
echo "运行下面这个命令开始配置 (加号/打卡时间/打卡目标/推送机器人):"
echo "  python3 /root/tg-checkin/setup.py"
