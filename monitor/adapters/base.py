# -*- coding: utf-8 -*-
"""Adapter 基类：每个厂商实现 collect 与 diff 两个方法。"""


class BaseAdapter:
    source = ""        # 数据源唯一标识
    source_name = ""   # 展示名称
    url = ""           # 数据源主页（邮件里附链接）

    def collect(self, cfg, timeout, retries):
        """采集并返回可 JSON 序列化的 payload。"""
        raise NotImplementedError

    def diff(self, old, new):
        """对比两次快照，返回变化事件列表，每个事件为 dict。"""
        raise NotImplementedError
