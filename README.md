# 免费模型活动监控

定时检测各 AI 厂商 / 模型平台的**免费模型上下架、价格与额度变动、官方公告活动**，有变化才发邮件，无变化静默。

**零第三方依赖**，仅使用 Python 3.8+ 标准库（`urllib` / `html.parser` / `sqlite3` / `smtplib`），克隆即可运行。

## 已接入数据源

| 数据源 | 采集方式 | 监控内容 |
|---|---|---|
| OpenRouter | 公开 models API | 免费模型（`:free`）上下架、上下文长度调整 |
| 硅基流动 SiliconFlow | 定价页 + 新闻页解析 | 免费状态切换、价格调整、模型上下架、官方公告（关键词过滤） |

## 目录结构

```
free-model-monitor/
├── main.py                  # 入口
├── config.example.json      # 配置模板
├── config.json              # 实际配置（自行创建，已 gitignore）
├── monitor/
│   ├── config.py            # 配置加载
│   ├── http.py              # HTTP 抓取（重试/超时）
│   ├── storage.py           # SQLite 快照存储
│   ├── notifier.py          # 邮件通知（HTML 模板 + SMTP）
│   └── adapters/            # 各厂商适配器，新增厂商在此扩展
│       ├── openrouter.py
│       └── siliconflow.py
├── data/monitor.db          # 快照库（首次运行自动生成）
├── run.sh / cron.example    # Linux 定时配置
└── .github/workflows/       # GitHub Actions 定时配置
```

## 快速开始

```bash
# 1. 准备配置
cp config.example.json config.json   # Windows 下用 copy 命令

# 2. 编辑 config.json，填写邮箱 SMTP 信息（见下方说明）

# 3. 先空跑验证（不写库、不发邮件，结果打印到屏幕）
python main.py --dry-run

# 4. 正式运行：首次建立基线并发送基线邮件，之后只推送真实变化
python main.py
```

## 邮件 SMTP 配置

`config.json` 中 `email` 段：

| 邮箱 | smtp_host | smtp_port | use_ssl |
|---|---|---|---|
| QQ 邮箱 | smtp.qq.com | 465 | true |
| 163 邮箱 | smtp.163.com | 465 | true |
| Gmail | smtp.gmail.com | 465 | true |

`password` 填的是**SMTP 授权码，不是邮箱登录密码**：

- QQ 邮箱：设置 → 账户 → 开启「IMAP/SMTP 服务」→ 生成授权码
- 163 邮箱：设置 → POP3/SMTP/IMAP → 开启 SMTP → 设置客户端授权码

也可以不把授权码写进文件，改用环境变量（优先级更高）：

```bash
export MONITOR_EMAIL_PASSWORD="你的授权码"
```

`receivers` 是收件人列表，可填多个邮箱。

## 定时部署（三选一）

### 方案 A：GitHub Actions（零成本，推荐）

1. 把本项目推送到 GitHub 仓库（私有仓库也有充足的免费 Actions 额度）；
2. 仓库 **Settings → Secrets and variables → Actions** 添加 Secret：
   - `MONITOR_EMAIL_PASSWORD`：邮箱 SMTP 授权码；
3. 工作流已内置**每天定时运行两次**（北京时间 08:03、14:03，避开整点高峰），并会自动把更新后的快照库提交回仓库；
4. 也可在 Actions 页面手动触发。按此频率每月约 30 分钟运行量，仅占私有仓库 2000 分钟免费额度的 1.5%。

> 注意：`config.json` 已被 gitignore，若仓库中没有该文件，Actions 会报配置缺失。私有仓库可强制执行 `git add -f config.json`，或把非敏感配置也改为通过仓库文件提供。

### 方案 B：Linux 服务器 / 云主机（crontab）

```bash
chmod +x run.sh
crontab -e
# 按 cron.example 粘贴，注意把路径改成项目的绝对路径
```

### 方案 C：Windows 本地任务计划

打开「任务计划程序 → 创建基本任务」，触发器设为每天，操作执行：

```
程序：python
参数："C:\路径\free-model-monitor\main.py"
```

电脑关机或休眠期间任务会跳过，适合作为备选。

## 工作原理

1. 各 Adapter 独立采集并归一化数据；
2. 与 SQLite 中该数据源的上一次快照逐项 Diff，生成变化事件；
3. 新快照入库；
4. 有变化才渲染 HTML 邮件推送；采集失败单独发故障邮件，且不影响其他数据源。

## 新增厂商

在 `monitor/adapters/` 下新建文件，继承 `BaseAdapter`，实现 `collect()`（采集）与 `diff()`（对比），再到 `main.py` 的 `ADAPTERS` 字典注册即可。建议优先使用官方 API，其次才是网页解析；网页解析需对页面结构失效做容错（本项目解析器会在结构异常时抛出明确错误而非静默误报）。
