# -*- coding: utf-8 -*-
"""配置加载：读取 config.json，敏感字段支持环境变量覆盖。"""
import json
import os


class ConfigError(Exception):
    pass


def load_config(path):
    if not os.path.exists(path):
        raise ConfigError(
            "配置文件不存在：%s\n请复制 config.example.json 为 config.json 并填写邮箱信息" % path
        )
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 邮箱密码优先取环境变量，便于在 GitHub Actions / 服务器上保密
    env_pwd = os.environ.get("MONITOR_EMAIL_PASSWORD")
    if env_pwd:
        cfg.setdefault("email", {})["password"] = env_pwd

    cfg.setdefault("heartbeat", False)
    cfg.setdefault("request_timeout", 30)
    cfg.setdefault("max_retries", 2)
    return cfg
