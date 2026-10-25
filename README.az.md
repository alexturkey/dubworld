# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · [ไทย](README.th.md) · [বাংলা](README.bn.md) · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md) · Azərbaycanca · [Bahasa Melayu](README.ms.md)

> DubWorld videolarınızı öz kompüterinizdə, heç bir onlayn xidmətə yükləmədən başqa dilə dublyaj edir: danışığı hər sözün vaxtı ilə birlikdə mətnə çevirir, tərcümə edir, sonra orijinal görüntü ilə ayaqlaşan süni (AI) səslə oxudur (danışıq ən çox 1,25 dəfə sürətlənir, qalan fərqi videonun tempindəki yüngül dəyişiklik qarşılayır), altyazı əlavə edir və yeni video hazırlayır. Standart dil türkcədir. Açığını deyək: Azərbaycan dilinə **dublyaj** hələ mümkün deyil, çünki bu repodakı səs mühərriklərinin heç biri hələlik azərbaycanca danışmır; amma azərbaycanca videoları başqa dillərə dublyaj etmək olar ([docs/diller.md](docs/diller.md)).

## Qoy quraşdırmanı AI köməkçiniz etsin

Proqramlaşdırma bilmək lazım deyil. Kompüterinizdə əmr icra edə bilən bir AI köməkçisi açın (Claude Code, Codex,
Gemini CLI və ya oxşarı) və bu bir cümləni yapışdırın:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

Köməkçi kompüterinizi (videokart, prosessor, yaddaş, disk) yoxlayır və yalnız bir dəfə, sadə dillə, necə quraşdırma
istədiyinizi soruşur: sürətli, kompüteriniz üçün tövsiyə olunan, yoxsa tam. Hər hissəni izah edir (nə edir, nə qədər yer
tutur, nə qədər çəkir, lisenziyası nədir) və standart səsdən başlayaraq seçilmiş hissələrin istifadə şərtlərini qəbul edib-etmədiyinizi
soruşur. Sonra quraşdırır, nümunə dublyaj hazırlayır və proqramın pəncərəsini açır.
İlk addımlar və tez-tez rast gəlinən problemlər, sadə dillə (ingiliscə): **[docs/getting-started.md](docs/getting-started.md)**.

**Lisenziyalar qısaca:** kod Apache-2.0. Standart modellər: Supertonic 3 səsi OpenRAIL-M ilə (istifadə məhdudiyyətləri, bir dəfə qəbul edilir); Opus-MT və türkcə söz vaxtı modeli CC BY 4.0 ilə (müəllifi göstərmək mütləqdir, NOTICE); FFmpeg yığımı GPL-3.0 (ayrıca proqram). Yalnız qeyri-kommersiya istifadəsi üçün və standart olaraq söndürülü: CrisperWhisper 2.0, XTTS-v2 və fr / de / es / it üçün WhisperX söz vaxtı modelləri. Bu repoda heç bir model çəkisi yoxdur ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Sürətli quraşdırma

Windows 10/11 x64; əvvəlcədən Python, CUDA və ya ffmpeg lazım deyil. **`kur.cmd`** faylına iki dəfə klikləyin (və ya
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1` işə salın); GPU və ya CPU profili özü seçilir
(`-Cpu` CPU-nu məcbur edir). Sonra tətbiqi açmaq üçün `arayuz.cmd` faylına iki dəfə klikləyin.
Hər şey repo qovluğunun içində qalır (`.venv`, `runtime_assets/`); hər yükləmənin versiyası sabitdir və
sha256 ilə yoxlanılır. Başlamaq üçün boş yer: GPU profili ilə 22 GB, yalnız CPU ilə 14 GB; quraşdırmadan sonra ölçülmüş istifadə ≈ 14,6 GB (GPU, sərt keçidli fayllar bir dəfə sayılıb; Fayl Bələdçisi ≈ 22 GB göstərir). Yoxlama: `.venv\Scripts\dubla.exe kontrol`.

Tələblər, addımların ardıcıllığı, Python mühitlərinin xəritəsi, əlavə mühərriklər, oflayn istifadə, yeniləmə, silmə və
tez-tez rast gəlinən xətalar (ingiliscə): **[docs/installation.md](docs/installation.md)**. Linux və macOS-u hələ sınamamışıq. Nümunə: [Apple M4 çipli Mac-də yalnız CPU ilə ingilis, türk və ərəb dillərinə dublyaj edilmiş məhsul təqdimatı](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## İstifadə

Masaüstü tətbiq: `arayuz.cmd` faylına iki dəfə klik (yerli veb tətbiq: `web.cmd`, yalnız 127.0.0.1-də). Tətbiqin interfeysi hələlik türkcədir. Əmr sətrindən:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Azərbaycan dilinə dublyaj hələ yoxdur, çünki səs mühərrikləri azərbaycanca oxumur; amma azərbaycanca videonu məsələn `--ayar genel.hedef_dil=en` ilə ingiliscəyə, adi əmrlə isə türkcəyə dublyaj edə bilərsiniz (azərbaycancadan tərcümə üçün Codex və ya Claude Code lazımdır). Nəticələr `cikti/<video>_<time>/` qovluğuna düşür: `dubbed_tr.mp4` (`AI-dubbed` etiketi ilə), orijinal altyazı `transcript_<lang>.srt` və işçi JSON faylları; son `dubbed_video:` sətri yolu göstərir. Bütün ayarlar (ingilis və türk dillərində): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Necə işləyir

1. **Səs:** FFmpeg səsi çıxarır; əlavə Demucs (MIT) danışığı fondan ayırır.
2. **Danışıqdan mətnə:** faster-whisper large-v3-turbo (MIT) və wav2vec2 CTC ilə söz vaxtları (ingiliscə MIT, türkcə CC BY 4.0); əlavə CrisperWhisper 2.0 (qeyri-kommersiya) və başqa mühərriklər.
3. **Danışanlar:** 3D-Speaker CAM++ (Apache-2.0) və cinsi tanıyan model (Apache-2.0) hər danışana bir AI səsi seçir.
4. **Tərcümə:** Codex CLI və ya Claude Code CLI quraşdırılıb və hesaba girilibsə onlar, yoxsa yerli Opus-MT ingiliscədən türkcəyə (CC BY 4.0); API arxa ucları əlavədir.
5. **Səs və vaxtlama:** standart Supertonic 3 (OpenRAIL-M), əlavə VoxCPM2 (Apache-2.0) və ya XTTS-v2 (qeyri-kommersiya); hər cümlə orijinal hissənin vaxtına doğru ən çox 1,25 dəfə sürətlənir, qalanını videonun vaxtı qarşılayır, ona görə də dublyaj orijinaldan uzun ola bilər.
6. **Video:** FFmpeg yeni səsi, SRT / VTT / ASS altyazını və `AI-dubbed` etiketini yazır.

## Ölçmələr

İstinad kompüteri: 4 GB Pascal GPU, Windows 10; üsul və bütün sətirlər [docs/olcumler.md](docs/olcumler.md) faylındadır.

| Nə | CPU profili | GPU profili |
|---|---|---|
| İlk quraşdırma, standart addımlar, əvvəldən axıra | ≈ 38 dəq | ≈ 44 dəq (paketlər 13,7 dəq) |
| Quraşdırmadan sonra disk | ≈ 13,2 GB (qovluqların cəmi) | ≈ 14,6 GB (sərt keçidlər bir dəfə) |
| 9 saniyəlik nümunə dublyaj, oflayn tərcümə | 528 san | 376 san |
| 30 saniyəlik ingiliscə klip, Demucs, Claude Code tərcüməsi | – | 744 san |

## Məhdudiyyətlər

- CrisperWhisper (əlavə mühərrik 13) olmadan faster-whisper çin və yapon dillərində danışığı ötürə və ya deyilməyən mətn uydura bilər (müşahidə edilib: çincə klipin ilk ≈ 10 saniyəsi itdi; bir qışqırıq uzun "ああ…" sətrinə çevrildi).
- CI yalnız CPU-nu sınayır; GPU yolu 4 GB Pascal kartında əl ilə işlədilib. Yeni kartlar (RTX 50), Linux və macOS sınanmayıb; quraşdırılan GPU kitabxanalarında Pascal-dan RTX 50-yə qədər nüvələr var, Maxwell isə CPU profilindən istifadə edir ([GPU dəstəyi cədvəli, ingiliscə](docs/installation.md#1-system-requirements)).
- Oflayn tərcüməçi yalnız ingiliscədən türkcəyə çevirir; başqa dil cütləri üçün Codex / Claude Code CLI və ya API arxa ucu lazımdır.
- İngilis və türk dilindən başqa mənbə dilləri üçün söz vaxtları: yapon və çin dilləri `scripts/kur.ps1 -Adim hizalama-diller` ilə, digərləri `DUBLAJ_CEVRIMICI=1` ilə bir dəfə işlətdikdən sonra.
- Hələ əvvəldən axıra sınanmayıb: real XTTS-v2 quraşdırması, RVC, real xidmətə qoşulmuş Telegram botu və CrisperWhisper 2 Medium; Moonshine sınaq mərhələsindədir. CrisperWhisper 2.0 Turbo (mühərrik 13) real səslə GTX 1050 Ti 4 GB-da sınanıb (tr, en, ja; ≈ 1,4 GB VRAM).

## Tikinti blokları

Hər mərhələ tək də işləyir, əmr sətrindən və ya Python-dan, mərhələlər arasındakı fayl formatları isə sənədləşdirilib
(mərhələ xəritəsi və JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` eyni mərhələləri funksiya kimi verir. Yalnız bir mərhələyə lazım olanı quraşdırın, məsələn
altyazı üçün `pip install -e ".[stt,hizalama,cpu]"`. Bu bloklardan qurulmuş beş kiçik alət: [examples/](examples/).

## Ailə / əlaqəli layihələr

| Repo | Nədir | Bu repo ondan necə istifadə edir |
|---|---|---|
| **DubWorld** (bu repo) | Tamamilə yerli video dublyaj axını, hər mərhələ ayrıca da istifadə oluna bilər | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | Söz-söz danışıqdan mətnə, söz vaxtları ilə (CrisperWhisper 2.0 Turbo + CTC uyğunlaşdırma) | Əlavə mühərrik 13: `scripts/kur.ps1 -Adim crisper` modeli həmin repo vasitəsilə sabit commit-də quraşdırır (çəkilər **qeyri-kommersiya**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | VoxCPM2 ilə səs dizaynı və oxuma, 8 dil, hazır səslər | Əlavə səs mühərriki `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` sabit commit-də quraşdırır; bu repo onu nazik adapterlə çağırır |

Hər qardaş reponun öz lisenziyası, quraşdırması və issue-ları var; sabit commit sayəsində bu birləşmə hər dəfə eyni nəticə ilə yenidən qurula bilər.

## Məsuliyyətli istifadə

> **Hüquqi qeyd.** Bu proqramla emal edib yaydığınız məzmunun, eləcə də ölkənizin qanunlarına və istifadə etdiyiniz sayt və
> xidmətlərin şərtlərinə əməl etməyin bütün məsuliyyəti sizin üzərinizdədir. Proqram "olduğu kimi", heç bir zəmanət olmadan
> təqdim olunur (Apache-2.0). Tam mətn: [ETHICS.md](ETHICS.md).

- **Hüquqlar və razılıq.** Yalnız sizə məxsus olan və ya tərcümə edib yenidən dublyaj etməyə haqqınız olan məzmunu emal edin,
  və orada tanına bilən insanların razılığını alın.
- **Səslər.** Heç kimi təqlid etməyin. İstinad səsi yalnız sizin öz səsiniz və ya açıq icazə vermiş birinin səsi ola bilər.
- **Etiketləyin.** Nəticədə `AI-dubbed` metaməlumat etiketi var; onu saxlayın və tamaşaçılarınıza aydın şəkildə bildirin
  ki, dublyaj AI ilə edilib (AB Süni İntellekt Aktının 50-ci maddəsi; Supertonic lisenziyası).
- **Yükləmələr.** Əlavə `youtube` (yt-dlp) və `galeri` (gallery-dl) modulları yalnız sizə məxsus və ya yükləməyə icazəniz olan məzmun üçündür; saytın şərtləri və
  yerli qanunlarınız qüvvədədir.
- **Qeyri-kommersiya mühərrikləri.** CrisperWhisper 2.0 və XTTS-v2 yalnız qeyri-kommersiya istifadəsi üçündür (standart olaraq söndürülü). Pullu və ya müştəri işindən əvvəl
  [THIRD_PARTY.md](THIRD_PARTY.md) faylında **Commercial?** sütununa baxın.
  fr / de / es / it mənbə səsi üçün söz vaxtı modelləri (CC BY-NC 4.0) də qeyri-kommersiyadır və ilk istifadədə razılıq istəyir.

## Kömək və dəstək

Suallar, fikirlər və nəticələriniz: [müzakirə forumu](https://github.com/alexturkey/dubworld/discussions). Quraşdırma problemi: [quraşdırma problemini bildirin](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); xətalar: [xəta bildirin](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(əməliyyat sistemini, GPU-nu, işlətdiyiniz əmri və çıxışın son sətirlərini yazın). Təhlükəsizlik məsələləri: SECURITY.md-yə baxın, açıq issue-da yazmayın.

## Lisenziya və təşəkkür

Kod: Apache-2.0 (LICENSE). Xarici hissələr və onların lisenziyaları: THIRD_PARTY.md. Məsuliyyətli istifadə: ETHICS.md.
Məxfilik (kompüterinizdə nə qalır, bulud arxa ucu nə alır): PRIVACY.md. Təhlükəsizlik bildirişləri: SECURITY.md. Dəyişikliklər: CHANGELOG.md.

<!-- i18n-source: README.md sha256:08d5cfa0c4f9 -->
