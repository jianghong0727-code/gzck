import html
import json
import urllib.parse

CSS = """
:root{font-family:system-ui,'Microsoft YaHei',sans-serif;color:#dce9ee;background:#0b151b;color-scheme:dark}*{box-sizing:border-box}body{margin:0}main{max-width:1200px;margin:auto;padding:36px 24px}h1{font-size:30px;margin:12px 0}h2{font-size:20px}.tag{color:#4ddca9;font-size:12px;letter-spacing:2px}p,.muted{color:#a7bcc5;line-height:1.7}section,.card{background:#13232d;border:1px solid #29404c;border-radius:14px;padding:22px;margin:18px 0}input,select,textarea,button{font:inherit;border:1px solid #395563;border-radius:8px;padding:10px;background:#0b1921;color:#e7f2f5}input:not([type=checkbox]),textarea{width:100%}label{display:block;margin:12px 0 6px;font-size:14px}button,.button{display:inline-block;background:#43d6a0;color:#07251b;font-weight:700;text-decoration:none;cursor:pointer;border:0;padding:11px 18px;border-radius:8px;margin-top:12px}a{color:#61dab7;overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}.row{display:flex;flex-wrap:wrap;gap:12px;align-items:center}.row>*{flex:1;min-width:140px}small{color:#a7bcc5}.pill{display:inline-block;border-radius:5px;background:#203e49;padding:4px 8px;font-size:12px}.warn{border-left:3px solid #f4c369;padding:12px;background:#2a291f}.error{color:#ffd198}.stats{font-size:18px}details{margin:16px 0}summary{cursor:pointer;color:#bcd4df}video{width:100%;max-height:260px;background:#050a0d;border-radius:8px}dl{font-size:13px;line-height:1.6}dt{color:#95afbb;margin-top:8px}dd{margin-left:0;overflow-wrap:anywhere}footer{margin-top:32px;color:#9cb5be;font-size:12px}.filters{position:sticky;top:0;background:#0b151bf2;padding:16px 0;z-index:1}#busy{display:none;position:fixed;inset:0;background:#071016ed;z-index:99;place-items:center;font-size:20px}
"""


def esc(value):
    return html.escape(str(value), quote=True)


def link(url, label):
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        return esc(label) + "（链接待核实）"
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'


def build_preview(report):
    clips = report.clips
    cards = []
    for c in clips:
        quality = f"{c.height}P" if c.height else "未知"
        video = ''
        if c.local_path:
            path = urllib.parse.quote(c.local_path, safe="/")
            video = f'<video controls preload="none" src="{esc(path)}"></video>'
        size = f"{c.size / 1024**2:.2f} MB" if c.size else "未知（下载时按流量限制检查）"
        cards.append(f'''<article class="card" data-source="{esc(c.source)}" data-quality="{quality}" data-player="{esc(c.player)}" data-license="{esc(c.license_status)}" data-category="{esc(c.category)}">
        <div class="row"><span class="pill">{esc(c.source)}</span><span class="pill">{esc(c.license_status)}</span></div>
        <h2>{esc(c.title)}</h2>{video}<p>{esc(c.player)} · {esc(c.category)} · 标题相关度 {c.relevance}%</p>
        <p>{c.width} × {c.height} · {esc(c.mime)} · {size}</p>
        <p>{esc(c.download_status)}</p><p>{link(c.page_url,'打开来源页面')}</p>
        <details><summary>许可、署名和下载信息</summary><dl>
        <dt>素材编号</dt><dd>{esc(c.id)}</dd><dt>作者</dt><dd>{esc(c.author or '待确认')}</dd>
        <dt>许可</dt><dd>{link(c.license_url,c.license_name or '待确认')}</dd>
        <dt>署名信息</dt><dd>{esc(c.attribution or '待确认')}</dd>
        <dt>审核说明</dt><dd>{esc(c.reason)}</dd><dt>人工审核依据</dt><dd>{esc(c.review_evidence)}</dd>
        <dt>真实下载链接（未确认许可的链接不可由本工具下载）</dt><dd>{esc(c.download_url or '未取得')}</dd>
        <dt>本地文件</dt><dd>{esc(c.local_path)}</dd><dt>SHA256</dt><dd>{esc(c.sha256)}</dd>
        </dl></details></article>''')
    filters = []
    for key, label, values in (("source", "来源", {c.source for c in clips}),
                               ("quality", "清晰度", {f"{c.height}P" if c.height else "未知" for c in clips}),
                               ("player", "球员 / 主题", {c.player for c in clips}),
                               ("license", "许可状态", {c.license_status for c in clips}),
                               ("category", "分类", {c.category for c in clips})):
        options = ''.join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in sorted(values))
        filters.append(f'<select aria-label="{label}" data-key="{key}"><option value="">全部{label}</option>{options}</select>')
    errors = ''.join(f'<li>{esc(e)}</li>' for e in report.errors)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>足球素材预览</title><style>{CSS}</style></head><body><main>
    <div class="tag">FOOTBALL MATERIAL ASSISTANT</div><h1>足球素材预览</h1>
    <p>关键词：{esc(report.query)}　/　英文：{esc(report.english)}<br>生成时间 UTC：{esc(report.created_at)}</p>
    <p class="stats">搜索结果 {len([c for c in clips if not c.id.startswith('reference-')])} 条 · 新增下载 {report.downloaded} 个 · 人工待审 {sum(c.license_status == '待人工审核' for c in clips)} 条</p>
    <p class="warn">许可状态基于来源元数据及人工审核记录。球员身份、肖像、商标及特定用途仍须核查；CC BY-SA 须遵守相同方式共享。相关度与分类仅按标题估算。未下载的素材不会自动加载远程媒体。</p>
    <ul class="error">{errors}</ul><div class="row filters">{''.join(filters)}</div>
    <p id="visible"></p><div class="grid">{''.join(cards) or '<section>没有可展示的素材。请检查 API 密钥、网络或缩短关键词；本页没有生成虚假结果。</section>'}</div>
    <footer>素材清单.csv 与人工审核清单.csv 可用 Excel 打开。下载链接可能过期，失效后请重新搜索。</footer>
    </main><script>
    const filters=[...document.querySelectorAll('select[data-key]')], cards=[...document.querySelectorAll('article[data-source]')];
    function update(){{let n=0;for(const c of cards){{c.hidden=!filters.every(f=>!f.value||c.dataset[f.dataset.key]===f.value);if(!c.hidden)n++;}}document.getElementById('visible').textContent='当前显示 '+n+' 条';}}
    filters.forEach(f=>f.addEventListener('change',update));update();
    </script></body></html>'''
