# TG 每日自动打卡 (软路由版)

在 OpenWrt / ImmortalWrt 软路由上跑的 Telegram 自动打卡脚本, 支持多账号 (最多可配 10 个, 建议逐步添加)。

## 一键安装

在软路由 SSH 里执行:

```sh
# 公开仓库
wget -qO- https://raw.githubusercontent.com/yiyewudao/tg-checkin/main/install.sh | sh

# 私有仓库 (token 只在下载时用, 不保存)
curl -sfL -H "Authorization: Bearer 你的TOKEN" \
  -o /tmp/install.sh https://raw.githubusercontent.com/yiyewudao/tg-checkin/main/install.sh \
  && sh /tmp/install.sh
```

安装脚本会: 装 python3/pip/telethon → 下载脚本到 `/root/tg-checkin/` → 写入每天 10:00 的定时任务。私有仓库下载时按提示输入 GitHub token (repo 权限) 即可, 也可以提前 `export GITHUB_TOKEN=xxx` 跳过输入。

## 服务器版 (Debian / Ubuntu)

```sh
wget -qO- https://raw.githubusercontent.com/yiyewudao/tg-checkin/main/install-server.sh | sh
```

`setup.py` 会自动识别软路由和服务器, 定时任务分别写入对应的 cron。

## 配置 (一个命令全搞定)

```sh
python3 /root/tg-checkin/setup.py
```

向导菜单:

1. **添加 TG 账号** — 按提示输入手机号、API ID、API Hash, 收 Telegram 验证码完成登录 (支持两步验证)。可重复添加多个号。
2. **设置打卡时间** — 比如每天 10:00。
3. **设置打卡目标** — 三种模式：
   - 所有账号用同一套：bot/群用户名 + 打卡命令，如 `sheeridverifier_bot:/checkin`，多个用逗号分隔；命令留空则自动点签到按钮。切换到统一时会汇报哪些账号的单独设置将被清除，需确认
   - 每个账号分别设置（独立）：指定账号完全用自己的目标，不跟随统一
   - 统一 + 个别账号额外加目标：先设统一目标，再给指定账号追加额外目标（实际打卡 = 统一 + 额外）；额外目标若已在统一里会自动去除并提示
4. **设置推送机器人** — 打卡结束后把成功/失败清单推送到你指定的机器人 (需要 bot token + chat ID)。
5. **设置代理** — 默认 `socks5://127.0.0.1:7891` (OpenClash)。
6. **立即测试打卡一次**。
7. **查看近7天打卡情况** (也可直接运行 `python3 checkin.py status`)，看完可选择立即手动打卡一次。

## 申请 Telegram API ID / Hash

1. 打开 https://my.telegram.org, 用手机号登录 (验证码发到该号的 Telegram App)。
2. 进 **API development tools** → **Create application**。
3. 填 App title / Short name (5-32 位字母数字), Platform 选 Other, 提交后得到 `api_id` 和 `api_hash`。

## 文件说明

| 文件 | 说明 |
|---|---|
| `install.sh` | 一键安装 (OpenWrt/软路由) |
| `install-server.sh` | 一键安装 (Debian/Ubuntu 服务器) |
| `setup.py` | 交互式配置向导 |
| `checkin.py` | 打卡主脚本 (定时任务调用) |
| `add_account.py` | 单独加号脚本 (setup.py 也会调用它) |
| `run.sh` | 定时任务入口 |
| `env.sh.example` | 配置模板 |

## 日志

打卡日志在 `/root/tg-checkin/checkin.log`, 定时任务为 `/etc/crontabs/root` 里的 `tg-checkin/run.sh` 那一行。
