# DubWorld

[English](README.md) · Türkçe · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · [ไทย](README.th.md) · [বাংলা](README.bn.md) · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md) · [Azərbaycanca](README.az.md) · [Bahasa Melayu](README.ms.md)

> DubWorld bir videoyu kendi bilgisayarınızda başka bir dile dublajlar: kelime zamanlı yazıya dökme, çeviri, özgün videoyla adım adım giden yapay ses (konuşma en çok 1,25 kat hızlanır, kalanı için görüntü yeniden zamanlanır), altyazı ve yeni video. Varsayılan dil Türkçe; diğer diller ses motoruna göre ([docs/diller.md](docs/diller.md)).

## Yapay zekâ asistanınıza kurdurun

Programlama bilgisi gerekmez. Bilgisayarınızda komut çalıştırabilen bir yapay zekâ asistanını (Claude Code, Codex,
Gemini CLI ya da benzeri) açın ve şu tek cümleyi yapıştırın:

```text
https://github.com/alexturkey/DubWorld adresindeki video dublaj programını bu bilgisayara kur. Depodaki AGENTS.md dosyasını adım adım uygula, donanımımı kendin algıla, bana teknik soru sorma. `dubla kontrol` HAZIR deyip örnek dublaj çalışınca programın penceresini benim için aç.
```

Asistan bilgisayarınızı ölçer (ekran kartı, işlemci, bellek, disk) ve size sade sözcüklerle bir kez nasıl bir kurulum
istediğinizi sorar: hızlı, bilgisayarınız için önerilen ya da tam. Her parçayı anlatır (ne yapar, ne kadar disk ve
zaman tutar, lisansı ne) ve seçtiğiniz parçaların kullanım şartlarını, önce varsayılan sesinkini, kabul edip
etmediğinizi sorar. Sonra kurar, örnek bir dublaj yapar ve program penceresini açar. İlk adımlar, sade anlatım ve sık
sorunlar: **[docs/baslarken.md](docs/baslarken.md)**.

**Lisans kutusu:** kod Apache-2.0. Varsayılan modeller: Supertonic 3 sesi OpenRAIL-M (kullanım kısıtları, bir kez onaylanır); Opus-MT ve Türkçe kelime zamanı modeli CC BY 4.0 (atıf, NOTICE); FFmpeg derlemesi GPL-3.0 (ayrı program). Yalnız ticari olmayan ve varsayılan kapalı: CrisperWhisper 2.0, XTTS-v2, fr / de / es / it için WhisperX kelime zamanı modelleri. Bu repoda hiçbir model ağırlığı yoktur ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Hızlı kurulum

Windows 10/11 x64; önceden Python, CUDA ya da ffmpeg gerekmez. **`kur.cmd`**'ye çift tıklayın (ya da
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); GPU ya da işlemci profilini kendisi seçer
(`-Cpu` işlemciyi zorlar). Sonra programı açmak için `arayuz.cmd`'ye çift tıklayın. Her şey repo
klasörünün içine kurulur (`.venv`, `runtime_assets/`); her indirme sabit ve sha256 doğrulamalıdır. Başlamak için boş disk: GPU
profiliyle 22 GB, yalnız işlemciyle 14 GB; kurulum sonrası ölçülen kullanım ≈ 14,6 GB (GPU, sabit bağlı dosyalar bir kez sayıldı; dosya gezgini ≈ 22 GB gösterir). Doğrulama: `.venv\Scripts\dubla.exe kontrol`.

Gereksinimler, adım sırası, Python ortamları haritası, isteğe bağlı motorlar, çevrimdışı kullanım, güncelleme,
kaldırma ve sık hatalar: **[docs/kurulum.md](docs/kurulum.md)**. Linux ve macOS henüz denenmedi. Örnek: [Apple M4 Mac'te, yalnız işlemciyle İngilizce, Türkçe ve Arapça seslendirilmiş ürün tanıtımı](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Kullanım

Masaüstü uygulaması: `arayuz.cmd`'ye çift tıklayın (yerel web uygulaması: `web.cmd`, yalnız 127.0.0.1). Uygulamanın ekranları Türkçe ve İngilizce: sağ üstten seçin (bilgisayar başka bir dildeyse İngilizce açılır). Komut satırından:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Sonuçlar `cikti/<video>_<zaman>/` altına yazılır: `dubbed_tr.mp4` (`AI-dubbed` etiketli), kaynak altyazı `transcript_<dil>.srt` ve işin JSON dosyaları; son satır `dubbed_video:` yolu yazar. Bütün ayarlar: [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Nasıl çalışır

1. **Ses:** FFmpeg sesi çıkarır; isteğe bağlı Demucs (MIT) konuşmayı arka plandan ayırır.
2. **Yazıya dökme:** faster-whisper large-v3-turbo (MIT) ve wav2vec2 CTC kelime zamanı (İngilizce MIT, Türkçe CC BY 4.0); isteğe bağlı CrisperWhisper 2.0 (ticari olmayan) ve diğer motorlar.
3. **Konuşmacılar:** 3D-Speaker CAM++ (Apache-2.0) ve cinsiyet sınıflandırıcı (Apache-2.0) her konuşmacıya yapay bir ses seçer.
4. **Çeviri:** kurulu ve oturum açıksa Codex CLI ya da Claude Code CLI, yoksa yerel Opus-MT İngilizceden Türkçeye (CC BY 4.0); API arka uçları isteğe bağlı.
5. **Ses ve zaman:** varsayılan Supertonic 3 (OpenRAIL-M), isteğe bağlı VoxCPM2 (Apache-2.0) ya da XTTS-v2 (ticari olmayan); her satır özgün segment süresine doğru en çok 1,25 kat hızlandırılır, kalanı için video yeniden zamanlanır; dublaj bu yüzden kaynaktan uzun olabilir.
6. **Video:** FFmpeg yeni sesi, SRT / VTT / ASS altyazıyı ve `AI-dubbed` etiketini yazar.

## Ölçümler

Başvuru makinesi: 4 GB Pascal GPU, Windows 10; yöntem ve bütün satırlar [docs/olcumler.md](docs/olcumler.md).

| Ne | İşlemci profili | GPU profili |
|---|---|---|
| İlk kurulum, varsayılan adımlar, baştan sona | ≈ 38 dk | ≈ 44 dk (paketler 13,7 dk) |
| Kurulum sonrası disk | ≈ 13,2 GB (klasör toplamı) | ≈ 14,6 GB (sabit bağlar bir kez sayıldı) |
| 9 sn örnek dublaj, çevrimdışı çeviri | 528 sn | 376 sn |
| 30 sn İngilizce parça, Demucs, Claude Code çevirisi | – | 744 sn |

## Sınırlar

- CrisperWhisper (isteğe bağlı 13. motor) yokken faster-whisper Çince ve Japoncada konuşmayı atlayabilir ya da uydurabilir (görülen: bir Çince parçanın ilk ≈ 10 sn'si atlandı; bağırma uzun bir "ああ…" satırına dönüştü).
- CI yalnız işlemciyi sınar; GPU yolu tek bir 4 GB Pascal kartta elle koşuldu. Yeni kartlar (RTX 50), Linux ve macOS denenmedi; kurulan GPU kitaplıkları Pascal'dan RTX 50'ye kadar çekirdek taşır, Maxwell işlemci profilini kullanır ([GPU çalışma matrisi](docs/kurulum.md#1-sistem-gereksinimleri)).
- Çevrimdışı çevirmen yalnız İngilizceden Türkçeye çevirir; diğer dil çiftleri Codex / Claude Code CLI ya da bir API arka ucu ister.
- İngilizce ve Türkçe dışındaki kaynak dillerde kelime zamanı: Japonca ve Çince `scripts/kur.ps1 -Adim hizalama-diller` ile, diğerleri bir kez `DUBLAJ_CEVRIMICI=1` ile çalıştırınca.
- Uçtan uca denenmedi: XTTS-v2 gerçek kurulumu, RVC, gerçek hizmete bağlı Telegram botu. CrisperWhisper 2.0 Turbo (13. motor) GTX 1050 Ti 4 GB'ta gerçek seste denendi (tr, en, ja; ≈ 1,4 GB VRAM).

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
| **DubWorld** (bu repo) | uçtan uca yerel video dublaj hattı, her aşama tek başına kullanılabilir | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | kelime zamanlı birebir yazıya dökme (CrisperWhisper 2.0 Turbo + CTC hizalama) | isteğe bağlı 13. motor: `scripts/kur.ps1 -Adim crisper` modeli o repo üzerinden sabit commit ile kurar (ağırlık **ticari olmayan**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | VoxCPM2 ses tasarımı ve okuma, 8 dil, hazır sesler | isteğe bağlı TTS motoru `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` sabit commit ile kurar; bu repo onu ince bir adaptörle çağırır |

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
  fr / de / es / it kaynak ses için kelime zamanı modelleri (CC BY-NC 4.0) de ticari değildir ve ilk kullanımda onay ister.

## Yardım ve destek

Soru, fikir ve sonuçlar: [Discussions](https://github.com/alexturkey/dubworld/discussions). Kurulum sorunu: [kurulum formu](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); hata: [hata raporu](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(işletim sistemi, GPU, komut ve son satırlarını ekleyin). Güvenlik açıkları: SECURITY.md, herkese açık issue değil.

## Lisans ve emek

Kod: Apache-2.0 (LICENSE). Üçüncü taraf bileşenler ve lisansları: THIRD_PARTY.md. Sorumlu kullanım: ETHICS.md.
Gizlilik (ne yerelde kalır, bulut arka ucu ne alır): PRIVACY.md. Güvenlik bildirimi: SECURITY.md. Değişiklikler: CHANGELOG.md.

<!-- i18n-source: README.md sha256:cdd2c731c59f -->
