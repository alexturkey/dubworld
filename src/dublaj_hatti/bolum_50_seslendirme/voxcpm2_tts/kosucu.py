"""VoxCPM2 kosucusu: kardes reponun sanal ortaminda calisir (bu paketi import ETMEZ).

Kullanim: <voxcpm2 .venv python> kosucu.py --kok <voxcpm2 repo> --is is.json --sonuc sonuc.json
is.json: {"ses": "hazir/<ad> | <ad>/<cesit> | klasor | kitaplik/<kimlik>", "dil": "tr", "calisma": "<klasor>",
          "parcalar": [{"index": 1, "text": "..."}, ...],
          "kitaplik": {"yol": "<ses.wav>", "metin": "<kaydin metni ya da bos>", "tohum": 123}}   # yalniz kitaplik/ seslerinde
sonuc.json: {"wavlar": {"1": "<yol>"}, "hatali": [index], "sure_sn": ..., "vram_tepe_mb": ..., "tohum": ...}
Butun parcalar tek motor oturumunda uretilir (model bir kez yuklenir).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kok", type=Path, required=True)
    parser.add_argument("--is", dest="is_dosyasi", type=Path, required=True)
    parser.add_argument("--sonuc", type=Path, required=True)
    args = parser.parse_args(argv)

    sys.path.insert(0, str(args.kok.resolve()))
    from ses_tasarim import ayarlar, motor, oku, okunus  # noqa: E402

    job = json.loads(args.is_dosyasi.read_text(encoding="utf-8"))
    settings = ayarlar.load(str(args.kok / "ayarlar.json"))
    work_dir = Path(job["calisma"]).resolve()
    library = job.get("kitaplik")
    if library:  # kullanicinin kendi sesi: referans = ses.wav, metin varsa referans metin, tohum kayitta sabit
        dil = job.get("dil") or "tr"
        seed = int(library["tohum"])
        reference = motor.reference_wav(Path(library["yol"]), work_dir)
        reference_text = str(library.get("metin") or "").strip()
        card = {"ad": library.get("ad") or "kitaplik"}
    else:
        voice_dir = oku.find_voice(settings, str(job["ses"]))
        card = json.loads((voice_dir / "ses.json").read_text(encoding="utf-8"))
        dil = oku.voice_language(voice_dir, job.get("dil") or None)
        seed = int(card["okuma_tohumu"])  # okumada sesin kendi tohumu sabit (tutarlilik)
        reference = motor.reference_wav(voice_dir / card.get("referans", "referans.wav"), work_dir)
        reference_text = card["ses_yaratilirken_okutulan_metin"]

    requests, ids = [], {}
    for part in job["parcalar"]:
        text = " ".join(line for line, _ in okunus.lines(okunus.spoken(str(part["text"]), dil))).strip()
        if not text:
            continue
        request_id = f"s{int(part['index'])}"
        ids[request_id] = int(part["index"])
        if library and not reference_text:  # yalniz sesten klon (metin yok): motor varsayilan kipi, --voice-ref
            requests.append({"id": request_id, "text": text, "seed": int(seed), "voice_ref": str(reference)})
        else:
            requests.append(motor.read_request(request_id, text, seed, reference, reference_text))

    result = motor.run_sequence(settings, requests, work_dir)
    out_dir = work_dir / "parcalar"
    out_dir.mkdir(parents=True, exist_ok=True)
    wavs = {}
    for request_id, audio in result["audios"].items():
        path = out_dir / f"{ids[request_id]:05d}.wav"
        motor.write_wav(path, audio)
        wavs[str(ids[request_id])] = str(path)
    summary = {
        "wavlar": wavs,
        "hatali": [ids[b] for b in result["bad"]],
        "sure_sn": result["seconds"],
        "vram_tepe_mb": result["vram_peak_mb"],
        "tohum": seed,
        "referans": str(reference),
        "referans_metin": bool(reference_text),
        "ses": card.get("ad"),
        "adim": motor.FIXED["adim"],
        "cfg": motor.FIXED["cfg"],
        "ornekleme": motor.SAMPLE_RATE,
    }
    args.sonuc.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
