# -*- coding: utf-8 -*-
"""邮件通知：SMTP 发送 HTML 邮件，按数据源分组展示变化。"""
import html as html_lib
import smtplib
import ssl
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


class NotifierError(Exception):
    pass


def _validate_email_config(e):
    """发送前校验，把配置缺失转成明确的中文错误而非底层编码异常。"""
    sender = e.get("sender", "")
    pwd = e.get("password", "")
    if not sender or "your_mailbox" in sender:
        raise NotifierError("发件邮箱仍是占位地址，请在 config.json 填写真实邮箱")
    if not pwd or not pwd.strip():
        raise NotifierError("邮箱授权码为空，请在 GitHub Secret 配置 MONITOR_EMAIL_PASSWORD")
    try:
        pwd.encode("ascii")
    except UnicodeEncodeError:
        raise NotifierError(
            "邮箱授权码仍是中文占位文字，请在 GitHub 仓库添加 Secret "
            "MONITOR_EMAIL_PASSWORD（QQ邮箱16位SMTP授权码）"
        )


# 变化类型 → 标签底色（仅用于区分，同时保留文字标签）
TYPE_COLORS = {
    "free_added": ("#dcfce7", "#15803d"),
    "model_added": ("#dcfce7", "#15803d"),
    "turned_free": ("#dcfce7", "#15803d"),
    "free_removed": ("#fee2e2", "#b91c1c"),
    "model_removed": ("#fee2e2", "#b91c1c"),
    "turned_paid": ("#fee2e2", "#b91c1c"),
    "price_changed": ("#fef3c7", "#a16207"),
    "context_changed": ("#fef3c7", "#a16207"),
    "announcement": ("#e0e7ff", "#3730a3"),
}


def _esc(s):
    return html_lib.escape(str(s if s is not None else ""))


def _render_baseline(reports):
    rows = "".join(
        '<tr><td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">%s</td>'
        '<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#64748b;">'
        "已建立基线，本次不报告变化</td></tr>" % _esc(r["source_name"])
        for r in reports
    )
    return _wrap("监控基线已建立",
                 "<p style='color:#475569;'>以下数据源已完成首次采集，从下一次运行起将只推送真实变化。</p>"
                 "<table style='border-collapse:collapse;width:100%%;font-size:14px;'>%s</table>" % rows)


def _render_changes(reports):
    blocks = []
    total = 0
    for r in reports:
        changes = r["changes"]
        if not changes:
            continue
        total += len(changes)
        rows = []
        for c in changes:
            bg, fg = TYPE_COLORS.get(c["type"], ("#e2e8f0", "#334155"))
            link = "<a href='%s' style='color:#2563eb;text-decoration:none;'>查看</a>" % _esc(c["url"]) \
                if c.get("url") else ""
            rows.append(
                "<tr style='border-bottom:1px solid #e2e8f0;'>"
                "<td style='padding:8px 10px;'><span style='background:%s;color:%s;border-radius:6px;"
                "padding:3px 9px;font-size:12.5px;font-weight:600;white-space:nowrap;'>%s</span></td>"
                "<td style='padding:8px 10px;font-weight:600;'>%s</td>"
                "<td style='padding:8px 10px;color:#64748b;'>%s</td>"
                "<td style='padding:8px 10px;white-space:nowrap;'>%s</td></tr>"
                % (bg, fg, _esc(c["label"]), _esc(c["target"]), _esc(c["detail"]), link)
            )
        blocks.append(
            "<div style='margin-bottom:18px;'><div style='font-size:15px;font-weight:700;color:#0f3a5f;"
            "margin-bottom:8px;'>%s <span style='color:#64748b;font-weight:400;font-size:13px;'>%d 项</span></div>"
            "<table style='border-collapse:collapse;width:100%%;font-size:14px;'>%s</table></div>"
            % (_esc(r["source_name"]), len(changes), "".join(rows))
        )
    return total, _wrap("发现 %d 项模型/活动变化" % total, "".join(blocks))


def _render_error(error_reports):
    items = "".join(
        "<li style='margin-bottom:6px;'><b>%s</b>：%s</li>"
        % (_esc(r["source_name"]), _esc(r["error"]))
        for r in error_reports
    )
    return _wrap("部分数据源采集失败",
                 "<ul style='color:#b91c1c;font-size:14px;line-height:1.7;'>%s</ul>"
                 "<p style='color:#64748b;font-size:13px;'>其余数据源结果已正常处理，失败项将在下次运行自动重试。</p>" % items)


def _wrap(title, body):
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        "<div style='max-width:760px;margin:0 auto;font-family:\"Segoe UI\",\"Microsoft YaHei\",sans-serif;"
        "color:#1e293b;'>"
        "<div style='background:#0f3a5f;color:#fff;padding:18px 22px;border-radius:10px 10px 0 0;'>"
        "<div style='font-size:18px;font-weight:700;'>%s</div>"
        "<div style='font-size:12.5px;opacity:.8;margin-top:4px;'>免费模型活动监控 · %s</div></div>"
        "<div style='border:1px solid #e2e8f0;border-top:none;border-radius:0 0 10px 10px;padding:20px;'>%s</div>"
        "<div style='text-align:center;color:#94a3b8;font-size:12px;margin-top:10px;'>本邮件由监控脚本自动发送，无变化时不会打扰</div></div>"
        % (title, today, body)
    )


def send_email(cfg, subject, html_body):
    e = cfg["email"]
    _validate_email_config(e)
    msg = MIMEMultipart("alternative")
    msg["From"] = e["sender"]
    msg["To"] = ", ".join(e["receivers"])
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if e.get("use_ssl", True):
        with smtplib.SMTP_SSL(e["smtp_host"], e["smtp_port"],
                              context=ssl.create_default_context(), timeout=30) as server:
            server.login(e["sender"], e["password"])
            server.sendmail(e["sender"], e["receivers"], msg.as_string())
    else:
        with smtplib.SMTP(e["smtp_host"], e["smtp_port"], timeout=30) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(e["sender"], e["password"])
            server.sendmail(e["sender"], e["receivers"], msg.as_string())


def notify(cfg, reports, error_reports):
    """根据运行结果决定发送哪类邮件；返回发送的主题（未发送返回 None）。"""
    changed = [r for r in reports if r.get("changes")]
    baselines = [r for r in reports if r.get("is_baseline")]

    # 错误通知（即使有其他结果也提醒）
    if error_reports:
        body = _render_error(error_reports)
        send_email(cfg, "【模型监控】部分数据源采集失败 %s" % datetime.now().strftime("%m-%d"), body)

    if changed:
        total, body = _render_changes(changed)
        send_email(cfg, "【模型监控】发现 %d 项变化 %s" % (total, datetime.now().strftime("%m-%d")), body)
        return "changes:%d" % total
    if baselines:
        body = _render_baseline(baselines)
        send_email(cfg, "【模型监控】监控基线已建立", body)
        return "baseline"
    if cfg.get("heartbeat"):
        body = _wrap("今日无变化", "<p style='color:#47556b;'>各数据源运行正常，未检测到模型或活动变化。</p>")
        send_email(cfg, "【模型监控】每日心跳 %s" % datetime.now().strftime("%m-%d"), body)
        return "heartbeat"
    return None
