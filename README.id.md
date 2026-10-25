# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · Bahasa Indonesia · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · [ไทย](README.th.md) · [বাংলা](README.bn.md) · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md) · [Azərbaycanca](README.az.md) · [Bahasa Melayu](README.ms.md)

> DubWorld men-dubbing video Anda ke bahasa lain langsung di komputer Anda sendiri, tanpa mengunggahnya ke layanan online mana pun: ucapan diubah menjadi teks lengkap dengan waktu setiap kata, diterjemahkan, lalu dibacakan oleh suara buatan (AI) yang tetap selaras dengan video aslinya (ucapan dipercepat paling banyak 1,25 kali, sisa selisihnya diserap dengan sedikit mengubah tempo video), diberi subtitle, dan jadilah video baru. Bahasa bawaannya Turki; bahasa Indonesia dan bahasa lain bergantung pada mesin suara yang dipilih ([docs/diller.md](docs/diller.md)).

## Biarkan asisten AI Anda yang memasangnya

Tidak perlu bisa pemrograman. Buka asisten AI yang bisa menjalankan perintah di komputer Anda (Claude Code, Codex,
Gemini CLI, atau yang serupa) lalu tempelkan satu kalimat ini:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

Asisten akan memeriksa komputer Anda (kartu grafis, prosesor, memori, disk) dan hanya bertanya sekali, dengan bahasa
sederhana, pemasangan seperti apa yang Anda mau: cepat, sesuai saran untuk komputer Anda, atau lengkap. Ia menjelaskan setiap
komponen (fungsinya, ruang disk yang dipakai, lama pemasangan, lisensinya) dan, mulai dari suara bawaan, menanyakan apakah Anda
menyetujui syarat penggunaan komponen yang dipilih. Setelah itu ia memasang, membuat contoh dubbing, dan membuka jendela program.
Langkah pertama dan masalah yang sering muncul, dengan bahasa sederhana (dalam bahasa Inggris): **[docs/getting-started.md](docs/getting-started.md)**.

**Ringkasan lisensi:** kode Apache-2.0. Model bawaan: suara Supertonic 3 di bawah OpenRAIL-M (ada batasan penggunaan, disetujui sekali); Opus-MT dan model waktu kata bahasa Turki di bawah CC BY 4.0 (wajib mencantumkan atribusi, NOTICE); build FFmpeg GPL-3.0 (program terpisah). Hanya untuk penggunaan non-komersial dan nonaktif secara bawaan: CrisperWhisper 2.0, XTTS-v2, serta model waktu kata WhisperX untuk fr / de / es / it. Repositori ini tidak berisi bobot model apa pun ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Pemasangan cepat

Windows 10/11 x64; tidak perlu Python, CUDA, atau ffmpeg terpasang sebelumnya. Klik dua kali **`kur.cmd`** (atau jalankan
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); profil GPU atau CPU dipilih otomatis
(`-Cpu` memaksa CPU). Setelah itu klik dua kali `arayuz.cmd` untuk membuka aplikasi.
Semuanya tetap berada di dalam folder repositori (`.venv`, `runtime_assets/`); setiap unduhan dikunci versinya dan
diperiksa dengan sha256. Ruang kosong untuk mulai: 22 GB dengan profil GPU, 14 GB hanya CPU; pemakaian terukur setelah pemasangan ≈ 14,6 GB (GPU, file hard link dihitung sekali; File Explorer menampilkan ≈ 22 GB). Pemeriksaan: `.venv\Scripts\dubla.exe kontrol`.

Kebutuhan, urutan langkah, peta lingkungan Python, mesin opsional, penggunaan offline, pembaruan, penghapusan, dan
galat yang sering muncul (dalam bahasa Inggris): **[docs/installation.md](docs/installation.md)**. Linux dan macOS belum kami uji. Contoh: [tur produk yang disulihsuarakan ke bahasa Inggris, Turki, dan Arab di Mac Apple M4, hanya dengan CPU](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Cara pakai

Aplikasi desktop: klik dua kali `arayuz.cmd` (aplikasi web lokal: `web.cmd`, hanya di 127.0.0.1). Antarmuka aplikasi saat ini berbahasa Turki. Dari baris perintah:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Untuk dubbing ke bahasa Indonesia gunakan `--ayar genel.hedef_dil=id` (terjemahan ke bahasa Indonesia memerlukan Codex atau Claude Code). Hasilnya masuk ke `cikti/<video>_<time>/`: `dubbed_tr.mp4` (dengan tag `AI-dubbed`), subtitle asli `transcript_<lang>.srt`, dan file kerja JSON; baris terakhir `dubbed_video:` menunjukkan lokasinya. Semua pengaturan (dalam bahasa Inggris dan Turki): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Cara kerjanya

1. **Audio:** FFmpeg mengambil suaranya; Demucs (MIT) opsional memisahkan ucapan dari latar belakang.
2. **Ucapan ke teks:** faster-whisper large-v3-turbo (MIT) dengan waktu kata wav2vec2 CTC (Inggris MIT, Turki CC BY 4.0); CrisperWhisper 2.0 opsional (non-komersial) dan mesin lain.
3. **Pembicara:** 3D-Speaker CAM++ (Apache-2.0) dan model pengenal jenis kelamin (Apache-2.0) memilih satu suara AI untuk setiap pembicara.
4. **Terjemahan:** Codex CLI atau Claude Code CLI jika terpasang dan sudah login, jika tidak Opus-MT lokal Inggris ke Turki (CC BY 4.0); backend API bersifat opsional.
5. **Suara dan waktu:** Supertonic 3 bawaan (OpenRAIL-M), VoxCPM2 (Apache-2.0) atau XTTS-v2 (non-komersial) opsional; setiap baris dipercepat paling banyak 1,25 kali menuju waktu segmen aslinya, sisanya diatur lewat waktu video, jadi hasil dubbing bisa lebih panjang dari aslinya.
6. **Video:** FFmpeg menulis suara baru, subtitle SRT / VTT / ASS, dan tag `AI-dubbed`.

## Pengukuran

Komputer acuan: GPU Pascal 4 GB, Windows 10; metode dan semua baris ada di [docs/olcumler.md](docs/olcumler.md).

| Apa | Profil CPU | Profil GPU |
|---|---|---|
| Pemasangan pertama, langkah bawaan, dari awal sampai akhir | ≈ 38 menit | ≈ 44 menit (paket 13,7 menit) |
| Disk setelah pemasangan | ≈ 13,2 GB (jumlah folder) | ≈ 14,6 GB (hard link dihitung sekali) |
| Contoh dubbing 9 detik, terjemahan offline | 528 detik | 376 detik |
| Klip bahasa Inggris 30 detik, Demucs, terjemahan Claude Code | – | 744 detik |

## Batasan

- Tanpa CrisperWhisper (mesin opsional 13), faster-whisper bisa melewatkan ucapan atau mengarang teks yang tidak pernah diucapkan dalam bahasa Mandarin dan Jepang (pernah terlihat: ≈ 10 detik pertama sebuah klip Mandarin hilang; sebuah teriakan menjadi baris "ああ…" yang panjang).
- CI hanya menguji CPU; jalur GPU dijalankan manual di kartu Pascal 4 GB. Kartu baru (RTX 50), Linux, dan macOS belum diuji; pustaka GPU yang dipasang memuat kernel dari Pascal sampai RTX 50, dan Maxwell memakai profil CPU ([tabel dukungan GPU, dalam bahasa Inggris](docs/installation.md#1-system-requirements)).
- Penerjemah offline hanya bisa Inggris ke Turki; pasangan bahasa lain membutuhkan Codex / Claude Code CLI atau backend API.
- Waktu kata untuk bahasa sumber selain Inggris dan Turki: Jepang dan Mandarin lewat `scripts/kur.ps1 -Adim hizalama-diller`, bahasa lain setelah sekali dijalankan dengan `DUBLAJ_CEVRIMICI=1`.
- Belum diuji dari awal sampai akhir: pemasangan XTTS-v2 sungguhan, RVC, bot Telegram yang terhubung ke layanan sungguhan, dan CrisperWhisper 2 Medium; Moonshine masih eksperimen. CrisperWhisper 2.0 Turbo (mesin 13) sudah diuji dengan audio sungguhan di GTX 1050 Ti 4 GB (tr, en, ja; ≈ 1,4 GB VRAM).

## Blok penyusun

Setiap tahap bisa dijalankan sendiri, dari baris perintah atau dari Python, dan format file antartahap terdokumentasi
(peta tahap dan JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` menyediakan tahap yang sama dalam bentuk fungsi. Pasang hanya yang dibutuhkan suatu tahap, misalnya
`pip install -e ".[stt,hizalama,cpu]"` untuk subtitle. Lima alat kecil yang dibangun dari blok ini: [examples/](examples/).

## Keluarga / proyek terkait

| Repositori | Apa itu | Bagaimana repositori ini memakainya |
|---|---|---|
| **DubWorld** (repositori ini) | Pipeline dubbing video yang sepenuhnya lokal, setiap tahap juga bisa dipakai terpisah | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | Ucapan ke teks kata demi kata dengan waktu kata (CrisperWhisper 2.0 Turbo + penyelarasan CTC) | Mesin opsional 13: `scripts/kur.ps1 -Adim crisper` memasang model lewat repositori itu pada commit tetap (bobot **non-komersial**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | Desain suara dan pembacaan dengan VoxCPM2, 8 bahasa, suara siap pakai | Mesin suara opsional `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` memasang pada commit tetap; repositori ini memanggilnya lewat adaptor tipis |

Setiap repositori pendamping punya lisensi, cara pemasangan, dan issue sendiri; commit tetap membuat gabungan ini bisa dibangun ulang dengan hasil yang sama.

## Penggunaan yang bertanggung jawab

> **Pemberitahuan hukum.** Anda sepenuhnya bertanggung jawab atas konten yang Anda proses dan terbitkan dengan perangkat lunak
> ini, serta atas kepatuhan pada hukum negara Anda dan syarat situs maupun layanan yang Anda gunakan. Perangkat lunak ini
> diberikan "apa adanya", tanpa jaminan apa pun (Apache-2.0). Teks lengkap: [ETHICS.md](ETHICS.md).

- **Hak dan persetujuan.** Proseslah hanya konten milik Anda atau yang Anda berhak terjemahkan dan dubbing ulang,
  dan mintalah persetujuan orang yang bisa dikenali di dalamnya.
- **Suara.** Tidak boleh meniru siapa pun. Suara referensi hanya boleh suara Anda sendiri atau suara orang yang sudah memberi izin jelas.
- **Beri label.** Hasilnya memuat tag metadata `AI-dubbed`; biarkan tetap ada, dan beri tahu penonton Anda dengan cara yang
  mudah terlihat bahwa dubbing dibuat dengan AI (EU AI Act Pasal 50; lisensi Supertonic).
- **Unduhan.** Ekstra opsional `youtube` (yt-dlp) dan `galeri` (gallery-dl) hanya untuk konten milik Anda atau yang boleh Anda unduh; syarat situs dan
  hukum setempat Anda tetap berlaku.
- **Mesin non-komersial.** CrisperWhisper 2.0 dan XTTS-v2 hanya untuk penggunaan non-komersial (nonaktif secara bawaan). Sebelum pekerjaan berbayar atau untuk klien,
  periksa kolom **Commercial?** di [THIRD_PARTY.md](THIRD_PARTY.md).
  Model waktu kata untuk audio sumber fr / de / es / it (CC BY-NC 4.0) juga non-komersial dan meminta persetujuan saat pertama kali dipakai.

## Bantuan dan dukungan

Pertanyaan, ide, dan hasil Anda: [forum diskusi](https://github.com/alexturkey/dubworld/discussions). Masalah pemasangan: [laporkan masalah pemasangan](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); bug: [laporkan bug](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(tuliskan sistem operasi, GPU, perintah yang dijalankan, dan baris terakhir keluarannya). Masalah keamanan: lihat SECURITY.md, jangan ditulis di issue publik.

## Lisensi dan atribusi

Kode: Apache-2.0 (LICENSE). Komponen pihak ketiga dan lisensinya: THIRD_PARTY.md. Penggunaan yang bertanggung jawab: ETHICS.md.
Privasi (apa yang tetap di komputer Anda, apa yang diterima backend cloud): PRIVACY.md. Laporan keamanan: SECURITY.md. Perubahan: CHANGELOG.md.

<!-- i18n-source: README.md sha256:08d5cfa0c4f9 -->
