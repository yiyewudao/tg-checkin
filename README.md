# TG 每日自动打卡 (软路由版)

在 OpenWrt / ImmortalWrt 软路由上跑的 Telegram 自动打卡脚本, 支持多账号 (最多可配 10 个, 建议逐步添加)。

## 🔧 配套固件: 自动构建的 ImmortalWrt

**[yiyewudao/immortalwrt-builder](https://github.com/yiyewudao/immortalwrt-builder)** —— x86-64 软路由固件自动构建, 与本项目配套使用:
- 每天自动追踪官方新版本 (含大版本) 并构建固件
- Nikki / OpenClash / PassWall / PassWall2 / Lucky / 应用商店 / Docker / QuickFile 可选
- 可选集成 TG 打卡依赖 (python3/pip): 固件"保留配置"升级后打卡自动恢复、依赖自愈
- 一键升级 (保留配置)

两个项目配合: 用自动构建的固件 + 本打卡脚本, 升级固件不断打卡。

## 一键安装

在软路由 SSH 里执行:

```sh
# 常规安装 (能直连 GitHub):
wget -qO- https://raw.githubusercontent.com/yiyewudao/tg-checkin/main/install.sh | sh

# 国内用户 (GitHub 被墙) 经中转服务器安装:
export TG_RAW_BASE="http://free.xlulu.eu.org:8000" && wget -qO- $TG_RAW_BASE/install.sh | sh
```

安装脚本会: 装 python3/pip/telethon → 下载脚本到 `/root/tg-checkin/` → 写入每天 10:00 的定时任务。

## 服务器版 (Debian / Ubuntu)

```sh
wget -qO- https://raw.githubusercontent.com/yiyewudao/tg-checkin/main/install-server.sh | sh

# 国内用户 (GitHub 被墙) 经中转服务器安装:
export TG_RAW_BASE="http://free.xlulu.eu.org:8000" && wget -qO- $TG_RAW_BASE/install-server.sh | sh
```

`setup.py` 会自动识别软路由和服务器, 定时任务分别写入对应的 cron。

## GitHub 被墙时: 用自己的服务器中转

如果你有能直连 GitHub 的空服务器, 让它做下载中转:

**在中转服务器上** (能直连 GitHub 的那台):
```sh
mkdir -p /tmp/tgraw && cd /tmp/tgraw
for f in install.sh install-server.sh checkin.py add_account.py setup.py run.sh env.sh.example; do
  curl -sLO https://raw.githubusercontent.com/yiyewudao/tg-checkin/main/$f
done
nohup python3 -m http.server 8000 >/tmp/tgraw.log 2>&1 &
```

**在要安装的目标机器上** (能访问上面那台服务器即可):
```sh
export TG_RAW_BASE="http://服务器IP:8000"
wget -qO- $TG_RAW_BASE/install.sh | sh          # 软路由
# 或 wget -qO- $TG_RAW_BASE/install-server.sh | sh  # Debian/Ubuntu
```

装完后中转服务器上跑 `pkill -f "http.server 8000"` 关掉服务即可。

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
| `run.sh` | 定时任务入口 (固件升级后依赖自愈) |
| `restore.sh` | 一键恢复：备份放回后自动装依赖、补 cron、验证账号 |
| `env.sh.example` | 配置模板 |

## 日志

打卡日志在 `/root/tg-checkin/checkin.log`, 定时任务为 `/etc/crontabs/root` 里的 `tg-checkin/run.sh` 那一行。

## 致谢

本项目特色内容由 Muse 支持编写，邀请码：Q3P6O6
