# -*- coding: utf-8 -*-
"""离线验证：构造快照对比全部事件类型，并把渲染结果存为 HTML 预览。"""
import os
from monitor.adapters.openrouter import OpenRouterAdapter
from monitor.adapters.siliconflow import SiliconFlowAdapter
from monitor.notifier import _render_changes, _render_baseline, _render_error

# ---------- OpenRouter ----------
or_old = {"free_models": {
    "vendor/model-a:free": {"name": "Model A", "context_length": 32000},
    "vendor/model-b:free": {"name": "Model B", "context_length  ": 64000},
}}
or_new = {"free_models": {
    "vendor/model-a:free": {"name": "Model A", "context_length": 64000},   # 上下文变化
    "vendor/model-c:free": {"name": "Model C", "context_length": 128000},  # 新增
}}
or_changes = OpenRouterAdapter().diff(or_old, or_new)

# ---------- SiliconFlow ----------
sf_old = {"models": {
    "acme/old-model": {"name": "Old", "prices": ["¥ 2.00"], "free_cols": 0, "is_free": False},
    "acme/was-free": {"name": "WasFree", "prices": [], "free_cols": 1, "is_free": True},
    "acme/price-model": {"name": "Price", "prices": ["¥ 1.00", "¥ 3.00"], "free_cols": 0, "is_free": False},
    "acme/gone-model": {"name": "Gone", "prices": ["¥ 5.00"], "free_cols": 0, "is_free": False},
}, "news": [{"id": "old1", "title": "历史文章", "url": "https://x/old1"}],
    "news_keywords": ["免费", "限免", "上线"]}
sf_new = {"models": {
    "acme/old-model": {"name": "Old", "prices": [], "free_cols": 1, "is_free": True},   # 转免费
    "acme/was-free": {"name": "WasFree", "prices": ["¥ 4.00"], "free_cols": 0, "is_free": False},  # 免费结束
    "acme/price-model": {"name": "Price", "prices": ["¥ 1.50", "¥ 3.00"], "free_cols": 0, "is_free": False},  # 调价
    "acme/new-model": {"name": "New", "prices": [], "free_cols": 2, "is_free": True},    # 新增免费
}, "news": [
    {"id": "n1", "title": "新模型上线限时免费", "url": "https://x/n1"},   # 命中关键词
    {"id": "n2", "title": "公司团建通知", "url": "https://x/n2"},         # 不命中，应过滤
], "news_keywords": ["免费", "限免", "上线"]}
sf_changes = SiliconFlowAdapter().diff(sf_old, sf_new)

reports = [
    {"source_name": "OpenRouter", "changes": or_changes},
    {"source_name": "硅基流动 SiliconFlow", "changes": sf_changes},
]

print("== OpenRouter events ==")
for c in or_changes:
    print(" ", c["label"], c["target"], c["detail"])
print("== SiliconFlow events ==")
for c in sf_changes:
    print(" ", c["label"], c["target"], c["detail"])

# 断言事件数量
assert len(or_changes) == 3, or_changes
assert len(sf_changes) == 6, sf_changes   # 4 模型事件 + 1 公告 + 1 调价
labels = [c["label"] for c in sf_changes]
assert "官方公告" in labels and not any("团建" in c["target"] for c in sf_changes)
print("\n全部断言通过")

# 渲染三种邮件并存档
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview")
os.makedirs(out, exist_ok=True)
total, change_html = _render_changes(reports)
open(os.path.join(out, "preview_changes.html"), "w", encoding="utf-8").write(change_html)
open(os.path.join(out, "preview_baseline.html"), "w", encoding="utf-8").write(
    _render_baseline([{"source_name": "OpenRouter"}, {"source_name": "硅基流动 SiliconFlow"}]))
open(os.path.join(out, "preview_error.html"), "w", encoding="utf-8").write(
    _render_error([{"source_name": "硅基流动 SiliconFlow", "error": "连接超时（模拟）"}]))
print("邮件预览已生成：", out)
