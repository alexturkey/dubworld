# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · Tiếng Việt · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md)

> DubWorld lồng tiếng video của bạn sang ngôn ngữ khác ngay trên máy tính của bạn, không cần tải lên bất kỳ dịch vụ trực tuyến nào: chuyển lời nói thành văn bản kèm thời điểm của từng từ, dịch, rồi cho một giọng đọc nhân tạo (AI) đọc lại sao cho khớp với video gốc (lời nói được đọc nhanh hơn tối đa 1,25 lần, phần chênh lệch còn lại được bù bằng cách điều chỉnh nhẹ tốc độ video), thêm phụ đề và xuất ra một video mới. Ngôn ngữ mặc định là tiếng Thổ Nhĩ Kỳ; tiếng Việt và các ngôn ngữ khác phụ thuộc vào công cụ giọng nói được chọn ([docs/diller.md](docs/diller.md)).

## Nhờ trợ lý AI cài đặt giúp bạn

Bạn không cần biết lập trình. Hãy mở một trợ lý AI có thể chạy lệnh trên máy bạn (Claude Code, Codex,
Gemini CLI hoặc công cụ tương tự) và dán câu sau:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

Trợ lý sẽ kiểm tra máy của bạn (card đồ họa, bộ xử lý, bộ nhớ, ổ đĩa) và chỉ hỏi một lần, bằng lời dễ hiểu, bạn muốn
cài theo kiểu nào: nhanh, theo gợi ý phù hợp với máy bạn, hay đầy đủ. Trợ lý giải thích từng thành phần (làm gì, chiếm bao
nhiêu dung lượng, cài mất bao lâu, giấy phép ra sao) và, bắt đầu từ giọng mặc định, hỏi bạn có đồng ý với điều khoản sử dụng
của các thành phần đã chọn không. Sau đó trợ lý cài đặt, tạo một bản lồng tiếng mẫu và mở cửa sổ chương trình.
Những bước đầu tiên và các lỗi thường gặp, giải thích dễ hiểu (bằng tiếng Anh): **[docs/getting-started.md](docs/getting-started.md)**.

**Tóm tắt giấy phép:** mã nguồn Apache-2.0. Mô hình mặc định: giọng Supertonic 3 theo OpenRAIL-M (có giới hạn sử dụng, đồng ý một lần); Opus-MT và mô hình thời điểm từ tiếng Thổ Nhĩ Kỳ theo CC BY 4.0 (bắt buộc ghi công, NOTICE); bản build FFmpeg GPL-3.0 (chương trình riêng). Chỉ dùng phi thương mại và tắt theo mặc định: CrisperWhisper 2.0, XTTS-v2 và các mô hình thời điểm từ WhisperX cho fr / de / es / it. Kho mã này không chứa trọng số mô hình nào ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Cài đặt nhanh

Windows 10/11 x64; không cần cài sẵn Python, CUDA hay ffmpeg. Nhấp đúp **`kur.cmd`** (hoặc chạy
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); chương trình tự chọn cấu hình GPU hoặc CPU
(`-Cpu` buộc dùng CPU). Sau đó nhấp đúp `arayuz.cmd` để mở ứng dụng.
Mọi thứ đều nằm trong thư mục kho mã (`.venv`, `runtime_assets/`); mỗi tệp tải về đều được cố định phiên bản và
kiểm tra bằng sha256. Dung lượng trống cần để bắt đầu: 22 GB với cấu hình GPU, 14 GB nếu chỉ dùng CPU; dung lượng đo được sau khi cài ≈ 14,6 GB (GPU, tệp hard link chỉ tính một lần; File Explorer hiển thị ≈ 22 GB). Kiểm tra: `.venv\Scripts\dubla.exe kontrol`.

Yêu cầu hệ thống, thứ tự các bước, sơ đồ môi trường Python, công cụ tùy chọn, dùng ngoại tuyến, cập nhật, gỡ cài đặt và
lỗi thường gặp (bằng tiếng Anh): **[docs/installation.md](docs/installation.md)**. Chúng tôi chưa thử trên Linux và macOS. Ví dụ: [video giới thiệu sản phẩm được lồng tiếng Anh, Thổ Nhĩ Kỳ và Ả Rập trên Mac Apple M4, chỉ dùng CPU](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Cách sử dụng

Ứng dụng máy tính: nhấp đúp `arayuz.cmd` (ứng dụng web cục bộ: `web.cmd`, chỉ trên 127.0.0.1). Giao diện ứng dụng hiện bằng tiếng Thổ Nhĩ Kỳ. Từ dòng lệnh:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Để lồng tiếng sang tiếng Việt, dùng `--ayar genel.hedef_dil=vi` (dịch sang tiếng Việt cần Codex hoặc Claude Code). Kết quả nằm trong `cikti/<video>_<time>/`: `dubbed_tr.mp4` (có thẻ `AI-dubbed`), phụ đề gốc `transcript_<lang>.srt` và các tệp JSON trung gian; dòng cuối `dubbed_video:` cho biết đường dẫn. Tất cả cài đặt (bằng tiếng Anh và tiếng Thổ Nhĩ Kỳ): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Cách hoạt động

1. **Âm thanh:** FFmpeg tách phần tiếng; Demucs (MIT) tùy chọn tách lời nói khỏi âm nền.
2. **Lời nói thành văn bản:** faster-whisper large-v3-turbo (MIT) với thời điểm từ wav2vec2 CTC (tiếng Anh MIT, tiếng Thổ Nhĩ Kỳ CC BY 4.0); CrisperWhisper 2.0 tùy chọn (phi thương mại) và các công cụ khác.
3. **Người nói:** 3D-Speaker CAM++ (Apache-2.0) và một mô hình nhận diện giới tính (Apache-2.0) chọn một giọng AI cho mỗi người nói.
4. **Dịch:** Codex CLI hoặc Claude Code CLI nếu đã cài và đăng nhập, nếu không thì Opus-MT cục bộ Anh sang Thổ Nhĩ Kỳ (CC BY 4.0); các backend API là tùy chọn.
5. **Giọng và thời gian:** mặc định Supertonic 3 (OpenRAIL-M), tùy chọn VoxCPM2 (Apache-2.0) hoặc XTTS-v2 (phi thương mại); mỗi câu được đọc nhanh hơn tối đa 1,25 lần để khớp thời lượng đoạn gốc, phần còn lại được bù bằng thời gian video, nên bản lồng tiếng có thể dài hơn bản gốc.
6. **Video:** FFmpeg ghi giọng mới, phụ đề SRT / VTT / ASS và thẻ `AI-dubbed`.

## Số đo

Máy tham chiếu: GPU Pascal 4 GB, Windows 10; phương pháp và tất cả các dòng trong [docs/olcumler.md](docs/olcumler.md).

| Nội dung | Cấu hình CPU | Cấu hình GPU |
|---|---|---|
| Cài đặt lần đầu, các bước mặc định, từ đầu đến cuối | ≈ 38 phút | ≈ 44 phút (gói 13,7 phút) |
| Dung lượng sau khi cài | ≈ 13,2 GB (tổng thư mục) | ≈ 14,6 GB (hard link tính một lần) |
| Lồng tiếng mẫu 9 giây, dịch ngoại tuyến | 528 giây | 376 giây |
| Đoạn tiếng Anh 30 giây, Demucs, dịch bằng Claude Code | – | 744 giây |

## Giới hạn

- Không có CrisperWhisper (công cụ tùy chọn 13), faster-whisper có thể bỏ sót lời nói hoặc bịa ra văn bản không ai nói trong tiếng Trung và tiếng Nhật (đã thấy: ≈ 10 giây đầu của một đoạn tiếng Trung bị mất; một tiếng hét thành một dòng "ああ…" dài).
- CI chỉ kiểm thử CPU; đường GPU được chạy thủ công trên card Pascal 4 GB. Card mới (RTX 50), Linux và macOS chưa được thử; thư viện GPU được cài có kernel từ Pascal đến RTX 50, còn Maxwell dùng cấu hình CPU ([bảng hỗ trợ GPU, bằng tiếng Anh](docs/installation.md#1-system-requirements)).
- Trình dịch ngoại tuyến chỉ dịch Anh sang Thổ Nhĩ Kỳ; các cặp ngôn ngữ khác cần Codex / Claude Code CLI hoặc backend API.
- Thời điểm từ cho ngôn ngữ nguồn ngoài tiếng Anh và tiếng Thổ Nhĩ Kỳ: tiếng Nhật và tiếng Trung qua `scripts/kur.ps1 -Adim hizalama-diller`, các ngôn ngữ khác sau một lần chạy với `DUBLAJ_CEVRIMICI=1`.
- Chưa thử từ đầu đến cuối: cài XTTS-v2 thật, RVC, bot Telegram nối với dịch vụ thật và CrisperWhisper 2 Medium; Moonshine vẫn đang thử nghiệm. CrisperWhisper 2.0 Turbo (công cụ 13) đã được thử với âm thanh thật trên GTX 1050 Ti 4 GB (tr, en, ja; ≈ 1,4 GB VRAM).

## Các khối xây dựng

Mỗi bước đều chạy được riêng, từ dòng lệnh hoặc từ Python, và định dạng tệp giữa các bước đều có tài liệu
(sơ đồ các bước và JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` cung cấp các bước này dưới dạng hàm. Chỉ cài những gì một bước cần, ví dụ
`pip install -e ".[stt,hizalama,cpu]"` để làm phụ đề. Năm công cụ nhỏ được ghép từ các khối này: [examples/](examples/).

## Gia đình / dự án liên quan

| Kho mã | Là gì | Kho mã này dùng nó thế nào |
|---|---|---|
| **DubWorld** (kho mã này) | Quy trình lồng tiếng video hoàn toàn cục bộ, từng bước cũng dùng riêng được | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | Chuyển lời nói thành văn bản từng chữ, kèm thời điểm từ (CrisperWhisper 2.0 Turbo + căn chỉnh CTC) | Công cụ tùy chọn 13: `scripts/kur.ps1 -Adim crisper` cài mô hình qua kho mã đó ở commit cố định (trọng số **phi thương mại**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | Thiết kế giọng và đọc văn bản với VoxCPM2, 8 ngôn ngữ, giọng có sẵn | Công cụ giọng tùy chọn `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` cài ở commit cố định; kho mã này gọi nó qua một bộ chuyển đổi mỏng |

Mỗi kho mã đi kèm có giấy phép, cách cài và issue riêng; nhờ commit cố định, bộ ghép này có thể dựng lại với kết quả y hệt.

## Sử dụng có trách nhiệm

> **Thông báo pháp lý.** Bạn hoàn toàn chịu trách nhiệm về nội dung bạn xử lý và công bố bằng phần mềm này, cũng như việc
> tuân thủ pháp luật nước bạn và điều khoản của các trang web, dịch vụ bạn sử dụng. Phần mềm được cung cấp "nguyên trạng",
> không kèm bất kỳ bảo đảm nào (Apache-2.0). Toàn văn: [ETHICS.md](ETHICS.md).

- **Quyền và sự đồng ý.** Chỉ xử lý nội dung của bạn hoặc nội dung bạn có quyền dịch và lồng tiếng lại,
  và hãy xin phép những người có thể nhận ra được trong đó.
- **Giọng nói.** Không mạo danh bất kỳ ai. Giọng tham chiếu chỉ được là giọng của bạn hoặc của người đã đồng ý rõ ràng.
- **Gắn nhãn.** Kết quả có thẻ siêu dữ liệu `AI-dubbed`; hãy giữ nguyên, và cho khán giả biết một cách dễ thấy
  rằng phần lồng tiếng được làm bằng AI (Điều 50 Đạo luật AI của EU; giấy phép Supertonic).
- **Tải xuống.** Phần bổ sung tùy chọn `youtube` (yt-dlp) và `galeri` (gallery-dl) chỉ dành cho nội dung của bạn hoặc nội dung bạn được phép tải; điều khoản của trang và
  luật địa phương vẫn áp dụng.
- **Công cụ phi thương mại.** CrisperWhisper 2.0 và XTTS-v2 chỉ dùng phi thương mại (tắt theo mặc định). Trước mọi công việc có trả phí hoặc cho khách hàng,
  hãy xem cột **Commercial?** trong [THIRD_PARTY.md](THIRD_PARTY.md).
  Các mô hình thời điểm từ cho âm thanh nguồn fr / de / es / it (CC BY-NC 4.0) cũng là phi thương mại và sẽ hỏi bạn đồng ý ở lần dùng đầu.

## Trợ giúp và hỗ trợ

Câu hỏi, ý tưởng và kết quả của bạn: [diễn đàn thảo luận](https://github.com/alexturkey/dubworld/discussions). Lỗi cài đặt: [báo lỗi cài đặt](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); lỗi chương trình: [gửi báo cáo lỗi](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(ghi hệ điều hành, GPU, lệnh đã chạy và vài dòng cuối của kết quả). Vấn đề bảo mật: xem SECURITY.md, đừng viết trong issue công khai.

## Giấy phép và ghi công

Mã nguồn: Apache-2.0 (LICENSE). Thành phần bên thứ ba và giấy phép: THIRD_PARTY.md. Sử dụng có trách nhiệm: ETHICS.md.
Quyền riêng tư (thứ gì ở lại trên máy bạn, backend đám mây nhận được gì): PRIVACY.md. Báo cáo bảo mật: SECURITY.md. Thay đổi: CHANGELOG.md.

<!-- i18n-source: README.md sha256:9622edb95c84 -->
