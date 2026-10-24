# Türkçe video dublaj hattı

[English](README.md) · [Türkçe](README.tr.md) · 简体中文 · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md)

> __TEK_CUMLE__（一句话说明它的用途）

## 让 AI 助手替你安装

无需编程。打开一个能在你电脑上执行命令的 AI 助手（Claude Code、Codex、Gemini CLI 或类似工具），粘贴下面这一句话：

```text
请把 __REPO_URL__ 上的视频配音程序安装到这台电脑上。逐步按照该仓库中的 AGENTS.md 文件操作，自行检测我的硬件，不要问我技术问题。当 `dubla kontrol` 显示 READY 且示例配音成功后，为我打开程序窗口。
```

助手会检查你的电脑，自行选择显卡（GPU）或仅处理器（CPU）的安装方式，并只问你一个问题：是否接受语音模型的使用条款。
随后程序窗口会打开。入门步骤、通俗说明和常见问题（英文）：**[docs/getting-started.md](docs/getting-started.md)**。

**许可证概览：** 代码为 Apache-2.0。__LISANS_KUTUSU__（与代码不同的模型/数据许可证；若全部兼容 Apache 则写"无"）

## 快速安装

Windows 10/11 x64；事先无需安装 Python、CUDA 或 ffmpeg。双击 **`kur.cmd`**（或运行
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`）；它会自行选择 GPU 或 CPU 配置
（`-Cpu` 强制使用 CPU）。然后双击 `arayuz.cmd` 打开程序。
所有内容都安装在仓库文件夹内（`.venv`、`runtime_assets/`）；每个下载都固定版本并经过 sha256 校验。磁盘：GPU 配置约
22 GB，仅 CPU 约 13 GB。检查：`.venv\Scripts\dubla.exe kontrol`。

系统要求、步骤顺序、Python 环境图、可选引擎、离线使用、更新、卸载和常见错误（英文）：
**[docs/installation.md](docs/installation.md)**。Linux 和 macOS 尚未测试。

## 用法

__KULLANIM__（一条示例命令 + 输出文件说明）

## 工作原理

__NASIL__（用 4–6 个要点描述流水线；写明每个外部模型及其许可证）

## 测量结果

__OLCUM_TABLOSU__（在参考机器上测量，方法见 docs/olcumler.md；不得从别处抄数字）

## 局限

__SINIRLAR__（哪些未测量、哪些是实验性的、哪些硬件未试过）

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
| **turkce-video-dublaj-hatti**（本仓库） | 端到端本地视频配音流水线，每个阶段都可单独使用 | - |
| [crisperwhisper-turkce-kelime-zamani](__STT_REPO_URL__) | 带词级时间戳的逐字语音转文字（CrisperWhisper 2.0 Turbo + CTC 对齐） | 可选引擎 13：`scripts/kur.ps1 -Adim crisper` 通过该仓库在固定 commit 安装模型（权重**仅限非商业**） |
| [voxcpm2-turkce-ses-tasarimi](__TTS_REPO_URL__) | VoxCPM2 声音设计与朗读，8 种语言，现成声音 | 可选 TTS 引擎 `voxcpm2`：`scripts/kur.ps1 -Adim voxcpm2` 在固定 commit 安装；本仓库通过一个薄适配器调用它 |

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

## 许可证与致谢

代码：Apache-2.0（LICENSE）。第三方组件及其许可证：THIRD_PARTY.md。负责任地使用：ETHICS.md。
隐私（哪些留在本地，云端后端会收到什么）：PRIVACY.md。安全报告：SECURITY.md。变更：CHANGELOG.md。

---

> This translation may lag; English is authoritative. 本译文可能滞后，以英文版为准。来源：README.md（同步标记见下）；
> 机器翻译（Claude），欢迎提交更正 PR。

<!-- i18n-source: README.md sha256:bf85d79d8132 -->
