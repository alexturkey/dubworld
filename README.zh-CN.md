# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · 简体中文 · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md)

> DubWorld 在你自己的电脑上把视频配音成另一种语言：带词级时间戳的语音转文字、翻译、与原视频同步的合成语音（语音最多加速 1.25 倍，其余由画面重新调整时长）、字幕和新视频。默认目标语言为土耳其语；其他语言取决于语音引擎（[docs/diller.md](docs/diller.md)）。

## 让 AI 助手替你安装

无需编程。打开一个能在你电脑上执行命令的 AI 助手（Claude Code、Codex、Gemini CLI 或类似工具），粘贴下面这一句话：

```text
请把 https://github.com/alexturkey/DubWorld 上的视频配音程序安装到这台电脑上。逐步按照该仓库中的 AGENTS.md 文件操作，自行检测我的硬件，不要问我技术问题。当 `dubla kontrol` 显示 READY 且示例配音成功后，为我打开程序窗口。
```

助手会测量你的电脑（显卡、处理器、内存、磁盘），并用通俗的话只问一次你想要哪种安装：快速、适合你电脑的推荐安装，或完整安装。
它会说明每个部分（作用、占用的磁盘和时间、许可证），并询问你是否接受所选部分的使用条款，首先是默认语音的条款。随后它完成安装、制作一个示例配音并打开程序窗口。入门步骤、通俗说明和常见问题（英文）：**[docs/getting-started.md](docs/getting-started.md)**。

**许可证概览：** 代码为 Apache-2.0。默认模型：Supertonic 3 声音采用 OpenRAIL-M（有使用限制，只需同意一次）；Opus-MT 和土耳其语词级时间模型采用 CC BY 4.0（需署名，见 NOTICE）；FFmpeg 构建为 GPL-3.0（独立程序）。仅限非商业且默认关闭：CrisperWhisper 2.0、XTTS-v2、fr / de / es / it 的 WhisperX 词级时间模型。本仓库不包含任何模型权重（[THIRD_PARTY.md](THIRD_PARTY.md)）。

## 快速安装

Windows 10/11 x64；事先无需安装 Python、CUDA 或 ffmpeg。双击 **`kur.cmd`**（或运行
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`）；它会自行选择 GPU 或 CPU 配置
（`-Cpu` 强制使用 CPU）。然后双击 `arayuz.cmd` 打开程序。
所有内容都安装在仓库文件夹内（`.venv`、`runtime_assets/`）；每个下载都固定版本并经过 sha256 校验。开始安装所需的可用磁盘：GPU 配置
22 GB，仅 CPU 14 GB；安装后实测占用约 14.6 GB（GPU，硬链接文件只计一次；文件管理器显示约 22 GB）。检查：`.venv\Scripts\dubla.exe kontrol`。

系统要求、步骤顺序、Python 环境图、可选引擎、离线使用、更新、卸载和常见错误（英文）：
**[docs/installation.md](docs/installation.md)**。Linux 和 macOS 尚未测试。示例：[在 Apple M4 Mac 上仅用 CPU 以英语、土耳其语和阿拉伯语配音的产品导览](https://x.com/MihenkAIdotcom/status/2114345171571925363)。

## 用法

桌面应用：双击 `arayuz.cmd`（本地网页应用：`web.cmd`，仅 127.0.0.1）。程序界面目前为土耳其语。命令行：

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

结果写入 `cikti/<video>_<time>/`：`dubbed_tr.mp4`（带 `AI-dubbed` 标签）、源字幕 `transcript_<lang>.srt` 以及任务的 JSON 文件；最后一行 `dubbed_video:` 给出路径。全部设置：[docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md)。

## 工作原理

1. **音频：** FFmpeg 提取声音；可选 Demucs（MIT）把语音和背景分开。
2. **语音转文字：** faster-whisper large-v3-turbo（MIT）加 wav2vec2 CTC 词级时间（英语 MIT，土耳其语 CC BY 4.0）；可选 CrisperWhisper 2.0（非商业）及其他引擎。
3. **说话人：** 3D-Speaker CAM++（Apache-2.0）和性别分类器（Apache-2.0）为每位说话人选择合成声音。
4. **翻译：** 已安装并登录时使用 Codex CLI 或 Claude Code CLI，否则使用本地 Opus-MT 英译土（CC BY 4.0）；API 后端可选。
5. **声音与时间：** 默认 Supertonic 3（OpenRAIL-M），可选 VoxCPM2（Apache-2.0）或 XTTS-v2（非商业）；每一行最多加速 1.25 倍以接近原始片段时长，其余由视频重新调整时长，因此配音可能比原片长。
6. **视频：** FFmpeg 写入新音频、SRT / VTT / ASS 字幕和 `AI-dubbed` 标签。

## 测量结果

参考机器：4 GB Pascal GPU，Windows 10；方法和全部数据见 [docs/olcumler.md](docs/olcumler.md)。

| 项目 | CPU 配置 | GPU 配置 |
|---|---|---|
| 首次安装，默认步骤，全程 | ≈ 38 分钟 | ≈ 44 分钟（软件包 13.7 分钟） |
| 安装后磁盘占用 | ≈ 13.2 GB（文件夹合计） | ≈ 14.6 GB（硬链接只计一次） |
| 9 秒示例配音，离线翻译 | 528 秒 | 376 秒 |
| 30 秒英语片段，Demucs，Claude Code 翻译 | – | 744 秒 |

## 局限

- 未安装 CrisperWhisper（可选引擎 13）时，faster-whisper 在中文和日语上可能漏掉语音或编造内容（实际观察：一段中文片段的前 ≈ 10 秒被跳过；喊叫变成了一长串 "ああ…"）。
- CI 只测试 CPU；GPU 路径在一张 4 GB Pascal 显卡上手动运行。较新的显卡（RTX 50）、Linux 和 macOS 未测试；安装的 GPU 库包含从 Pascal 到 RTX 50 的内核，Maxwell 使用 CPU 配置（[GPU runtime matrix](docs/installation.md#1-system-requirements)）。
- 离线翻译器只支持英语到土耳其语；其他语言对需要 Codex / Claude Code CLI 或 API 后端。
- 英语和土耳其语以外源语言的词级时间：日语和中文用 `scripts/kur.ps1 -Adim hizalama-diller`，其他语言需用 `DUBLAJ_CEVRIMICI=1` 运行一次。
- 未做端到端测试：XTTS-v2 实际安装、RVC、连接真实服务的 Telegram 机器人、CrisperWhisper 2 Medium；Moonshine 为实验性。CrisperWhisper 2.0 Turbo（引擎 13）已在 GTX 1050 Ti 4 GB 上用真实音频测试（tr、en、ja；显存约 1.4 GB）。

## 构建模块

每个阶段都可以单独从命令行或 Python 运行，阶段之间使用有文档的文件格式
（阶段图和 JSON Schema：[docs/mimari.md](docs/mimari.md)）：

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` 以函数形式提供相同的阶段。只安装某个阶段需要的部分，例如字幕用
`pip install -e ".[stt,hizalama,cpu]"`。基于这些模块的五个小工具：[examples/](examples/)。

## 相关项目

| 仓库 | 内容 | 本仓库如何使用 |
|---|---|---|
| **DubWorld**（本仓库） | 端到端本地视频配音流水线，每个阶段都可单独使用 | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | 带词级时间戳的逐字语音转文字（CrisperWhisper 2.0 Turbo + CTC 对齐） | 可选引擎 13：`scripts/kur.ps1 -Adim crisper` 通过该仓库在固定 commit 安装模型（权重**仅限非商业**） |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | VoxCPM2 声音设计与朗读，8 种语言，现成声音 | 可选 TTS 引擎 `voxcpm2`：`scripts/kur.ps1 -Adim voxcpm2` 在固定 commit 安装；本仓库通过一个薄适配器调用它 |

每个兄弟仓库各自保留许可证、安装方式和问题跟踪；固定 commit 让组合可复现。

## 负责任地使用

> **法律声明。** 你使用本软件处理和发布的内容，以及遵守你所在地法律和所用网站与服务的条款，完全由你本人负责。
> 本软件按"原样"提供，不附带任何担保（Apache-2.0）。全文和具有约束力的英文版本：[ETHICS.md](ETHICS.md)。

- **权利与同意。** 只处理你拥有或已获准翻译并重新配音的素材，并取得其中可识别人物的同意。
- **声音。** 禁止冒充。参考声音只能是你自己的，或其所有者明确同意的声音。
- **标注。** 输出带有 `AI-dubbed` 元数据标签；请保留它，并向观众明确告知这是 AI 配音（欧盟《人工智能法》第 50 条；Supertonic 许可证）。
- **下载。** 可选的 `youtube`（yt-dlp）和 `galeri`（gallery-dl）扩展仅用于你拥有或有权下载的内容；网站条款和你所在地的法律适用。
- **非商业引擎。** CrisperWhisper 2.0 和 XTTS-v2 仅限非商业使用（默认关闭）。在任何付费或客户工作之前，请查看
  [THIRD_PARTY.md](THIRD_PARTY.md) 的 **Commercial?** 一栏。
  fr / de / es / it 源音频的词级时间模型（CC BY-NC 4.0）同样仅限非商业使用，首次使用时会请求同意。

## 帮助与支持

问题、想法和结果：[Discussions](https://github.com/alexturkey/dubworld/discussions)。安装问题：[安装 issue](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml)；缺陷：[缺陷报告](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
（请附上操作系统、GPU、命令及最后几行输出）。安全问题请按 SECURITY.md 报告，不要发公开 issue。

## 许可证与致谢

代码：Apache-2.0（LICENSE）。第三方组件及其许可证：THIRD_PARTY.md。负责任地使用：ETHICS.md。
隐私（哪些留在本地，云端后端会收到什么）：PRIVACY.md。安全报告：SECURITY.md。变更：CHANGELOG.md。

---

> This translation may lag; English is authoritative. 本译文可能滞后，以英文版为准。来源：README.md（同步标记见下）；
> 机器翻译（Claude），欢迎提交更正 PR。

<!-- i18n-source: README.md sha256:c7531e7aa8a8 -->
