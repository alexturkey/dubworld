"""Codex CLI ile kapak görseli üretimi (`codex exec` + yerleşik görsel üretim aracı).

Güvenlik ve düzen:
- Codex ayrı süreçte, pencere açmadan, yalnız iş klasörüne yazabilen kum havuzunda (workspace-write) çalışır;
  kabuk, tarayıcı, eklenti gibi özellikler kapatılır, yalnız görsel üretim açık kalır.
- İş klasörü, geçici CODEX_HOME ve şema/son mesaj dosyaları çıktı klasörünün DIŞINDA, `tempfile.mkdtemp` ile açılan
  işe özel bir kökte durur. Codex'e yazma izni (`--cd`, `--add-dir`) yalnız iş klasörüne verilir; doğrulanan
  görseller sonra çıktı klasörüne kopyalanır (Codex kullanıcının çıktı klasörüne hiç yazamaz).
- Kullanıcının kayıtlı Codex girişi bu geçici CODEX_HOME'a kopyalanır (iş klasörünün dışında); iş bitince (hata olsa
  da) kök silinir. API anahtarı ortam değişkenleri alt sürece geçmez.
- Transkript veridir: istem (istem.md) transkriptteki talimatların uygulanmayacağını söyler.
- Sonuç JSON şemayla zorlanır; her görsel PNG, 9:16, en az 800x1400 olmalı.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

PAKET = Path(__file__).resolve().parent
ISTEM_DOSYASI = PAKET / "istem.md"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
VARSAYILAN_MODEL = "gpt-5.6-luna"
VARSAYILAN_CABA = "medium"
VARSAYILAN_ADET = 5
ZAMAN_ASIMI_SN = 900
EN_UZUN_TRANSKRIPT = 180_000
ENGELLI_ORTAM = ("OPENAI_API_KEY", "CODEX_API_KEY")
ACIK_OZELLIK = "image_generation"
KAPALI_OZELLIKLER = (
    "apps", "browser_use", "browser_use_external", "browser_use_full_cdp_access", "computer_use", "goals", "hooks",
    "in_app_browser", "multi_agent", "personality", "plugins", "remote_plugin", "shell_snapshot", "shell_tool",
    "skill_mcp_dependency_install", "skill_search", "tool_suggest", "workspace_dependencies",
)


class KapakHatasi(RuntimeError):
    def __init__(self, mesaj: str, kod: str = "kapak_hatasi") -> None:
        super().__init__(mesaj)
        self.kod = kod


def _codex_onek() -> list[str]:
    from dublaj_hatti.bolum_40_ceviri.llm_kopru.scripts.bridge_worker import codex_command_prefix

    return codex_command_prefix()


def codex_kurulu() -> bool:
    ozel = os.environ.get("CODEX_BRIDGE_CODEX_BIN", "").strip()
    return bool((ozel and Path(ozel).is_file()) or shutil.which("codex"))


def cikti_semasi(adet: int) -> dict[str, Any]:
    return {
        "type": "object", "additionalProperties": False, "required": ["status", "images"],
        "properties": {
            "status": {"type": "string", "const": "success"},
            "images": {"type": "array", "minItems": adet, "maxItems": adet, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["variant_index", "cover_text", "artifact", "self_check"],
                "properties": {
                    "variant_index": {"type": "integer", "minimum": 1, "maximum": adet},
                    "cover_text": {"type": "string"},
                    "artifact": {"type": "object", "additionalProperties": False, "required": ["path", "mime_type"],
                                 "properties": {"path": {"type": "string", "minLength": 1},
                                                "mime_type": {"type": "string", "const": "image/png"}}},
                    "self_check": {"type": "object", "additionalProperties": False, "required": ["safe_area"],
                                   "properties": {"safe_area": {"type": "boolean", "const": True}}},
                },
            }},
        },
    }


def dosya_adi(sira: int) -> str:
    return f"kapak_{sira:02d}_9x16.png"


def istem_olustur(transkript: str, hedef_dil: str, adet: int, cikti: Path) -> str:
    sablon = ISTEM_DOSYASI.read_text(encoding="utf-8").replace("IMAGE_COUNT", str(adet)).replace("OUTPUT_DIR", str(cikti))
    girdi = json.dumps({"transcript_text": transkript, "target_language_code": hedef_dil, "image_count": adet,
                        "output_file_names": [dosya_adi(i) for i in range(1, adet + 1)]},
                       ensure_ascii=False, separators=(",", ":"))
    return f"{sablon}\nINPUT_JSON\n{girdi}\n"


def komut_olustur(onek: list[str], calisma: Path, sema: Path, son_mesaj: Path,
                  model: str = VARSAYILAN_MODEL, caba: str = VARSAYILAN_CABA) -> list[str]:
    """Yazma izni yalnız `calisma` (iş klasörü): `--cd` ve `--add-dir` ikisi de onu gösterir."""
    kapali = [arg for ozellik in KAPALI_OZELLIKLER for arg in ("--disable", ozellik)]
    return [*onek, "exec", "--json", "--skip-git-repo-check", "--ignore-user-config", "--enable", ACIK_OZELLIK,
            *kapali, "-c", f'model_reasoning_effort="{caba}"', "--model", model, "--cd", str(calisma),
            "--add-dir", str(calisma), "--sandbox", "workspace-write", "--output-schema", str(sema),
            "--output-last-message", str(son_mesaj), "-"]


def _yalitilmis_ortam(codex_home: Path) -> dict[str, str]:
    ortam = {k: v for k, v in os.environ.items() if k not in ENGELLI_ORTAM}
    kaynak = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    hedef = codex_home
    hedef.mkdir(parents=True, exist_ok=True)
    if (kaynak / "auth.json").is_file():
        shutil.copy2(kaynak / "auth.json", hedef / "auth.json")
    gorsel_becerisi = kaynak / "skills" / ".system" / "imagegen"
    if gorsel_becerisi.is_dir():
        shutil.copytree(gorsel_becerisi, hedef / "skills" / ".system" / "imagegen", dirs_exist_ok=True)
    ortam["CODEX_HOME"] = str(hedef)
    return ortam


def png_dogrula(yol: Path) -> dict[str, Any]:
    from PIL import Image

    with Image.open(yol) as resim:
        en, boy = resim.size
        bicim = str(resim.format or "").upper()
    if bicim != "PNG":
        raise KapakHatasi(f"{yol.name} PNG değil", "gorsel_sozlesmesi")
    if en < 800 or boy < 1400:
        raise KapakHatasi(f"{yol.name} çözünürlüğü yetersiz ({en}x{boy})", "gorsel_sozlesmesi")
    if abs(en / boy - 9 / 16) > 0.01:
        raise KapakHatasi(f"{yol.name} oranı 9:16 değil ({en}x{boy})", "gorsel_sozlesmesi")
    return {"genislik": en, "yukseklik": boy}


def _kaynak_bul(deger: str, calisma: Path, codex_home: Path | None = None) -> Path | None:
    """Görsel yalnız iş klasöründen ya da geçici CODEX_HOME/generated_images'tan alınır (başka yer reddedilir)."""
    aday = Path(deger)
    uretilen = (codex_home or calisma / "codex_home") / "generated_images"
    adaylar = [aday] if aday.is_absolute() else [calisma / aday, uretilen / aday]
    izinli = (calisma.resolve(), uretilen.resolve())
    for yol in adaylar:
        try:
            gercek = yol.resolve()
        except OSError:
            continue
        if gercek.is_file() and gercek.stat().st_size > 0 and any(gercek.is_relative_to(k) for k in izinli):
            return gercek
    if uretilen.is_dir() and aday.name:
        bulunan = [p.resolve() for p in uretilen.rglob(aday.name) if p.is_file()]
        if len(bulunan) == 1:
            return bulunan[0]
    return None


def sonucu_dogrula(sonuc: dict[str, Any], calisma: Path, cikti: Path, adet: int,
                   codex_home: Path | None = None) -> list[dict[str, Any]]:
    if sonuc.get("status") != "success" or not isinstance(sonuc.get("images"), list):
        raise KapakHatasi("Codex sonucu başarılı değil", "gecersiz_sonuc")
    gorseller = sorted(sonuc["images"], key=lambda o: int(o.get("variant_index") or 0))
    if [int(o.get("variant_index") or 0) for o in gorseller] != list(range(1, adet + 1)):
        raise KapakHatasi(f"Codex 1-{adet} sıralı kapak vermedi", "gecersiz_sonuc")
    cikan = []
    for oge in gorseller:
        if (oge.get("self_check") or {}).get("safe_area") is not True:
            raise KapakHatasi("güvenli alan denetimi geçmedi", "gecersiz_sonuc")
        kaynak = _kaynak_bul(str((oge.get("artifact") or {}).get("path") or ""), calisma, codex_home)
        if kaynak is None:
            raise KapakHatasi("Codex görsel dosyasını vermedi", "gorsel_yok")
        hedef = cikti / dosya_adi(int(oge["variant_index"]))
        png_dogrula(kaynak)  # önce doğrula, sonra kullanıcının klasörüne kopyala
        shutil.copy2(kaynak, hedef)
        cikan.append({"sira": int(oge["variant_index"]), "kapak_metni": str(oge.get("cover_text") or "").strip(),
                      "yol": str(hedef), **png_dogrula(hedef)})
    return cikan


def kapak_uret(transkript: str, cikti_klasoru: str | Path, hedef_dil: str = "tr", adet: int = VARSAYILAN_ADET,
               zaman_asimi_sn: int = ZAMAN_ASIMI_SN, logger: Any = None) -> dict[str, Any]:
    """Kapakları üretir ve `kapak_ozeti.json` yazar. Codex yoksa KapakHatasi(kod='codex_yok')."""
    transkript = (transkript or "").strip()
    if not transkript:
        raise KapakHatasi("transkript boş", "gecersiz_girdi")
    if len(transkript) > EN_UZUN_TRANSKRIPT:
        raise KapakHatasi("transkript kapak sınırını aşıyor", "gecersiz_girdi")
    if not 1 <= int(adet) <= 9:
        raise KapakHatasi("kapak sayısı 1-9 olmalı", "gecersiz_girdi")
    if not codex_kurulu():
        raise KapakHatasi("Codex CLI bulunamadı (npm i -g @openai/codex ; codex login); kapak adımı atlandı",
                          "codex_yok")
    cikti = Path(cikti_klasoru).resolve()
    cikti.mkdir(parents=True, exist_ok=True)
    gecici_kok = Path(tempfile.mkdtemp(prefix="dubworld_kapak_")).resolve()
    calisma, codex_home, kontrol = gecici_kok / "is", gecici_kok / "codex_home", gecici_kok / "kontrol"
    for klasor in (calisma, codex_home, kontrol):
        klasor.mkdir()
    try:
        sema, son_mesaj = kontrol / "sema.json", kontrol / "son_mesaj.json"
        sema.write_text(json.dumps(cikti_semasi(adet)), encoding="utf-8")
        model = os.environ.get("DUBLAJ_KAPAK_MODEL", VARSAYILAN_MODEL)
        caba = os.environ.get("DUBLAJ_KAPAK_CABA", VARSAYILAN_CABA)
        basla = time.time()
        try:
            tamam = subprocess.run(
                komut_olustur(_codex_onek(), calisma, sema, son_mesaj, model, caba),
                input=istem_olustur(transkript, hedef_dil, adet, calisma), text=True, encoding="utf-8",
                errors="replace", capture_output=True, cwd=str(calisma), env=_yalitilmis_ortam(codex_home),
                timeout=zaman_asimi_sn, creationflags=NO_WINDOW,
            )
        except subprocess.TimeoutExpired as hata:
            raise KapakHatasi(f"Codex {zaman_asimi_sn} sn içinde bitmedi", "zaman_asimi") from hata
        if tamam.returncode != 0:
            ayrinti = (tamam.stderr or tamam.stdout or "").strip()[-1500:]
            kod = "codex_giris" if any(k in ayrinti.lower() for k in ("401", "unauthorized", "not logged in")) else "codex_hata"
            raise KapakHatasi(f"Codex başarısız (çıkış {tamam.returncode}): {ayrinti}", kod)
        if not son_mesaj.is_file():
            raise KapakHatasi("Codex son mesaj dosyasını yazmadı", "sonuc_yok")
        gorseller = sonucu_dogrula(json.loads(son_mesaj.read_text(encoding="utf-8")), calisma, cikti, adet,
                                   codex_home)
        ozet = {"durum": "tamam", "adet": adet, "hedef_dil": hedef_dil, "model": model, "caba": caba,
                "sure_sn": round(time.time() - basla, 1), "gorseller": gorseller}
        (cikti / "kapak_ozeti.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
        if logger:
            logger.info("[KAPAK] %d kapak hazır (%.0f sn)", adet, ozet["sure_sn"])
        return ozet
    finally:
        shutil.rmtree(gecici_kok, ignore_errors=True)  # kopyalanan giriş dosyası dahil
