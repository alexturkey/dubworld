# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · 日本語 · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md)

> DubWorld は自分のコンピューター上で動画を別の言語に吹き替えます。単語タイムスタンプ付きの文字起こし、翻訳、元の動画と歩調を合わせた合成音声（発話は最大 1.25 倍まで速め、残りは映像の時間を調整）、字幕、新しい動画を作ります。既定はトルコ語で、他の言語は音声エンジンによります（[docs/diller.md](docs/diller.md)）。

## AI アシスタントにインストールしてもらう

プログラミングの知識は不要です。お使いのコンピューターでコマンドを実行できる AI アシスタント（Claude Code、Codex、
Gemini CLI など）を開き、次の一文を貼り付けてください。

```text
https://github.com/alexturkey/DubWorld にある動画吹き替えプログラムをこのコンピューターにインストールしてください。そのリポジトリの AGENTS.md ファイルに一歩ずつ従い、ハードウェアは自分で検出し、私に技術的な質問をしないでください。`dubla kontrol` が READY と表示し、サンプルの吹き替えが動いたら、プログラムのウィンドウを開いてください。
```

アシスタントはコンピューター（グラフィックカード、プロセッサー、メモリー、ディスク）を測り、どんなインストールにするかを平易な言葉で一度だけ尋ねます：
クイック、このコンピューター向けの推奨、またはフル。各部分（何をするか、ディスク容量と時間、ライセンス）を説明し、選んだ部分の利用規約に同意するかどうかを、まず既定の音声から尋ねます。その後インストールし、サンプルの吹き替えを作り、プログラムのウィンドウを開きます。最初の手順、平易な説明、よくある問題（英語）：
**[docs/getting-started.md](docs/getting-started.md)**。

**ライセンス概要：** コードは Apache-2.0。既定のモデル：Supertonic 3 の音声は OpenRAIL-M（利用制限あり、同意は一度だけ）、Opus-MT とトルコ語の単語タイミングモデルは CC BY 4.0（帰属表示、NOTICE）、FFmpeg のビルドは GPL-3.0（別プログラム）。非商用のみで既定は無効：CrisperWhisper 2.0、XTTS-v2、fr / de / es / it 用の WhisperX 単語タイミングモデル。このリポジトリにモデルの重みは含まれません（[THIRD_PARTY.md](THIRD_PARTY.md)）。

## クイックインストール

Windows 10/11 x64。Python、CUDA、ffmpeg の事前インストールは不要です。**`kur.cmd`** をダブルクリック（または
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1` を実行）すると、GPU か CPU のプロファイルを自動で選びます
（`-Cpu` で CPU を強制）。その後 `arayuz.cmd` をダブルクリックしてアプリを開きます。
すべてリポジトリのフォルダー内に入ります（`.venv`、`runtime_assets/`）。ダウンロードはすべて固定版で sha256 検証済みです。
開始に必要な空きディスク：GPU プロファイルで 22 GB、CPU のみで 14 GB。インストール後の実測使用量は約 14.6 GB（GPU、ハードリンクのファイルは一度だけ数える。エクスプローラーでは約 22 GB と表示）。確認：`.venv\Scripts\dubla.exe kontrol`。

要件、手順の順序、Python 環境の一覧、オプションのエンジン、オフライン利用、更新、アンインストール、よくあるエラー（英語）：
**[docs/installation.md](docs/installation.md)**。Linux と macOS はまだテストされていません。

## 使い方

デスクトップアプリ：`arayuz.cmd` をダブルクリック（ローカル Web アプリ：`web.cmd`、127.0.0.1 のみ）。アプリの画面は今のところトルコ語です。コマンドラインから：

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

結果は `cikti/<video>_<time>/` に出力されます：`dubbed_tr.mp4`（`AI-dubbed` タグ付き）、元言語の字幕 `transcript_<lang>.srt`、ジョブの JSON ファイル。最後の行 `dubbed_video:` がパスを示します。すべての設定：[docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md)。

## 仕組み

1. **音声：** FFmpeg が音を取り出し、任意の Demucs（MIT）が話し声と背景を分離します。
2. **文字起こし：** faster-whisper large-v3-turbo（MIT）と wav2vec2 CTC による単語タイミング（英語 MIT、トルコ語 CC BY 4.0）。任意で CrisperWhisper 2.0（非商用）など他のエンジン。
3. **話者：** 3D-Speaker CAM++（Apache-2.0）と性別分類器（Apache-2.0）が話者ごとに合成音声を選びます。
4. **翻訳：** インストール済みでログインしていれば Codex CLI または Claude Code CLI、なければローカルの Opus-MT 英語→トルコ語（CC BY 4.0）。API バックエンドは任意。
5. **音声とタイミング：** 既定は Supertonic 3（OpenRAIL-M）、任意で VoxCPM2（Apache-2.0）または XTTS-v2（非商用）。各行は元のセグメントの長さに向けて最大 1.25 倍まで速め、残りは動画の時間を調整するため、吹き替えが元より長くなることがあります。
6. **動画：** FFmpeg が新しい音声、SRT / VTT / ASS 字幕、`AI-dubbed` タグを書き込みます。

## 計測結果

基準マシン：4 GB Pascal GPU、Windows 10。方法と全データは [docs/olcumler.md](docs/olcumler.md)。

| 項目 | CPU プロファイル | GPU プロファイル |
|---|---|---|
| 初回インストール、既定の手順、全体 | 約 38 分 | 約 44 分（パッケージ 13.7 分） |
| インストール後のディスク | 約 13.2 GB（フォルダー合計） | 約 14.6 GB（ハードリンクは一度だけ） |
| 9 秒のサンプル吹き替え、オフライン翻訳 | 528 秒 | 376 秒 |
| 30 秒の英語クリップ、Demucs、Claude Code 翻訳 | – | 744 秒 |

## 制限

- CrisperWhisper（任意のエンジン 13）がない場合、faster-whisper は中国語と日本語で発話を飛ばしたり内容を作り出したりすることがあります（確認例：中国語クリップの最初の約 10 秒が抜けた、叫び声が長い "ああ…" の行になった）。
- CI は CPU のみをテストします。GPU 経路は 4 GB Pascal カード 1 枚で手動実行しました。新しいカード（RTX 50）、Linux、macOS は未検証です。インストールされる GPU ライブラリは Pascal から RTX 50 までのカーネルを含み、Maxwell は CPU プロファイルを使います（[GPU runtime matrix](docs/installation.md#1-system-requirements)）。
- オフライン翻訳は英語→トルコ語のみです。他の言語の組み合わせには Codex / Claude Code CLI または API バックエンドが必要です。
- 英語とトルコ語以外の元言語の単語タイミング：日本語と中国語は `scripts/kur.ps1 -Adim hizalama-diller`、その他は `DUBLAJ_CEVRIMICI=1` で一度実行した後。
- エンドツーエンド未検証：XTTS-v2 の実インストール、RVC、実サービスに接続した Telegram ボット、CrisperWhisper エンジン。Moonshine は実験的です。

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
| **DubWorld**（このリポジトリ） | エンドツーエンドのローカル動画吹き替えパイプライン。各段階を単独でも利用可能 | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | 単語タイムスタンプ付きの逐語的な音声文字起こし（CrisperWhisper 2.0 Turbo + CTC アライメント） | オプションのエンジン 13：`scripts/kur.ps1 -Adim crisper` がそのリポジトリ経由で固定コミットのモデルをインストール（重みは**非商用のみ**） |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | VoxCPM2 による音声デザインと読み上げ、8 言語、既製の音声 | オプションの TTS エンジン `voxcpm2`：`scripts/kur.ps1 -Adim voxcpm2` が固定コミットでインストール。このリポジトリは薄いアダプター経由で呼び出す |

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
  fr / de / es / it の元音声用の単語タイミングモデル（CC BY-NC 4.0）も非商用で、初回使用時に同意を求めます。

## ヘルプとサポート

質問・アイデア・結果: [Discussions](https://github.com/alexturkey/dubworld/discussions)。インストールの問題: [インストール issue](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml)、バグ: [バグ報告](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
（OS、GPU、コマンドと最後の出力行を添えてください）。セキュリティの問題は公開 issue ではなく SECURITY.md へ。

## ライセンスとクレジット

コード：Apache-2.0（LICENSE）。サードパーティーのコンポーネントとライセンス：THIRD_PARTY.md。責任ある利用：ETHICS.md。
プライバシー（何がローカルに残り、クラウドのバックエンドが何を受け取るか）：PRIVACY.md。セキュリティ報告：SECURITY.md。変更履歴：CHANGELOG.md。

---

> This translation may lag; English is authoritative. この翻訳は遅れている場合があります。英語版が正本です。出典：README.md（同期マーカーは下記）。
> 機械翻訳（Claude）です。修正の PR を歓迎します。

<!-- i18n-source: README.md sha256:6829b755ca26 -->
