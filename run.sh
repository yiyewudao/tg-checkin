#!/bin/sh
# 定时任务调用入口: 加载配置 -> 跑打卡 -> 写日志
DIR=/root/tg-checkin
[ -f "$DIR/env.sh" ] && . "$DIR/env.sh"
/usr/bin/python3 "$DIR/checkin.py" checkin >> "$DIR/checkin.log" 2>&1
