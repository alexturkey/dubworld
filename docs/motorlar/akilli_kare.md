# Smart frame (crop to content) (`akilli_kare`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Measures the top/bottom or side black/static bars of the video on 24 sample frames, finds the
content box and crops the dubbed video to that box (libx264, crf 18). Audio and subtitles do not change. If there are
no bars, the video stays as it is.

| | |
|---|---|
| License | code: OpenCV (opencv-python-headless) Apache-2.0; no weights |
| Install | `pip install .[akilli-kare]` |
| Hardware | CPU only, ~500 MB RAM (estimate) |
| Default | off |

**Setting:** `DubConfig.smart_frame_capture_enabled = true` (settings-file key once it is added to the settings layer:
`video.akilli_kare = true`). Outputs in the job folder: `video_smart_frame.mp4`, `smart_frame_analysis.json`,
`smart_frame_preview.jpg` (the chosen box framed in red).

**Common errors**
- `Akıllı kare için OpenCV kurulu değil` → the extra is not installed; the pipeline continues with the source video uncropped.
- No crop at all (`full_frame_detected`) → there are no bars, or they are very thin; this is the correct behaviour.
- If a moving logo/text is on the bar, the box can widen; check the preview JPG.

## How it works in this pipeline / Neden böyle

- **Principle:** edge bars (black or static areas) are measured on 24 sample frames, the real moving content box is
  found and the video is cropped to that box; the natural aspect ratio of the content box is kept ("kare" does not
  mean 1:1).
- **Why this choice:** a title, padding or black area added to vertical carrier videos shrinks the subtitle placement
  and the watched area. Cropping affects only the picture; audio and timing do not change.
- **How it fits:** prepares the picture video before subtitle placement and the final encode; the setting is part of
  the stage checkpoint fingerprint ([ADR 0012](../adr/0012-stage-checkpoints-and-resume.md)). If OpenCV is not
  installed, the pipeline uses the source video unchanged.
- Place in the end-to-end flow: [pipeline-flow.md, branch table](../engineering/pipeline-flow.md#5-branches-what-a-choice-changes)

## Türkçe

**Akıllı kare (`akilli_kare`)**

**Ne yapar:** Videonun üst/alt ya da yan siyah/sabit bantlarını 24 örnek karede ölçer, içerik kutusunu bulur ve
dublajlı videoyu o kutuya kırpar (libx264, crf 18). Ses ve altyazı değişmez. Bant yoksa video olduğu gibi kalır.

| | |
|---|---|
| Lisans | kod: OpenCV (opencv-python-headless) Apache-2.0; ağırlık yok |
| Kurulum | `pip install .[akilli-kare]` |
| Donanım | yalnız işlemci, ~500 MB RAM (tahmini) |
| Varsayılan | kapalı |

**Ayar:** `DubConfig.smart_frame_capture_enabled = true` (ayar dosyası anahtarı ayar katmanına eklenince:
`video.akilli_kare = true`). Çıktılar iş klasöründe: `video_smart_frame.mp4`, `smart_frame_analysis.json`,
`smart_frame_preview.jpg` (seçilen kutu kırmızı çerçeveli).

**Sık hata**
- `Akıllı kare için OpenCV kurulu değil` → extras kurulmamış; hat kaynak videoyu kırpmadan sürdürür.
- Hiç kırpmadı (`full_frame_detected`) → bantlar zaten yok ya da çok ince; doğru davranış.
- Hareketli logo/yazı bantta ise kutu genişleyebilir; önizleme JPG'sine bakın.

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** 24 örnek karede kenar bantları (siyah ya da sabit alan) ölçülür, gerçek hareketli içerik kutusu bulunur ve
  video bu kutuya kırpılır; içerik kutusunun doğal en-boy oranı korunur ("kare" 1:1 anlamına gelmez).
- **Neden böyle:** dikey taşıyıcı videolara eklenen başlık, boşluk ya da siyah alan, altyazı yerleşimini ve izlenen
  alanı küçültür. Kırpma yalnız görüntüyü etkiler; ses ve zamanlama değişmez.
- **Diğer parçalarla ahengi:** altyazı yerleşimi ve son kodlamadan önce görüntü videosunu hazırlar; ayar aşamanın ara
  kayıt parmak izindedir ([ADR 0012](../adr/0012-stage-checkpoints-and-resume.md)). OpenCV kurulu değilse hat kaynak videoyu
  değiştirmeden kullanır.
- Uçtan uca akıştaki yeri: [hat_akisi.md, dallanma tablosu](../muhendislik/hat_akisi.md#5-dallanmalar-bir-seçim-neyi-değiştirir)
