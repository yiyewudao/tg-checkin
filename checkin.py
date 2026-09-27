#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram 每日自动打卡脚本 (软路由/OpenWrt 版, Telethon userbot, 多账号)
用法:
    python3 checkin.py probe    # 首次运行: 交互登录 + 查看 bot 的消息/按钮(不点击)
    python3 checkin.py checkin  # 每日打卡: 每个账号依次给目标 bot 发打卡指令, 结束后推送报告
    python3 checkin.py status   # 查看近7天打卡情况
环境变量 (多个账号用英文逗号分隔, 三个变量的账号数量必须一致):
    TG_API_ID   如: 123456,234567
    TG_API_HASH 如: aabbcc,ddeeff
    TG_PHONE    如: +13237141808,+15555555555
    TG_PROXY    (可选, 所有账号共用, 例如 socks5://127.0.0.1:7891)
打卡目标 (可选):
    TG_TARGETS  格式 bot名:命令, 多个用英文逗号分隔, 例如:
                sheeridverifier_bot:/checkin,mygroup:/sign
                命令留空则走按钮点击模式 (自动点含"签到/打卡"关键词的按钮)
                不配置则默认 sheeridverifier_bot:/checkin
打卡报告推送 (可选, 配置后每次 checkin 结束推送成功/失败清单):
    TG_NOTIFY_BOT_TOKEN  推送用机器人 token (BotFather 处获取)
    TG_NOTIFY_CHAT_ID    接收报告的 chat id (先给机器人发任意消息, 再通过 getUpdates 查)
"""
import asyncio
import datetime
import json
import logging
import random
import os
import re
import subprocess
import sys

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "checkin_history.jsonl")

# 默认打卡目标 (TG_TARGETS 未配置时使用): bot/群用户名 -> 打卡指令(直接发送)
# 值为 None 则走按钮点击流程 (关键词见 BUTTON_KEYWORDS)
DEFAULT_TARGETS = {
    "sheeridverifier_bot": "/checkin",
}

# 按钮式打卡时的按钮文字关键词(任一命中即点击), 仅当目标命令为空时使用
BUTTON_KEYWORDS = ["签到", "打卡", "check in", "check-in", "checkin", "✅", "☑"]

PROXY_URL = os.environ.get("TG_PROXY", "").strip()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("checkin")


def load_targets():
    """从 TG_TARGETS 解析打卡目标, 未配置则用默认。"""
    raw = os.environ.get("TG_TARGETS", "").strip()
    if not raw:
        return dict(DEFAULT_TARGETS)
    targets = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        name, _, cmd = item.partition(":")
        name = name.strip().lstrip("@")
        cmd = cmd.strip()
        if name:
            targets[name] = cmd or None
    return targets or dict(DEFAULT_TARGETS)


TARGETS = load_targets()


def load_accounts():
    """解析多账号配置, 返回 [(api_id, api_hash, phone, session_file), ...]。"""
    ids = [s.strip() for s in os.environ.get("TG_API_ID", "").split(",") if s.strip()]
    hashes = [s.strip() for s in os.environ.get("TG_API_HASH", "").split(",") if s.strip()]
    phones = [s.strip() for s in os.environ.get("TG_PHONE", "").split(",") if s.strip()]
    if not ids or not hashes or not phones:
        print("请先设置环境变量 TG_API_ID / TG_API_HASH / TG_PHONE (多个账号用英文逗号分隔)")
        sys.exit(1)
    if not (len(ids) == len(hashes) == len(phones)):
        print(f"账号数量不一致: API_ID {len(ids)} 个, API_HASH {len(hashes)} 个, PHONE {len(phones)} 个")
        sys.exit(1)
    accounts = []
    for api_id, api_hash, phone in zip(ids, hashes, phones):
        safe = "".join(c for c in phone if c.isdigit()) or "nophone"
        session = os.path.join(BASE_DIR, f"checkin_session_{safe}")
        accounts.append((int(api_id), api_hash, phone, session))
    return accounts


def parse_proxy(url):
    """socks5://127.0.0.1:7890 或 http://127.0.0.1:7890 -> telethon proxy 元组。"""
    if not url:
        return None
    scheme, _, rest = url.partition("://")
    host, _, port = rest.partition(":")
    port = int(port or 0)
    if scheme in ("socks5", "socks5h"):
        return ("socks5", host, port)
    if scheme == "http":
        return ("http", host, port)
    raise ValueError(f"不支持的代理协议: {scheme}")


def curl_proxy_args():
    """给 curl 用的代理参数 (socks5 -> socks5h, 远端解析域名)。"""
    if not PROXY_URL:
        return []
    px = PROXY_URL
    if px.startswith("socks5://"):
        px = "socks5h://" + px[len("socks5://"):]
    return ["-x", px]


async def ensure_login(client, phone, interactive, tag):
    await client.connect()
    if await client.is_user_authorized():
        me = await client.get_me()
        log.info("[%s] 已登录: %s (@%s)", tag, me.first_name, me.username)
        return
    if not interactive:
        log.error("[%s] 登录态失效且非交互模式, 跳过。请手动跑一次 probe 模式重新登录。", tag)
        raise RuntimeError("login expired")
    await client.send_code_request(phone)
    code = input(f"[{tag}] Telegram 验证码: ").strip()
    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        import getpass
        pw = getpass.getpass(f"[{tag}] 两步验证密码: ")
        await client.sign_in(password=pw)
    me = await client.get_me()
    log.info("[%s] 登录成功: %s (@%s)", tag, me.first_name, me.username)


async def probe_bot(client, bot_username):
    """只看不点: 输出 bot 最近消息与按钮, 用于确认打卡流程。"""
    bot = await client.get_entity(bot_username)
    await client.send_message(bot, "/start")
    await asyncio.sleep(4)
    msgs = await client.get_messages(bot, limit=5)
    for m in msgs:
        print("=" * 50)
        print("消息内容:", (m.text or "")[:800])
        if m.buttons:
            for row in m.buttons:
                for b in row:
                    print("按钮:", b.text)
        else:
            print("(无按钮)")


async def click_button_checkin(client, bot_username):
    """按钮式打卡: 发 /start 后点击含关键词的内联按钮。"""
    bot = await client.get_entity(bot_username)
    await client.send_message(bot, "/start")
    await asyncio.sleep(4)
    clicked = None
    async for m in client.iter_messages(bot, limit=8):
        if not m.buttons:
            continue
        for row in m.buttons:
            for b in row:
                text = (b.text or "")
                if any(k.lower() in text.lower() for k in BUTTON_KEYWORDS):
                    await m.click(text=b.text)
                    clicked = text
                    break
            if clicked:
                break
        if clicked:
            break
    return f"已点击: {clicked}" if clicked else "未找到打卡按钮"


async def do_checkin(client, tag):
    results = {}
    for bot_username, command in TARGETS.items():
        try:
            if command:
                bot = await client.get_entity(bot_username)
                await client.send_message(bot, command)
                await asyncio.sleep(4)
                last = await client.get_messages(bot, limit=1)
                reply = (last[0].text or "")[:120] if last else ""
                results[bot_username] = f"已发送 {command}" + (f", 回执: {reply}" if reply else "")
            else:
                results[bot_username] = await click_button_checkin(client, bot_username)
            await asyncio.sleep(2)
        except Exception as e:  # noqa: BLE001
            results[bot_username] = f"失败: {type(e).__name__}: {e}"
    for k, v in results.items():
        log.info("[%s] %s -> %s", tag, k, v)
    return results


def send_notify(outcomes):
    """打卡结束后推送报告到指定机器人。outcomes: [(phone, ok, detail), ...]。"""
    token = os.environ.get("TG_NOTIFY_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TG_NOTIFY_CHAT_ID", "").strip()
    if not token or not chat_id:
        log.info("未配置 TG_NOTIFY_BOT_TOKEN/TG_NOTIFY_CHAT_ID, 跳过推送")
        return
    ok_list = [p for p, ok, _ in outcomes if ok]
    fail_list = [(p, d) for p, ok, d in outcomes if not ok]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"📋 TG 打卡报告 {now}", ""]
    lines.append(f"✅ 成功 ({len(ok_list)}):")
    lines.extend(f"  • {p}" for p in ok_list) if ok_list else lines.append("  无")
    lines.append(f"❌ 失败 ({len(fail_list)}):")
    lines.extend(f"  • {p}: {d}" for p, d in fail_list) if fail_list else lines.append("  无")
    text = "\n".join(lines)
    cmd = ["curl", "-s", "-m", "30", *curl_proxy_args(),
           "--data-urlencode", f"chat_id={chat_id}",
           "--data-urlencode", f"text={text}",
           f"https://api.telegram.org/bot{token}/sendMessage"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
        if '"ok":true' in r.stdout:
            log.info("打卡报告已推送到机器人")
        else:
            log.warning("推送报告失败: %s", (r.stdout or r.stderr)[:200])
    except Exception as e:  # noqa: BLE001
        log.warning("推送报告异常: %s", e)


async def run_account(api_id, api_hash, phone, session_file, proxy, mode):
    tag = phone
    client = TelegramClient(session_file, api_id, api_hash, proxy=proxy)
    try:
        await ensure_login(client, phone, interactive=(mode == "probe"), tag=tag)
        if mode == "probe":
            for bot in TARGETS:
                print(f"\n### [{tag}] 探测 @{bot} ###")
                await probe_bot(client, bot)
            return True, "probe 完成"
        results = await do_checkin(client, tag)
        bad = [f"{k}: {v}" for k, v in results.items() if v.startswith("失败")]
        if bad:
            return False, "; ".join(bad)
        return True, "; ".join(f"{k}: {v}" for k, v in results.items())
    except RuntimeError as e:
        return False, f"登录失效: {e}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
    finally:
        await client.disconnect()


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "checkin"
    if mode == "status":
        show_status()
        return
    accounts = load_accounts()
    proxy = parse_proxy(PROXY_URL)
    if proxy:
        log.info("使用代理: %s", PROXY_URL)
    log.info("共 %d 个账号, 打卡目标: %s", len(accounts),
             ", ".join(f"{k}->{v or '按钮模式'}" for k, v in TARGETS.items()))
    outcomes = []
    for i, (api_id, api_hash, phone, session_file) in enumerate(accounts):
        ok, detail = await run_account(api_id, api_hash, phone, session_file, proxy, mode)
        outcomes.append((phone, ok, detail))
        if i < len(accounts) - 1:
            if mode == "checkin":
                delay = 5 + random.random() * 8
                log.info("等待 %.1f 秒后处理下一个账号...", delay)
                await asyncio.sleep(delay)
            else:
                await asyncio.sleep(2)
    if mode == "checkin":
        send_notify(outcomes)
        save_history(outcomes)


def save_history(outcomes):
    """每次打卡后记一条结构化记录, 供 status 命令查看近7天情况。"""
    rec = {
        "date": datetime.date.today().isoformat(),
        "time": datetime.datetime.now().strftime("%H:%M"),
        "accounts": [
            {"phone": p, "ok": ok, "detail": d[:200]} for p, ok, d in outcomes
        ],
    }
    try:
        with open(HISTORY_FILE, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        log.warning("写入打卡历史失败: %s", e)


def show_status():
    """查看近7天打卡情况: 优先读结构化历史, 缺失的日期回退解析 checkin.log。"""
    today = datetime.date.today()
    days = [(today - datetime.timedelta(days=i)).isoformat() for i in range(7)]
    days_set = set(days)
    records = {}  # date -> {phone: (ok, detail)}
    jsonl_dates = set()

    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                d = rec.get("date", "")
                if d not in days_set:
                    continue
                jsonl_dates.add(d)
                for a in rec.get("accounts", []):
                    records.setdefault(d, {})[a.get("phone", "?")] = (
                        bool(a.get("ok")), a.get("detail", "")[:100])

    logf = os.path.join(BASE_DIR, "checkin.log")
    pat = re.compile(r"^(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}.*\[(\+[\d]+)\] (\S+) -> (.*)$")
    if os.path.exists(logf):
        with open(logf, encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = pat.match(line.strip())
                if not m:
                    continue
                d, phone, target, detail = m.groups()
                if d not in days_set or d in jsonl_dates:
                    continue
                ok = not detail.startswith("失败")
                short = f"{target}: {detail[:80]}"
                prev = records.setdefault(d, {}).get(phone)
                if prev is None:
                    records[d][phone] = (ok, short)
                else:
                    records[d][phone] = (prev[0] and ok, prev[1] + "; " + short)

    print("=" * 52)
    print("近7天打卡情况")
    print("=" * 52)
    for i, d in enumerate(days):
        label = "今天" if i == 0 else ("昨天" if i == 1 else f"{i}天前")
        print(f"{d} ({label})")
        day_rec = records.get(d)
        if not day_rec:
            print("  ⚪ 当天未运行打卡")
        else:
            for phone, (ok, detail) in day_rec.items():
                mark = "✅" if ok else "❌"
                print(f"  {mark} {phone}  {detail}")
    print("=" * 52)


if __name__ == "__main__":
    asyncio.run(main())
