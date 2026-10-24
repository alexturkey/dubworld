# Türkçe video dublaj hattı

[English](README.md) · Türkçe · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md)

> __TEK_CUMLE__ (tek cümleyle ne yapar)

## Yapay zekâ asistanınıza kurdurun

Programlama bilgisi gerekmez. Bilgisayarınızda komut çalıştırabilen bir yapay zekâ asistanını (Claude Code, Codex,
Gemini CLI ya da benzeri) açın ve şu tek cümleyi yapıştırın:

```text
__REPO_URL__ adresindeki video dublaj programını bu bilgisayara kur. Depodaki AGENTS.md dosyasını adım adım uygula, donanımımı kendin algıla, bana teknik soru sorma. `dubla kontrol` HAZIR deyip örnek dublaj çalışınca programın penceresini benim için aç.
```

Asistan bilgisayarınızı denetler, ekran kartıyla (GPU) mı yalnız işlemciyle (CPU) mi kurulacağını kendisi seçer ve
size tek bir soru sorar: sesin kullanım şartlarını kabul edip etmediğiniz. Sonra program penceresi açılır. İlk
adımlar, sade anlatım ve sık sorunlar: **[docs/baslarken.md](docs/baslarken.md)**.

**Lisans kutusu:** kod Apache-2.0. __LISANS_KUTUSU__

## Hızlı kurulum

Windows 10/11 x64; önceden Python, CUDA ya da ffmpeg gerekmez. **`kur.cmd`**'ye çift tıklayın (ya da
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); GPU ya da işlemci profilini kendisi seçer
(`-Cpu` işlemciyi zorlar). Sonra programı açmak için `arayuz.cmd`'ye çift tıklayın. Her şey repo
klasörünün içine kurulur (`.venv`, `runtime_assets/`); her indirme sabit ve sha256 doğrulamalıdır. Disk: GPU
profiliyle ≈ 22 GB, yalnız işlemciyle ≈ 13 GB. Doğrulama: `.venv\Scripts\dubla.exe kontrol`.

Gereksinimler, adım sırası, Python ortamları haritası, isteğe bağlı motorlar, çevrimdışı kullanım, güncelleme,
kaldırma ve sık hatalar: **[docs/kurulum.md](docs/kurulum.md)**. Linux ve macOS henüz denenmedi.

## Kullanım

__KULLANIM__

## Nasıl çalışır

__NASIL__

## Ölçümler

__OLCUM_TABLOSU__ (başvuru makinesinde ölçüldü, yöntem docs/olcumler.md; başka yerden sayı kopyalanmaz)

## Sınırlar

__SINIRLAR__

## Yapı taşları

Her aşama komut satırından ya da Python'dan tek başına çalışır; aşamalar arasında belgelenmiş dosya biçimleri vardır
(aşama haritası ve JSON şemaları: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` aynı aşamaları işlev olarak verir. Yalnız gereken aşamayı kurun, ör. altyazı için
`pip install -e ".[stt,hizalama,cpu]"`. Bu parçalardan kurulmuş beş küçük araç: [examples/](examples/).

## Aile / ilgili projeler

| Repo | Ne | Bu repo nasıl kullanır |
|---|---|---|
| **turkce-video-dublaj-hatti** (bu repo) | uçtan uca yerel video dublaj hattı, her aşama tek başına kullanılabilir | - |
| [crisperwhisper-turkce-kelime-zamani](__STT_REPO_URL__) | kelime zamanlı birebir yazıya dökme (CrisperWhisper 2.0 Turbo + CTC hizalama) | isteğe bağlı 13. motor: `scripts/kur.ps1 -Adim crisper` modeli o repo üzerinden sabit commit ile kurar (ağırlık **ticari olmayan**) |
| [voxcpm2-turkce-ses-tasarimi](__TTS_REPO_URL__) | VoxCPM2 ses tasarımı ve okuma, 8 dil, hazır sesler | isteğe bağlı TTS motoru `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` sabit commit ile kurar; bu repo onu ince bir adaptörle çağırır |

Her kardeş repo kendi lisansını, kurulumunu ve sorun kaydını taşır; sabit commit'ler birleşimi tekrarlanabilir kılar.

## Sorumlu kullanım

> **Yasal uyarı.** Bu yazılımla işlediğiniz ve yayımladığınız içerikten, bulunduğunuz yerin yasalarına ve
> kullandığınız site ve hizmetlerin şartlarına uymaktan yalnız siz sorumlusunuz. Yazılım "olduğu gibi", garantisiz
> sunulur (Apache-2.0). Tam metin ve bağlayıcı İngilizce sürüm: [ETHICS.md](ETHICS.md).

- **Hak ve rıza.** Yalnız sahibi olduğunuz ya da çevirip yeniden seslendirme izni aldığınız malzemeyi işleyin;
  içindeki tanınabilir kişilerin rızasını alın.
- **Sesler.** Taklit yok. Referans ses yalnız sizin ya da sahibinin açık rıza verdiği bir ses olabilir.
- **Etiketleyin.** Çıktılarda `AI-dubbed` meta etiketi vardır; silmeyin, ayrıca izleyiciye yapay zekâ dublajını
  görünür biçimde söyleyin (AB Yapay Zekâ Tüzüğü md. 50; Supertonic lisansı).
- **İndirme.** İsteğe bağlı `youtube` (yt-dlp) ve `galeri` (gallery-dl) ekleri yalnız sahibi olduğunuz ya da indirme izniniz olan içerik
  içindir; sitenin şartları ve yerel yasanız geçerlidir.
- **Ticari olmayan motorlar.** CrisperWhisper 2.0 ve XTTS-v2 yalnız ticari olmayan kullanım içindir (varsayılan kapalı).
  Ücretli ya da müşteri işinden önce [THIRD_PARTY.md](THIRD_PARTY.md) **Commercial?** sütununa bakın.

## Lisans ve emek

Kod: Apache-2.0 (LICENSE). Üçüncü taraf bileşenler ve lisansları: THIRD_PARTY.md. Sorumlu kullanım: ETHICS.md.
Gizlilik (ne yerelde kalır, bulut arka ucu ne alır): PRIVACY.md. Güvenlik bildirimi: SECURITY.md. Değişiklikler: CHANGELOG.md.
