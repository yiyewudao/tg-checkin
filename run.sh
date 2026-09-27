#!/bin/sh
# 定时任务调用入口: 加载配置 -> 自愈依赖 -> 跑打卡 -> 写日志
DIR=/root/tg-checkin
[ -f "$DIR/env.sh" ] && . "$DIR/env.sh"
# 自愈: 固件"保留配置"升级后 pip 依赖会丢失, 缺失时自动重装
# (python3/python3-pip 已打进固件, /root/tg-checkin 需在 /etc/sysupgrade.conf 中备份)
if ! /usr/bin/python3 -c "import telethon" 2>/dev/null; then
  echo "$(date '+%F %T') telethon 缺失(可能刚升级过固件), 自动重装依赖..." >> "$DIR/checkin.log"
  PIP_ROOT_USER_ACTION=ignore /usr/bin/python3 -m pip install --quiet telethon pysocks python-socks >> "$DIR/checkin.log" 2>&1
fi
/usr/bin/python3 "$DIR/checkin.py" checkin >> "$DIR/checkin.log" 2>&1
