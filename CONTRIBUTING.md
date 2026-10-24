# Katkı / Contributing

**TR** aşağıda, **EN** below.

## TR

Hoş geldin. Hat, yerel bir videoyu baştan sona dublajlar: kaynak → transkript (STT) → kelime zamanı → çeviri →
seslendirme (TTS) → zaman uydurma → altyazı → video. Her adım değiştirilebilir bir motordur; en değerli katkılar yeni
bir motor, daha iyi bir istem ya da gerçek donanımda ölçülmüş bir sonuçtur.

### Başlarken

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
python -m pip install --no-deps -e .         # yalnız paket; birim testleri standart kütüphaneyle koşar (CI ile aynı)
python -m pip install pytest ruff pre-commit
pre-commit install                           # her commit'te hızlı denetim
python -m pytest -m "not gpu and not slow"   # CI ile aynı CPU testleri
ruff check --select E9,F63,F7,F82 src tests  # CI'yi durduran kurallar
python scripts/belge_dogrula.py              # belgelerdeki bağlantı/yol/komut/ayar/ortam değişkeni koda uyuyor mu
```

Tam hat (gerçek video ile deneme) için `scripts/kur.ps1`: Python 3.11.14, hash'li kilit dosyası
(`requirements/gpu.txt` ya da `cpu.txt`), modeller ve ffmpeg sabit sürüm + sha256 ile repo klasörüne kurulur.
Kilit dosyalarını elle değiştirme; `requirements/*.in` değişir, kilit yeniden üretilir ve PR'da ikisi birlikte gelir.

### Kod düzeni

Paket `src/dublaj_hatti/`, klasörler akış sırasıyla numaralı (`bolum_10_kaynak_edinme` … `bolum_80_arayuz_ve_teslim`).
Aşamaların listesi ve sırası `bolum_00_omurga/core/asama_sozlesmesi.py` içindedir; ana akış
`bolum_00_omurga/core/dubber.py`. Bütün varsayılanlar tek yorumlu dosyadadır: `src/dublaj_hatti/varsayilan.toml` (kullanıcı
üstü `ayarlar/kullanici.toml`, git dışı). Yeni bir ayar eklerken yorumuyla oraya yaz; CLI, masaüstü ve web arayüzü
oradan okur.

### Yeni STT (transkript) motoru eklemek

1. `src/dublaj_hatti/bolum_20_transkripsiyon/<ad>_motoru/` klasörü aç: `__init__.py`, `README.md` (ne, lisans,
   donanım), motoru çalıştıran modül (örnek: `faster_whisper_motoru/worker.py`).
2. Ağır ya da ayrı ortam isteyen motorun adaptörü `bolum_00_omurga/runtime/<ad>_runtime.py` içine gider (örnek:
   `whisperx_runtime.py`); alt süreçler pencere açmaz (Windows'ta `CREATE_NO_WINDOW`).
3. Çıktı, diğer motorlarla aynı segment ve kelime zamanı biçimidir; kelime zamanı yoksa CTC hizalama adımı doldurur.
4. Motoru seçilebilir yap: `src/dublaj_hatti/kayit.py` içindeki `MOTORLAR` listesine bir `Motor("stt", "<ad>", ...)`
   satırı ekle (lisans, resmî kaynak, kurulum adımı, kurulu mu denetimi). Ayar şeması, `dubla kontrol`, masaüstü ve
   web arayüzü seçeneği oradan alır. Çalıştırma noktası: `dubber.py` içinde `_transcribe_<ad>` dalı.
5. Python bağımlılığını `pyproject.toml` içinde kendi `stt-<ad>` grubuna ve `requirements/ek_<ad>.in` dosyasına ekle; ağırlıkları `scripts/kur.ps1`'e sabit
   commit + sha256 ile ekle, repoya koyma.
6. `docs/motorlar/<ad>.md` yaz (ne, lisans, donanım, kurulum, ayarlar) ve `THIRD_PARTY.md`'ye resmî kaynak
   bağlantısıyla satır ekle.

### Yeni çeviri arka ucu eklemek

1. LLM tabanlı arka uç: `src/dublaj_hatti/bolum_40_ceviri/llm_kopru/backends/<ad>/` altında `backend_config.json`
   (model, effort, zaman aşımı), `output_schema*.json` (dönen JSON şeması) ve `prompt.md` / `prompts/` (örnek:
   `codex_exec/`). Sonuç `llm_kopru/shared_result_contract` biçimine uymalıdır.
2. Arka ucu `kayit.py` içindeki `MOTORLAR` listesine (`Motor("ceviri", ...)`) ve `bolum_40_ceviri/arka_uc_secimi.py`
   içindeki `KOPRU_ADI` eşlemesine ekle; API anahtarı gerekiyorsa
   `API_ANAHTARI_DEGISKENLERI`'ne ortam değişkeni adıyla (anahtarın kendisi asla repoya girmez). Otomatik sıra
   (codex → claude → yerel) yalnız tartışılarak değişir.
3. Yerel (çevrimdışı) model: `bolum_40_ceviri/yerel_ceviri/` örneğini izle; model kur betiğinde sabit commit + sha256.
4. Görünen ad: `bolum_40_ceviri/gorunum_adlari.py`. Belge: `docs/motorlar/<ad>.md`.

### Yeni TTS (seslendirme) motoru eklemek

1. `src/dublaj_hatti/bolum_50_seslendirme/<ad>_tts/` klasörü (örnek: `supertonic_tts/`).
2. `bolum_50_seslendirme/tts_orkestratoru/` motoru segment listesiyle çağırır; her segment için bir ses dosyası ve
   süresi döner, zaman uydurma (atempo) ortak adımdır.
3. Seçim: `kayit.py` içindeki `MOTORLAR` listesine `Motor("tts", "<ad>", ...)` satırı; çalıştırma noktası
   `tts_orkestratoru/service.py` içindeki `build_dubbed_audio` dalı.
4. Gerçek bir kişinin sesini taklit eden, ses klonlayan ya da resmî olmayan bir motor kabul edilmez (`ETHICS.md`).

### İstem (prompt) değiştirmek ya da eklemek

İstemler arka ucun klasöründedir (`llm_kopru/backends/<ad>/prompt.md`, `prompts/`; Claude için
`bolum_40_ceviri/claude_code_cli/backends/claude_code_cli/`). Ortak katman: `llm_kopru/prompt_katmani/`. İstem
değişikliğinde çıktı şeması bozulmamalı; PR'a aynı girdinin önceki ve sonraki çevirisinden kısa bir örnek ekle
(telifli metin değil, kendi cümlen).

### Kurallar

- Ağırlık, model, video, ses kaydı ya da ikili dosya PR'a girmez; her indirme resmî kaynaktan, sabit sürüm + sha256.
- Kişisel yol, ad, e-posta, hesap adı, API anahtarı kodda, testte ve günlükte yer almaz.
- Testler GPU'suz koşmalı; GPU ya da model isteyen test `@pytest.mark.gpu` / `@pytest.mark.slow` ile işaretlenir.
- Davranışı değiştiren her değişiklik `CHANGELOG.md` "Unreleased" bölümüne yazılır; sürümler SemVer.
- Davranış kuralları: `CODE_OF_CONDUCT.md`. Güvenlik açığı: herkese açık issue yerine `SECURITY.md`.

## EN

Welcome. The pipeline dubs a local video end to end: source → transcript (STT) → word timing → translation → TTS →
timing fit → subtitles → video. Every stage is a swappable engine; the most valuable contributions are a new engine,
a better prompt, or a result measured on real hardware.

### Getting started

```bash
python -m venv .venv
python -m pip install --no-deps -e .         # package only; unit tests need just the standard library (same as CI)
python -m pip install pytest ruff pre-commit
pre-commit install
python -m pytest -m "not gpu and not slow"   # same CPU tests as CI
ruff check --select E9,F63,F7,F82 src tests  # rules that fail CI
python scripts/belge_dogrula.py              # docs vs code: links, paths, commands, settings, env vars
```

Full pipeline (real video runs): `scripts/kur.ps1` installs Python 3.11.14, the hash-locked profile
(`requirements/gpu.txt` or `cpu.txt`), models and ffmpeg pinned (version + sha256) inside the repo folder. Do not edit
lock files by hand; change `requirements/*.in`, regenerate the lock and commit both.

### Layout

Package `src/dublaj_hatti/`, folders numbered in pipeline order. Stage list: `bolum_00_omurga/core/asama_sozlesmesi.py`;
main flow: `bolum_00_omurga/core/dubber.py`. All defaults live in one commented file, `src/dublaj_hatti/varsayilan.toml`
(user overrides in `ayarlar/kullanici.toml`, git-ignored); CLI, desktop and web UI read it.

### Adding an STT engine

Create `bolum_20_transkripsiyon/<name>_motoru/` (`__init__.py`, `README.md`, runner module, see
`faster_whisper_motoru/`); put heavy/separate-env adapters in `bolum_00_omurga/runtime/<name>_runtime.py`; emit the
common segment + word-timing format; add a `stt-<name>` extra in `pyproject.toml`, pinned weights in
`scripts/kur.ps1`, `docs/motorlar/<name>.md` and a `THIRD_PARTY.md` row with the official source. Registration: add a
`Motor("stt", "<name>", ...)` entry to `MOTORLAR` in `src/dublaj_hatti/kayit.py` (license, official source, install
step, installed check); the config schema, `dubla kontrol` and both interfaces read it. Entry point: a
`_transcribe_<name>` branch in `dubber.py`.

### Adding a translation backend

LLM backends live in `bolum_40_ceviri/llm_kopru/backends/<name>/` (`backend_config.json`, `output_schema*.json`,
`prompt.md` / `prompts/`, see `codex_exec/`) and must return the `shared_result_contract` shape. Register the name in
`kayit.py` (`MOTORLAR`) and `KOPRU_ADI` (`bolum_40_ceviri/arka_uc_secimi.py`) and its API-key environment variable in
`API_ANAHTARI_DEGISKENLERI`; keys never enter the repo. Offline models follow `bolum_40_ceviri/yerel_ceviri/`.

### Adding a TTS engine

Create `bolum_50_seslendirme/<name>_tts/` (see `supertonic_tts/`); `tts_orkestratoru/` calls it per segment and the
shared timing-fit step (atempo) follows. Registration: a `Motor("tts", "<name>", ...)` entry in `kayit.py`;
entry point: the `build_dubbed_audio` branch in `tts_orkestratoru/service.py`. No voice cloning, no imitation of real people, no unofficial engines (`ETHICS.md`).

### Changing or adding prompts

Prompts sit next to their backend (`llm_kopru/backends/<name>/prompt.md`, `prompts/`; Claude:
`bolum_40_ceviri/claude_code_cli/backends/claude_code_cli/`), shared layer `llm_kopru/prompt_katmani/`. Keep the output
schema valid and add a short before/after translation of your own sentence to the PR.

### Rules

No weights, media or binaries in PRs; every download official and pinned (version + sha256). No personal paths,
names, e-mails, accounts or API keys anywhere. Tests run without a GPU; mark others `gpu` / `slow`. Behaviour changes
go into `CHANGELOG.md` under "Unreleased"; versions follow SemVer. Conduct: `CODE_OF_CONDUCT.md`. Security issues:
`SECURITY.md`, not public issues.
