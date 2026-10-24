"""Seçim denetim kaydı: bir işin hangi ayarlarla çalıştığı ve devamda neyin değiştiği.

İş klasörüne `secim_denetimi.json` (makine) ve `secim_denetimi.txt` (insan) yazılır. Devam işinde ebeveyn işle
karşılaştırma ve bağımlılık kararı (hangi aşamadan yeniden çalıştığı ve neden) da kayda girer.
Kişisel veri yazılmaz: yalnız ayar anahtarları ve değerleri, iş numaraları, aşama adları.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from dublaj_hatti.is_yonetimi.asamalar import asama_adi

SECIM_DENETIMI_JSON = "secim_denetimi.json"
SECIM_DENETIMI_TXT = "secim_denetimi.txt"
SEMA_SURUMU = 1


def secim_karsilastirmasi(eski: dict[str, Any], yeni: dict[str, Any]) -> dict[str, Any]:
    degisen = [{"anahtar": k, "eski": eski.get(k), "yeni": yeni.get(k)}
               for k in sorted(set(eski) | set(yeni)) if eski.get(k) != yeni.get(k)]
    return {"degisen": degisen, "korunan_sayisi": len(set(eski) & set(yeni)) - len(degisen)}


def denetim_kaydi(is_kaydi: dict[str, Any], ebeveyn: dict[str, Any] | None = None) -> dict[str, Any]:
    ayar = _json(is_kaydi.get("settings_json"))
    plan = _json(is_kaydi.get("checkpoint_plan_json"))
    kayit: dict[str, Any] = {
        "schema_version": SEMA_SURUMU,
        "job_id": int(is_kaydi["job_id"]),
        "komut": is_kaydi.get("command") or "dubla",
        "arayuz": is_kaydi.get("request_origin") or "",
        "dublaj_kipi": is_kaydi.get("dubbing_mode") or "segment_sync",
        "ayarlar": dict(sorted(ayar.items())),
        "kullanici_degisiklikleri": _json(is_kaydi.get("overrides_json"), list),
    }
    if ebeveyn is not None:
        kayit["ebeveyn_job_id"] = int(ebeveyn["job_id"])
        kayit["devam_asamasi"] = is_kaydi.get("resume_after_stage") or ""
        kayit["karsilastirma"] = secim_karsilastirmasi(_json(ebeveyn.get("settings_json")), ayar)
        kayit["bagimlilik"] = plan
    return kayit


def denetim_metni(kayit: dict[str, Any]) -> str:
    satirlar = [f"İş #{kayit['job_id']} · {kayit['komut']} · kip {kayit['dublaj_kipi']} · arayüz {kayit['arayuz']}"]
    if "ebeveyn_job_id" in kayit:
        asama = kayit.get("devam_asamasi") or ""
        satirlar.append(f"Devam: iş #{kayit['ebeveyn_job_id']} kaydından, korunan son aşama: {asama_adi(asama)}")
        plan = kayit.get("bagimlilik") or {}
        for alan in plan.get("changed_fields") or []:
            hedef = alan.get("direct_stage") or {}
            etki = asama_adi(hedef.get("stage_id", "")) if hedef else "aşama etkisi yok"
            satirlar.append(f"  değişti: {alan['field']}: {alan['old']!r} → {alan['new']!r} (etki: {etki})")
        if not plan.get("changed_fields"):
            satirlar.append("  ayar değişikliği yok")
    satirlar.append("Ayarlar:")
    satirlar += [f"  {k} = {v!r}" for k, v in kayit["ayarlar"].items()]
    return "\n".join(satirlar) + "\n"


def denetim_yaz(run_dir: str | Path, is_kaydi: dict[str, Any], ebeveyn: dict[str, Any] | None = None) -> Path:
    hedef = Path(run_dir)
    kayit = denetim_kaydi(is_kaydi, ebeveyn)
    _atomik_yaz(hedef / SECIM_DENETIMI_JSON, json.dumps(kayit, ensure_ascii=False, indent=2, sort_keys=True))
    _atomik_yaz(hedef / SECIM_DENETIMI_TXT, denetim_metni(kayit))
    return hedef / SECIM_DENETIMI_JSON


def _json(ham: Any, tur: type = dict) -> Any:
    try:
        deger = json.loads(str(ham or "")) if ham else tur()
    except (TypeError, ValueError):
        return tur()
    return deger if isinstance(deger, tur) else tur()


def _atomik_yaz(yol: Path, metin: str) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_name(f".{yol.name}.{uuid.uuid4().hex}.tmp")
    try:
        gecici.write_text(metin, encoding="utf-8")
        os.replace(gecici, yol)
    finally:
        gecici.unlink(missing_ok=True)
