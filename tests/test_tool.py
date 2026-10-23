"""全部使用模拟 API/视频字节，不代表真实搜索或可用素材。"""
import io
import json
import os
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

from football_tool.core import (Clip, Network, PEXELS_LICENSE, Report, add_reference,
    allowed_url, assess, broadcast_risk, commons_license, commons_search, download,
    export_report, make_zip, pexels_search, review_clip, search, translate, variant_score)
from football_tool.preview import build_preview

MEDIA = "https://video-files.pexels.com/test-fixture.mp4"
VIDEO = b"\x00\x00\x00\x18ftypisom" + b"0" * 100  # 仅用于文件头与下载流程测试，不是真实可播放视频


class Response(io.BytesIO):
    def __init__(self, data=VIDEO, *, declared=None, mime="video/mp4"):
        super().__init__(data)
        self.headers = {"Content-Type": mime}
        if declared is not None:
            self.headers["Content-Length"] = str(declared)


class FakeNetwork:
    def __init__(self, data=None, body=VIDEO, declared=None, mime="video/mp4"):
        self.data, self.body, self.declared, self.mime = data or {}, body, declared, mime
        self.calls = []

    def json(self, url, params=None, headers=None):
        self.calls.append((url, params, headers))
        if isinstance(self.data, Exception):
            raise self.data
        return self.data

    def open(self, url, **kwargs):
        self.calls.append(url)
        return Response(self.body, declared=self.declared, mime=self.mime)


def fixture_clip(id="fixture-1", **changes):
    c = Clip(id, "Pexels", "Football training fixture", "https://www.pexels.com/", MEDIA,
             1920, 1080, 0, "video/mp4", "模拟作者", "Pexels License", PEXELS_LICENSE,
             "模拟作者 / Pexels", "足球训练", "训练")
    c.__dict__.update(changes)
    return assess(c)


class TranslationTests(unittest.TestCase):
    def test_required_examples_work_without_network(self):
        cases = {"梅西进球庆祝": "Lionel Messi goal celebration", "姆巴佩训练": "Kylian Mbappe training",
                 "亚马尔日常生活": "Lamine Yamal daily life", "球场球迷欢呼": "football fans cheering",
                 "足球场空镜": "empty football stadium"}
        n = FakeNetwork()
        for cn, en in cases.items():
            self.assertEqual(translate(cn, n)[0], en)
        self.assertEqual(n.calls, [])

    def test_unknown_chinese_failure_does_not_guess(self):
        r = search("未收录的主题", net=FakeNetwork(data=ValueError("网络不可用")))
        self.assertEqual(r.clips, [])
        self.assertIn("翻译失败", r.errors[0])

    def test_manual_override(self):
        self.assertEqual(translate("任意内容", FakeNetwork(), "football stadium")[0], "football stadium")

    def test_public_translation(self):
        n = FakeNetwork({"responseStatus": 200, "responseData": {"translatedText": "football shoes"}})
        self.assertEqual(translate("足球鞋子", n)[0], "football shoes")


class PermissionTests(unittest.TestCase):
    def test_broadcast_blocked_even_with_open_license(self):
        c = fixture_clip(title="UEFA Champions League match highlights")
        self.assertEqual(c.license_status, "禁止下载")
        with self.assertRaises(ValueError):
            review_clip(c, "已核对来源及开放许可链接，允许使用")

    def test_license_whitelist_rejects_restrictions_and_mismatch(self):
        for name, url in [("CC BY-NC 4.0", "https://creativecommons.org/licenses/by-nc/4.0/"),
                          ("CC BY 4.0", "https://example.org/"),
                          ("CC BY-SA 3.0", "https://creativecommons.org/licenses/by-sa/4.0/"),
                          ("CC BY 4.0", "https://creativecommons.org/licenses/by-sa/4.0/")]:
            self.assertFalse(commons_license(name, url))
        self.assertTrue(commons_license("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"))
        self.assertTrue(commons_license("CC0", "https://creativecommons.org/publicdomain/zero/1.0/"))

    def test_unknown_author_review_and_audit(self):
        c = fixture_clip(author="", attribution="")
        self.assertEqual(c.license_status, "待人工审核")
        review_clip(c, "核查来源页面、Pexels 许可、人物身份及使用范围均符合", author="已核实作者")
        self.assertEqual(c.license_status, "人工已确认")
        self.assertIn("已核实作者", c.attribution)

    def test_external_reference_never_downloads(self):
        r = Report("足球")
        c = add_reference(r, "https://www.youtube.com/watch?v=test", "待核实足球片段")
        with self.assertRaises(ValueError):
            review_clip(c, "假设人工确认了一个外部平台的内容")
        with tempfile.TemporaryDirectory() as d:
            n = FakeNetwork()
            self.assertEqual(download(r, d, net=n), 0)
            self.assertEqual(n.calls, [])

    def test_media_hosts_and_schemes(self):
        for url in ["http://video-files.pexels.com/a.mp4", "https://pexels.com.evil.test/a", "https://127.0.0.1/a", "file:///etc/passwd", "https://a:secret@video-files.pexels.com/a", "https://upload.wikimedia.org:8443/a"]:
            self.assertFalse(allowed_url(url, True))
        self.assertTrue(allowed_url(MEDIA, True))


class ProviderTests(unittest.TestCase):
    def test_pexels_selects_1080_mp4_and_captures_metadata(self):
        n = FakeNetwork({"videos": [{"id": 123, "url": "https://www.pexels.com/video/football-training-123/",
            "user": {"name": "模拟作者"}, "video_files": [
                {"file_type": "video/mp4", "width": 3840, "height": 2160, "link": MEDIA},
                {"file_type": "video/mp4", "width": 1920, "height": 1080, "link": MEDIA}]}]})
        c = pexels_search(n, "football", 5, "test-only-secret")[0]
        self.assertEqual((c.width, c.height, c.license_status), (1920, 1080, "许可已确认"))
        self.assertEqual(n.calls[0][2], {"Authorization": "test-only-secret"})

    def test_commons_derivative_and_restrictions(self):
        meta = {k: {"value": v} for k, v in {"Artist": "<b>模拟作者</b>", "LicenseShortName": "CC BY-SA 4.0",
                "LicenseUrl": "https://creativecommons.org/licenses/by-sa/4.0/", "Restrictions": "personality rights"}.items()}
        n = FakeNetwork({"query": {"pages": {"1": {"pageid": 1, "title": "File:Football training.webm", "videoinfo": [{
            "mime": "video/webm", "url": "https://upload.wikimedia.org/fixture.webm", "width": 1280, "height": 720,
            "extmetadata": meta, "derivatives": [{"src": "https://upload.wikimedia.org/fixture.mp4", "type": "video/mp4", "width": 1920, "height": 1080}]}]}}}})
        c = commons_search(n, "football", 5)[0]
        self.assertEqual((c.height, c.mime, c.author), (1080, "video/mp4", "模拟作者"))
        self.assertEqual(c.license_status, "待人工审核")

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key_and_network_failure_are_honest(self):
        r = search("足球", net=FakeNetwork(data=urllib.error.URLError("网络拒绝")))
        self.assertEqual(len(r.clips), 0)
        self.assertEqual(len(r.errors), 2)
        self.assertIn("PEXELS_API_KEY", r.errors[0])

    @patch.dict(os.environ, {"PEXELS_API_KEY": "test-only-secret"})
    def test_player_identity_requires_review_and_no_fallback(self):
        n = FakeNetwork({"videos": [{"id": 1, "url": "https://www.pexels.com/video/football-training-1/",
            "user": {"name": "作者"}, "video_files": [{"file_type": "video/mp4", "width": 1920, "height": 1080, "link": MEDIA}]}]})
        r = search("姆巴佩训练", sources=("Pexels",), net=n)
        self.assertIn("未核实", r.clips[0].player)
        self.assertEqual(r.clips[0].license_status, "待人工审核")
        self.assertEqual(n.calls[0][1]["query"], "Kylian Mbappe training")


class DownloadTests(unittest.TestCase):
    def test_download_dedup_ledger_and_default_five(self):
        with tempfile.TemporaryDirectory() as d:
            clips = [fixture_clip(id=f"fixture-{i}", download_url=MEDIA + f"?id={i}") for i in range(7)]
            r, n = Report("足球", clips=clips), FakeNetwork()
            # 每次模拟不同文件内容，以检查数量上限。
            original = n.open
            def distinct_open(url, **kwargs):
                n.body = VIDEO + url.encode()
                return original(url, **kwargs)
            n.open = distinct_open
            self.assertEqual(download(r, d, net=n), 5)
            self.assertEqual(len(list(Path(d).rglob("*.mp4"))), 5)
            self.assertIn("限额", clips[-1].download_status)
            n.calls.clear()
            self.assertEqual(download(Report("足球", clips=clips[:5]), d, net=n), 0)
            self.assertEqual(n.calls, [])

    def test_same_url_avoids_second_download(self):
        with tempfile.TemporaryDirectory() as d:
            n = FakeNetwork()
            r = Report("足球", clips=[fixture_clip(), fixture_clip(id="another-id")])
            self.assertEqual(download(r, d, net=n), 1)
            self.assertEqual(len(n.calls), 1)
            other = fixture_clip(id="different-url", download_url=MEDIA + "?same-content=1")
            self.assertEqual(download(Report("足球", clips=[other]), d, net=n), 0)
            self.assertEqual(other.download_status, "内容重复（已复用）")
            self.assertEqual(other.local_path, r.clips[0].local_path)
            self.assertEqual(len(list(Path(d).rglob("*.mp4"))), 1)

    def test_streaming_limit_removes_partial_without_length(self):
        with tempfile.TemporaryDirectory() as d:
            c = fixture_clip()
            n = FakeNetwork(body=VIDEO + b"0" * 2 * 1024 ** 2)
            self.assertEqual(download(Report("足球", clips=[c]), d, max_mb=1, net=n), 0)
            self.assertFalse(list(Path(d).rglob("*.part")))
            self.assertFalse(list(Path(d).rglob("*.mp4")))
            self.assertIn("大小上限", c.download_status)

    def test_known_size_is_skipped_without_request(self):
        with tempfile.TemporaryDirectory() as d:
            n = FakeNetwork()
            c = fixture_clip(size=2*1024**2)
            self.assertEqual(download(Report("足球", clips=[c]), d, max_mb=1, net=n), 0)
            self.assertEqual(n.calls, [])

    def test_failed_transfer_counts_toward_total_budget(self):
        with tempfile.TemporaryDirectory() as d:
            clips = [fixture_clip(id=str(i), download_url=MEDIA+f"?i={i}") for i in range(3)]
            n = FakeNetwork(body=VIDEO+b"0"*2*1024**2)
            self.assertEqual(download(Report("足球", clips=clips), d, total_mb=1, net=n), 0)
            self.assertEqual(len(n.calls), 1)

    def test_incomplete_or_html_is_not_video(self):
        for n in (FakeNetwork(declared=1000), FakeNetwork(body=b"<html>error</html>"), FakeNetwork(body=b"", declared=0), FakeNetwork(mime="text/html")):
            with tempfile.TemporaryDirectory() as d:
                self.assertEqual(download(Report("足球", clips=[fixture_clip()]), d, net=n), 0)
                self.assertFalse(list(Path(d).rglob("*.mp4")))

    def test_pending_or_blocked_clips_never_request_media(self):
        with tempfile.TemporaryDirectory() as d:
            n = FakeNetwork()
            r = Report("足球", clips=[fixture_clip(author=""), fixture_clip(title="Premier League broadcast")])
            self.assertEqual(download(r, d, net=n), 0)
            self.assertEqual(n.calls, [])


class ExportTests(unittest.TestCase):
    def test_csv_html_zip_and_secret_exclusion(self):
        with tempfile.TemporaryDirectory() as d:
            c = fixture_clip(title='=1+1 <script>alert("X")</script>')
            r = Report("足球", clips=[c])
            download(r, d, net=FakeNetwork())
            export_report(r, d)
            (Path(d)/".env").write_text("PEXELS_API_KEY=never-export", "utf-8")
            z = make_zip(d)
            csv = (Path(d)/"素材清单.csv").read_text("utf-8-sig")
            self.assertIn("'=1+1", csv)
            page = (Path(d)/"素材预览.html").read_text("utf-8")
            self.assertNotIn('<script>alert("X")</script>', page)
            self.assertIn('data-key="license"', page)
            with zipfile.ZipFile(z) as f:
                self.assertIn(c.local_path, f.namelist())
                self.assertNotIn(".env", f.namelist())
                self.assertNotIn(".downloads.json", f.namelist())
                self.assertNotIn("素材导出.zip", f.namelist())

    def test_empty_report_no_invented_links(self):
        with tempfile.TemporaryDirectory() as d:
            r = Report("足球", errors=["网络不可用"])
            stats = export_report(r, d)
            self.assertEqual(stats["真实搜索结果数"], 0)
            data = json.loads((Path(d)/"素材记录.json").read_text("utf-8"))
            self.assertEqual(data["clips"], [])


if __name__ == "__main__":
    unittest.main()
