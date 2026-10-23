"""本机 HTTP 集成测试；只用缺少密钥的 Pexels 分支，不访问外网。"""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        env = os.environ.copy()
        env.pop("PEXELS_API_KEY", None)
        cls.proc = subprocess.Popen([sys.executable, "app.py", "--output", cls.tmp.name,
                                    "--port", str(cls.port), "--no-browser"],
                                   cwd=Path(__file__).resolve().parents[1], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        cls.base = f"http://127.0.0.1:{cls.port}"
        for _ in range(50):
            try:
                with cls.client.open(cls.base, timeout=1) as response:
                    page = response.read().decode()
                cls.token = re.search(r'name="token" value="([^"]+)"', page)[1]
                return
            except OSError:
                time.sleep(.05)
        cls.tearDownClass()
        raise RuntimeError("本机中文界面启动失败")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.tmp.cleanup()

    def post(self, path, **fields):
        request = urllib.request.Request(self.base + path,
            data=urllib.parse.urlencode({"token": self.token, **fields}).encode(),
            headers={"Origin": self.base})
        return self.client.open(request, timeout=5)

    def test_chinese_ui_search_and_zip_export(self):
        with self.post("/search", query="足球场空镜", pexels="on", limit="5", auto="on") as r:
            page = r.read().decode()
        self.assertIn("缺少 PEXELS_API_KEY", page)
        self.assertIn("搜索 0 条", page)
        with self.client.open(self.base + "/files/" + urllib.parse.quote("素材预览.html")) as r:
            preview = r.read().decode()
        self.assertIn("没有可展示的素材", preview)
        with self.post("/reference", url="https://www.youtube.com/watch?v=fixture", title="流程验证来源，不代表真实素材") as r:
            self.assertIn("来源已记录", r.read().decode())
        with self.post("/zip") as r:
            self.assertIn("ZIP 已生成", r.read().decode())
        with self.client.open(self.base + "/files/" + urllib.parse.quote("素材导出.zip")) as r:
            self.assertEqual(r.headers.get_content_type(), "application/zip")
            self.assertGreater(len(r.read()), 100)
        with zipfile.ZipFile(Path(self.tmp.name)/"素材导出.zip") as z:
            data = json.loads(z.read("素材记录.json"))
        self.assertEqual(data["clips"][0]["license_status"], "待人工审核")
        self.assertEqual(data["clips"][0]["download_url"], "")

    def test_csrf_and_private_files_are_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post("/search", token="wrong-token", query="足球")
        self.assertEqual(error.exception.code, 403)
        for path in ["/files/.downloads.json", "/files/../app.py"]:
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.client.open(self.base + path)
            self.assertEqual(error.exception.code, 404)

    def test_host_header_rejected(self):
        req = urllib.request.Request(self.base, headers={"Host": "untrusted.example"})
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.client.open(req)
        self.assertEqual(error.exception.code, 403)
