# -*- coding: utf-8 -*-
"""免费模型活动监控入口：采集 → 快照对比 → 邮件通知。"""
import argparse
import os
import sys
import traceback

from monitor.config import load_config, ConfigError
from monitor.storage import SnapshotStore
from monitor.notifier import notify
from monitor.adapters.openrouter import OpenRouterAdapter
from monitor.adapters.siliconflow import SiliconFlowAdapter

ADAPTERS = {
    "openrouter": OpenRouterAdapter,
    "siliconflow": SiliconFlowAdapter,
}


def main():
    parser = argparse.ArgumentParser(description="免费模型活动监控")
    parser.add_argument("-c", "--config",
                        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
                        help="配置文件路径")
    parser.add_argument("--dry-run", action="store_true",
                        help="只采集和对比，不写快照、不发邮件，结果打印到屏幕")
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        print("[配置错误] %s" % e)
        return 2

    root = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(root, "data", "monitor.db")
    store = None if args.dry_run else SnapshotStore(db_path)

    reports, error_reports = [], []
    timeout = cfg["request_timeout"]
    retries = cfg["max_retries"]

    for source, adapter_cls in ADAPTERS.items():
        src_cfg = cfg.get("sources", {}).get(source, {})
        if not src_cfg.get("enabled", False):
            print("[跳过] %s 未启用" % source)
            continue
        adapter = adapter_cls()
        try:
            print("[采集] %s ..." % adapter.source_name)
            payload = adapter.collect(src_cfg, timeout, retries)
            old = None if args.dry_run else store.latest(source)

            if old is None:
                reports.append({"source_name": adapter.source_name,
                                "is_baseline": True, "changes": []})
                print("  首次采集，建立基线")
            else:
                changes = adapter.diff(old, payload)
                reports.append({"source_name": adapter.source_name, "changes": changes})
                print("  变化 %d 项" % len(changes))

            if not args.dry_run:
                store.save(source, payload)
        except Exception as e:
            error_reports.append({"source_name": adapter.source_name, "error": str(e)})
            print("[错误] %s : %s" % (adapter.source_name, e))
            traceback.print_exc()

    if store is not None:
        store.close()

    if args.dry_run:
        for r in reports:
            print("\n== %s ==" % r.get("source_name"))
            for c in r.get("changes", []):
                print("  [%s] %s %s %s" % (c["label"], c["target"], c["detail"], c.get("url", "")))
            if r.get("is_baseline"):
                print("  (基线)")
        for r in error_reports:
            print("\n[错误] %s: %s" % (r["source_name"], r["error"]))
        return 0

    result = notify(cfg, reports, error_reports)
    print("\n通知结果：%s" % (result or "无变化，未发送"))
    return 1 if error_reports else 0


if __name__ == "__main__":
    sys.exit(main())
