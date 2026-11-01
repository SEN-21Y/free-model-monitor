# -*- coding: utf-8 -*-
"""HTTP 工具：基于 urllib，带 UA、超时和有限重试。"""
import time
import urllib.request
import urllib.error

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class HttpError(Exception):
    pass


def fetch(url, timeout=30, max_retries=2):
    """抓取 URL，返回字节内容。失败按重试次数退避后抛出 HttpError。"""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(2 * (attempt + 1))
    raise HttpError("抓取失败 %s : %s" % (url, last_err))


def fetch_json(url, timeout=30, max_retries=2):
    import json
    raw = fetch(url, timeout=timeout, max_retries=max_retries)
    return json.loads(raw.decode("utf-8"))


def fetch_html(url, timeout=30, max_retries=2):
    raw = fetch(url, timeout=timeout, max_retries=max_retries)
    return raw.decode("utf-8", errors="ignore")
