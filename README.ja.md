# Türkçe video dublaj hattı

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · 日本語 · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md)

> __TEK_CUMLE__（何をするものかを一文で）

## AI アシスタントにインストールしてもらう

プログラミングの知識は不要です。お使いのコンピューターでコマンドを実行できる AI アシスタント（Claude Code、Codex、
Gemini CLI など）を開き、次の一文を貼り付けてください。

```text
__REPO_URL__ にある動画吹き替えプログラムをこのコンピューターにインストールしてください。そのリポジトリの AGENTS.md ファイルに一歩ずつ従い、ハードウェアは自分で検出し、私に技術的な質問をしないでください。`dubla kontrol` が READY と表示し、サンプルの吹き替えが動いたら、プログラムのウィンドウを開いてください。
```

アシスタントはコンピューターを調べ、グラフィックカード（GPU）か CPU のみの構成かを自分で選び、質問は一つだけです：
音声モデルの利用規約に同意するかどうか。その後プログラムのウィンドウが開きます。最初の手順、平易な説明、よくある問題（英語）：
**[docs/getting-started.md](docs/getting-started.md)**。

**ライセンス概要：** コードは Apache-2.0。__LISANS_KUTUSU__（コードと異なるモデル／データのライセンス。すべて Apache 互換なら「なし」）

## クイックインストール

Windows 10/11 x64。Python、CUDA、ffmpeg の事前インストールは不要です。**`kur.cmd`** をダブルクリック（または
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1` を実行）すると、GPU か CPU のプロファイルを自動で選びます
（`-Cpu` で CPU を強制）。その後 `arayuz.cmd` をダブルクリックしてアプリを開きます。
すべてリポジトリのフォルダー内に入ります（`.venv`、`runtime_assets/`）。ダウンロードはすべて固定版で sha256 検証済みです。
ディスク：GPU プロファイルで約 22 GB、CPU のみで約 13 GB。確認：`.venv\Scripts\dubla.exe kontrol`。

要件、手順の順序、Python 環境の一覧、オプションのエンジン、オフライン利用、更新、アンインストール、よくあるエラー（英語）：
**[docs/installation.md](docs/installation.md)**。Linux と macOS はまだテストされていません。

## 使い方

__KULLANIM__（コマンド例を一つ＋出力ファイルの説明）

## 仕組み

__NASIL__（パイプラインを 4–6 項目で。外部モデルはすべてライセンスとともに明記）

## 計測結果

__OLCUM_TABLOSU__（基準マシンで計測、方法は docs/olcumler.md。他所の数値を転記しない）

## 制限

__SINIRLAR__（計測していないもの、実験的なもの、試していないハードウェア）

## 構成要素

各段階はコマンドラインまたは Python から単独で動き、段階間のファイル形式は文書化されています
（段階マップと JSON スキーマ：[docs/mimari.md](docs/mimari.md)）。

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` で同じ段階を関数として使えます。必要な段階だけをインストールしてください。例：字幕なら
`pip install -e ".[stt,hizalama,cpu]"`。これらの部品で作った小さなツール 5 つ：[examples/](examples/)。

## 関連プロジェクト

| リポジトリ | 内容 | このリポジトリでの使い方 |
|---|---|---|
| **turkce-video-dublaj-hatti**（このリポジトリ） | エンドツーエンドのローカル動画吹き替えパイプライン。各段階を単独でも利用可能 | - |
| [crisperwhisper-turkce-kelime-zamani](__STT_REPO_URL__) | 単語タイムスタンプ付きの逐語的な音声文字起こし（CrisperWhisper 2.0 Turbo + CTC アライメント） | オプションのエンジン 13：`scripts/kur.ps1 -Adim crisper` がそのリポジトリ経由で固定コミットのモデルをインストール（重みは**非商用のみ**） |
| [voxcpm2-turkce-ses-tasarimi](__TTS_REPO_URL__) | VoxCPM2 による音声デザインと読み上げ、8 言語、既製の音声 | オプションの TTS エンジン `voxcpm2`：`scripts/kur.ps1 -Adim voxcpm2` が固定コミットでインストール。このリポジトリは薄いアダプター経由で呼び出す |

兄弟リポジトリはそれぞれ独自のライセンス、インストール方法、課題管理を持ちます。固定コミットにより組み合わせを再現できます。

## 責任ある利用

> **法的免責。** 本ソフトウェアで処理・公開するコンテンツ、およびお住まいの地域の法律と利用するサイトやサービスの規約の遵守は、
> すべて利用者の責任です。本ソフトウェアは「現状のまま」無保証で提供されます（Apache-2.0）。全文と拘束力のある英語版：[ETHICS.md](ETHICS.md)。

- **権利と同意。** 自分が所有するか、翻訳と再吹き替えの許可を得た素材だけを処理し、映っている識別可能な人物の同意を得てください。
- **音声。** なりすまし禁止。参照音声は自分自身の声か、所有者が明示的に同意した声に限ります。
- **表示。** 出力には `AI-dubbed` メタデータタグが付きます。削除せず、視聴者にも AI 吹き替えであることを明示してください
  （EU AI 法第 50 条、Supertonic ライセンス）。
- **ダウンロード。** オプションの `youtube`（yt-dlp）と `galeri`（gallery-dl）拡張は、所有しているかダウンロードが許可されたコンテンツ用です。
  サイトの規約と地域の法律が適用されます。
- **非商用エンジン。** CrisperWhisper 2.0 と XTTS-v2 は非商用利用のみです（既定ではオフ）。有償または顧客向けの作業の前に
  [THIRD_PARTY.md](THIRD_PARTY.md) の **Commercial?** 列を確認してください。

## ライセンスとクレジット

コード：Apache-2.0（LICENSE）。サードパーティーのコンポーネントとライセンス：THIRD_PARTY.md。責任ある利用：ETHICS.md。
プライバシー（何がローカルに残り、クラウドのバックエンドが何を受け取るか）：PRIVACY.md。セキュリティ報告：SECURITY.md。変更履歴：CHANGELOG.md。

---

> This translation may lag; English is authoritative. この翻訳は遅れている場合があります。英語版が正本です。出典：README.md（同期マーカーは下記）。
> 機械翻訳（Claude）です。修正の PR を歓迎します。

<!-- i18n-source: README.md sha256:bf85d79d8132 -->
