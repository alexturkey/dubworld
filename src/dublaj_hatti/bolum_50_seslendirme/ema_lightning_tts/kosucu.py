"""EMA Lightning koşucusu: ayrı süreçte çalışır, model bir kez yüklenir, bütün parçalar okunur, süreç kapanır.

Kullanım: python -B kosucu.py --is is.json --sonuc sonuc.json
is.json: {"yol": "torch-cuda" | "onnx-cpu" | "torch-cpu", "agirlik": "<klasör>", "onnx": "<klasör>",
          "hiz": 1.0, "tohum": 0, "is_parcacigi": 4, "calisma": "<klasör>",
          "parcalar": [{"index": 1, "text": "..."}, ...]}
sonuc.json: {"wavlar": {"1": "<yol>"}, "yol": ..., "yukleme_sn": ..., "sure_sn": ..., "ses_sn": ..., "vram_tepe_mb": ...}

Üç aşama (metin, ses, çözücü) paketin kendi Engine'iyle sırayla çalışır (ema_lightning.engine: piece, plan,
think, decode); GPU ve işlemci yolu aynı kodu izler, yalnız aşamaların hesaplandığı yer değişir: torch (CUDA ya da
işlemci) ya da ONNX Runtime (işlemci; dosyalar resmî ağırlıktan yerelde dışa aktarılır, onnx_aktar.py).
Bu modül dublaj_hatti paketini içe aktarmaz; ağırlık özetleri ayarlar.py ile aynıdır (test eşitliği denetler).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
import types
import wave
from pathlib import Path

import numpy as np

AGIRLIK_SHA256 = {
    "ema.pt": "95aec03dafbe0e1d69bca774ab597c779464729a14bc99bfcb52480090c7dfe6",
    "decoder.pt": "9595819b173f411340f63d11332695121a97f8bf1f6d8b6fef0b21cf99c7ad67",
}
ORNEKLEME = 48000
GPU_TOPLU = 8  # GPU'da metin ve ses aşaması 8 cümlelik toplu iş (4 GB kartta tepe bellek ölçüldü: motor belgesi)


class AgirlikHatasi(RuntimeError):
    pass


def dogrulanmis_bayt(klasor: Path, ad: str) -> bytes:
    """Ağırlık baytları; sha256 sabit değerle aynı değilse hiçbir şey yüklenmez (torch.load'dan önce)."""
    yol = klasor / ad
    if not yol.is_file():
        raise AgirlikHatasi(f"EMA ağırlığı yok: {yol} (kurulum: scripts/kur.ps1 -Adim tts-ema)")
    veri = yol.read_bytes()
    ozet = hashlib.sha256(veri).hexdigest()
    if ozet != AGIRLIK_SHA256[ad]:
        raise AgirlikHatasi(f"EMA ağırlığı sha256 tutmadı: {yol} ({ozet}); dosya yüklenmedi, yeniden indirin")
    return veri


class Motor:
    """Engine + Frontend; `yol`a göre aşamalar torch'ta ya da ONNX Runtime'da hesaplanır."""

    def __init__(self, yol: str, agirlik: Path, onnx: Path, is_parcacigi: int):
        import torch
        from ema_lightning.engine import Engine
        from ema_lightning.frontend import Frontend

        self.torch = torch
        torch.set_num_threads(max(1, is_parcacigi))
        self.yol = yol
        if yol == "onnx-cpu":
            import onnxruntime as ort

            meta = json.loads((onnx / "ema_meta.json").read_text(encoding="utf-8"))
            secenek = ort.SessionOptions()
            secenek.intra_op_num_threads = max(1, is_parcacigi)
            secenek.inter_op_num_threads = 1
            self.oturum = {ad: ort.InferenceSession(str(onnx / f"{ad}.onnx"), secenek,
                                                    providers=["CPUExecutionProvider"])
                           for ad in ("text", "sound", "decoder")}
            self.tipler = {ad: {g.name: g.type for g in o.get_inputs()} for ad, o in self.oturum.items()}
            model = types.SimpleNamespace(vocab=meta["vocab"], stoi={c: i for i, c in enumerate(meta["vocab"])},
                                          times=meta["times"], latent_dim=meta["latent_dim"])
            self.engine = Engine(model, types.SimpleNamespace(hop=meta["hop"]), "cpu")
            self.engine.run = self._onnx_run
            vocab = meta["vocab"]
        else:
            from ema_lightning.decoder import load_decoder
            from ema_lightning.model import load_acoustic

            cihaz = "cuda" if yol == "torch-cuda" else "cpu"
            # cuDNN kıyaslaması eski kartlarda her yeni boyutta yeniden arama yapar ve okumayı çok yavaşlatır
            # (paket yalnız lightning() içinde açar; burada açıkça kapalı). Sesi değiştirmez, yalnız hızı.
            torch.backends.cudnn.benchmark = False
            ema, dec = dogrulanmis_bayt(agirlik, "ema.pt"), dogrulanmis_bayt(agirlik, "decoder.pt")
            model = load_acoustic(io.BytesIO(ema), cihaz)
            self.engine = Engine(model, load_decoder(io.BytesIO(dec), cihaz), cihaz)
            vocab = model.vocab
        self.frontend = Frontend(vocab)
        self.toplu = GPU_TOPLU if yol == "torch-cuda" else 1

    def _onnx_run(self, stage, **girdi):
        ad = {"text": "text", "sound": "sound", "decode": "decoder"}[stage]
        donustur = {"tensor(int64)": np.int64, "tensor(bool)": np.bool_, "tensor(float)": np.float32}
        besle = {k: girdi[k].cpu().numpy().astype(donustur[t]) for k, t in self.tipler[ad].items()}
        cikti = [self.torch.from_numpy(x) for x in self.oturum[ad].run(None, besle)]
        return tuple(cikti) if stage == "text" else cikti[0]

    def senk(self) -> None:
        if self.yol == "torch-cuda":
            self.torch.cuda.synchronize()

    def oku(self, metinler: list[str], hiz: float, tohum: int) -> list[np.ndarray]:
        """Her metin için 48 kHz dalga: paket parçalara böler (cümle/yan cümle), parça sonrası sessizlik paketinki."""
        from ema_lightning.chunker import chunk

        e = self.engine
        isler = []  # (metin sırası, Piece)
        for sira, metin in enumerate(metinler):
            for i, (parca, ara) in enumerate(chunk(self.frontend(metin), hiz)):
                isler.append((sira, e.piece(parca, ara, (tohum * 1_000_003 + i) % 2**63)))
        with self.torch.no_grad():
            for b in range(0, len(isler), self.toplu):
                grup = [p for _, p in isler[b:b + self.toplu]]
                e.plan(grup, hiz)
                e.think(grup)
        dalgalar: list[list[np.ndarray]] = [[] for _ in metinler]
        with self.torch.no_grad():
            for sira, p in isler:
                ses = e.decode([(p, (0, p.frames))])[0].float().cpu().numpy()
                dalgalar[sira].append(ses)
                if p.pause:
                    dalgalar[sira].append(np.zeros(round(p.pause * ORNEKLEME), np.float32))
                p.h = p.dur = p.latents = None
        return [np.concatenate(d).astype(np.float32) if d else np.zeros(0, np.float32) for d in dalgalar]


def wav_yaz(yol: Path, dalga: np.ndarray) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(".part")
    with wave.open(str(gecici), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(ORNEKLEME)
        w.writeframes((np.clip(dalga, -1.0, 1.0) * 32767).astype("<i2").tobytes())
    gecici.replace(yol)


def main(argv=None) -> int:
    ayr = argparse.ArgumentParser()
    ayr.add_argument("--is", dest="is_dosyasi", type=Path, required=True)
    ayr.add_argument("--sonuc", type=Path, required=True)
    args = ayr.parse_args(argv)
    job = json.loads(args.is_dosyasi.read_text(encoding="utf-8"))
    calisma = Path(job["calisma"]).resolve()
    t0 = time.perf_counter()
    motor = Motor(job["yol"], Path(job["agirlik"]), Path(job["onnx"]), int(job.get("is_parcacigi") or 4))
    if motor.yol == "torch-cuda":
        motor.torch.cuda.reset_peak_memory_stats()
    yukleme = time.perf_counter() - t0
    parcalar = [p for p in job["parcalar"] if str(p.get("text") or "").strip()]
    motor.senk()
    t1 = time.perf_counter()
    dalgalar = motor.oku([str(p["text"]) for p in parcalar], float(job.get("hiz") or 1.0), int(job.get("tohum") or 0))
    motor.senk()
    sure = time.perf_counter() - t1
    wavlar = {}
    for p, dalga in zip(parcalar, dalgalar, strict=True):
        yol = calisma / "parcalar" / f"{int(p['index']):05d}.wav"
        wav_yaz(yol, dalga)
        wavlar[str(int(p["index"]))] = str(yol)
    vram = int(motor.torch.cuda.max_memory_allocated() / 2**20) if motor.yol == "torch-cuda" else 0
    ozet = {"wavlar": wavlar, "yol": motor.yol, "yukleme_sn": round(yukleme, 3), "sure_sn": round(sure, 3),
            "ses_sn": round(sum(len(d) for d in dalgalar) / ORNEKLEME, 3), "vram_tepe_mb": vram,
            "ornekleme": ORNEKLEME}
    args.sonuc.write_text(json.dumps(ozet, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
