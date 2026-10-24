"""Anahtarsiz yerel ceviri: Helsinki-NLP Opus-MT (MarianMT, CC-BY-4.0).

Model dosyalari kurulum betigiyle sabit commit + sha256 dogrulamasiyla `runtime_assets/model_cache/opus_mt/<cift>/`
altina iner; calisirken internete cikilmaz.
"""

from __future__ import annotations

import logging
from pathlib import Path

from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import runtime_asset_root

logger = logging.getLogger("dublaj_hatti")

YEREL_MODELLER = {
    ("en", "tr"): {
        "repo_id": "Helsinki-NLP/opus-mt-tc-big-en-tr",
        "klasor": "en-tr",
    },
}
BATCH_SIZE = 16
MAX_NEW_TOKENS = 256
NUM_BEAMS = 4


class YerelCeviriHatasi(RuntimeError):
    pass


def yerel_model_dizini(source_lang: str, target_lang: str) -> Path:
    spec = YEREL_MODELLER.get((source_lang, target_lang))
    if spec is None:
        desteklenen = ", ".join(f"{s}->{t}" for s, t in YEREL_MODELLER)
        raise YerelCeviriHatasi(
            f"Yerel ceviri bu dil cifti icin yok: {source_lang}->{target_lang}. "
            f"Desteklenen: {desteklenen}. Baska dil icin LLM ceviri saglayicisi secin."
        )
    return runtime_asset_root() / "model_cache" / "opus_mt" / spec["klasor"]


def _resolve_device(device: str) -> str:
    import torch

    choice = str(device or "auto").strip().lower()
    if choice == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if choice == "cuda" and not torch.cuda.is_available():
        raise YerelCeviriHatasi("GPU secildi ama CUDA kullanilamiyor; cihaz ayarini 'cpu' ya da 'auto' yapin")
    return choice


class yerel_ceviri_translator:
    def __init__(self, source_lang: str = "en", target_lang: str = "tr", device: str = "auto"):
        self.source_lang = str(source_lang or "").strip().lower()
        self.target_lang = str(target_lang or "tr").strip().lower()
        self.device_choice = device
        self.last_video_usage_report = ""
        self._model = None
        self._tokenizer = None
        self._device = "cpu"

    def _load(self) -> None:
        if self._model is not None:
            return
        model_dir = yerel_model_dizini(self.source_lang, self.target_lang)
        if not (model_dir / "config.json").is_file():
            raise YerelCeviriHatasi(f"Yerel ceviri modeli kurulu degil: {model_dir}. Kurulum: scripts/kur.ps1 -Adim modeller")
        from transformers import MarianMTModel, MarianTokenizer

        self._device = _resolve_device(self.device_choice)
        self._tokenizer = MarianTokenizer.from_pretrained(str(model_dir), local_files_only=True)
        model = MarianMTModel.from_pretrained(str(model_dir), local_files_only=True)
        self._model = model.to(self._device).eval()
        logger.info("Yerel ceviri modeli yuklendi: %s (%s)", model_dir.name, self._device)

    def translate_texts(self, texts: list[str]) -> list[str]:
        import torch

        if self.source_lang == self.target_lang:
            return list(texts)
        self._load()
        results = list(texts)
        bos_cikti: list[int] = []
        pending = [(index, text) for index, text in enumerate(texts) if str(text or "").strip()]
        for start in range(0, len(pending), BATCH_SIZE):
            chunk = pending[start:start + BATCH_SIZE]
            batch = self._tokenizer([text for _, text in chunk], return_tensors="pt", padding=True, truncation=True, max_length=512)
            batch = {key: value.to(self._device) for key, value in batch.items()}
            with torch.inference_mode():
                generated = self._model.generate(**batch, num_beams=NUM_BEAMS, max_new_tokens=MAX_NEW_TOKENS)
            decoded = self._tokenizer.batch_decode(generated, skip_special_tokens=True)
            for (index, _), translated in zip(chunk, decoded, strict=True):
                if not translated.strip():
                    bos_cikti.append(index)
                results[index] = translated.strip()
        if bos_cikti:
            # Kaynak metne sessizce dönmek yasak (ADR 0009): çevrilmemiş cümle "tamamlandı" diye seslendirilirdi.
            numaralar = ", ".join(str(i + 1) for i in bos_cikti[:10]) + (" ..." if len(bos_cikti) > 10 else "")
            raise YerelCeviriHatasi(
                f"Yerel ceviri {len(bos_cikti)} segmentte bos cikti verdi (segment no: {numaralar}); kaynak metin "
                "ceviri yerine kullanilmaz. Baska ceviri arka ucu secin ya da segment metnini kontrol edin."
            )
        return results

    def translate_single(self, text: str) -> str:
        return self.translate_texts([text])[0]

    def translate_segments(self, segments: list, run_dir=None, batch_size=None) -> list[str]:
        texts = [str(getattr(segment, "text", segment) or "") for segment in segments]
        return self.translate_texts(texts)
