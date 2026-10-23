"""Actions 入口测试：模拟接口，不访问素材站、不计入真实素材结果。"""
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from football_tool.core import Report
from scripts.run_actions import execute
from test_tool import FakeNetwork, fixture_clip


class ActionsTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_auto_without_key_uses_commons_and_preserves_literal_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "must-not-exist"
            query = f"football $(touch {marker})"
            env = {"INPUT_QUERY": query, "GITHUB_STEP_SUMMARY": str(root / "summary.md")}
            net = FakeNetwork()
            self.assertEqual(execute(env, root, net), 0)
            self.assertEqual(len(net.calls), 1)
            self.assertIn("commons.wikimedia.org", net.calls[0][0])
            self.assertEqual(net.calls[0][1]["gsrsearch"], query + " filetype:video")
            self.assertFalse(marker.exists())
            summary = (root / "summary.md").read_text("utf-8")
            self.assertIn("未设置 PEXELS_API_KEY", summary)
            self.assertTrue((root / "素材导出.zip").is_file())

    @patch.dict(os.environ, {}, clear=True)
    def test_all_missing_key_still_exports_honest_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = execute({"INPUT_QUERY": "足球", "INPUT_SOURCE": "all"}, root, FakeNetwork())
            self.assertEqual(code, 2)
            with zipfile.ZipFile(root / "素材导出.zip") as archive:
                stats = json.loads(archive.read("运行报告.json"))
            self.assertEqual(stats["真实搜索结果数"], 0)
            self.assertIn("PEXELS_API_KEY", stats["错误"][0])

    def test_invalid_limits_fail_before_network_and_export_reason(self):
        for count in ("1000", "-1", "5;echo bad", "1.5"):
            with tempfile.TemporaryDirectory() as directory:
                net = FakeNetwork()
                self.assertEqual(execute({"INPUT_QUERY": "足球", "INPUT_MAX_COUNT": count}, directory, net), 2)
                self.assertEqual(net.calls, [])
                stats = json.loads((Path(directory) / "运行报告.json").read_text("utf-8"))
                self.assertTrue(stats["错误"])

    def test_search_only_does_not_download(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Report("足球训练", clips=[fixture_clip()])
            net = FakeNetwork()
            with patch("scripts.run_actions.search", return_value=report):
                self.assertEqual(execute({"INPUT_QUERY": "足球训练", "INPUT_SEARCH_ONLY": "true"}, directory, net), 0)
            self.assertEqual(net.calls, [])
            self.assertFalse(list(Path(directory).rglob("*.mp4")))

    def test_confirmed_only_downloads_and_exports_video(self):
        with tempfile.TemporaryDirectory() as directory:
            confirmed = fixture_clip()
            pending = fixture_clip(id="pending", author="")
            report = Report("足球训练", clips=[confirmed, pending])
            net = FakeNetwork()
            with patch("scripts.run_actions.search", return_value=report):
                self.assertEqual(execute({"INPUT_QUERY": "足球训练", "INPUT_MAX_COUNT": "1"}, directory, net), 0)
            self.assertEqual(len(net.calls), 1)
            with zipfile.ZipFile(Path(directory)/"素材导出.zip") as archive:
                self.assertIn(confirmed.local_path, archive.namelist())
                self.assertEqual(len([p for p in archive.namelist() if p.endswith(".mp4")]), 1)

    def test_multiline_script_rejected_with_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            net = FakeNetwork()
            self.assertEqual(execute({"INPUT_QUERY": "第一段文案\n第二段文案"}, directory, net), 2)
            self.assertEqual(net.calls, [])
            stats = json.loads((Path(directory)/"运行报告.json").read_text("utf-8"))
            self.assertIn("镜头关键词", stats["错误"][0])
