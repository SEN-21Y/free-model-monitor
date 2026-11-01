# -*- coding: utf-8 -*-
"""OpenRouter：通过公开 models API 监控 :free 免费模型上下架。"""
from .base import BaseAdapter
from ..http import fetch_json


class OpenRouterAdapter(BaseAdapter):
    source = "openrouter"
    source_name = "OpenRouter"
    url = "https://openrouter.ai/models"

    def collect(self, cfg, timeout, retries):
        data = fetch_json(cfg.get("base_url", "https://openrouter.ai/api/v1/models"),
                          timeout=timeout, max_retries=retries)
        free_models = {}
        for m in data.get("data", []):
            mid = m.get("id", "")
            pricing = m.get("pricing", {})
            is_free = mid.endswith(":free") or (
                str(pricing.get("prompt", "0")) == "0"
                and str(pricing.get("completion", "0")) == "0"
                and mid.endswith(":free")
            )
            if is_free:
                free_models[mid] = {
                    "name": m.get("name", mid),
                    "context_length": m.get("context_length"),
                }
        return {"free_models": free_models}

    def diff(self, old, new):
        changes = []
        old_models = old.get("free_models", {}) if old else {}
        new_models = new.get("free_models", {})

        for mid in sorted(set(new_models) - set(old_models)):
            changes.append({
                "type": "free_added",
                "label": "新增免费模型",
                "target": mid,
                "detail": "上下文 %s tokens" % new_models[mid].get("context_length"),
                "url": self.url,
            })
        for mid in sorted(set(old_models) - set(new_models)):
            changes.append({
                "type": "free_removed",
                "label": "免费模型下架",
                "target": mid,
                "detail": "上下文 %s tokens" % old_models[mid].get("context_length"),
                "url": self.url,
            })
        # 上下文长度调整
        for mid in sorted(set(old_models) & set(new_models)):
            o = old_models[mid].get("context_length")
            n = new_models[mid].get("context_length")
            if o != n:
                changes.append({
                    "type": "context_changed",
                    "label": "上下文长度调整",
                    "target": mid,
                    "detail": "%s → %s tokens" % (o, n),
                    "url": self.url,
                })
        return changes
