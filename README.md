# 足球视频素材助手

输入球员名字或足球主题，搜索、检查许可、下载和导出。可直接在 **GitHub 网页一键运行**，也可在本机打开中文界面。使用 **Pexels 官方视频 API** 与 **Wikimedia Commons 官方 API**；无爬虫、无第三方 Python 依赖，本机运行支持 Windows、macOS、Linux，要求 Python 3.10 或更新版本。

## 推荐：只用 GitHub 网页，不安装 Python

1. 打开本仓库的 [素材运行入口](https://github.com/jianghong0727-code/gzck/actions/workflows/materials.yml)。如果 GitHub 首次提示启用工作流，点击 **I understand my workflows, go ahead and enable them**。
2. 点击右侧 **Run workflow**，分支选 `main`。
3. 在 `query` 输入一个主题或镜头关键词，例如“足球场空镜”。整段短视频文案请先在聊天中拆成镜头关键词，再逐次运行。
4. 保持默认参数即可：`source=auto`、最多 5 个、单个 100 MB、本次总计 300 MB。英文翻译不准确时填写可选的 `english`；只想先看清单可勾选 `search_only`。
5. 点击绿色 **Run workflow**，等任务结束，打开该次运行记录。
6. 查看 **Summary** 中的真实搜索数、下载数和失败原因。在下方 **Artifacts** 点击 `football-materials-运行编号` 下载 ZIP，解压后打开 `素材预览.html` 或中文 CSV。

**产物只保留 3 天，请及时下载。** 即便任务因接口错误变红，仍会尝试上传已生成的清单和视频；请打开运行记录检查 Artifacts，而不要把“失败”理解成一定没有文件。GitHub 网络也可能受素材站限流或拒绝，程序会如实记录，不能保证一定有结果。

默认 `auto` 在未设置密钥时仅搜索无需密钥的 Commons，并在摘要提示；设置密钥后搜索两站。选 `all` 时若缺密钥，会在结果中保留 Pexels 缺密钥错误。Commons 结果可能较少，建议配置 Pexels。

### 在 GitHub 保存 Pexels 密钥（只做一次）

1. 在 <https://www.pexels.com/api/> 申请自己的 API Key。
2. 打开仓库的 [Actions 密钥设置](https://github.com/jianghong0727-code/gzck/settings/secrets/actions)。对应菜单是 **Settings → Secrets and variables → Actions → New repository secret**。
3. **Name** 填 `PEXELS_API_KEY`，**Secret** 粘贴自己的密钥，点击 **Add secret**。
4. 回到素材运行入口执行即可。不要把密钥填进 `query`、`english`、源码或聊天中。

只会把该 Secret 注入素材搜索步骤，不注入自动测试。工作流仅有读取仓库权限，不把视频写回代码仓库；输入经环境变量传给 Python，不拼成终端命令。

当前仓库为公开仓库，运行摘要、关键词和产物可能对其他人可见，只输入可公开的搜索词。每次 Actions 使用独立临时目录，不复用上次视频；跨运行去重请下载项目在本机使用同一个 `output/` 目录。待审核素材不会由 Actions 自动解锁，可下载清单后在本机中文界面核查。

项目另有[自动测试入口](https://github.com/jianghong0727-code/gzck/actions/workflows/tests.yml)，推送和 PR 会在 Python 3.10 / 3.12 上运行测试，不需要素材 API 密钥。

## 最简单的启动方法

1. 从 <https://www.python.org/downloads/> 安装 Python，Windows 安装时勾选 **Add Python to PATH**。
2. 下载并解压本项目。Windows 双击 `启动.bat`；macOS 在终端进入项目目录执行 `sh 启动.command`。
3. 浏览器会打开 **http://127.0.0.1:8765**。如果没有自动打开，复制这个地址到浏览器。
4. 输入主题，点击“开始搜索与整理”。默认自动下载许可已确认的素材，最多 **5 个**，单个不超过 **100 MB**，本次总下载不超过 **300 MB**。
5. 点击“查看素材 / 筛选预览”，可按来源、清晰度、球员或主题、许可状态、分类筛选。点击“生成导出 ZIP”后，再点击“保存 ZIP 到电脑”。

通用启动命令：

```bash
python app.py
```

macOS/Linux 如无 `python` 命令，改用 `python3`。Windows 如无 `py` 启动器，可在项目目录执行 `python app.py`。`requirements.txt` 已提供，全部使用标准库，**不用安装额外包**。

## 设置 Pexels 密钥

在 <https://www.pexels.com/api/> 申请 API Key，然后在**准备启动程序的同一个终端**设置环境变量。

Windows PowerShell：

```powershell
$env:PEXELS_API_KEY = "替换成你自己的密钥"
python app.py
```

macOS / Linux：

```bash
export PEXELS_API_KEY='替换成你自己的密钥'
python3 app.py
```

不要把实际密钥写进源码、README 或提交到 GitHub。程序只读取环境变量，不读取 `.env` 文件，也不把密钥写入清单或 ZIP。**不配置密钥也能搜索 Wikimedia Commons**，Pexels 会显示明确的跳过原因。

## 中文关键词与结果

以下示例可通过内置词库自动翻译，无需额外翻译服务：

| 输入 | 自动英文关键词 |
| --- | --- |
| 梅西进球庆祝 | Lionel Messi goal celebration |
| 姆巴佩训练 | Kylian Mbappe training |
| 亚马尔日常生活 | Lamine Yamal daily life |
| 球场球迷欢呼 | football fans cheering |
| 足球场空镜 | empty football stadium |

内置部分常见球员与足球词汇。遇到未收录的中文，程序会向 MyMemory 公开翻译 API 发送该关键词；翻译受其限额和网络影响。可填写“英文关键词”跳过自动翻译。翻译失败会停止本次搜索并说明原因，不猜测球员姓名。

搜索每来源仅请求一页，默认 12 条，最多 40 条，不自动翻页、不并发抓取。结果按标题与英文关键词的匹配程度排序，按**素材标题**分类为“进球庆祝、训练、采访、日常生活、球迷、通用足球画面”。这是标题估算，未做视觉识别。标题无法验证目标球员身份时，标为“通用足球（球员未核实）”并进入审核，不会用普通训练画面冒充该球员。

素材站通常没有知名球员的可商用比赛镜头，具体球员可能是零结果。不会自动改搜其他球员、编造来源链接，或转向比赛转播网站下载。

## 许可检查与人工审核

| 状态 | 行为 |
| --- | --- |
| 许可已确认 | 官方接口提供受支持的许可和作者信息，可自动下载 |
| 待人工审核 | 缺作者、许可不明、有额外限制或球员身份未核实；不下载 |
| 人工已确认 | 用户核查许可页面、作者、使用范围及额外限制并记录审核依据后，可下载 |
| 禁止下载 | 标题或 Commons 描述命中疑似欧冠、英超等转播/集锦风险，不能用人工审核解锁 |

自动接受 Pexels License，以及名称、版本、官方许可链接相匹配的 CC BY、CC BY-SA 1.0/2.0/2.5/3.0/4.0、CC0、Public Domain Mark。NC、ND、多许可未明确、缺许可链接等均须审核；当前人工审核也只支持这些已实现的开放许可，不支持绕过限制下载私人授权或外部平台媒体。

Commons 的 CC BY / CC BY-SA 必须按许可保留作者、作品名、来源、许可链接，修改时说明修改；CC BY-SA 还包含相同方式共享条件。Pexels 不强制署名，清单仍提供建议署名。清单中的署名是可用模板；发布时请结合修改情况补充说明。

**“许可已确认”指来源元数据通过规则检查，不代表已完成全面法律审查。** 元数据由素材平台/上传者提供，文字规则不能识别所有转播画面；使用前应观看并核对来源，发现赛事转播不要使用。开放版权许可也不自动覆盖球员肖像、商标、隐私、广告代言或其他用途限制。不得将人物画面用于暗示代言，不得将 Pexels 素材原样转售为素材包，具体遵守来源条款：

- Pexels License：<https://www.pexels.com/license/>
- Pexels 服务条款：<https://www.pexels.com/terms-of-service/>
- Commons 站外使用指南：<https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia>
- Commons API：<https://commons.wikimedia.org/w/api.php>
- MyMemory 翻译说明与配额：<https://mymemory.translated.net/doc/spec.php>、<https://mymemory.translated.net/doc/usagelimits.php>

对于 YouTube、X 或其他版权不明确的内容，界面提供“保存其他平台来源”，只保存用户提供的页面链接和标题，标记待确认；不自动检索这些网站，也不抓取它们的媒体，不使用 yt-dlp、登录凭据或绕过网站限制。

## 下载与输出文件

按 **MP4 → 横屏近似 16:9 → 接近 1080P** 的顺序选择可用文件。Commons 经常只有 WebM / OGV，会记录真实格式，不修改扩展名伪装 MP4，不转码；若需要 MP4，可在预览按格式信息自行选择其他素材。

输出目录结构：

```text
output/
  梅西/
    训练/
      pexels-编号.mp4
  素材清单.csv
  人工审核清单.csv
  素材记录.json
  素材预览.html
  运行报告.json
  素材导出.zip
  .downloads.json        # 下载去重索引，不放入 ZIP
```

CSV 使用 UTF-8 BOM，Excel 可直接打开，含来源页面、真实下载链接、宽高、字节大小、作者、许可、许可链接、署名、审核依据、下载状态和 SHA256。文件大小未知时记录 0，预览显示“未知”；成功下载后填写实际字节数。

每次新搜索更新当前清单与预览，过去已下载文件保留，`.downloads.json` 用于跨搜索去重；重启界面后可恢复最后一份报告。需保留多份完整清单时，请先导出 ZIP 或使用不同 `--output` 目录。ZIP 只包含当前报告及当前引用的视频，不包含其他旧下载、环境文件或密钥。

下载同时检查元数据大小、响应 Content-Length 和实际流量，无长度信息也会流式限额，超限/中断删除 `.part` 临时文件。失败尝试消耗本次流量预算；每次网络下载尝试也计入数量限额，防止反复请求。按来源编号、下载链接和内容 SHA256 去重。下载只接受官方受支持 CDN 的 HTTPS 链接，不下载未知平台重定向。

`output/`、视频、ZIP、临时文件与密钥配置已被 `.gitignore` 排除，**不要强制把大型视频加入 Git**。

## 命令行用法

默认搜索后下载许可已确认素材并导出：

```bash
python app.py search "足球场空镜" --zip
python app.py search "姆巴佩训练" --search-only
python app.py search "球迷欢呼" --source commons --max-count 3 --max-mb 30 --total-mb 60 --zip
python app.py --output output/本次搜索 search "梅西进球庆祝" --english "Lionel Messi goal celebration" --zip
python app.py --port 8766 --no-browser
```

`--output`、`--port`、`--no-browser` 放在 `search` 之前；其余搜索参数放后面。搜索接口出错或密钥缺失时退出码为 2，同时仍生成真实报告；成功（包括合法零结果）退出码为 0。下载失败记录在运行报告和素材清单。无 API 错误但文件超限或全部待审可能产生 0 个下载，这是预期行为。

仅监听 `127.0.0.1`，不向局域网开放。请求含防跨站令牌，私有去重索引不会通过网页下载。若端口占用，用 `--port 8766` 换端口；若代理/网络阻止官方接口，会显示 HTTP 或连接错误，不会生成虚假素材。

## 测试和本次实际运行

```bash
python -m unittest discover -s tests -v
```

测试包含中文翻译、官方响应解析、1080P 选择、许可版本一致性、赛事拦截、人工审核、未知平台仅保存链接、数量/流量限制、失败清理、去重、CSV 防公式注入、HTML 转义、ZIP 内容和本机 HTTP 界面的搜索/导出流程。

测试使用显式标注的**模拟响应和模拟视频头字节**，用于验证逻辑，不是实际下载成功的素材，也没有作为素材导出。

首次开发时 25 项测试通过，补充 Actions 后新增 6 项测试，覆盖无密钥自动选择、字面输入传递、限额验证、仅搜索、许可下载和文案输入提示。测试结果见 `测试报告.md`。其中 3 项通过真实启动本机 HTTP 服务验证中文界面、搜索零结果、CSV/ZIP 导出和访问限制。界面未做浏览器视觉自动化测试；Windows/macOS 启动脚本已提供，但未在这两个系统实机执行。测试环境的默认沙箱禁止创建套接字，开放本机网络执行权限后 HTTP 集成测试通过；外部官方接口仍被代理拒绝。

2026-10-23（北京时间）的真实联网尝试：搜索“足球场空镜”，Pexels 缺少 `PEXELS_API_KEY`；Commons 被环境代理拒绝（`Tunnel connection failed: 403 Forbidden`）。真实搜索结果 **0 条**，真实视频下载 **0 个**。另对 Pexels API 连通性检查也得到代理 HTTP 403。`output/` 已生成空结果 CSV、HTML、运行报告与 ZIP，如实保留错误。

## 从当前任务导出到电脑

本次已在仓库内生成 `output/交付/足球视频素材助手.zip`（源码、说明、测试与本次真实报告）和 `output/交付/本次素材结果.zip`（清单和预览）。由于网络/密钥限制，素材结果包内没有视频。

如果当前任务客户端提供文件列表或工作区下载入口，在其中进入上述目录，选择 ZIP 并下载到电脑；完整项目包解压后按上面的步骤启动。当前运行环境的聊天附件专用目录不存在且不可写，因此不能提供聊天附件直接下载链接。

也可在本 GitHub 仓库点击 **Code → Download ZIP** 下载项目源码。被忽略的视频和本地 ZIP 不会包含在源码包里；**视频与素材清单请按本文开头的 Actions 步骤运行后，从 Artifacts 下载**。这样无需依赖聊天附件导出功能。

未来在你电脑上成功下载后，点击中文界面“生成导出 ZIP”→“保存 ZIP 到电脑”。也可直接找到项目的 `output/素材导出.zip`。解压后打开 `素材预览.html`，已下载视频可离线预览。
