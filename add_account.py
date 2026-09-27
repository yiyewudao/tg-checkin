#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式添加打卡账号 (在软路由 SSH 里运行):
    python3 /root/tg-checkin/add_account.py
按提示输入手机号、API ID、API Hash, 收验证码完成登录,
脚本会自动把新账号追加到 env.sh, 下次定时打卡自动生效。
"""
import asyncio
import getpass
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, "env.sh")
sys.path.insert(0, BASE_DIR)
from checkin import parse_proxy  # noqa: E402
from telethon import TelegramClient  # noqa: E402
from telethon.errors import SessionPasswordNeededError  # noqa: E402


def read_env():
    vals = {}
    with open(ENV_FILE) as f:
        for line in f:
            m = re.match(r'export\s+(\w+)="(.*)"\s*$', line.strip())
            if m:
                vals[m.group(1)] = m.group(2)
    return vals


def write_env(vals):
    lines = []
    with open(ENV_FILE) as f:
        for line in f:
            m = re.match(r'export\s+(\w+)=', line.strip())
            if m and m.group(1) in vals:
                lines.append(f'export {m.group(1)}="{vals[m.group(1)]}"\n')
            else:
                lines.append(line)
    with open(ENV_FILE, "w") as f:
        f.writelines(lines)
    os.chmod(ENV_FILE, 0o600)


async def main():
    vals = read_env()
    phones = [p for p in vals.get("TG_PHONE", "").split(",") if p.strip()]
    print(f"当前已有 {len(phones)} 个账号: {', '.join(phones) if phones else '无'}")
    print("-" * 40)

    phone = input("手机号 (带+号, 如 +12524401456): ").strip()
    if not phone:
        print("手机号不能为空")
        return
    if phone in phones:
        print("该手机号已存在, 无需重复添加")
        return
    api_id = input("API ID: ").strip()
    api_hash = input("API Hash: ").strip()
    if not api_id or not api_hash:
        print("API ID / API Hash 不能为空")
        return

    proxy = parse_proxy(vals.get("TG_PROXY", "").strip())
    safe = "".join(c for c in phone if c.isdigit())
    session = os.path.join(BASE_DIR, f"checkin_session_{safe}")
    client = TelegramClient(session, int(api_id), api_hash, proxy=proxy)
    await client.connect()
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"该 session 已登录: {me.first_name} (@{me.username})")
        else:
            print("正在发送验证码到该号码的 Telegram App...")
            await client.send_code_request(phone)
            code = input("Telegram 验证码: ").strip()
            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                pw = getpass.getpass("两步验证密码: ")
                await client.sign_in(password=pw)
            me = await client.get_me()
            print(f"登录成功: {me.first_name} (@{me.username}) id={me.id}")

        # 追加到 env.sh, 三项数量保持一致
        def append(key, v):
            cur = vals.get(key, "").strip()
            vals[key] = f"{cur},{v}" if cur else v

        append("TG_API_ID", api_id)
        append("TG_API_HASH", api_hash)
        append("TG_PHONE", phone)
        write_env(vals)
        print(f"\n已加入打卡列表, 当前共 {len(phones) + 1} 个账号, 每天 10:00 自动打卡生效。")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
