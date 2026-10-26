"""Motor kaydı: hattın seçilebilir her motoru (transkripsiyon, çeviri, seslendirme, isteğe bağlı ekler) tek yerde.

Bu kayıt; ayar şemasının seçenek listelerini, `dubla kontrol` çıktısını, arayüzlerin seçeneklerini ve belge
tablolarını besler. Yeni motor eklemek (CONTRIBUTING.md "Yeni motor"):
  1. motor kodunu ilgili `bolum_*` klasörüne koy,
  2. buraya bir `Motor` satırı ekle (ad, lisans, kaynak, kurulum adımı, kurulu mu denetimi),
  3. `bolum_00_omurga/core/dubber.py` içinde motor adına göre dalı ekle (çalıştırma noktası),
  4. `docs/motorlar/<ad>.md` sayfasını yaz, THIRD_PARTY.md'ye satır ekle.

Donanım ve dil alanları (`cihaz`, `vram_mb`, `cpu`, `bellek`, `kanit`, `diller`) aşağıdaki `_DONANIM_DIL` tablosundan
gelir; her değerin kaynağı `kanit` alanında ("ölçüldü" / "belgeye göre" / "tahmin") ve docs/donanim.md, docs/diller.md
tablolarında yazılıdır. Ölçümler 4 GB VRAM'li Pascal sınıfı bir GPU'da alınmıştır (docs/engineering/).

`lisans` alanı ağırlığın/hizmetin lisansıdır ve resmî kaynaktan okunur (THIRD_PARTY.md ile aynı, 2026-10-24).
`ticari`: "evet" | "hayır" | "şartlı" (kullanım kısıtı ya da yükümlülük var) | "hizmet şartları" (bulut).
Ticari olmayan ya da şartlı motorun ilk kullanımında gösterilecek metin tek yerde: `lisans_uyarisi(ad)`.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Callable
from dataclasses import dataclass, field, replace


def _modul(ad: str) -> Callable[[], bool]:
    return lambda: importlib.util.find_spec(ad) is not None


def _ortam(*degiskenler: str) -> Callable[[], bool]:
    return lambda: any(os.environ.get(d, "").strip() for d in degiskenler)


# Bulut STT motorlarının okuduğu anahtar adları (motorun kendi config.py'si ile aynı; test eşitliği denetler).
STT_API_ANAHTARLARI: dict[str, tuple[str, ...]] = {
    "elevenlabs_scribe_v2": ("ELEVENLABS_API_KEY",),  # elevenlabs_scribe_v2_motoru/config.py
}


def _ceviri_anahtari(ad: str) -> Callable[[], bool]:
    """Çeviri API anahtarı: tek kaynak köprünün okuduğu adlar (arka_uc_secimi.API_ANAHTARI_DEGISKENLERI)."""

    def denetle() -> bool:
        from dublaj_hatti.bolum_40_ceviri.arka_uc_secimi import api_anahtari_var

        return api_anahtari_var(ad)

    return denetle


def _crisper() -> bool:
    from dublaj_hatti.yapilandirma import crisper_turbo_kurulu

    return crisper_turbo_kurulu()


def _konusmaci() -> bool:
    from dublaj_hatti.yapilandirma import konusmaci_modelleri_kurulu

    return konusmaci_modelleri_kurulu()


def _voxcpm2() -> bool:
    from dublaj_hatti.bolum_50_seslendirme.voxcpm2_tts import voxcpm2_durumu

    return bool(voxcpm2_durumu()["kurulu"])


def _ema() -> bool:
    from dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts import ema_durumu

    return bool(ema_durumu()["kurulu"])


def _xtts() -> bool:
    from dublaj_hatti.bolum_50_seslendirme.xtts_tts import xtts_durumu

    return bool(xtts_durumu()["kurulu"])


def _rvc() -> bool:
    from dublaj_hatti.bolum_50_seslendirme.rvc_ses_donusturme import rvc_durumu

    return bool(rvc_durumu()["kurulu"])


def _parakeet() -> bool:
    """Paket (sherpa-onnx) ve model dosyaları (kur.ps1 -Adim parakeet; scripts/modeller.json adım `parakeet`)."""
    if importlib.util.find_spec("sherpa_onnx") is None:
        return False
    from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import parakeet_unified_en_int8_model_dir

    kok = parakeet_unified_en_int8_model_dir()
    return all((kok / ad).is_file() for ad in PARAKEET_MODEL_DOSYALARI)


PARAKEET_MODEL_DOSYALARI = ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt")


def _faster_whisper_ctc() -> bool:
    """faster-whisper + CTC kutusunun Python'u (WhisperX) + sabit CTC modelleri en/tr (kur.ps1 -Adim modeller)."""
    if importlib.util.find_spec("faster_whisper") is None:
        return False
    if not os.environ.get("DUBLAJ_WHISPERX_PYTHON", "").strip() and importlib.util.find_spec("whisperx") is None:
        return False
    from dublaj_hatti.bolum_00_omurga.runtime.ctc_model_durumu import kontrol_ozeti

    return all(kontrol_ozeti().values())


def _galeri() -> bool:
    from dublaj_hatti.bolum_10_kaynak_edinme.adim_20_kaynak_alma.galeri_indirici import galeri_kurulu

    return galeri_kurulu()


def _cli(degisken: str, komut: str) -> Callable[[], bool]:
    def denetle() -> bool:
        import shutil

        return bool(os.environ.get(degisken, "").strip() or shutil.which(komut))

    return denetle


@dataclass(frozen=True)
class Motor:
    tur: str  # stt | ceviri | tts | ek
    ad: str  # ayar değeri (ör. transkripsiyon.motor = "faster-whisper")
    gorunen_ad: str
    lisans: str
    ticari: str
    kaynak: str  # resmî kaynak (model kartı / proje sayfası)
    kurulum: str  # scripts/kur.ps1 adımı ya da kısa yol
    cihaz: str  # gpu | cpu | gpu+cpu | bulut
    kurulu: Callable[[], bool] = field(compare=False, repr=False, default=lambda: False)
    not_: str = ""
    bellek: str = ""  # tepe bellek / donanım notu, kaynağıyla (docs/donanim.md)
    vram_mb: int = 0  # GPU'da tepe VRAM (MB); 0 = GPU kullanmaz ya da bilinmiyor
    cpu: str = ""  # işlemcide: iyi | çalışır | yavaş | çalışmaz | bulut
    kanit: str = ""  # vram_mb / cpu değerinin dayanağı: ölçüldü | belgeye göre | tahmin
    diller: frozenset[str] | None = None  # stt: kaynak dilleri, tts/çeviri: hedef dilleri; None = çok dilli
    dil_notu: str = ""
    deneysel: str = ""  # boş değilse motor DENEYSEL: bilinen sınırın kısa gerekçesi (arayüz etiketi + ayar uyarısı)
    # Motor bilgi satırı (arayüz "Motorlar" seçicisi API ile okur; stt ve tts motorları için zorunlu, test denetler)
    ticari_kullanim: bool = False  # lisans ticari kullanıma izin veriyor mu (şartlı = evet, şartı THIRD_PARTY.md'de)
    donanim_metni: str = ""  # kısa donanım gereği (İngilizce, arayüz çevirisi ayrı)
    diller_metni: str = ""  # kısa dil kapsamı (İngilizce)
    guc_tr: str = ""  # tek satır: motorun güçlü yanı (Türkçe)
    guc_en: str = ""  # one line: the engine's strength (English)

    @property
    def belge(self) -> str:
        return f"docs/motorlar/{self.ad}.md"


# --- dil listeleri (kaynakları docs/diller.md) ----------------------------------------------------------------
# Supertonic 3: bolum_50_seslendirme/supertonic_tts/runtime.py AVAILABLE_LANGS ("na" hariç; test eşitliği denetler)
SUPERTONIC_DILLERI = frozenset({
    "ar", "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr", "hi", "hr", "hu", "id", "it", "ja", "ko",
    "lt", "lv", "nl", "pl", "pt", "ro", "ru", "sk", "sl", "sv", "tr", "uk", "vi",
})
# VoxCPM2: ses tasarımı (kardeş) reposunda uçtan uca denenmiş diller; başka dil okunur ama denenmedi (uyarı)
VOXCPM2_DENENEN_DILLER = frozenset({"tr", "en", "fr", "de", "es", "ru", "zh", "ja"})
# EMA Lightning: yalnız Türkçe (model kartı "Limitations"; ema_lightning_tts/ayarlar.py EMA_DILLERI ile aynı)
EMA_DILLERI = frozenset({"tr"})
# XTTS v2: model kartı (huggingface.co/coqui/XTTS-v2) dilleri; bolum_50_seslendirme/xtts_tts/api.py XTTS_DILLERI
XTTS_DILLERI = frozenset({"en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh", "ja", "hu",
                          "ko", "hi"})
# Hedef dil seçicilerinde (Önerilen sekmesi, düğme "<Dil> dublajla") dilin kendi dilindeki adı; tts_hedef_dilleri()
# içindeki her kodun burada adı olmalı (tests/test_hedef_dil_secici.py). Bilinmeyen kod arayüzde kodun kendisiyle görünür.
DIL_KENDI_ADLARI: dict[str, str] = {
    "ar": "العربية", "bg": "Български", "cs": "Čeština", "da": "Dansk", "de": "Deutsch", "el": "Ελληνικά",
    "en": "English", "es": "Español", "et": "Eesti", "fi": "Suomi", "fr": "Français", "hi": "हिन्दी",
    "hr": "Hrvatski", "hu": "Magyar", "id": "Bahasa Indonesia", "it": "Italiano", "ja": "日本語", "ko": "한국어",
    "lt": "Lietuvių", "lv": "Latviešu", "nl": "Nederlands", "pl": "Polski", "pt": "Português", "ro": "Română",
    "ru": "Русский", "sk": "Slovenčina", "sl": "Slovenščina", "sv": "Svenska", "tr": "Türkçe", "uk": "Українська",
    "vi": "Tiếng Việt", "zh": "中文",
}


def dil_kendi_adi(kod: str) -> str:
    """Dil kodunun kendi dilindeki adı ("de" → "Deutsch"); tabloda yoksa kodun kendisi."""
    return DIL_KENDI_ADLARI.get(kod, kod)


def dublajla_etiketi(kod: str, arayuz: str | None = None) -> str:
    """Önerilen sekmesindeki ana düğmenin yazısı, arayüz dilinde tam cümle ("Almanca dublajla", "Dub into German")."""
    from dublaj_hatti import arayuz_dili

    return arayuz_dili.t("dugme.dublajla", arayuz, hedef=arayuz_dili.dil_adi(kod, arayuz))
# VoxCPM2 hazır sesleri (kardeş repo hazir_sesler/, sabit commit; açıklamalar docs/sesler.md)
VOXCPM2_HAZIR_SESLER = (
    "haber_spikeri", "cekici_spiker", "belgesel_hanim", "gizemli_bilge", "tok_anlatici", "yasli_bilge",
    "masal_cadisi", "anlatici_en", "anlatici_fr", "anlatici_de", "anlatici_es", "anlatici_ru", "anlatici_zh",
    "anlatici_ja",
)
# hazır seslerin cinsiyeti (ses.json tarifinden); cinsiyete göre favori listenin dil bazlı varsayılanı bundan
VOXCPM2_HAZIR_CINSIYET = {
    "haber_spikeri": "male", "cekici_spiker": "female", "belgesel_hanim": "female", "gizemli_bilge": "male",
    "tok_anlatici": "male", "yasli_bilge": "male", "masal_cadisi": "female", "anlatici_en": "male",
    "anlatici_fr": "male", "anlatici_de": "male", "anlatici_es": "male", "anlatici_ru": "male",
    "anlatici_zh": "male", "anlatici_ja": "male",
}
# dublaja uygun varsayılan sıra (karakter sesleri masal_cadisi / yasli_bilge listede yok; kullanıcı ekleyebilir)
_VOXCPM2_TR_KADIN = ("belgesel_hanim", "cekici_spiker")
_VOXCPM2_TR_ERKEK = ("haber_spikeri", "tok_anlatici", "gizemli_bilge")


def voxcpm2_varsayilan_havuz(dil: str) -> tuple[list[str], list[str]]:
    """Hedef dile göre hazır seslerden (kadın, erkek) favori listesi; o dilde hazır ses yoksa boş."""
    if dil == "tr":
        return [f"hazir/{a}" for a in _VOXCPM2_TR_KADIN], [f"hazir/{a}" for a in _VOXCPM2_TR_ERKEK]
    ad = f"anlatici_{dil}"
    if ad in VOXCPM2_HAZIR_SESLER:
        kadin = [f"hazir/{a}" for a in VOXCPM2_HAZIR_SESLER if a.endswith(f"_{dil}") and VOXCPM2_HAZIR_CINSIYET[a] == "female"]
        erkek = [f"hazir/{a}" for a in VOXCPM2_HAZIR_SESLER if a.endswith(f"_{dil}") and VOXCPM2_HAZIR_CINSIYET[a] == "male"]
        return kadin, erkek
    return [], []


SUPERTONIC_SESLER = tuple(f"F{i}" for i in range(1, 6)) + tuple(f"M{i}" for i in range(1, 6))
YALNIZ_INGILIZCE = frozenset({"en"})

_HAM_MOTORLAR: tuple[Motor, ...] = (
    # --- transkripsiyon (STT) -------------------------------------------------------------------------
    Motor("stt", "faster-whisper", "faster-whisper (Whisper large-v3-turbo, CTranslate2)", "MIT", "evet",
          "https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo", "varsayılan (modeller)",
          "gpu+cpu", _modul("faster_whisper"),
          "Kelime zamanı Whisper'ın kendisinden (CTC yok); önerilen akışın yedeği faster_whisper_ctc'dir."),
    Motor("stt", "faster_whisper_ctc", "faster-whisper + CTC hizalama (önerilen akışın yedeği)",
          "MIT (faster-whisper); hizalama: tr CC-BY-4.0 (atıf), en MIT (fairseq) (THIRD_PARTY.md)", "evet",
          "https://github.com/SYSTRAN/faster-whisper", "varsayılan (modeller: stt + hizalama)", "gpu+cpu",
          _faster_whisper_ctc, "transkripsiyon.motor=auto CrisperWhisper kullanamazsa bunu seçer."),
    Motor("stt", "whisperx", "WhisperX (faster-whisper + wav2vec2 hizalama)",
          "BSD-2-Clause (kod); modeller MIT / CC-BY-4.0", "evet",
          "https://github.com/m-bain/whisperX", "varsayılan (paketler)", "gpu+cpu", _modul("whisperx")),
    Motor("stt", "crisperwhisper_turbo_ct2", "CrisperWhisper 2.0 Turbo (CT2)",
          "nyra health Non-Commercial Research License (ağırlık); kod MIT", "hayır",
          "https://huggingface.co/nyralabs/CrisperWhisper2.0_turbo", "crisper (-TicariOlmayanKabul)", "gpu",
          _crisper, "WSL2 + NVIDIA gerekir; kelime zamanı en hassas motor."),
    Motor("stt", "parakeet_cpu_align", "Parakeet (sherpa-onnx, yalnız İngilizce) + CTC hizalama",
          "NVIDIA Open Model License (ağırlık); sherpa-onnx Apache-2.0", "şartlı", "https://github.com/k2-fsa/sherpa-onnx",
          "parakeet (paket + model)", "cpu", _parakeet),
    Motor("stt", "elevenlabs_scribe_v2", "ElevenLabs Scribe v2 (bulut)", "hizmet şartları", "hizmet şartları",
          "https://elevenlabs.io", ".env anahtarı", "bulut", _ortam(*STT_API_ANAHTARLARI["elevenlabs_scribe_v2"]),
          "Ses dosyası hizmete gönderilir (PRIVACY.md)."),
    Motor("stt", "youtube_translate", "YouTube json3 altyazı metni + CTC kelime hizalama",
          "kod: yt-dlp Unlicense; metin: videonun otomatik altyazısı (YouTube şartları); hizalama ağırlığı CTC ile aynı",
          "hizmet şartları", "https://github.com/yt-dlp/yt-dlp", "youtube (pip install .[youtube])", "gpu+cpu",
          _modul("yt_dlp"), "Yalnız YouTube bağlantısıyla; ses tanıma çalışmaz, metin altyazıdan gelir.",
          "CTC hizalama kadar: işlemcide ~2 GB RAM (tahmini)"),
    # --- çeviri ---------------------------------------------------------------------------------------
    Motor("ceviri", "yerel", "Opus-MT en→tr (yerel)", "CC-BY-4.0", "evet",
          "https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-tr", "varsayılan (modeller)", "gpu+cpu",
          _modul("transformers"), "Yalnız İngilizce → Türkçe; ağsız çalışır."),
    Motor("ceviri", "codex", "Codex CLI (OpenAI)", "hizmet şartları", "hizmet şartları",
          "https://github.com/openai/codex", "npm i -g @openai/codex ; codex login", "bulut",
          _cli("CODEX_BRIDGE_CODEX_BIN", "codex"), "Metin hizmete gönderilir (PRIVACY.md)."),
    Motor("ceviri", "claude_code", "Claude Code CLI (Anthropic)", "hizmet şartları", "hizmet şartları",
          "https://docs.anthropic.com/en/docs/claude-code", "npm i -g @anthropic-ai/claude-code", "bulut",
          _cli("CODEX_BRIDGE_CLAUDE_CLI", "claude"), "Metin hizmete gönderilir (PRIVACY.md)."),
    Motor("ceviri", "gemini_2_5_flash", "Gemini 2.5 Flash (API)", "hizmet şartları", "hizmet şartları",
          "https://ai.google.dev", ".env anahtarı", "bulut", _ceviri_anahtari("gemini_2_5_flash")),
    Motor("ceviri", "gemini_3_1_flash_lite_tier_1", "Gemini 3.1 Flash Lite (API)", "hizmet şartları",
          "hizmet şartları", "https://ai.google.dev", ".env anahtarı", "bulut", _ceviri_anahtari("gemini_3_1_flash_lite_tier_1")),
    Motor("ceviri", "gemma_4_26b", "Gemma 4 26B (Gemini API)", "hizmet şartları", "hizmet şartları",
          "https://ai.google.dev", ".env anahtarı", "bulut", _ceviri_anahtari("gemma_4_26b")),
    Motor("ceviri", "groq_llama_4_scout", "Llama 4 Scout (Groq API)", "hizmet şartları", "hizmet şartları",
          "https://console.groq.com", ".env anahtarı", "bulut", _ceviri_anahtari("groq_llama_4_scout")),
    Motor("ceviri", "cerebras_llama_3_1_8b", "Llama 3.1 8B (Cerebras API)", "hizmet şartları", "hizmet şartları",
          "https://cloud.cerebras.ai", ".env anahtarı", "bulut", _ceviri_anahtari("cerebras_llama_3_1_8b")),
    Motor("ceviri", "mistral_nemo", "Mistral Nemo (Mistral API)", "hizmet şartları", "hizmet şartları",
          "https://console.mistral.ai", ".env anahtarı", "bulut", _ceviri_anahtari("mistral_nemo")),
    # --- seslendirme (TTS) ----------------------------------------------------------------------------
    Motor("tts", "supertonic", "Supertonic 3", "BigScience Open RAIL-M (kullanım kısıtları, Ek A)", "şartlı",
          "https://huggingface.co/Supertone/supertonic-3", "varsayılan (modeller)", "gpu+cpu",
          _modul("onnxruntime"), "Önerilen akışın sesi; işlemcide de hızlı."),
    Motor("tts", "voxcpm2", "VoxCPM2 (Türkçe ses tasarımı)", "Apache-2.0 (kod ve ağırlık)", "evet",
          "https://github.com/OpenBMB/VoxCPM", "voxcpm2", "gpu", _voxcpm2, "NVIDIA GPU gerekir."),
    Motor("tts", "ema_lightning", "EMA Lightning (Türkçe, tek ses; GPU ya da işlemci ONNX)",
          "Apache-2.0 (kod ve ağırlık)", "evet", "https://huggingface.co/canberkkkkkk/ema-lightning", "tts-ema",
          "gpu+cpu", _ema, "Yalnız Türkçe; ses sentetik (gerçek kişi değil, model kartı). ses.ema_cihaz: auto | cuda | cpu."),
    Motor("tts", "xtts", "XTTS v2 (Coqui, referans sesle)",
          "kod: coqui-tts MPL-2.0; ağırlık: Coqui Public Model License (ticari olmayan); çıktı: CPML'e tabi",
          "hayır", "https://huggingface.co/coqui/XTTS-v2", "tts-xtts (pip install .[tts-xtts]) + CPML onayı",
          "gpu+cpu", _xtts, "Varsayılan kapalı; referans ses yalnız kendi ya da izinli ses; ağırlığı kullanıcı indirir.",
          "GPU ~4 GB VRAM ya da işlemci + 8 GB RAM (yavaş); tahmini, ölçülmedi"),
    # --- isteğe bağlı ekler ---------------------------------------------------------------------------
    Motor("ek", "demucs", "Demucs (konuşma / arka plan ayrıştırma)", "MIT", "evet",
          "https://github.com/facebookresearch/demucs", "demucs", "gpu+cpu", _modul("demucs")),
    Motor("ek", "yt_dlp", "yt-dlp (bağlantıdan indirme)", "Unlicense", "evet",
          "https://github.com/yt-dlp/yt-dlp", "youtube", "cpu", _modul("yt_dlp"),
          "Yalnız hakkınız olan ya da izinli içerik; sitenin kullanım şartları size aittir."),
    Motor("ek", "konusmaci_ayrimi", "3D-Speaker CAM++ (ModelScope) + Silero VAD", "Apache-2.0 / MIT", "evet",
          "https://github.com/modelscope/3D-Speaker", "varsayılan (modeller)", "gpu+cpu",
          _konusmaci),
    Motor("ek", "cinsiyet_siniflandirici", "wav2vec2 XLSR-53 cinsiyet sınıflandırıcı", "Apache-2.0", "evet",
          "https://huggingface.co/alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech",
          "varsayılan (modeller)", "gpu+cpu", _konusmaci, "Eğitim verisi LibriSpeech (CC BY 4.0)."),
    Motor("ek", "segment_cinsiyet_kipi", "Segment bazlı cinsiyet kipi (her cümle ayrı ses)",
          "Apache-2.0 (kod ve ağırlık: alefiury wav2vec2 @7a28165f)", "evet",
          "https://huggingface.co/alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech",
          "varsayılan (modeller)", "gpu+cpu", _konusmaci, "ses.cinsiyet_kipi = segment; konuşmacı ayrımı yapılmaz.",
          "model 1,26 GB; işlemcide ~3 GB RAM (tahmini)"),
    Motor("ek", "akilli_kare", "Akıllı kare (kenar bandı kırpma)", "kod: OpenCV Apache-2.0", "evet",
          "https://github.com/opencv/opencv-python", "akilli-kare (pip install .[akilli-kare])", "cpu",
          _modul("cv2"), "Varsayılan kapalı; yalnız görüntüyü kırpar, ses ve altyazı değişmez.", "~500 MB RAM (tahmini)"),
    Motor("ek", "rvc", "RVC ses dönüştürme (kendi modeliniz)",
          "kod: RVC WebUI MIT; model: kullanıcının (sesin sahibinin rızası zorunlu)", "şartlı",
          "https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI",
          "elle (docs/motorlar/rvc.md; DUBLAJ_RVC_KOK)", "gpu+cpu", _rvc,
          "Varsayılan kapalı; ses.rvc_riza_onayi = true olmadan çalışmaz.", "GPU ~2 GB VRAM önerilir (tahmini)"),
    Motor("ek", "gallery_dl", "gallery-dl (galeri bağlantısından indirme, ayrı süreç)",
          "GPL-2.0-only (yalnız komut satırı alt süreci; içe aktarılmaz)", "evet",
          "https://github.com/mikf/gallery-dl", "galeri (pip install .[galeri])", "cpu", _galeri,
          "Yalnız hakkınız olan ya da izinli içerik; giriş çerezleri yalnız sizin gallery-dl ayarınızda.", "<100 MB RAM"),
    Motor("ek", "kapak_gorseli", "Kapak görseli (Codex CLI görsel üretimi)", "hizmet şartları (OpenAI)",
          "hizmet şartları", "https://github.com/openai/codex", "npm i -g @openai/codex ; codex login", "bulut",
          _cli("CODEX_BRIDGE_CODEX_BIN", "codex"), "Transkript hizmete gönderilir (PRIVACY.md); Codex yoksa atlanır.",
          "yerel yük yok"),
    Motor("ek", "telegram_botu", "Telegram botu (uzaktan kumanda)", "kod: python-telegram-bot LGPL-3.0-only",
          "evet", "https://github.com/python-telegram-bot/python-telegram-bot", "telegram (pip install .[telegram])",
          "cpu", _modul("telegram"), "Varsayılan kapalı; belirteç ve izinli kimlik yalnız .env'de.", "~100 MB RAM"),
)

# --- motor × donanım × dil (K7/K5) ------------------------------------------------------------------------------
# Kaynaklar: docs/engineering/{gpu_memory_and_isolation,transcription,crisperwhisper_turbo_ct2,word_alignment,
# source_audio_and_separation,speakers_and_segments,tts_timing_and_mix,low_vram}.md; VoxCPM2 kardeş repo docs/4gb.md.
# Tablo biçimi ve tam kaynak sütunu: docs/donanim.md. "ölçüldü" = gerçek koşu kaydı; "belgeye göre" = model kartı,
# kod sabiti ya da yazılı kural (koşu kaydı yok); "tahmin" = doğrulanmadı.
_DONANIM_DIL: dict[str, dict] = {
    "faster-whisper": dict(vram_mb=1150, cpu="çalışır", kanit="ölçüldü",
                           bellek="GPU int8 ~1,15 GB / float32 ~3,45 GB VRAM (aynı model WhisperX içinde ölçüldü); "
                                  "işlemcide int8 (hız ölçülmedi)",
                           dil_notu="çok dilli (Whisper large-v3-turbo); distil-* yalnız İngilizce"),
    "faster_whisper_ctc": dict(vram_mb=2400, cpu="çalışır", kanit="ölçüldü",
                               bellek="tanıma ve hizalama sırayla, ayrı süreçte: tanıma GPU int8 ~1,15 GB; CTC 1,65-2,4 GB "
                                      "VRAM (ölçüldü). İşlemcide CTC süresi docs/engineering/timing-sources.md §2.1",
                               dil_notu="çok dilli tanıma; kelime zamanı CTC modeli olan dillerde (sabit: en, tr; "
                                        "diğerleri DUBLAJ_CEVRIMICI=1 ile bir kez; docs/diller.md)"),
    "whisperx": dict(vram_mb=1150, cpu="çalışır", kanit="ölçüldü",
                     bellek="GPU int8 1147 MiB / float32 3451 MiB VRAM (ölçüldü); işlemcide hız ölçülmedi",
                     dil_notu="çok dilli; hizalama modeli dile göre (docs/diller.md)"),
    "crisperwhisper_turbo_ct2": dict(vram_mb=1450, cpu="çalışmaz", kanit="ölçüldü",
                                     bellek="GPU int8 ~1,4 GB VRAM (74 dk seste 1435 MiB, ölçüldü); işlemci yolu yok",
                                     dil_notu="Whisper dilleri; gerçek seste denenen tr, en, ja"),
    "parakeet_cpu_align": dict(vram_mb=0, cpu="iyi", kanit="ölçüldü", diller=YALNIZ_INGILIZCE,
                               bellek="işlemci int8 ~1,9 GB RAM; 96,9 sn ses 11,9 sn, 8 iş parçacığı (ölçüldü)"),
    "elevenlabs_scribe_v2": dict(vram_mb=0, cpu="bulut", kanit="ölçüldü",
                                 bellek="yerel yük yok (bulut); 41,9 dk ses 112 sn (ölçüldü)",
                                 dil_notu="hizmetin dil listesi (language_code ya da otomatik)"),
    "youtube_translate": dict(vram_mb=2400, cpu="yavaş", kanit="ölçüldü",
                              bellek="yalnız CTC hizalama: GPU 1,65-2,4 GB VRAM; işlemcide 3,5 dk ses ~10 dk (ölçüldü)",
                              dil_notu="videonun altyazı izi; CTC hizalama modeli olan diller"),
    "yerel": dict(vram_mb=1000, cpu="çalışır", kanit="tahmin", diller=frozenset({"tr"}),
                  bellek="Opus-MT tc-big (MarianMT); VRAM/RAM ölçülmedi (~1 GB tahmin); CPU duman testi geçti",
                  dil_notu="yalnız İngilizce → Türkçe"),
    "supertonic": dict(cihaz="cpu", vram_mb=0, cpu="iyi", kanit="ölçüldü", diller=SUPERTONIC_DILLERI,
                       bellek="işlemci ~1,8 GB RAM (önbellekle; ölçüldü); ~2,3x gerçek zaman. CUDA sağlayıcısı daha "
                              "yavaş çıktı, kullanılmaz"),
    "voxcpm2": dict(vram_mb=3000, cpu="çalışmaz", kanit="ölçüldü", diller=None,
                    bellek="GPU 2,6-3,0 GB VRAM (Q8_0 GGUF + 4 GB yaması; ölçüldü), 1 sn ses ~2 sn; işlemcide 48,5 sn "
                           "ses 535 sn (ölçüldü) → bu repoda işlemci kapalı",
                    dil_notu="denenen: tr, en, fr, de, es, ru, zh, ja; diğerleri denenmedi (uyarı)"),
    "ema_lightning": dict(vram_mb=200, cpu="iyi", kanit="ölçüldü", diller=EMA_DILLERI,
                          bellek="GPU cihazda 191 MB (PyTorch 94 MB; ölçüldü), 9 sn ses 0,93 sn; "
                                 "işlemci ONNX 12 sn açılış, ~11x gerçek zaman (ölçüldü)",
                          dil_notu="yalnız Türkçe"),
    "xtts": dict(vram_mb=2000, cpu="yavaş", kanit="belgeye göre", diller=XTTS_DILLERI,
                 bellek="model yükü ~2 GB VRAM (kaynak belge; tepe ölçülmedi); işlemcide çok yavaş (tahmin)"),
    "demucs": dict(vram_mb=2750, cpu="yavaş", kanit="ölçüldü",
                   bellek="GPU 2749 MiB VRAM, 75 dk seste süreç ağacı 7,15 GB RAM (ölçüldü); işlemcide yavaş (belge)"),
    "konusmaci_ayrimi": dict(vram_mb=1000, cpu="çalışır", kanit="belgeye göre",
                             bellek="<1 GB VRAM (belge); işlemcide CPU duman testinde çalıştı"),
    "cinsiyet_siniflandirici": dict(vram_mb=1000, cpu="çalışır", kanit="belgeye göre",
                                    bellek="model 1,26 GB; <1 GB VRAM (belge); işlemcide CPU duman testinde çalıştı"),
    "segment_cinsiyet_kipi": dict(vram_mb=1000, cpu="çalışır", kanit="belgeye göre",
                                  bellek="cinsiyet sınıflandırıcıyla aynı: <1 GB VRAM (belge), işlemcide ~3 GB RAM "
                                         "(tahmin)"),
    "akilli_kare": dict(vram_mb=0, cpu="iyi", kanit="tahmin", bellek="yalnız işlemci, ~500 MB RAM (tahmin)"),
    "rvc": dict(vram_mb=2000, cpu="yavaş", kanit="tahmin", bellek="~2 GB VRAM önerilir; işlemcide yavaş (tahmin)"),
    "yt_dlp": dict(vram_mb=0, cpu="iyi", kanit="tahmin", bellek="ağ işi, <100 MB RAM (tahmin)"),
    "gallery_dl": dict(vram_mb=0, cpu="iyi", kanit="tahmin", bellek="ağ işi, <100 MB RAM (tahmin)"),
    "kapak_gorseli": dict(vram_mb=0, cpu="bulut", kanit="belgeye göre", bellek="yerel yük yok (bulut)"),
    "telegram_botu": dict(vram_mb=0, cpu="iyi", kanit="tahmin", bellek="~100 MB RAM (tahmin)"),
}
_BULUT_VARSAYILAN = dict(vram_mb=0, cpu="bulut", kanit="belgeye göre", bellek="yerel yük yok (bulut)")

# --- motor bilgi satırı: lisans (ticari mi), donanım, diller, güçlü yan (TR + EN) ---------------------------------
# Arayüz bunu `motor_bilgisi()` / `motor_bilgileri()` ile okur. Değerlerin kaynağı yukarıdaki Motor satırları,
# docs/donanim.md ve docs/diller.md; yeni stt/tts motoru buraya satır eklemeden testi geçemez.
_BILGI: dict[str, tuple[bool, str, str, str, str]] = {
    "faster-whisper": (True, "CPU or NVIDIA GPU", "Whisper languages (about 99)",
                       "Sağlam, her makinede çalışan temel tanıma; kelime zamanı Whisper'dan.",
                       "Solid baseline recognition that runs on any machine; word times come from Whisper."),
    "faster_whisper_ctc": (True, "CPU or NVIDIA GPU", "Whisper languages; word times for languages with a CTC model",
                           "GPU olmadan da çalışan önerilen akış; kelime zamanı ayrı hizalama modelinden.",
                           "Recommended flow that also runs without a GPU; word times from a separate alignment model."),
    "whisperx": (True, "CPU or NVIDIA GPU", "Whisper languages; alignment model per language",
                 "faster-whisper + wav2vec2 hizalama tek pakette.",
                 "faster-whisper plus wav2vec2 alignment in one package."),
    "crisperwhisper_turbo_ct2": (False, "NVIDIA GPU + WSL2 (no CPU path)", "Whisper languages; tested tr, en, ja",
                                 "Sözcükleri olduğu gibi yazar (dolgu sesleri dahil); en hassas kelime zamanı.",
                                 "Writes words verbatim (fillers included); the most precise word times."),
    "parakeet_cpu_align": (True, "CPU (about 1.9 GB RAM)", "English only",
                           "İngilizce için ölçülmüş en hızlı CPU yolu (96,9 sn ses 11,9 sn).",
                           "The fastest measured CPU path for English (96.9 s of audio in 11.9 s)."),
    "elevenlabs_scribe_v2": (True, "None (cloud, own API key)", "Service language list",
                             "Bulut tanıma; ses hizmete gönderilir.", "Cloud recognition; audio is sent to the service."),
    "youtube_translate": (True, "CPU or NVIDIA GPU (alignment only)", "Languages of the video's subtitle track",
                          "Videonun altyazı metnini kullanır, ses tanıma yapmaz.",
                          "Uses the video's subtitle text, no speech recognition."),
    "supertonic": (True, "CPU (NVIDIA GPU not needed)", "31 languages",
                   "Her makinede hızlı, 31 dil; varsayılan yedek ses.",
                   "Fast on any machine, 31 languages; the default fallback voice."),
    "voxcpm2": (True, "NVIDIA GPU, about 3 GB VRAM", "Tested: tr, en, fr, de, es, ru, zh, ja",
                "Ses tasarımı ve metinsiz ses klonlama; en doğal ses.",
                "Voice design and cloning from audio alone; the most natural voice."),
    "ema_lightning": (True, "CPU or NVIDIA GPU", "Turkish only",
                      "Türkçe için küçük ve hızlı tek ses.", "Small, fast single voice for Turkish."),
    "xtts": (False, "NVIDIA GPU (about 4 GB VRAM) or slow CPU", "17 languages",
             "Referans sesle klonlama (kullanımdan kalkıyor).", "Cloning from a reference voice (being deprecated)."),
}


def _bilgi_ekle(m: Motor) -> Motor:
    b = _BILGI.get(m.ad)
    if b is None:
        return m
    return replace(m, ticari_kullanim=b[0], donanim_metni=b[1], diller_metni=b[2], guc_tr=b[3], guc_en=b[4])


MOTORLAR: tuple[Motor, ...] = tuple(
    _bilgi_ekle(replace(m, **_DONANIM_DIL.get(m.ad, _BULUT_VARSAYILAN if m.cihaz == "bulut" else {})))
    for m in _HAM_MOTORLAR
)


def motorlar(tur: str) -> tuple[Motor, ...]:
    return tuple(m for m in MOTORLAR if m.tur == tur)


def motor(ad: str) -> Motor:
    for m in MOTORLAR:
        if m.ad == ad:
            return m
    raise KeyError(ad)


def motor_bilgisi(ad: str) -> dict[str, object]:
    """Tek motorun arayüz bilgi satırı (JSON'a çevrilebilir): lisans, donanım, diller, güçlü yan (TR + EN)."""
    m = motor(ad)
    return {
        "id": m.ad,
        "kind": m.tur,
        "name": m.gorunen_ad,
        "licence_commercial": m.ticari_kullanim,
        "licence": m.lisans,
        "hardware": m.donanim_metni,
        "languages": m.diller_metni,
        "strength": {"tr": m.guc_tr, "en": m.guc_en},
    }


def motor_bilgileri(tur: str | None = None) -> list[dict[str, object]]:
    """Bilgi satırı olan motorların listesi (tur: stt | tts | None = ikisi)."""
    turler = (tur,) if tur else ("stt", "tts")
    return [motor_bilgisi(m.ad) for t in turler for m in motorlar(t)]


def adlar(tur: str, auto: bool = True) -> list[str]:
    return (["auto"] if auto else []) + [m.ad for m in motorlar(tur)]


def tts_hedef_dilleri() -> list[str]:
    """Arayüzün hedef dil listesi: TTS motorlarının okuyabildiği dillerin birleşimi (VoxCPM2 için denenenler)."""
    return sorted(SUPERTONIC_DILLERI | VOXCPM2_DENENEN_DILLER | XTTS_DILLERI | EMA_DILLERI)


def tts_dil_suzgeci() -> dict[str, dict[str, list[str]]]:
    """Seçili TTS'e göre hedef dil açılır listesi: {"tts": {"izinli": [...], "denenmemis": [...]}}.

    "izinli" dışındaki dil o TTS'te hata verir; "denenmemis" dil seçilebilir ama uyarı verir (VoxCPM2).
    """
    tum = tts_hedef_dilleri()
    return {
        # auto: VoxCPM2 ya da Supertonic'e çözülür; ikisinden birinin okuyabildiği diller listelenir
        "auto": {"izinli": sorted(SUPERTONIC_DILLERI | VOXCPM2_DENENEN_DILLER), "denenmemis": []},
        "supertonic": {"izinli": sorted(SUPERTONIC_DILLERI), "denenmemis": []},
        "voxcpm2": {"izinli": tum, "denenmemis": sorted(set(tum) - VOXCPM2_DENENEN_DILLER)},
        "ema_lightning": {"izinli": sorted(EMA_DILLERI), "denenmemis": []},
        "xtts": {"izinli": sorted(XTTS_DILLERI), "denenmemis": []},
    }


def durum(tur: str) -> dict[str, bool]:
    cikti = {}
    for m in motorlar(tur):
        try:
            cikti[m.ad] = bool(m.kurulu())
        except Exception:  # denetim hiçbir zaman `kontrol` komutunu düşürmez
            cikti[m.ad] = False
    return cikti


# --- lisans uyarıları (ilk kullanımda gösterilir; metin yalnız burada) ------------------------------------
_UYARI_TICARI_DEGIL = (
    "{ad}: model ağırlıkları yalnız TİCARİ OLMAYAN kullanım için lisanslıdır ({lisans}). "
    "Ücretli, müşteri ya da gelir getiren işte kullanmayın; çıktıları ticari model eğitiminde kullanmayın. "
    "Ayrıntı: THIRD_PARTY.md, ETHICS.md.\n"
    "{ad}: the model weights are licensed for NON-COMMERCIAL use only ({lisans}). "
    "Do not use them for paid, client or monetised work, or to train commercial models. See THIRD_PARTY.md."
)
_UYARI_SARTLI = (
    "{ad}: lisans kullanım şartı getirir ({lisans}). {ek}Ayrıntı: THIRD_PARTY.md.\n"
    "{ad}: this license carries use conditions ({lisans}). {ek_en}See THIRD_PARTY.md."
)
_SARTLI_EK = {
    "rvc": (
        "Modelin sesi size ait değilse sesin sahibinin açık izni gerekir; gerçek kişiyi izinsiz taklit yasaktır. ",
        "If the model's voice is not yours you need the owner's explicit consent; no unauthorised impersonation. ",
    ),
    "supertonic": (
        "Taklit, yanıltıcı içerik ve yasa dışı kullanım yasaktır; çıktının makine üretimi olduğu açıklanmalıdır. ",
        "No impersonation, deceptive or unlawful use; disclose that the output is machine-generated. ",
    ),
    "parakeet_cpu_align": (
        "Modeli yeniden dağıtırsanız NVIDIA lisansını ve atıf notunu ekleyin. ",
        "If you redistribute the model, include the NVIDIA license and its attribution notice. ",
    ),
}


def lisans_uyarisi(ad: str) -> str | None:
    """Ticari olmayan ya da şartlı motor için ilk kullanımda gösterilecek iki dilli uyarı; diğerleri için None."""
    m = motor(ad)
    if m.ticari == "hayır":
        return _UYARI_TICARI_DEGIL.format(ad=m.gorunen_ad, lisans=m.lisans)
    if m.ticari == "şartlı":
        ek, ek_en = _SARTLI_EK.get(m.ad, ("", ""))
        return _UYARI_SARTLI.format(ad=m.gorunen_ad, lisans=m.lisans, ek=ek, ek_en=ek_en)
    return None
