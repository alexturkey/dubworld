# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · [ไทย](README.th.md) · [বাংলা](README.bn.md) · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md) · [Azərbaycanca](README.az.md) · Bahasa Melayu

> DubWorld mengalih suara video anda ke bahasa lain terus di komputer anda sendiri, tanpa memuat naiknya ke mana-mana perkhidmatan dalam talian: pertuturan ditukar kepada teks berserta masa setiap perkataan, diterjemah, kemudian dibaca oleh suara tiruan (AI) yang kekal seiring dengan video asal (pertuturan dipercepat paling banyak 1.25 kali, baki perbezaan diserap dengan sedikit mengubah tempo video), sari kata ditambah, dan video baharu dihasilkan. Bahasa lalai ialah bahasa Turki. Terus terang: alih suara **ke** bahasa Melayu belum boleh lagi, kerana tiada satu pun enjin suara dalam repositori ini yang bertutur bahasa Melayu buat masa ini; tetapi video berbahasa Melayu boleh dialih suara ke bahasa lain ([docs/diller.md](docs/diller.md)).

## Biar pembantu AI anda yang memasangnya

Anda tidak perlu tahu pengaturcaraan. Buka pembantu AI yang boleh menjalankan arahan di komputer anda (Claude Code, Codex,
Gemini CLI atau yang seumpamanya) dan tampal satu ayat ini:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

Pembantu akan memeriksa komputer anda (kad grafik, pemproses, memori, cakera) dan hanya bertanya sekali, dalam bahasa mudah,
pemasangan jenis apa yang anda mahu: pantas, disyorkan untuk komputer anda, atau lengkap. Ia menerangkan setiap komponen (apa
fungsinya, berapa ruang yang diambil, berapa lama, apa lesennya) dan, bermula dengan suara lalai, bertanya sama ada anda
menerima syarat penggunaan komponen yang dipilih. Selepas itu ia memasang, membuat contoh alih suara dan membuka tetingkap program.
Langkah pertama dan masalah biasa, diterangkan dengan mudah (dalam bahasa Inggeris): **[docs/getting-started.md](docs/getting-started.md)**.

**Lesen secara ringkas:** kod Apache-2.0. Model lalai: suara Supertonic 3 di bawah OpenRAIL-M (sekatan penggunaan, diterima sekali); Opus-MT dan model masa perkataan bahasa Turki di bawah CC BY 4.0 (atribusi wajib, NOTICE); binaan FFmpeg GPL-3.0 (program berasingan). Hanya untuk kegunaan bukan komersial dan dimatikan secara lalai: CrisperWhisper 2.0, XTTS-v2 dan model masa perkataan WhisperX untuk fr / de / es / it. Repositori ini tidak mengandungi sebarang pemberat model ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Pemasangan pantas

Windows 10/11 x64; tidak perlu Python, CUDA atau ffmpeg dipasang terlebih dahulu. Klik dua kali **`kur.cmd`** (atau jalankan
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); profil GPU atau CPU dipilih secara automatik
(`-Cpu` memaksa CPU). Kemudian klik dua kali `arayuz.cmd` untuk membuka aplikasi.
Semuanya kekal di dalam folder repositori (`.venv`, `runtime_assets/`); setiap muat turun dikunci versinya dan
disemak dengan sha256. Ruang kosong untuk bermula: 22 GB dengan profil GPU, 14 GB dengan CPU sahaja; penggunaan yang diukur selepas pemasangan ≈ 14.6 GB (GPU, fail pautan keras dikira sekali; File Explorer menunjukkan ≈ 22 GB). Semakan: `.venv\Scripts\dubla.exe kontrol`.

Keperluan, susunan langkah, peta persekitaran Python, enjin pilihan, penggunaan luar talian, kemas kini, nyahpasang dan
ralat biasa (dalam bahasa Inggeris): **[docs/installation.md](docs/installation.md)**. Kami belum menguji Linux dan macOS. Contoh: [lawatan produk yang dialih suara ke bahasa Inggeris, Turki dan Arab pada Mac Apple M4, dengan CPU sahaja](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Cara guna

Aplikasi desktop: klik dua kali `arayuz.cmd` (aplikasi web tempatan: `web.cmd`, hanya pada 127.0.0.1). Antara muka aplikasi dalam bahasa Inggeris dan Turki: pilih di penjuru kanan atas (jika komputer menggunakan bahasa lain, aplikasi dibuka dalam bahasa Inggeris). Dari baris arahan:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Alih suara ke bahasa Melayu belum tersedia, kerana enjin suara belum boleh membaca bahasa Melayu; tetapi video berbahasa Melayu boleh dialih suara ke bahasa Inggeris dengan `--ayar genel.hedef_dil=en`, atau ke bahasa Turki dengan arahan biasa (terjemahan daripada bahasa Melayu memerlukan Codex atau Claude Code). Hasilnya masuk ke `cikti/<video>_<time>/`: `dubbed_tr.mp4` (dengan tag `AI-dubbed`), sari kata asal `transcript_<lang>.srt` dan fail kerja JSON; baris terakhir `dubbed_video:` menunjukkan laluannya. Semua tetapan (dalam bahasa Inggeris dan Turki): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Cara ia berfungsi

1. **Audio:** FFmpeg mengeluarkan bunyi; Demucs (MIT) pilihan memisahkan pertuturan daripada latar belakang.
2. **Pertuturan ke teks:** faster-whisper large-v3-turbo (MIT) dengan masa perkataan wav2vec2 CTC (Inggeris MIT, Turki CC BY 4.0); CrisperWhisper 2.0 pilihan (bukan komersial) dan enjin lain.
3. **Penutur:** 3D-Speaker CAM++ (Apache-2.0) dan model pengecam jantina (Apache-2.0) memilih satu suara AI untuk setiap penutur.
4. **Terjemahan:** Codex CLI atau Claude Code CLI jika dipasang dan sudah log masuk, jika tidak Opus-MT tempatan Inggeris ke Turki (CC BY 4.0); bahagian belakang API adalah pilihan.
5. **Suara dan masa:** lalai Supertonic 3 (OpenRAIL-M), pilihan VoxCPM2 (Apache-2.0) atau XTTS-v2 (bukan komersial); setiap ayat dipercepat paling banyak 1.25 kali ke arah masa segmen asal, bakinya diselaraskan melalui masa video, jadi alih suara boleh lebih panjang daripada asal.
6. **Video:** FFmpeg menulis suara baharu, sari kata SRT / VTT / ASS dan tag `AI-dubbed`.

## Ukuran

Komputer rujukan: GPU Pascal 4 GB, Windows 10; kaedah dan semua baris dalam [docs/olcumler.md](docs/olcumler.md).

| Apa | Profil CPU | Profil GPU |
|---|---|---|
| Pemasangan pertama, langkah lalai, dari mula hingga akhir | ≈ 38 min | ≈ 44 min (pakej 13.7 min) |
| Cakera selepas pemasangan | ≈ 13.2 GB (jumlah folder) | ≈ 14.6 GB (pautan keras dikira sekali) |
| Contoh alih suara 9 saat, terjemahan luar talian | 528 s | 376 s |
| Klip bahasa Inggeris 30 saat, Demucs, terjemahan Claude Code | – | 744 s |

## Had

- Tanpa CrisperWhisper (enjin pilihan 13), faster-whisper boleh terlepas pertuturan atau mereka teks yang tidak pernah diucapkan dalam bahasa Cina dan Jepun (pernah dilihat: ≈ 10 saat pertama sebuah klip Cina hilang; satu jeritan menjadi baris "ああ…" yang panjang).
- CI hanya menguji CPU; laluan GPU dijalankan secara manual pada kad Pascal 4 GB. Kad baharu (RTX 50), Linux dan macOS belum diuji; pustaka GPU yang dipasang mempunyai kernel dari Pascal hingga RTX 50, dan Maxwell menggunakan profil CPU ([jadual sokongan GPU, dalam bahasa Inggeris](docs/installation.md#1-system-requirements)).
- Penterjemah luar talian hanya Inggeris ke Turki; pasangan bahasa lain memerlukan Codex / Claude Code CLI atau bahagian belakang API.
- Masa perkataan untuk bahasa sumber selain Inggeris dan Turki: Jepun dan Cina melalui `scripts/kur.ps1 -Adim hizalama-diller`, yang lain selepas sekali dijalankan dengan `DUBLAJ_CEVRIMICI=1`.
- Belum diuji dari mula hingga akhir: pemasangan XTTS-v2 sebenar, RVC, bot Telegram yang disambung ke perkhidmatan sebenar dan CrisperWhisper 2 Medium; Moonshine masih percubaan. CrisperWhisper 2.0 Turbo (enjin 13) telah diuji dengan audio sebenar pada GTX 1050 Ti 4 GB (tr, en, ja; ≈ 1.4 GB VRAM).

## Blok binaan

Setiap peringkat boleh dijalankan sendiri, dari baris arahan atau dari Python, dan format fail antara peringkat didokumenkan
(peta peringkat dan JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` menyediakan peringkat yang sama sebagai fungsi. Pasang hanya apa yang diperlukan oleh sesuatu peringkat, contohnya
`pip install -e ".[stt,hizalama,cpu]"` untuk sari kata. Lima alat kecil yang dibina daripada blok ini: [examples/](examples/).

## Keluarga / projek berkaitan

| Repositori | Apa itu | Bagaimana repositori ini menggunakannya |
|---|---|---|
| **DubWorld** (repositori ini) | Saluran alih suara video yang sepenuhnya tempatan, setiap peringkat juga boleh digunakan berasingan | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | Pertuturan ke teks perkataan demi perkataan dengan masa perkataan (CrisperWhisper 2.0 Turbo + penjajaran CTC) | Enjin pilihan 13: `scripts/kur.ps1 -Adim crisper` memasang model melalui repositori itu pada commit tetap (pemberat **bukan komersial**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | Reka bentuk suara dan bacaan dengan VoxCPM2, 8 bahasa, suara sedia guna | Enjin suara pilihan `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` memasang pada commit tetap; repositori ini memanggilnya melalui penyesuai nipis |

Setiap repositori saudara mempunyai lesen, pemasangan dan isu sendiri; dengan commit tetap, gabungan ini boleh dibina semula dengan hasil yang sama.

## Penggunaan bertanggungjawab

> **Notis undang-undang.** Anda bertanggungjawab sepenuhnya terhadap kandungan yang anda proses dan terbitkan dengan perisian
> ini, serta mematuhi undang-undang negara anda dan syarat laman dan perkhidmatan yang anda gunakan. Perisian ini diberikan
> "seadanya", tanpa sebarang jaminan (Apache-2.0). Teks penuh: [ETHICS.md](ETHICS.md).

- **Hak dan persetujuan.** Proses hanya kandungan milik anda atau yang anda berhak terjemah dan alih suara semula,
  dan dapatkan persetujuan orang yang boleh dikenali di dalamnya.
- **Suara.** Jangan meniru sesiapa. Suara rujukan hanya boleh suara anda sendiri atau orang yang telah memberi kebenaran jelas.
- **Labelkan.** Hasilnya membawa tag metadata `AI-dubbed`; biarkan ia kekal dan beritahu penonton anda dengan jelas
  bahawa alih suara dibuat dengan AI (Perkara 50 Akta AI EU; lesen Supertonic).
- **Muat turun.** Tambahan pilihan `youtube` (yt-dlp) dan `galeri` (gallery-dl) hanya untuk kandungan milik anda atau yang anda dibenarkan muat turun; syarat laman dan
  undang-undang tempatan anda terpakai.
- **Enjin bukan komersial.** CrisperWhisper 2.0 dan XTTS-v2 hanya untuk kegunaan bukan komersial (dimatikan secara lalai). Sebelum kerja berbayar atau untuk pelanggan,
  semak lajur **Commercial?** dalam [THIRD_PARTY.md](THIRD_PARTY.md).
  Model masa perkataan untuk audio sumber fr / de / es / it (CC BY-NC 4.0) juga bukan komersial dan meminta persetujuan pada penggunaan pertama.

## Bantuan dan sokongan

Soalan, idea dan hasil anda: [forum perbincangan](https://github.com/alexturkey/dubworld/discussions). Masalah pemasangan: [laporkan masalah pemasangan](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); pepijat: [laporkan pepijat](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(tulis sistem pengendalian, GPU, arahan yang dijalankan dan beberapa baris terakhir output). Isu keselamatan: lihat SECURITY.md, jangan tulis dalam isu awam.

## Lesen dan penghargaan

Kod: Apache-2.0 (LICENSE). Komponen pihak ketiga dan lesennya: THIRD_PARTY.md. Penggunaan bertanggungjawab: ETHICS.md.
Privasi (apa yang kekal di komputer anda, apa yang diterima bahagian belakang awan): PRIVACY.md. Laporan keselamatan: SECURITY.md. Perubahan: CHANGELOG.md.

<!-- i18n-source: README.md sha256:bb424df69aff -->
