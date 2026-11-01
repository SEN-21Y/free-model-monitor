# -*- coding: utf-8 -*-
"""硅基流动：监控定价页（免费状态/价格/上下架）与新闻公告页。"""
from html.parser import HTMLParser

from .base import BaseAdapter
from ..http import fetch_html


class PricingParser(HTMLParser):
    """按 div 嵌套深度精确切分 pricing-row，提取模型 slug、价格列与免费标记。"""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.cur = None
        self.row_level = None
        self.depth = 0
        self.in_a = False
        self.in_free = False
        self.in_price = False
        self.buf = []

    def _archive(self):
        if self.cur and self.cur["slug"]:
            self.rows.append(self.cur)
        self.cur = None
        self.row_level = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get("class", "")
        if tag == "div":
            self.depth += 1
        if tag == "div" and d.get("id", "").startswith("pricing-row-text-"):
            self._archive()
            self.cur = {"slug": None, "name": "", "prices": [], "free_cols": 0}
            self.row_level = self.depth - 1
            return
        if self.cur is None:
            return
        if tag == "a" and self.cur["slug"] is None and d.get("title"):
            self.cur["slug"] = d["title"]
            self.in_a = True
            self.buf = []
        elif tag == "span":
            if "min-w-[58px]" in cls:
                self.in_free = True
                self.buf = []
            elif "tabular-nums" in cls:
                self.in_price = True
                self.buf = []

    def handle_data(self, data):
        if self.in_a or self.in_free or self.in_price:
            self.buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_a:
            self.cur["name"] = "".join(self.buf).strip()
            self.in_a = False
            self.buf = []
        elif tag == "span" and self.in_free:
            if "免费" in "".join(self.buf):
                self.cur["free_cols"] += 1
            self.in_free = False
            self.buf = []
        elif tag == "span" and self.in_price:
            txt = "".join(self.buf).strip()
            if txt:
                self.cur["prices"].append(txt)
            self.in_price = False
            self.buf = []
        if tag == "div":
            self.depth -= 1
            if self.cur is not None and self.depth == self.row_level:
                self._archive()


class NewsParser(HTMLParser):
    """提取 h3 内文章链接（id、标题），以及文章日期。"""

    def __init__(self):
        super().__init__()
        self.articles = []
        self.in_h3 = False
        self.in_a = False
        self.buf = []
        self.cur_href = None
        self._seen = set()

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "h3":
            self.in_h3 = True
        if tag == "a" and self.in_h3 and d.get("href", "").startswith("/news/"):
            self.in_a = True
            self.cur_href = d["href"]
            self.buf = []

    def handle_data(self, data):
        if self.in_a:
            self.buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_a:
            title = "".join(self.buf).strip()
            aid = self.cur_href.split("/news/")[-1]
            if title and aid not in self._seen:
                self._seen.add(aid)
                self.articles.append({"id": aid, "title": title,
                                      "url": "https://cloud-rd.siliconflow.cn" + self.cur_href})
            self.in_a = False
            self.buf = []
        if tag == "h3":
            self.in_h3 = False


class SiliconFlowAdapter(BaseAdapter):
    source = "siliconflow"
    source_name = "硅基流动 SiliconFlow"
    url = "https://siliconflow.cn/pricing"

    def collect(self, cfg, timeout, retries):
        # 定价页
        pricing_html = fetch_html(cfg.get("pricing_url", self.url),
                                  timeout=timeout, max_retries=retries)
        pp = PricingParser()
        pp.feed(pricing_html)
        if pp.cur is not None:
            pp._archive()

        models = {}
        for r in pp.rows:
            models[r["slug"]] = {
                "name": r["name"],
                "prices": r["prices"],
                "free_cols": r["free_cols"],
                "is_free": r["free_cols"] > 0,
            }

        # 新闻页
        news_html = fetch_html(cfg.get("news_url", "https://cloud-rd.siliconflow.cn/news"),
                               timeout=timeout, max_retries=retries)
        np_ = NewsParser()
        np_.feed(news_html)

        return {"models": models, "news": np_.articles,
                "news_keywords": cfg.get("news_keywords", [])}

    def diff(self, old, new):
        changes = []
        old_models = old.get("models", {}) if old else {}
        new_models = new.get("models", {})

        # 上下架
        for slug in sorted(set(new_models) - set(old_models)):
            m = new_models[slug]
            changes.append({
                "type": "model_added",
                "label": "新增模型（免费）" if m["is_free"] else "新增模型",
                "target": slug,
                "detail": "、".join(m["prices"]) if m["prices"] else "免费",
                "url": self.url,
            })
        for slug in sorted(set(old_models) - set(new_models)):
            changes.append({
                "type": "model_removed",
                "label": "模型下架",
                "target": slug,
                "detail": "",
                "url": self.url,
            })

        # 免费状态与价格变化
        for slug in sorted(set(old_models) & set(new_models)):
            o, n = old_models[slug], new_models[slug]
            if o["is_free"] != n["is_free"]:
                if n["is_free"]:
                    changes.append({
                        "type": "turned_free",
                        "label": "转为免费",
                        "target": slug,
                        "detail": "原价格 %s → 免费" % ("、".join(o["prices"]) or "—"),
                        "url": self.url,
                    })
                else:
                    changes.append({
                        "type": "turned_paid",
                        "label": "免费结束",
                        "target": slug,
                        "detail": "免费 → %s" % ("、".join(n["prices"]) or "付费"),
                        "url": self.url,
                    })
            elif o["prices"] != n["prices"]:
                changes.append({
                    "type": "price_changed",
                    "label": "价格调整",
                    "target": slug,
                    "detail": "%s → %s" % ("、".join(o["prices"]) or "—",
                                           "、".join(n["prices"]) or "—"),
                    "url": self.url,
                })

        # 新闻公告：仅推送含关键词的新文章
        keywords = new.get("news_keywords", [])
        old_ids = {a["id"] for a in old.get("news", [])} if old else set()
        for a in new.get("news", []):
            if a["id"] in old_ids:
                continue
            if keywords and not any(k in a["title"] for k in keywords):
                continue
            changes.append({
                "type": "announcement",
                "label": "官方公告",
                "target": a["title"],
                "detail": "",
                "url": a["url"],
            })
        return changes
