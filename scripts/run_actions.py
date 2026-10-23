"""GitHub Actions 入口。用户输入通过环境变量传递，不拼接成 shell 命令。"""
from __future__ import annotations

import html
import os
from pathlib import Path

from football_tool.core import Report, download, export_report, make_zip, search


def integer(env, key, default, minimum, maximum):
    try:
        value = int(env.get(key, str(default)))
    except (ValueError, TypeError):
        raise ValueError(f"{key} 必须是整数") from None
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} 必须在 {minimum}–{maximum} 之间")
    return value


def write_summary(report, stats, env):
    title = "已完成" if not report.errors else "存在错误，请查看原因与产物"
    lines = [f"# 足球素材运行结果：{title}", "",
             f"关键词：<code>{html.escape(report.query)}</code>", "",
             f"英文关键词：<code>{html.escape(report.english)}</code>", "",
             "|真实搜索结果|新增下载|待人工审核|禁止下载|", "|---:|---:|---:|---:|",
             f"|{stats['真实搜索结果数']}|{stats['新增下载数']}|{stats['待审核数']}|{stats['禁止下载数']}|", ""]
    for message in report.notes + report.errors:
        lines.extend([html.escape(message), ""])
    lines.extend(["在本次运行页面的 **Artifacts** 区域下载 `football-materials` 开头的产物。",
                  "解压后打开 `素材预览.html`；零下载或运行报错时，也可下载清单检查原因。",
                  "待审核素材不会自动下载；本流程不支持绕过审核。产物保留 3 天，请及时保存。", ""])
    summary = "\n".join(lines)
    if env.get("GITHUB_STEP_SUMMARY"):
        with Path(env["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as out:
            out.write(summary)
    print(f"真实搜索结果：{stats['真实搜索结果数']}；新增下载：{stats['新增下载数']}；待审核：{stats['待审核数']}")
    print("有错误，详情见运行摘要与运行报告。" if report.errors else "完成，请在 Artifacts 下载结果。")


def execute(env=None, output="output", net=None):
    env = os.environ if env is None else env
    root = Path(output)
    try:
        query = env.get("INPUT_QUERY", "足球场空镜").strip()
        english = env.get("INPUT_ENGLISH", "").strip()
        if not query or len(query) > 200 or len(english) > 200 or "\n" in query or "\r" in query:
            raise ValueError("请填写单行 1–200 字的主题或球员关键词；整段文案请先拆成镜头关键词")
        source = env.get("INPUT_SOURCE", "auto")
        choices = {"all": ("Pexels", "Wikimedia Commons"), "pexels": ("Pexels",), "commons": ("Wikimedia Commons",)}
        no_key = not os.getenv("PEXELS_API_KEY", "").strip()
        if source == "auto":
            sources = choices["commons" if no_key else "all"]
        elif source in choices:
            sources = choices[source]
        else:
            raise ValueError("来源必须是 auto、all、pexels 或 commons")
        limit = integer(env, "INPUT_LIMIT", 12, 1, 40)
        max_count = integer(env, "INPUT_MAX_COUNT", 5, 1, 20)
        max_mb = integer(env, "INPUT_MAX_MB", 100, 1, 2048)
        total_mb = integer(env, "INPUT_TOTAL_MB", 300, 1, 4096)
        search_only = env.get("INPUT_SEARCH_ONLY", "false").lower()
        if search_only not in {"true", "false"}:
            raise ValueError("仅搜索开关必须是 true 或 false")
        report = search(query, english=english, sources=sources, limit=limit, net=net)
        if source == "auto" and no_key:
            report.notes.append("未设置 PEXELS_API_KEY，自动选择仅搜索 Wikimedia Commons；可在仓库 Secrets 中添加密钥后搜索 Pexels。")
        if search_only == "true":
            report.notes.append("本次仅搜索，未尝试下载媒体。")
        else:
            # 先保存搜索结果，下载阶段意外中断时仍有许可与来源记录。
            export_report(report, root)
            download(report, root, max_count=max_count, max_mb=max_mb, total_mb=total_mb, net=net)
    except (ValueError, OSError) as exc:
        report = Report("输入或执行失败", errors=[str(exc)])
    stats = export_report(report, root)
    make_zip(root)
    write_summary(report, stats, env)
    return 2 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(execute())
