#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TG 打卡一站式配置向导 (在软路由 SSH 里运行):
    python3 /root/tg-checkin/setup.py
一个命令搞定: 加 TG 号 / 打卡时间 / 打卡目标(bot或群+命令) / 推送机器人 / 代理 / 测试打卡。
"""
import asyncio
import os
import re
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, "env.sh")
CRON_FILE = "/etc/crontabs/root"
RUN_LINE = "/root/tg-checkin/run.sh"


def read_env():
    vals = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                m = re.match(r'export\s+(\w+)="(.*)"\s*$', line.strip())
                if m:
                    vals[m.group(1)] = m.group(2)
    return vals


def write_env(vals):
    order = ["TG_API_ID", "TG_API_HASH", "TG_PHONE", "TG_PROXY",
             "TG_TARGETS", "TG_NOTIFY_BOT_TOKEN", "TG_NOTIFY_CHAT_ID"]
    with open(ENV_FILE, "w") as f:
        for k in order:
            f.write(f'export {k}="{vals.get(k, "")}"\n')
    os.chmod(ENV_FILE, 0o600)


def mask(v, key):
    if not v:
        return "未配置"
    if key in ("TG_API_HASH", "TG_NOTIFY_BOT_TOKEN"):
        return v[:6] + "***"
    return v


def show_current(vals):
    phones = [p for p in vals.get("TG_PHONE", "").split(",") if p.strip()]
    print("=" * 46)
    print("当前配置:")
    print(f"  TG 账号 ({len(phones)}): {', '.join(phones) if phones else '无'}")
    print(f"  打卡目标: {vals.get('TG_TARGETS') or 'sheeridverifier_bot:/checkin (默认)'}")
    print(f"  推送机器人: {'已配置' if vals.get('TG_NOTIFY_BOT_TOKEN') else '未配置'}")
    print(f"  代理: {vals.get('TG_PROXY') or '未配置'}")
    print(f"  打卡时间: {current_cron()}")
    print("=" * 46)


def current_cron():
    try:
        with open(CRON_FILE) as f:
            for line in f:
                if RUN_LINE in line:
                    parts = line.split()
                    return f"每天 {parts[1]}:{parts[0].zfill(2)}"
    except FileNotFoundError:
        pass
    return "未设置"


def set_cron(hour, minute):
    lines, found = [], False
    try:
        with open(CRON_FILE) as f:
            lines = f.readlines()
    except FileNotFoundError:
        pass
    out = []
    for line in lines:
        if RUN_LINE in line:
            out.append(f"{minute} {hour} * * * {RUN_LINE}\n")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{minute} {hour} * * * {RUN_LINE}\n")
    with open(CRON_FILE, "w") as f:
        f.writelines(out)
    subprocess.run(["/etc/init.d/cron", "restart"], capture_output=True)
    print(f"已设置为每天 {hour}:{str(minute).zfill(2)} 打卡")


async def add_account_flow():
    sys.path.insert(0, BASE_DIR)
    import add_account
    await add_account.main()


def main():
    vals = read_env()
    while True:
        show_current(vals)
        print("1. 添加 TG 账号")
        print("2. 设置打卡时间")
        print("3. 设置打卡目标 (bot/群 + 命令)")
        print("4. 设置推送机器人")
        print("5. 设置代理")
        print("6. 立即测试打卡一次")
        print("0. 退出")
        choice = input("选: ").strip()
        if choice == "1":
            asyncio.run(add_account_flow())
            vals = read_env()
        elif choice == "2":
            h = input("小时 (0-23, 如 10): ").strip()
            m = input("分钟 (0-59, 如 0): ").strip() or "0"
            if h.isdigit() and m.isdigit() and 0 <= int(h) <= 23 and 0 <= int(m) <= 59:
                set_cron(int(h), int(m))
            else:
                print("时间格式不对")
        elif choice == "3":
            print("逐行输入打卡目标, 格式: bot用户名:命令")
            print("例: sheeridverifier_bot:/checkin")
            print("命令留空则用按钮模式 (自动点签到按钮)。空行结束:")
            targets = []
            while True:
                line = input("> ").strip().lstrip("@")
                if not line:
                    break
                targets.append(line)
            if targets:
                vals["TG_TARGETS"] = ",".join(targets)
                write_env(vals)
                print(f"已设置 {len(targets)} 个目标")
        elif choice == "4":
            token = input("机器人 token (BotFather 给的): ").strip()
            chat_id = input("chat ID: ").strip()
            if token and chat_id:
                vals["TG_NOTIFY_BOT_TOKEN"] = token
                vals["TG_NOTIFY_CHAT_ID"] = chat_id
                write_env(vals)
                print("推送机器人已配置")
            else:
                print("token 和 chat ID 不能为空")
        elif choice == "5":
            cur = vals.get("TG_PROXY", "")
            p = input(f"代理地址 (回车保持 {cur or '未配置'}): ").strip()
            if p:
                vals["TG_PROXY"] = p
                write_env(vals)
                print("代理已更新")
        elif choice == "6":
            print("开始测试打卡...")
            env = dict(os.environ)
            for k, v in vals.items():
                env[k] = v
            r = subprocess.run([sys.executable, os.path.join(BASE_DIR, "checkin.py"),
                                "checkin"], env=env)
            print("测试结束" if r.returncode == 0 else "测试异常, 看上方日志")
        elif choice == "0":
            print("退出")
            break
        else:
            print("无效选项")
        print()


if __name__ == "__main__":
    main()
