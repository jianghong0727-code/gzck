"""仅监听本机的标准库中文界面。"""
import hmac
import json
import mimetypes
import secrets
import shutil
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .core import (Clip, Report, add_reference, download, export_report, make_zip,
                   review_clip, search)
from .preview import CSS, esc


def serve(root, port=8765, open_browser=True):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    state = {"report": None, "message": ""}
    stored = root / "素材记录.json"
    if stored.exists():
        obj = json.loads(stored.read_text("utf-8"))
        obj["clips"] = [Clip(**c) for c in obj["clips"]]
        state["report"] = Report(**obj)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def valid_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def send(self, text, code=200):
            raw = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "frame-ancestors 'self'; base-uri 'none'; object-src 'none'")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self.valid_host():
                return self.send("不允许的主机", 403)
            path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            if path.startswith("/files/"):
                name = path.removeprefix("/files/")
                target = (root / name).resolve()
                allowed = {"素材清单.csv", "人工审核清单.csv", "素材记录.json", "运行报告.json", "素材预览.html", "素材导出.zip"}
                if state["report"]:
                    allowed.update(c.local_path for c in state["report"].clips if c.local_path)
                if name not in allowed or not target.is_relative_to(root) or not target.is_file():
                    return self.send("文件不存在", 404)
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(target.stat().st_size))
                if target.suffix in {".csv", ".json", ".zip"}:
                    self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(target.name))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                with target.open("rb") as src:
                    shutil.copyfileobj(src, self.wfile)
                return
            if path != "/":
                return self.send("页面不存在", 404)
            hidden = f'<input type="hidden" name="token" value="{token}">'
            r = state["report"]
            errors = ''.join(f'<li>{esc(e)}</li>' for e in r.errors) if r else ''
            options = ''.join(f'<option value="{esc(c.id)}">{esc(c.title[:60])} [{esc(c.id)}]</option>' for c in r.clips if c.license_status == "待人工审核" and c.source in {"Pexels", "Wikimedia Commons"}) if r else ''
            result = f'''<section><h2>本次结果</h2><p class="stats">搜索 {len([c for c in r.clips if not c.id.startswith('reference-')])} 条 · 新增下载 {r.downloaded} 个 · 待审核 {sum(c.license_status == '待人工审核' for c in r.clips)} 条</p>
            <ul class="error">{errors}</ul><a class="button" target="_blank" href="/files/素材预览.html">查看素材 / 筛选预览</a>
            <a class="button" href="/files/素材清单.csv">下载中文清单</a>
            <a class="button" href="/files/人工审核清单.csv">下载待审清单</a>
            <form action="/download" method="post">{hidden}<h2>下载已确认许可的素材</h2>{limits()}<button>按限额自动下载</button></form>
            <form action="/zip" method="post">{hidden}<button>生成导出 ZIP</button></form>
            {'<a class="button" href="/files/素材导出.zip">保存 ZIP 到电脑</a>' if (root/'素材导出.zip').exists() else ''}</section>
            <section><h2>人工审核</h2><p>先打开来源页面，核对许可、作者、球员身份及额外限制。赛事转播条目不能解锁。本站外链接始终只保存来源。</p>
            <form action="/review" method="post">{hidden}<label>待审素材</label><select name="id" required>{options}</select>
            <label>审核依据（必填，至少 12 字）</label><textarea name="evidence" required placeholder="许可页面 URL、适用范围、限制核查及球员身份确认"></textarea>
            <details><summary>补充缺失许可信息</summary><label>作者</label><input name="author"><label>许可名称（例如 CC BY-SA 4.0）</label><input name="license_name"><label>许可链接</label><input name="license_url" type="url"></details>
            <button>记录审核通过</button></form></section>
            <section><h2>保存其他平台来源</h2><p>YouTube、X 等只保存来源链接和待确认状态，不抓取媒体。</p>
            <form action="/reference" method="post">{hidden}<label>来源页面</label><input name="url" type="url" required><label>标题</label><input name="title" required><button>加入人工审核清单</button></form></section>''' if r else ''
            self.send(f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>足球素材助手</title><style>{CSS}</style></head><body><main>
            <div class="tag">FOOTBALL MATERIAL ASSISTANT / 本机运行</div><h1>找到足球画面，保留每一份授权依据。</h1>
            <p>输入球员或主题 → 官方 API 搜索 → 许可检查 → 下载与导出</p>
            <p class="warn">优先 1080P、MP4、横屏 16:9；Commons 缺少 MP4 时可保留 WebM / OGV。不会下载疑似赛事转播；人物身份未核实或许可不明会进入人工审核。肖像、商标与具体用途须另行核查。</p>
            <p role="status">{esc(state['message'])}</p><section><h2>搜索素材</h2>
            <form action="/search" method="post">{hidden}<label>球员名字或足球主题</label><input name="query" required maxlength="200" placeholder="例如：梅西进球庆祝 / 姆巴佩训练 / 足球场空镜" value="{esc(r.query if r else '')}">
            <label>英文关键词（可选，用于修正翻译）</label><input name="english" maxlength="200" placeholder="例如：Lionel Messi goal celebration">
            <p><small>内置常见球员和足球词库。未知中文将发送给 MyMemory 公共翻译 API；网络不可用时请手填英文。</small></p>
            <div class="row"><label><input type="checkbox" name="pexels" checked> Pexels（需环境变量密钥）</label><label><input type="checkbox" name="commons" checked> Wikimedia Commons（无需密钥）</label></div>
            <label>每来源搜索条数（1–40，只请求一页）</label><input name="limit" type="number" min="1" max="40" value="12">
            {limits()}<label><input type="checkbox" name="auto" checked> 搜索后自动下载许可已确认的素材</label>
            <button>开始搜索与整理</button></form></section>{result}
            <footer>密钥只从 PEXELS_API_KEY 读取。输出目录：{esc(root)}。关闭终端即可停止服务；Ctrl+C 安全退出。</footer></main>
            <div id="busy">正在处理，请稍候；网络请求可能需要数十秒…</div><script>document.querySelectorAll('form').forEach(f=>f.addEventListener('submit',()=>document.getElementById('busy').style.display='grid'));</script></body></html>''')

        def do_POST(self):
            if not self.valid_host() or self.headers.get("Origin", f"http://127.0.0.1:{port}") not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}:
                return self.send("请求来源无效", 403)
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length < 16000:
                return self.send("请求过大或为空", 400)
            fields = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            get = lambda k, default="": fields.get(k, [default])[0]
            if not hmac.compare_digest(get("token"), token):
                return self.send("请求令牌失效，请刷新页面", 403)
            try:
                r = state["report"]
                if self.path == "/search":
                    sources = tuple(s for k, s in (("pexels", "Pexels"), ("commons", "Wikimedia Commons")) if k in fields)
                    if not sources:
                        raise ValueError("请选择至少一个来源")
                    # 参数在发起任何下载前验证。
                    limits_values = (int(get("max_count", "5")), int(get("max_mb", "100")), int(get("total_mb", "300")))
                    if not (1 <= limits_values[0] <= 20 and 1 <= limits_values[1] <= 2048 and 1 <= limits_values[2] <= 4096):
                        raise ValueError("下载限额超出允许范围")
                    r = search(get("query"), english=get("english"), limit=int(get("limit", "12")), sources=sources)
                    state["report"] = r
                    if "auto" in fields:
                        download(r, root, max_count=limits_values[0], max_mb=limits_values[1], total_mb=limits_values[2])
                    state["message"] = "搜索完成，接口错误及空结果已如实记录。"
                elif r is None:
                    raise ValueError("请先搜索一次")
                elif self.path == "/download":
                    n = download(r, root, max_count=int(get("max_count", "5")), max_mb=int(get("max_mb", "100")), total_mb=int(get("total_mb", "300")))
                    state["message"] = f"本次新增下载 {n} 个；详情见素材预览。"
                elif self.path == "/reference":
                    add_reference(r, get("url"), get("title"))
                    state["message"] = "来源已记录，不会抓取该平台媒体。"
                elif self.path == "/review":
                    clip = next((c for c in r.clips if c.id == get("id")), None)
                    if not clip:
                        raise ValueError("未找到待审核素材")
                    review_clip(clip, get("evidence"), get("author"), get("license_name"), get("license_url"))
                    state["message"] = "审核记录已保存，可点击下载已确认许可的素材。"
                elif self.path != "/zip":
                    raise ValueError("未知操作")
                if r:
                    export_report(r, root)
                    # 报告变动后使旧 ZIP 失效，避免导出过期审核状态。
                    (root / "素材导出.zip").unlink(missing_ok=True)
                    if self.path == "/zip":
                        make_zip(root)
                        state["message"] = "ZIP 已生成，请点击“保存 ZIP 到电脑”。"
            except Exception as exc:
                state["message"] = "操作未完成：" + str(exc)
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"中文界面：http://127.0.0.1:{port}  （Ctrl+C 退出）", flush=True)
    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def limits():
    return '''<div class="row"><div><label>最多下载（个）</label><input name="max_count" type="number" min="1" max="20" value="5"></div>
    <div><label>单文件上限（MB）</label><input name="max_mb" type="number" min="1" max="2048" value="100"></div>
    <div><label>本次总下载上限（MB）</label><input name="total_mb" type="number" min="1" max="4096" value="300"></div></div>'''
