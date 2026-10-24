"""EMA Lightning işlemci yolu: resmî ağırlıktan ONNX dışa aktarımı ve eşitlik denetimi (kurulumda bir kez).

Neden yerelde: model yayıncısı ONNX dosyası yayımlamaz; üçüncü kişinin dönüştürdüğü dosya yerine aynı sha256'lı resmî
ağırlıktan (ayarlar.EMA_AGIRLIK_SHA256) bu makinede üretilir. Üç aşama ayrı dosyadır (paketin Engine'indeki
text_stage, sound_stage ve çözücü); kalan mantık (parçalama, zaman çizelgesi, gürültü) paketin Python kodunda kalır.
Dışa aktarılan her dosya torch ile aynı girdide karşılaştırılır; fark EMA_ONNX_TOLERANS'ı aşarsa dosyalar silinmez
ama aktarim.json "gecti": false yazar ve işlemci yolu ONNX yerine torch'u kullanır (api.ema_durumu).
"""

from __future__ import annotations

import hashlib
import io
import json
import time
from pathlib import Path

import numpy as np

from dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts.ayarlar import (
    EMA_ONNX_DOSYALARI,
    EMA_ONNX_OPSET,
    EMA_ONNX_TOLERANS,
    EMA_PAKET_SURUMU,
    agirlik_dizini,
    onnx_dizini,
)
from dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts.kosucu import dogrulanmis_bayt

DENEME_METNI = "Bugün hava çok güzel, yarın da yağmur yağacakmış; toplantı öğleden sonra başlayacak."


def _sha256(yol: Path) -> str:
    h = hashlib.sha256()
    with yol.open("rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def aktar(hedef: Path | None = None, agirlik: Path | None = None) -> dict:
    """text.onnx, sound.onnx, decoder.onnx + ema_meta.json + aktarim.json yazar; aktarim.json içeriğini döndürür."""
    import torch
    from ema_lightning.decoder import load_decoder
    from ema_lightning.engine import Engine
    from ema_lightning.frontend import Frontend
    from ema_lightning.model import load_acoustic

    hedef = Path(hedef or onnx_dizini())
    agirlik = Path(agirlik or agirlik_dizini())
    hedef.mkdir(parents=True, exist_ok=True)
    model = load_acoustic(io.BytesIO(dogrulanmis_bayt(agirlik, "ema.pt")), "cpu")
    dec = load_decoder(io.BytesIO(dogrulanmis_bayt(agirlik, "decoder.pt")), "cpu")

    def expm1(g, x):  # ONNX'te expm1 işlemi yok: exp(x) - 1 (log süre en çok 6'ya kırpıldığı için kayıp yok)
        return g.op("Sub", g.op("Exp", x), g.op("Constant", value_t=torch.tensor(1.0)))

    torch.onnx.register_custom_op_symbolic("aten::expm1", expm1, EMA_ONNX_OPSET)

    class Metin(torch.nn.Module):
        def forward(self, ids, mask):
            return model.text_stage(ids, mask)

    class Ses(torch.nn.Module):
        def forward(self, h, dur, mask, cw, wstart, fw, fp, fmask, noise):
            return model.sound_stage(h, dur, mask, cw, wstart, fw, fp, fmask, noise)

    class Cozucu(torch.nn.Module):
        def forward(self, z, lengths):
            return dec(z.transpose(1, 2), lengths)

    # Gerçek bir cümlenin aşama girdileri (paketin kendi Engine'i hazırlar); dinamik eksenlerle her boyuta açılır.
    engine = Engine(model, dec, "cpu")
    frontend = Frontend(model.vocab)
    parca = engine.piece(frontend(DENEME_METNI), 0.0, 0)
    kayit: dict[str, dict] = {}
    asil_run = engine.run

    def yakala(stage, **girdi):
        kayit[stage] = girdi
        return asil_run(stage, **girdi)

    engine.run = yakala
    with torch.no_grad():
        engine.plan([parca], 1.0)
        engine.think([parca])
        engine.decode([(parca, (0, parca.frames))])
    engine.run = asil_run

    B, L, T = {0: "B"}, {0: "B", 1: "L"}, {0: "B", 1: "T"}
    tanim = {
        "text": (Metin(), ["ids", "mask"], ["h", "dur"], {"ids": L, "mask": L, "h": L, "dur": L}),
        "sound": (Ses(), ["h", "dur", "mask", "cw", "wstart", "fw", "fp", "fmask", "noise"], ["latents"],
                  {"h": L, "dur": L, "mask": L, "cw": L, "wstart": L, "fw": T, "fp": T, "fmask": T,
                   "noise": {0: "B", 2: "T"}, "latents": T}),
        "decode": (Cozucu(), ["z", "lengths"], ["audio"], {"z": {0: "B", 1: "P"}, "lengths": B,
                                                          "audio": {0: "B", 1: "S"}}),
    }
    dosya_adi = {"text": "text.onnx", "sound": "sound.onnx", "decode": "decoder.onnx"}
    t0 = time.perf_counter()
    for stage, (modul, girisler, cikislar, eksen) in tanim.items():
        ornek = tuple(kayit[stage][ad] for ad in girisler)
        gecici = hedef / (dosya_adi[stage] + ".part")
        torch.onnx.export(modul, ornek, str(gecici), input_names=girisler, output_names=cikislar,
                          dynamic_axes=eksen, opset_version=EMA_ONNX_OPSET, dynamo=False)
        gecici.replace(hedef / dosya_adi[stage])
    aktarim_sn = time.perf_counter() - t0

    meta = {"vocab": list(model.vocab), "times": [float(t) for t in model.times], "latent_dim": int(model.latent_dim),
            "hop": int(dec.hop), "sample_rate": 48000, "opset": EMA_ONNX_OPSET}
    (hedef / "ema_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    fark = _esitlik(hedef, model, dec)
    sonuc = {
        "paket": EMA_PAKET_SURUMU, "torch": torch.__version__, "opset": EMA_ONNX_OPSET,
        "aktarim_sn": round(aktarim_sn, 1), "en_buyuk_fark": fark, "tolerans": EMA_ONNX_TOLERANS,
        "gecti": all(v <= EMA_ONNX_TOLERANS for v in fark.values()),
        "sha256": {ad: _sha256(hedef / ad) for ad in EMA_ONNX_DOSYALARI},
    }
    (hedef / "aktarim.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return sonuc


def _esitlik(hedef: Path, model, dec) -> dict[str, float]:
    """Dışa aktarımdan FARKLI boyutlu bir cümlede torch ile ONNX Runtime çıktılarının en büyük mutlak farkı."""
    import onnxruntime as ort
    import torch
    from ema_lightning.engine import Engine
    from ema_lightning.frontend import Frontend

    oturum = {ad: ort.InferenceSession(str(hedef / f"{ad}.onnx"), providers=["CPUExecutionProvider"])
              for ad in ("text", "sound", "decoder")}
    engine = Engine(model, dec, "cpu")
    parca = engine.piece(Frontend(model.vocab)("Saat on beşte gelin, sizi bekliyoruz."), 0.0, 7)
    with torch.no_grad():
        ids, mask = parca.ids[None], torch.ones(1, parca.letters, dtype=torch.bool)
        h, dur = model.text_stage(ids, mask)
        oh, od = oturum["text"].run(None, {"ids": ids.numpy(), "mask": mask.numpy()})
        engine.plan([parca], 1.0)
        girdi = {"h": parca.h[None], "dur": parca.dur[None], "mask": mask, "cw": parca.cw[None],
                 "wstart": parca.wstart[None], "fw": parca.fw[None], "fp": parca.fp[None],
                 "fmask": torch.ones(1, parca.frames, dtype=torch.bool), "noise": engine.noise(parca)[None]}
        lat = model.sound_stage(**girdi)
        ol = oturum["sound"].run(None, {k: v.numpy() for k, v in girdi.items()})[0]
        uzunluk = torch.tensor([parca.frames])
        ses = dec(lat.transpose(1, 2), uzunluk)
        oa = oturum["decoder"].run(None, {"z": lat.numpy(), "lengths": uzunluk.numpy()})[0]
    return {"text": float(max(np.abs(oh - h.numpy()).max(), np.abs(od - dur.numpy()).max())),
            "sound": float(np.abs(ol - lat.numpy()).max()), "decoder": float(np.abs(oa - ses.numpy()).max())}
