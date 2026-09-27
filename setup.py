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
        for k in sorted(vals):
            if k.startswith("TG_TARGETS_") and k not in order:
                f.write(f'export {k}="{vals[k]}"\n')
    os.chmod(ENV_FILE, 0o600)


def mask(v, key):
    if not v:
        return "未配置"
    if key in ("TG_API_HASH", "TG_NOTIFY_BOT_TOKEN"):
        return v[:6] + "***"
    return v


def show_current(vals):
    phones = [p for p in vals.get("TG_PHONE", "").split(",") if p.strip()]
    per = per_account_targets(vals)
    print("=" * 46)
    print("当前配置:")
    print(f"  TG 账号 ({len(phones)}): {', '.join(phones) if phones else '无'}")
    print(f"  打卡目标(统一): {vals.get('TG_TARGETS') or 'sheeridverifier_bot:/checkin (默认)'}")
    for digits, (kind, v) in sorted(per.items()):
        print(f"    └ {digits} {kind}模式: {v}")
    print(f"  推送机器人: {'已配置' if vals.get('TG_NOTIFY_BOT_TOKEN') else '未配置'}")
    print(f"  代理: {vals.get('TG_PROXY') or '未配置'}")
    print(f"  打卡时间: {current_cron()}")
    print("=" * 46)


def is_openwrt():
    return os.path.exists("/etc/crontabs/root")


def parse_cron_line(line):
    parts = line.split()
    return f"每天 {parts[1]}:{parts[0].zfill(2)}"


def current_cron():
    if is_openwrt():
        try:
            with open(CRON_FILE) as f:
                for line in f:
                    if RUN_LINE in line:
                        return parse_cron_line(line)
        except FileNotFoundError:
            pass
    else:
        try:
            out = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
            for line in out.splitlines():
                if RUN_LINE in line:
                    return parse_cron_line(line)
        except FileNotFoundError:
            pass
    return "未设置"


def set_cron(hour, minute):
    new_line = f"{minute} {hour} * * * {RUN_LINE}"
    if is_openwrt():
        lines, found = [], False
        try:
            with open(CRON_FILE) as f:
                lines = f.readlines()
        except FileNotFoundError:
            pass
        out = []
        for line in lines:
            if RUN_LINE in line:
                out.append(new_line + "\n")
                found = True
            else:
                out.append(line)
        if not found:
            out.append(new_line + "\n")
        with open(CRON_FILE, "w") as f:
            f.writelines(out)
        subprocess.run(["/etc/init.d/cron", "restart"], capture_output=True)
    else:
        cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        lines = [l for l in cur.splitlines() if RUN_LINE not in l]
        lines.append(new_line)
        p = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n",
                           text=True, capture_output=True)
        if p.returncode != 0:
            print("写入 crontab 失败:", p.stderr.strip()[:200])
            return
    print(f"已设置为每天 {hour}:{str(minute).zfill(2)} 打卡")


async def add_account_flow():
    sys.path.insert(0, BASE_DIR)
    import add_account
    await add_account.main()


def manual_checkin(vals):
    print("开始手动打卡...")
    env = dict(os.environ)
    for k, v in vals.items():
        env[k] = v
    r = subprocess.run([sys.executable, os.path.join(BASE_DIR, "checkin.py"),
                        "checkin"], env=env)
    print("打卡结束" if r.returncode == 0 else "打卡异常, 看上方日志")


def prompt_targets():
    """逐行读取打卡目标, 返回列表; 首行即空行返回空列表。"""
    print("逐行输入打卡目标, 格式: bot用户名:命令")
    print("例: sheeridverifier_bot:/checkin")
    print("命令留空则用按钮模式 (自动点签到按钮)。空行结束:")
    targets = []
    while True:
        line = input("> ").strip().lstrip("@")
        if not line:
            break
        targets.append(line)
    return targets


def prompt_extras():
    """输入某账号的额外目标。返回 (changed, new_value)。"""
    print("逐行输入额外打卡目标, 空行结束。")
    print("首行直接回车=保持不变, 首行只输入 - =清除额外目标:")
    lines = []
    while True:
        line = input("> ").strip().lstrip("@")
        if not line:
            break
        lines.append(line)
    if not lines:
        return False, ""
    if lines == ["-"]:
        return True, ""
    return True, ",".join(lines)


def target_names(raw):
    """从 'bot:/cmd,group:' 提取 [bot, group]。"""
    names = []
    for item in (raw or "").split(","):
        name = item.strip().lstrip("@").partition(":")[0].strip()
        if name:
            names.append(name)
    return names


def per_account_targets(vals):
    """返回 {手机号数字: (模式, 值)}, 模式为 '独立' 或 '额外'。"""
    out = {}
    for k, v in vals.items():
        if not v:
            continue
        if k.startswith("TG_TARGETS_ADD_"):
            out[k[len("TG_TARGETS_ADD_"):]] = ("额外", v)
        elif k.startswith("TG_TARGETS_"):
            out[k[len("TG_TARGETS_"):]] = ("独立", v)
    return out


def audit_targets(vals, phones):
    """统一目标变更后检查并汇报:
    1) 额外目标里已包含在统一目标中的 -> 自动去除并汇报;
    2) 账号已不在列表中的残留配置 -> 汇报并询问是否清除。"""
    unified = set(target_names(vals.get("TG_TARGETS", "")))
    phone_digits = {"".join(c for c in p if c.isdigit()) for p in phones}
    for k in sorted([k for k in vals if k.startswith("TG_TARGETS_") and vals[k]]):
        is_add = k.startswith("TG_TARGETS_ADD_")
        digits = k[len("TG_TARGETS_ADD_" if is_add else "TG_TARGETS_"):]
        if digits not in phone_digits:
            print(f"⚠ {digits} 的{'额外' if is_add else '独立'}目标残留 (该账号已不在列表中): {vals[k]}")
            ans = input("是否清除? (y/N): ").strip().lower()
            if ans in ("y", "yes"):
                del vals[k]
                print("已清除")
            continue
        if is_add:
            redundant = [n for n in target_names(vals[k]) if n in unified]
            if redundant:
                print(f"⚠ 账号 {digits} 的额外目标 {','.join(redundant)} 已在统一目标中, 自动去除")
                keep = [item for item in vals[k].split(",")
                        if item.strip().lstrip("@").partition(":")[0].strip() not in redundant]
                if keep:
                    vals[k] = ",".join(keep)
                else:
                    del vals[k]


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
        print("7. 查看近7天打卡情况")
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
            print("1. 所有账号用同一套打卡目标")
            print("2. 每个账号分别设置打卡目标 (独立)")
            print("3. 统一目标 + 个别账号额外加目标")
            sub = input("选: ").strip()
            phones = [p for p in vals.get("TG_PHONE", "").split(",") if p.strip()]
            if sub == "1":
                targets = prompt_targets()
                if not targets:
                    print("未输入, 未修改")
                    continue
                vals["TG_TARGETS"] = ",".join(targets)
                per = per_account_targets(vals)
                if per:
                    print("⚠ 统一后以下账号的单独设置将不存在:")
                    for digits, (kind, v) in sorted(per.items()):
                        print(f"  {digits} ({kind}模式): {v}")
                    ans = input("确认清除这些单独设置? (y/N): ").strip().lower()
                    if ans in ("y", "yes"):
                        for k in [k for k in vals if k.startswith("TG_TARGETS_")]:
                            del vals[k]
                        print("单独设置已清除")
                    else:
                        print("已保留单独设置 (这些账号仍用自己的目标, 不跟随统一)")
                else:
                    print("已设为统一目标")
                audit_targets(vals, phones)
                write_env(vals)
            elif sub == "2":
                if not phones:
                    print("还没有账号, 先用菜单 1 加号")
                    continue
                for p in phones:
                    digits = "".join(c for c in p if c.isdigit())
                    key = f"TG_TARGETS_{digits}"
                    add_key = f"TG_TARGETS_ADD_{digits}"
                    cur = vals.get(key, "")
                    print(f"--- 账号 {p} (当前: {cur or '跟随统一设置'}) ---")
                    print("直接回车=跟随统一设置, 输入目标=单独设置")
                    targets = prompt_targets()
                    if targets:
                        vals[key] = ",".join(targets)
                        if add_key in vals:
                            del vals[add_key]
                            print(f"{p} 的额外目标已清除 (独立模式优先)")
                        print(f"{p} 已单独设置")
                    elif key in vals:
                        del vals[key]
                        print(f"{p} 已改回跟随统一设置")
                write_env(vals)
            elif sub == "3":
                if not phones:
                    print("还没有账号, 先用菜单 1 加号")
                    continue
                print("先设置统一目标 (首行回车=保持当前)")
                targets = prompt_targets()
                if targets:
                    vals["TG_TARGETS"] = ",".join(targets)
                    print("统一目标已更新")
                for p in phones:
                    digits = "".join(c for c in p if c.isdigit())
                    key = f"TG_TARGETS_ADD_{digits}"
                    rep_key = f"TG_TARGETS_{digits}"
                    if rep_key in vals:
                        print(f"--- 账号 {p} 当前为独立模式, 转为额外模式 (独立设置将清除) ---")
                        del vals[rep_key]
                    cur = vals.get(key, "")
                    print(f"--- 账号 {p} (当前额外: {cur or '无'}) ---")
                    changed, new_val = prompt_extras()
                    if changed:
                        if new_val:
                            vals[key] = new_val
                            print(f"{p} 额外目标已设置")
                        else:
                            vals.pop(key, None)
                            print(f"{p} 额外目标已清除")
                audit_targets(vals, phones)
                write_env(vals)
            else:
                print("无效选项")
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
            manual_checkin(vals)
        elif choice == "7":
            subprocess.run([sys.executable, os.path.join(BASE_DIR, "checkin.py"), "status"])
            ans = input("是否立即手动打卡一次? (y/N): ").strip().lower()
            if ans in ("y", "yes"):
                manual_checkin(vals)
        elif choice == "0":
            print("退出")
            break
        else:
            print("无效选项")
        print()


if __name__ == "__main__":
    main()
