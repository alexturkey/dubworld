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
# Bellek bütçesi (Düzeltme A, O2): bir toplu işte en uzun girdi tokeni x girdi sayısı x ışın sayısı bu değeri geçmez.
# 16 x 128 x 4: kısa altyazı segmentleri eskisi gibi 16'lık gruplanır; uzun girdiler küçük gruplara düşer. Eski üst
# sınır 16 x 512 x 4 = 32768 idi (4 GB kartta OOM riski). OOM olursa grup yarıya iner, 1'de de olursa işlemciye geçilir.
TOKEN_BUTCESI = BATCH_SIZE * 128 * NUM_BEAMS
# Modelin konum sınırı (config max_position_embeddings 512): bunu aşan tek cümle kesilmez, açık hata verir.
GIRDI_TOKEN_SINIRI = 512
# Bu kadar tokenden uzun girdi cümle sınırından bölünür, cümleler bu sınıra sığdıkça aynı parçada kalır. Ölçüm
# (2026-10-25, işlemci, 40 kısa İngilizce cümleden birleştirilen girdiler, birleşik / tek tek çeviri karakter oranı):
# 44-111 token 0,93-1,08 (içerik tam); 135-202 token 0,47-0,73: model erken bitirip cümle atlıyor. Eskiden 512'ye kadar
# tek parça gidiyordu (sessiz içerik kaybı). 96 ve altı eskisiyle aynı yoldan geçer (byte-aynı, altın test).
BOLME_ESIGI = 96
_CUMLE_SONU = r"(?<=[.!?…;:])\s+"


class YerelCeviriHatasi(RuntimeError):
    pass


class _Parca:
    """Çevrilecek bir parça: hangi girdinin kaçıncı parçası, metni ve token sayısı."""

    __slots__ = ("metin_no", "sira", "metin", "token")

    def __init__(self, metin_no: int, sira: int, metin: str, token: int) -> None:
        self.metin_no, self.sira, self.metin, self.token = metin_no, sira, metin, token


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


def _bellek_tasmasi_mi(hata: BaseException) -> bool:
    import torch

    oom = getattr(torch.cuda, "OutOfMemoryError", None) if hasattr(torch, "cuda") else None
    if oom is not None and isinstance(hata, oom):
        return True
    return isinstance(hata, RuntimeError) and "out of memory" in str(hata).lower()


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

    def _token_sayisi(self, metin: str) -> int:
        return len(self._tokenizer(metin, truncation=False, verbose=False)["input_ids"])

    def _parcala(self, metin_no: int, metin: str) -> list[_Parca]:
        """Kısa girdi tek parça (eski yol, sonuç aynı). Uzun girdi cümle sınırından BOLME_ESIGI'ne sığan parçalara
        bölünür; tek cümle GIRDI_TOKEN_SINIRI'ni aşarsa kesmek yerine açık hata."""
        token = self._token_sayisi(metin)
        if token <= BOLME_ESIGI:
            return [_Parca(metin_no, 0, metin, token)]
        import re

        cumleler = [c for c in re.split(_CUMLE_SONU, metin.strip()) if c.strip()]
        parcalar: list[str] = []
        for cumle in cumleler:
            if parcalar and self._token_sayisi(parcalar[-1] + " " + cumle) <= BOLME_ESIGI:
                parcalar[-1] = parcalar[-1] + " " + cumle
            else:
                parcalar.append(cumle)
        sonuc = []
        for sira, parca in enumerate(parcalar):
            parca_token = self._token_sayisi(parca)
            if parca_token > GIRDI_TOKEN_SINIRI:
                raise YerelCeviriHatasi(
                    f"Yerel ceviri: segment {metin_no + 1} icinde {parca_token} tokenlik tek cumle var; Opus-MT en cok "
                    f"{GIRDI_TOKEN_SINIRI} token alir ve metin sessizce kesilmez. Cumleyi bolun ya da LLM ceviri "
                    "arka ucu secin."
                )
            if parca_token > BOLME_ESIGI:
                logger.warning("Yerel ceviri: segment %d icinde %d tokenlik tek cumle bolunemedi; ceviriyi kontrol edin",
                               metin_no + 1, parca_token)
            sonuc.append(_Parca(metin_no, sira, parca, parca_token))
        logger.info("Yerel ceviri: segment %d (%d token) %d parcaya bolundu", metin_no + 1, token, len(sonuc))
        return sonuc

    def _cpuya_gec(self) -> None:
        import torch

        logger.warning("Yerel ceviri: GPU belleği bir girdiye bile yetmedi; işlemciye geçiliyor (sonuç aynı model)")
        self._model = self._model.to("cpu")
        self._device = "cpu"
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _uret(self, metinler: list[str]) -> list[str]:
        import torch

        batch = self._tokenizer(metinler, return_tensors="pt", padding=True)
        batch = {key: value.to(self._device) for key, value in batch.items()}
        with torch.inference_mode():
            generated = self._model.generate(**batch, num_beams=NUM_BEAMS, max_new_tokens=MAX_NEW_TOKENS)
        self._kesik_cikti_denetle(generated, metinler)
        return self._tokenizer.batch_decode(generated, skip_special_tokens=True)

    def _kesik_cikti_denetle(self, generated, metinler: list[str]) -> None:
        """MAX_NEW_TOKENS dolup bitiş tokeni gelmediyse çeviri kesiktir: sessizce kısa metin dönülmez."""
        shape = getattr(generated, "shape", None)
        eos = getattr(getattr(self._model, "config", None), "eos_token_id", None)
        if shape is None or eos is None or shape[-1] <= MAX_NEW_TOKENS:
            return
        for satir, metin in zip(generated, metinler, strict=True):
            if not bool((satir == eos).any()):
                raise YerelCeviriHatasi(
                    f"Yerel ceviri ciktisi {MAX_NEW_TOKENS} token sinirinda kesildi (girdi: {metin[:60]!r}...); "
                    "kesik ceviri kullanilmaz. Girdiyi bolun ya da LLM ceviri arka ucu secin."
                )

    def translate_texts(self, texts: list[str]) -> list[str]:
        if self.source_lang == self.target_lang:
            return list(texts)
        self._load()
        results = list(texts)
        parcalar: list[_Parca] = []
        for index, text in enumerate(texts):
            if str(text or "").strip():
                parcalar.extend(self._parcala(index, text))
        # Uzunluğa göre sırala (uzun önce: bellek sınırı ilk grupta görülür; az dolgu = az bellek ve iş).
        sirali = sorted(parcalar, key=lambda p: p.token, reverse=True)
        cevrilen: dict[tuple[int, int], str] = {}
        tavan = BATCH_SIZE
        i = 0
        while i < len(sirali):
            en_uzun = max(1, sirali[i].token)
            adet = max(1, min(tavan, TOKEN_BUTCESI // (en_uzun * NUM_BEAMS), len(sirali) - i))
            grup = sirali[i:i + adet]
            try:
                decoded = self._uret([p.metin for p in grup])
            except Exception as hata:  # yalnız bellek taşması yakalanır, gerisi aynen yükselir
                if not _bellek_tasmasi_mi(hata):
                    raise
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                if adet > 1:
                    tavan = max(1, adet // 2)
                    logger.warning("Yerel ceviri: bellek yetmedi, grup %d -> %d", adet, tavan)
                    continue
                if self._device != "cpu":
                    self._cpuya_gec()
                    continue
                raise
            for parca, translated in zip(grup, decoded, strict=True):
                cevrilen[(parca.metin_no, parca.sira)] = translated.strip()
            i += adet
        bos_cikti: list[int] = []
        for index in sorted({p.metin_no for p in parcalar}):
            parcali = [cevrilen[(p.metin_no, p.sira)] for p in parcalar if p.metin_no == index]
            if not all(parca.strip() for parca in parcali):
                bos_cikti.append(index)
            results[index] = " ".join(parcali).strip()
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
