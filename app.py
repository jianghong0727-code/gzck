#!/usr/bin/env python3
"""python app.py 启动中文界面；python app.py search 运行命令行。"""
import argparse
import json
import sys
from pathlib import Path

from football_tool.core import download, export_report, make_zip, search


def main():
    parser = argparse.ArgumentParser(description="足球视频素材助手（中文界面、官方 API、许可审核）")
    parser.add_argument("--output", default=str(Path(__file__).parent / "output"), help="输出目录")
    parser.add_argument("--port", type=int, default=8765, help="本机界面端口")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    sub = parser.add_subparsers(dest="command")
    cli = sub.add_parser("search", help="命令行搜索并生成清单")
    cli.add_argument("query", help="中文或英文关键词")
    cli.add_argument("--english", default="", help="手动英文关键词")
    cli.add_argument("--source", choices=["all", "pexels", "commons"], default="all")
    cli.add_argument("--limit", type=int, default=12, help="每来源一页的条数，最多40")
    cli.add_argument("--max-count", type=int, default=5)
    cli.add_argument("--max-mb", type=int, default=100)
    cli.add_argument("--total-mb", type=int, default=300)
    cli.add_argument("--search-only", action="store_true", help="仅搜索，不下载")
    cli.add_argument("--zip", action="store_true", help="生成素材导出 ZIP")
    args = parser.parse_args()
    if args.command == "search":
        sources = {"all": ("Pexels", "Wikimedia Commons"), "pexels": ("Pexels",), "commons": ("Wikimedia Commons",)}[args.source]
        report = search(args.query, english=args.english, limit=args.limit, sources=sources)
        if not args.search_only:
            download(report, args.output, max_count=args.max_count, max_mb=args.max_mb, total_mb=args.total_mb)
        stats = export_report(report, args.output)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        if args.zip:
            print("导出文件：", make_zip(args.output))
        return 2 if report.errors else 0
    from football_tool.web import serve
    serve(args.output, args.port, not args.no_browser)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print("无法完成操作：" + str(exc) + "。请检查参数、目录权限或端口；用 python app.py --help 查看帮助。", file=sys.stderr)
        raise SystemExit(1)
