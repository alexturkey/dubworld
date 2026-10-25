# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · 한국어 · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md)

> DubWorld는 영상을 어떤 서비스에도 올리지 않고 내 컴퓨터에서 다른 언어로 더빙합니다. 말소리를 단어별 타이밍과 함께 글로 옮기고, 번역하고, 원본 영상과 박자를 맞춘 합성 음성으로 읽힙니다(말소리는 최대 1.25배까지만 빨라지고, 남는 차이는 화면 속도를 살짝 조정해 메웁니다). 마지막으로 자막을 붙여 새 영상을 만들어 줍니다. 기본 언어는 튀르키예어이며, 한국어와 다른 언어는 선택한 음성 엔진에 따라 지원됩니다([docs/diller.md](docs/diller.md)).

## AI 어시스턴트에게 설치를 맡기세요

프로그래밍을 몰라도 됩니다. 내 컴퓨터에서 명령을 실행할 수 있는 AI 어시스턴트(Claude Code, Codex, Gemini CLI
등)를 열고 아래 문장 하나를 붙여 넣으세요.

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

어시스턴트가 컴퓨터 사양(그래픽카드, 프로세서, 메모리, 디스크)을 확인한 뒤, 어떤 설치를 원하는지 쉬운 말로 딱 한 번
물어봅니다: 빠른 설치, 내 컴퓨터에 맞춘 추천 설치, 전체 설치. 구성 요소마다 무엇을 하는지, 디스크를 얼마나 쓰는지,
시간이 얼마나 걸리는지, 라이선스가 무엇인지 설명하고, 고른 구성 요소의 이용 약관에 동의하는지 기본 음성부터 차례로
묻습니다. 그다음 설치하고, 샘플 더빙을 만들고, 프로그램 창을 열어 줍니다. 처음 시작하는 방법과 자주 겪는 문제(영어):
**[docs/getting-started.md](docs/getting-started.md)**.

**라이선스 요약:** 코드는 Apache-2.0. 기본 모델: Supertonic 3 음성은 OpenRAIL-M(사용 제한, 한 번 동의); Opus-MT와 튀르키예어 단어 타이밍 모델은 CC BY 4.0(출처 표시, NOTICE); FFmpeg 빌드는 GPL-3.0(별도 프로그램). 비상업적 용도만 가능하며 기본으로 꺼져 있는 것: CrisperWhisper 2.0, XTTS-v2, fr / de / es / it용 WhisperX 단어 타이밍 모델. 이 저장소에는 모델 가중치가 하나도 들어 있지 않습니다([THIRD_PARTY.md](THIRD_PARTY.md)).

## 빠른 설치

Windows 10/11 x64. Python, CUDA, ffmpeg를 미리 설치할 필요가 없습니다. **`kur.cmd`**를 더블클릭하세요(또는
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1` 실행). GPU 프로필과 CPU 프로필 중 맞는 것을 알아서
고릅니다(`-Cpu`를 붙이면 CPU 강제). 설치가 끝나면 `arayuz.cmd`를 더블클릭해 앱을 엽니다.
모든 파일은 저장소 폴더 안(`.venv`, `runtime_assets/`)에 들어가고, 모든 다운로드는 버전이 고정되어 있으며
sha256으로 검증됩니다. 시작에 필요한 여유 공간: GPU 프로필 22 GB, CPU 전용 14 GB. 설치 후 실측 사용량 ≈ 14.6 GB(GPU, 하드 링크 파일은 한 번만 계산; 파일 탐색기에는 ≈ 22 GB로 보임). 확인 명령: `.venv\Scripts\dubla.exe kontrol`.

요구 사항, 설치 단계 순서, Python 환경 구성도, 선택 엔진, 오프라인 사용, 업데이트, 제거, 자주 나는 오류(영어):
**[docs/installation.md](docs/installation.md)**. Linux와 macOS는 아직 저희가 직접 테스트하지 않았습니다. 사용 예: [Apple M4 Mac에서 CPU만으로 영어·튀르키예어·아랍어 내레이션을 입힌 제품 소개 영상](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## 사용법

데스크톱 앱: `arayuz.cmd` 더블클릭(로컬 웹 앱: `web.cmd`, 127.0.0.1에서만 열림). 앱 화면은 현재 튀르키예어로만 되어 있습니다. 명령줄에서는 이렇게 씁니다.

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

한국어로 더빙하려면 `--ayar genel.hedef_dil=ko`를 쓰세요(한국어 번역에는 Codex나 Claude Code가 필요합니다). 결과는 `cikti/<video>_<time>/`에 저장됩니다: `dubbed_tr.mp4`(`AI-dubbed` 태그 포함), 원본 자막 `transcript_<lang>.srt`, 작업 JSON 파일들. 마지막 줄 `dubbed_video:`가 경로를 알려 줍니다. 전체 설정(영어·튀르키예어): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## 동작 방식

1. **오디오:** FFmpeg가 소리를 추출하고, 선택 사항인 Demucs(MIT)가 말소리와 배경음을 분리합니다.
2. **음성 인식:** faster-whisper large-v3-turbo(MIT)와 wav2vec2 CTC 단어 타이밍(영어 MIT, 튀르키예어 CC BY 4.0). 선택적으로 CrisperWhisper 2.0(비상업)과 다른 엔진도 쓸 수 있습니다.
3. **화자:** 3D-Speaker CAM++(Apache-2.0)와 성별 분류기(Apache-2.0)가 화자마다 합성 음성을 골라 줍니다.
4. **번역:** Codex CLI나 Claude Code CLI가 설치되어 로그인되어 있으면 그것을, 없으면 로컬 Opus-MT로 영어→튀르키예어(CC BY 4.0)를 씁니다. API 백엔드는 선택 사항입니다.
5. **음성과 타이밍:** 기본은 Supertonic 3(OpenRAIL-M), 선택으로 VoxCPM2(Apache-2.0) 또는 XTTS-v2(비상업). 문장마다 원본 구간 길이에 맞춰 최대 1.25배까지 빨라지고 나머지는 영상 속도로 맞추므로, 더빙이 원본보다 길어질 수 있습니다.
6. **영상:** FFmpeg가 새 오디오, SRT / VTT / ASS 자막, `AI-dubbed` 태그를 기록합니다.

## 측정값

기준 컴퓨터: 4 GB Pascal GPU, Windows 10. 측정 방법과 전체 표는 [docs/olcumler.md](docs/olcumler.md).

| 항목 | CPU 프로필 | GPU 프로필 |
|---|---|---|
| 첫 설치, 기본 단계, 처음부터 끝까지 | ≈ 38분 | ≈ 44분(패키지 13.7분) |
| 설치 후 디스크 | ≈ 13.2 GB(폴더 합계) | ≈ 14.6 GB(하드 링크 한 번만 계산) |
| 9초 샘플 더빙, 오프라인 번역 | 528초 | 376초 |
| 30초 영어 클립, Demucs, Claude Code 번역 | – | 744초 |

## 한계

- CrisperWhisper(선택 엔진 13)가 없으면 faster-whisper가 중국어·일본어에서 말을 건너뛰거나 없는 말을 지어낼 수 있습니다(실제 사례: 중국어 클립 앞부분 ≈ 10초 누락, 고함이 긴 "ああ…" 줄로 바뀜).
- CI는 CPU만 테스트합니다. GPU 경로는 4 GB Pascal 카드 한 장에서 직접 돌려 봤습니다. 최신 카드(RTX 50), Linux, macOS는 시험하지 않았습니다. 설치되는 GPU 라이브러리는 Pascal부터 RTX 50까지 커널을 포함하며, Maxwell은 CPU 프로필을 씁니다([GPU 지원표, 영어](docs/installation.md#1-system-requirements)).
- 오프라인 번역기는 영어→튀르키예어만 지원합니다. 다른 언어 조합에는 Codex / Claude Code CLI나 API 백엔드가 필요합니다.
- 영어·튀르키예어가 아닌 원본 음성의 단어 타이밍: 일본어와 중국어는 `scripts/kur.ps1 -Adim hizalama-diller`로, 나머지는 `DUBLAJ_CEVRIMICI=1`로 한 번 실행한 뒤 사용할 수 있습니다.
- 아직 처음부터 끝까지 시험하지 않은 것: XTTS-v2 실제 설치, RVC, 실제 서비스와 연결한 Telegram 봇, CrisperWhisper 2 Medium. Moonshine은 실험 단계입니다. CrisperWhisper 2.0 Turbo(엔진 13)는 GTX 1050 Ti 4 GB에서 실제 음성으로 테스트했습니다(tr, en, ja; VRAM ≈ 1.4 GB).

## 구성 요소

각 단계는 명령줄이나 Python에서 따로 쓸 수 있고, 단계 사이의 파일 형식도 문서로 정리되어 있습니다
(단계 구성도와 JSON Schema: [docs/mimari.md](docs/mimari.md)).

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api`로 같은 단계를 함수로 쓸 수 있습니다. 필요한 단계에 맞는 것만 설치하세요. 예를 들어 자막만
만들려면 `pip install -e ".[stt,hizalama,cpu]"`. 이 구성 요소로 만든 작은 도구 다섯 개: [examples/](examples/).

## 패밀리 / 관련 프로젝트

| 저장소 | 무엇인가 | 이 저장소에서 쓰는 방법 |
|---|---|---|
| **DubWorld**(이 저장소) | 로컬에서 도는 영상 더빙 파이프라인, 단계별 단독 사용 가능 | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | 단어별 타이밍이 있는 축어 음성 인식(CrisperWhisper 2.0 Turbo + CTC 정렬) | 선택 엔진 13: `scripts/kur.ps1 -Adim crisper`가 그 저장소를 통해 고정 commit으로 모델을 설치(가중치 **비상업**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | VoxCPM2 음성 디자인과 낭독, 8개 언어, 준비된 음성 | 선택 음성 엔진 `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2`가 고정 commit으로 설치, 이 저장소는 얇은 어댑터로 호출 |

형제 저장소마다 라이선스, 설치, 이슈는 따로 관리되며, 고정 commit 덕분에 같은 조합을 언제든 다시 만들 수 있습니다.

## 책임 있는 사용

> **법적 고지.** 이 소프트웨어로 처리하고 공개하는 콘텐츠, 그리고 거주 국가의 법률과 이용하는 사이트·서비스의 약관을
> 지키는 책임은 전적으로 사용자에게 있습니다. 소프트웨어는 "있는 그대로" 제공되며 어떠한 보증도 없습니다
> (Apache-2.0). 전문: [ETHICS.md](ETHICS.md).

- **권리와 동의.** 직접 소유했거나 번역·재더빙 허락을 받은 자료만 처리하고, 영상 속 식별 가능한 인물의
  동의를 받으세요.
- **목소리.** 다른 사람 흉내는 금지입니다. 참조 음성은 본인 목소리이거나 주인이 명시적으로 동의한 목소리만 쓸 수 있습니다.
- **표시하기.** 결과물에는 `AI-dubbed` 메타데이터 태그가 들어갑니다. 지우지 말고, 시청자에게도 AI 더빙임을
  눈에 보이게 알리세요(EU AI Act 제50조, Supertonic 라이선스).
- **다운로드.** 선택 기능 `youtube`(yt-dlp)와 `galeri`(gallery-dl)는 본인 소유이거나 내려받을 권리가 있는 콘텐츠용입니다. 사이트 약관과
  현지 법률이 적용됩니다.
- **비상업 엔진.** CrisperWhisper 2.0과 XTTS-v2는 비상업적 용도만 가능합니다(기본으로 꺼져 있음). 유료 작업이나 고객 작업 전에는
  [THIRD_PARTY.md](THIRD_PARTY.md)의 **Commercial?** 열을 꼭 확인하세요.
  fr / de / es / it 원본 음성용 단어 타이밍 모델(CC BY-NC 4.0)도 비상업용이며, 처음 쓸 때 동의를 묻습니다.

## 도움말과 지원

질문, 아이디어, 사용 결과 공유: [토론 게시판](https://github.com/alexturkey/dubworld/discussions). 설치 문제: [설치 문제 신고](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml), 버그: [버그 신고](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(운영체제, GPU, 실행한 명령, 출력 마지막 몇 줄을 적어 주세요). 보안 문제는 공개 이슈가 아니라 SECURITY.md 안내를 따라 주세요.

## 라이선스와 크레딧

코드: Apache-2.0(LICENSE). 외부 구성 요소와 라이선스: THIRD_PARTY.md. 책임 있는 사용: ETHICS.md.
개인정보(내 컴퓨터에 남는 것, 클라우드 백엔드로 가는 것): PRIVACY.md. 보안 신고: SECURITY.md. 변경 이력: CHANGELOG.md.

<!-- i18n-source: README.md sha256:48bbf9594411 -->
