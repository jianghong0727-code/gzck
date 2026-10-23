from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

CATEGORIES = ("进球庆祝", "训练", "采访", "日常生活", "球迷", "通用足球画面")
PEXELS_LICENSE = "https://www.pexels.com/license/"
PLAYERS = {"梅西": "Lionel Messi", "姆巴佩": "Kylian Mbappe", "亚马尔": "Lamine Yamal",
           "C罗": "Cristiano Ronaldo", "c罗": "Cristiano Ronaldo", "哈兰德": "Erling Haaland",
           "内马尔": "Neymar", "贝林厄姆": "Jude Bellingham", "萨拉赫": "Mohamed Salah"}
TERMS = {"进球庆祝": "goal celebration", "日常生活": "daily life", "球迷欢呼": "fans cheering",
         "足球场空镜": "empty football stadium", "球场球迷欢呼": "football fans cheering",
         "足球场": "football stadium", "球场": "football stadium", "球迷": "football fans",
         "欢呼": "cheering", "进球": "goal", "庆祝": "celebration", "训练": "training",
         "采访": "interview", "日常": "daily life", "足球": "football", "空镜": "empty stadium"}


@dataclass
class Clip:
    id: str
    source: str
    title: str
    page_url: str
    download_url: str = ""
    width: int = 0
    height: int = 0
    size: int = 0
    mime: str = ""
    author: str = ""
    license_name: str = ""
    license_url: str = ""
    attribution: str = ""
    player: str = "通用足球"
    category: str = "通用足球画面"
    relevance: int = 0
    license_status: str = "待人工审核"
    reason: str = ""
    download_status: str = "未下载"
    local_path: str = ""
    sha256: str = ""
    review_evidence: str = ""
    checked_at: str = ""


@dataclass
class Report:
    query: str
    english: str = ""
    clips: list[Clip] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    downloaded: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def clean(value):
    return html.unescape(re.sub(r"<[^>]*>", " ", str(value or ""))).strip()


def safe_name(value):
    value = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", value).strip(" .")[:70]
    return value if value and value not in {".", ".."} else "未命名"


def allowed_url(url, media=False):
    p = urllib.parse.urlsplit(url)
    host = (p.hostname or "").lower()
    roots = ("pexels.com", "upload.wikimedia.org") if media else (
        "api.pexels.com", "commons.wikimedia.org", "api.mymemory.translated.net")
    return p.scheme == "https" and not p.username and not p.password and p.port in (None, 443) and any(
        host == root or (root == "pexels.com" and host.endswith(".pexels.com")) for root in roots)


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl, media=getattr(req, "is_media", False)):
            raise ValueError("接口重定向到不受支持的域名")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        redirected.is_media = getattr(req, "is_media", False)
        return redirected


class Network:
    def __init__(self):
        self.opener = urllib.request.build_opener(SafeRedirect())

    def open(self, url, headers=None, media=False):
        if not allowed_url(url, media):
            raise ValueError("仅允许官方 API 与受支持的素材 CDN HTTPS 链接")
        req = urllib.request.Request(url, headers={"User-Agent": "FootballMaterialAssistant/1.0 (personal limited API client)", **(headers or {})})
        req.is_media = media
        return self.opener.open(req, timeout=20)

    def json(self, url, params=None, headers=None):
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for attempt in range(2):
            try:
                with self.open(url, headers) as response:
                    raw = response.read(8 * 1024 * 1024 + 1)
                    if len(raw) > 8 * 1024 * 1024:
                        raise ValueError("接口响应超过 8MB")
                    data = json.loads(raw)
                    if "error" in data:
                        raise ValueError("官方 API 返回错误：" + str(data["error"]))
                    return data
            except urllib.error.HTTPError as exc:
                if attempt == 0 and exc.code in (429, 500, 502, 503, 504):
                    delay = exc.headers.get("Retry-After", "2")
                    if not delay.isdigit() or int(delay) > 5:
                        raise ValueError(f"HTTP {exc.code}，请稍后再试，已停止请求") from None
                    time.sleep(max(1, int(delay)))
                    continue
                raise ValueError(f"HTTP {exc.code}：密钥无效、额度不足或网络拒绝；未返回素材") from None


def translate(query, net, override=""):
    if override.strip():
        return override.strip(), "使用手动英文关键词"
    translated = query
    for cn, en in sorted({**PLAYERS, **TERMS}.items(), key=lambda x: -len(x[0])):
        translated = translated.replace(cn, " " + en + " ")
    if re.search(r"[\u4e00-\u9fff]", translated):
        # 未知词使用公开翻译 API；失败时要求手动英文，绝不伪造翻译。
        if len(query.encode("utf-8")) > 450:
            raise ValueError("关键词过长，请缩短到 450 字节内或填写英文关键词")
        data = net.json("https://api.mymemory.translated.net/get", {"q": query, "langpair": "zh-CN|en"})
        translated = html.unescape(data.get("responseData", {}).get("translatedText", ""))
        if data.get("responseStatus") != 200 or not translated or re.search(r"[\u4e00-\u9fff]", translated):
            raise ValueError("自动翻译失败，请填写英文关键词")
        return translated, "未知中文词已使用 MyMemory 翻译（关键词会发送给该服务）"
    return " ".join(translated.split()), "使用本地球员及足球词库翻译"


def player_for(query, english):
    for cn, en in PLAYERS.items():
        if cn.lower() in query.lower() or en.lower() in english.lower() or en.split()[-1].lower() in english.lower():
            return cn if cn != "c罗" else "C罗"
    return safe_name(query)


def category_for(text):
    text = text.lower()
    groups = {"进球庆祝": ("celebrat", "进球", "庆祝"), "训练": ("train", "practice", "warm up", "训练"),
              "采访": ("interview", "press conference", "采访"), "日常生活": ("daily", "lifestyle", "日常"),
              "球迷": ("fans", "supporter", "crowd", "球迷", "cheering")}
    return next((c for c, words in groups.items() if any(w in text for w in words)), CATEGORIES[-1])


def broadcast_risk(text):
    return bool(re.search(r"uefa|champions[ -]league|premier[ -]league|la[ -]?liga|fifa[ -]world[ -]cup|bundesliga|serie[ -]a|ligue[ -]1|highlights|full[ -]match|goal[ -]replay|broadcast|televised|sky[ -]sports|bein[ -]sports|tnt[ -]sports|espn|欧冠|英超|西甲|德甲|意甲|法甲|世界杯|比赛集锦|比赛录像|比赛转播|进球回放|进球集锦", text, re.I))


def commons_license(name, url):
    # 多许可、非商业/禁止演绎和无明确链接的条目均留待人工审核。
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {"creativecommons.org", "www.creativecommons.org"}:
        return False
    if re.fullmatch(r"/licenses/by(?:-sa)?/(?:1\.0|2\.0|2\.5|3\.0|4\.0)/?", parsed.path):
        return bool(re.fullmatch(r"CC BY(?:-SA)? (?:1\.0|2\.0|2\.5|3\.0|4\.0)", name, re.I)) and (
            ("-sa/" in parsed.path) == ("-sa" in name.lower())) and name.split()[-1] == parsed.path.rstrip("/").split("/")[-1]
    return parsed.path.rstrip("/") in {"/publicdomain/zero/1.0", "/publicdomain/mark/1.0"} and name.lower() in {
        "cc0", "cc0 1.0", "public domain", "public domain mark", "pdm"}


def assess(clip, context=""):
    if broadcast_risk(clip.title + " " + context):
        clip.license_status, clip.reason = "禁止下载", "疑似未授权赛事转播或比赛集锦；不支持人工绕过"
    elif not clip.download_url or not allowed_url(clip.download_url, True):
        clip.license_status, clip.reason = "待人工审核", "没有受支持的真实媒体下载链接"
    elif not clip.author or not clip.attribution:
        clip.license_status, clip.reason = "待人工审核", "作者或署名信息缺失"
    elif clip.source == "Pexels" and clip.license_url == PEXELS_LICENSE:
        clip.license_status, clip.reason = "许可已确认", "Pexels 官方 API 素材，按 Pexels License 使用"
    elif clip.source == "Wikimedia Commons" and commons_license(clip.license_name, clip.license_url):
        clip.license_status, clip.reason = "许可已确认", "官方元数据给出受支持的开放许可；保留署名及相同方式共享条件"
    else:
        clip.license_status, clip.reason = "待人工审核", "许可缺失、受限或尚未支持自动确认"
    clip.checked_at = datetime.now(timezone.utc).isoformat()
    return clip


def variant_score(v):
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    mime = v.get("file_type", v.get("type", ""))
    return (mime.split(";")[0] == "video/mp4", w > h and h > 0 and abs(w / h - 16 / 9) < .08,
            -abs(h - 1080), w)


def pexels_search(net, query, limit, key):
    data = net.json("https://api.pexels.com/videos/search", {"query": query, "per_page": limit,
                    "orientation": "landscape", "size": "medium"}, {"Authorization": key})
    result = []
    for item in data.get("videos", []):
        variants = [v for v in item.get("video_files", []) if v.get("file_type") == "video/mp4" and allowed_url(v.get("link", ""), True)]
        v = max(variants, key=variant_score) if variants else {}
        title = clean(item.get("url", "").rstrip("/").split("/")[-1].replace("-", " "))
        author = clean(item.get("user", {}).get("name", ""))
        clip = Clip("pexels-" + str(item["id"]), "Pexels", title, item.get("url", ""),
                    v.get("link", ""), int(v.get("width") or 0), int(v.get("height") or 0),
                    int(v.get("size") or 0), v.get("file_type", ""), author,
                    "Pexels License", PEXELS_LICENSE, f"视频：{author} / Pexels（许可不强制署名，建议保留来源）" if author else "")
        result.append(assess(clip))
    return result


def commons_search(net, query, limit):
    data = net.json("https://commons.wikimedia.org/w/api.php", {"action": "query", "format": "json",
        "generator": "search", "gsrsearch": query + " filetype:video", "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "videoinfo", "viprop": "url|size|mime|extmetadata|derivatives"})
    result = []
    pages = data.get("query", {}).get("pages", {}).values()
    for page in sorted(pages, key=lambda p: p.get("index", 0)):
        info = (page.get("videoinfo") or [{}])[0]
        if not info.get("mime", "").startswith("video/"):
            continue
        meta = info.get("extmetadata", {})
        get = lambda name: clean(meta.get(name, {}).get("value", ""))
        variants = [v for v in info.get("derivatives", []) if v.get("type", "").split(";")[0] in {"video/mp4", "video/webm", "video/ogg"} and allowed_url(v.get("src", ""), True)]
        variants.append({"src": info.get("url", ""), "type": info.get("mime", ""), "width": info.get("width", 0), "height": info.get("height", 0), "size": info.get("size", 0)})
        variants = [v for v in variants if allowed_url(v.get("src", ""), True)]
        v = max(variants, key=variant_score) if variants else {}
        title = clean(page.get("title", "").removeprefix("File:"))
        author, name, url = get("Artist"), get("LicenseShortName"), get("LicenseUrl")
        clip = Clip("commons-" + str(page["pageid"]), "Wikimedia Commons", title,
                    info.get("descriptionurl") or "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(page["title"].replace(" ", "_")),
                    v.get("src", ""), int(v.get("width") or 0), int(v.get("height") or 0), int(v.get("size") or 0),
                    v.get("type", "").split(";")[0], author, name, url,
                    f"{title} — {author} — {name} — {url}；{get('Credit')}" if author else "")
        assess(clip, get("ImageDescription"))
        if get("Restrictions") and clip.license_status != "禁止下载":
            clip.license_status, clip.reason = "待人工审核", "Commons 标注额外限制：" + get("Restrictions")
        result.append(clip)
    return result


def search(query, *, english="", limit=12, sources=("Pexels", "Wikimedia Commons"), net=None):
    if not query.strip() or len(query) > 200:
        raise ValueError("请输入 1–200 字关键词")
    if not 1 <= limit <= 40:
        raise ValueError("每来源搜索数量须为 1–40")
    net, report = net or Network(), Report(query.strip())
    try:
        report.english, note = translate(query.strip(), net, english)
        report.notes.append(note)
    except Exception as exc:
        report.errors.append("翻译失败：" + str(exc) + "；请填写英文关键词后重试")
        return report
    player = player_for(query, report.english)
    for source in sources:
        try:
            if source == "Pexels":
                key = os.getenv("PEXELS_API_KEY", "").strip()
                if not key:
                    report.errors.append("Pexels：缺少 PEXELS_API_KEY 环境变量，已跳过；不会写入或导出密钥")
                    continue
                clips = pexels_search(net, report.english, limit, key)
            elif source == "Wikimedia Commons":
                clips = commons_search(net, report.english, limit)
            else:
                continue
            for clip in clips:
                text = clip.title.lower()
                tokens = re.findall(r"[a-z0-9]+", report.english.lower())
                clip.relevance = round(100 * sum(t in text for t in tokens) / max(1, len(tokens)))
                named = next((en for cn, en in PLAYERS.items() if cn == player), "")
                if named and named.split()[-1].lower() not in text:
                    clip.player = "通用足球（球员未核实）"
                    clip.reason += "；标题未验证该球员身份"
                    if clip.license_status == "许可已确认":
                        clip.license_status = "待人工审核"
                else:
                    clip.player = player
                # 标题可验证的分类；不把查询意图冒充视频内容。
                clip.category = category_for(clip.title)
                report.clips.append(clip)
        except Exception as exc:
            # 异常可能包含带鉴权参数的服务响应，只保留安全的类别/常规信息。
            reason = str(exc) if isinstance(exc, (ValueError, urllib.error.URLError)) else type(exc).__name__
            key = os.getenv("PEXELS_API_KEY", "")
            report.errors.append(source + "：" + (reason.replace(key, "[已隐藏]") if key else reason))
    report.clips = sorted({c.id: c for c in report.clips}.values(), key=lambda c: -c.relevance)
    return report


def add_reference(report, url, title):
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise ValueError("来源链接须为 HTTPS 公开页面")
    clip = Clip("reference-" + hashlib.sha256(url.encode()).hexdigest()[:16], p.hostname,
                title.strip() or "待核实来源", url, player=player_for(report.query, report.english),
                reason="仅保存链接；未取得可核验的素材许可和官方下载接口")
    if broadcast_risk(clip.title):
        clip.license_status, clip.reason = "禁止下载", "疑似赛事转播；仅保存来源记录"
    report.clips.append(clip)
    return clip


def review_clip(clip, evidence, author="", license_name="", license_url=""):
    if clip.license_status == "禁止下载" or broadcast_risk(clip.title):
        raise ValueError("疑似赛事转播不能通过人工审核绕过下载限制")
    if clip.source not in {"Pexels", "Wikimedia Commons"}:
        raise ValueError("外部平台只记录来源；本工具不抓取该平台媒体")
    if len(evidence.strip()) < 12:
        raise ValueError("请填写不少于 12 字的审核依据，含许可页面与使用范围")
    candidate = Clip(**asdict(clip))
    candidate.author = author.strip() or candidate.author
    candidate.license_name = license_name.strip() or candidate.license_name
    candidate.license_url = license_url.strip() or candidate.license_url
    if candidate.source == "Pexels":
        valid = candidate.license_name == "Pexels License" and candidate.license_url == PEXELS_LICENSE
    else:
        valid = commons_license(candidate.license_name, candidate.license_url)
    if not valid or not candidate.author or not allowed_url(candidate.download_url, True):
        raise ValueError("审核仍需受支持的开放许可、许可链接、作者及官方下载地址")
    candidate.attribution = f"{candidate.title} — {candidate.author} — {candidate.license_name} — {candidate.license_url} — {candidate.page_url}"
    candidate.license_status, candidate.review_evidence = "人工已确认", evidence.strip()
    candidate.reason = "用户核查来源、额外限制和球员身份后确认；审核依据已记录"
    candidate.checked_at = datetime.now(timezone.utc).isoformat()
    clip.__dict__.update(candidate.__dict__)


def is_video(data, mime):
    if mime == "video/mp4":
        return len(data) >= 12 and data[4:8] == b"ftyp"
    if mime == "video/webm":
        return data.startswith(b"\x1aE\xdf\xa3")
    if mime == "video/ogg":
        return data.startswith(b"OggS")
    return False


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(report, root, *, max_count=5, max_mb=100, total_mb=300, net=None):
    if not 1 <= max_count <= 20 or not 1 <= max_mb <= 2048 or not 1 <= total_mb <= 4096:
        raise ValueError("数量须为 1–20，单文件大小 1–2048 MB，总大小 1–4096 MB")
    root, net = Path(root).resolve(), net or Network()
    root.mkdir(parents=True, exist_ok=True)
    ledger_path = root / ".downloads.json"
    ledger = json.loads(ledger_path.read_text("utf-8")) if ledger_path.exists() else {}
    count, total, attempts = 0, 0, 0
    for clip in report.clips:
        if clip.license_status not in {"许可已确认", "人工已确认"}:
            continue
        if broadcast_risk(clip.title) or not allowed_url(clip.download_url, True):
            clip.download_status = "已拦截：来源或赛事风险"
            continue
        entry = ledger.get(clip.id) or next((e for e in ledger.values() if e.get("url") == clip.download_url), None)
        if entry:
            path = (root / entry["path"]).resolve()
            if path.is_relative_to(root) and path.is_file() and file_sha256(path) == entry["sha256"]:
                clip.local_path, clip.sha256 = entry["path"], entry["sha256"]
                clip.size = path.stat().st_size
                clip.download_status = "已存在（去重）"
                continue
        if count >= max_count or attempts >= max_count or total >= total_mb * 1024 ** 2:
            clip.download_status = "已跳过：本次数量/流量限额"
            continue
        budget = min(max_mb * 1024 ** 2, total_mb * 1024 ** 2 - total)
        if clip.size > budget:
            clip.download_status = "已跳过：文件超过大小限制"
            continue
        suffix = {"video/mp4": ".mp4", "video/webm": ".webm", "video/ogg": ".ogv"}.get(clip.mime)
        if not suffix:
            clip.download_status = "已跳过：不支持的视频格式"
            continue
        directory = root / safe_name(clip.player) / safe_name(clip.category)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / (safe_name(clip.id) + suffix)
        partial, received = target.with_suffix(suffix + ".part"), 0
        attempts += 1
        try:
            digest = hashlib.sha256()
            with net.open(clip.download_url, media=True) as response:
                length = int(response.headers.get("Content-Length", 0))
                content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
                if content_type not in {clip.mime, "application/octet-stream", "binary/octet-stream"}:
                    raise ValueError("服务器没有返回预期视频类型")
                if length > budget:
                    raise ValueError("Content-Length 超过大小限制")
                with partial.open("wb") as out:
                    first = True
                    while True:
                        chunk = response.read(min(65536, budget - received + 1))
                        if not chunk:
                            break
                        received += len(chunk)
                        total += len(chunk)
                        if received > budget:
                            raise ValueError("流式下载触及大小上限，已删除未完成文件")
                        if first and not is_video(chunk, clip.mime):
                            raise ValueError("文件头不是预期视频，已拒绝保存")
                        first = False
                        digest.update(chunk)
                        out.write(chunk)
                if received == 0 or (length and length != received):
                    raise ValueError("视频为空或下载不完整")
            hashed = digest.hexdigest()
            duplicate = next((e for e in ledger.values() if e["sha256"] == hashed and (root / e["path"]).is_file()), None)
            if duplicate:
                partial.unlink()
                clip.local_path, clip.sha256 = duplicate["path"], hashed
                clip.download_status = "内容重复（已复用）"
            else:
                partial.replace(target)
                clip.local_path, clip.sha256 = target.relative_to(root).as_posix(), hashed
                clip.download_status = "下载成功"
                count += 1
            clip.size = received
            ledger[clip.id] = {"path": clip.local_path, "sha256": hashed, "url": clip.download_url}
            temp = ledger_path.with_suffix(".tmp")
            temp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), "utf-8")
            temp.replace(ledger_path)
        except Exception as exc:
            partial.unlink(missing_ok=True)
            clip.download_status = "下载失败：" + str(exc)
            report.errors.append(clip.id + "：" + str(exc))
    report.downloaded += count
    return count


CSV_FIELDS = {"id": "素材编号", "source": "来源", "title": "标题", "player": "球员或主题", "category": "分类",
    "relevance": "标题相关度", "page_url": "来源页面", "download_url": "真实下载链接", "width": "宽度", "height": "高度",
    "size": "文件大小字节", "mime": "格式", "author": "作者", "license_name": "许可名称", "license_url": "许可链接",
    "attribution": "署名信息", "license_status": "许可状态", "reason": "审核说明", "review_evidence": "人工审核依据",
    "checked_at": "许可检查时间UTC", "download_status": "下载状态", "local_path": "本地文件", "sha256": "SHA256"}


def export_report(report, root):
    from .preview import build_preview
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for filename, clips in (("素材清单.csv", report.clips), ("人工审核清单.csv", [c for c in report.clips if c.license_status == "待人工审核"])):
        with (root / filename).open("w", encoding="utf-8-sig", newline="") as out:
            writer = csv.writer(out)
            writer.writerow(CSV_FIELDS.values())
            for clip in clips:
                values = [getattr(clip, k) for k in CSV_FIELDS]
                writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v for v in values])
    (root / "素材记录.json").write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), "utf-8")
    (root / "素材预览.html").write_text(build_preview(report), "utf-8")
    stats = {"关键词": report.query, "英文关键词": report.english, "真实搜索结果数": len([c for c in report.clips if not c.id.startswith("reference-")]),
             "新增下载数": report.downloaded, "待审核数": sum(c.license_status == "待人工审核" for c in report.clips),
             "禁止下载数": sum(c.license_status == "禁止下载" for c in report.clips), "错误": report.errors, "说明": report.notes,
             "生成时间UTC": report.created_at}
    (root / "运行报告.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), "utf-8")
    return stats


def make_zip(root):
    root = Path(root).resolve()
    target = root / "素材导出.zip"
    # 只打包当前报告引用的文件，避免混入其他运行、临时文件或密钥。
    report = json.loads((root / "素材记录.json").read_text("utf-8"))
    names = {"素材清单.csv", "人工审核清单.csv", "素材记录.json", "素材预览.html", "运行报告.json"}
    names.update(c["local_path"] for c in report["clips"] if c.get("local_path"))
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
        for name in sorted(names):
            path = (root / name).resolve()
            if path.is_relative_to(root) and path.is_file():
                out.write(path, path.relative_to(root).as_posix())
    return target
