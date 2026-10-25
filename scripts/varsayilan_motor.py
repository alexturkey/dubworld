"""Seçilen VoxCPM2 sesini bu makinenin varsayılanı yapar: `ayarlar/kullanici.toml` içine `[ses] motor` ve `voxcpm2_ses`.

Kullanıcı bir ses tasarlayıp ya da hazır ses seçip "dublajda bunu kullan" deyince çağrılır (AGENTS.md, ses tasarımı
akışı). Paketteki `varsayilan.toml` değişmez; yalnız git dışı kullanıcı katmanı yazılır.

- `--ses` verilen sesi `voxcpm2_ses` yapar (kullanıcının açık seçimi; varsa eski değerin yerine yazılır).
- `motor` yalnız dosyada yoksa yazılır (kullanıcının motor seçimi korunur); `genel.cihaz = "cpu"` ise hiçbir şey
  yazılmaz (VoxCPM2 işlemcide çalışmaz).
Geri alma: `ayarlar/kullanici.toml` içindeki bu betiğin yazdığı satırları silmek.

Kullanım: python scripts/varsayilan_motor.py --motor voxcpm2 [--ses ayse/2] [--dosya ayarlar/kullanici.toml]
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
KULLANICI = REPO / "ayarlar" / "kullanici.toml"
SES_BASLIGI = re.compile(r"^\s*\[ses\]\s*(#.*)?$")
BOLUM_BASLIGI = re.compile(r"^\s*\[")
NOT = "  # scripts/varsayilan_motor.py yazdı; geri almak için bu satırı silin"


def _ses_bolumune_yaz(metin: str, anahtar: str, deger: str) -> str:
    """`[ses]` bölümünde `anahtar` satırını değiştirir ya da ekler; bölüm yoksa sona açar."""
    satir = f"{anahtar} = {_toml_metin(deger)}{NOT}"
    satirlar = metin.splitlines()
    bolum = next((i for i, s in enumerate(satirlar) if SES_BASLIGI.match(s)), None)
    if bolum is None:
        return metin + ("\n" if metin and not metin.endswith("\n") else "") + f"[ses]\n{satir}\n"
    son = next((i for i in range(bolum + 1, len(satirlar)) if BOLUM_BASLIGI.match(satirlar[i])), len(satirlar))
    anahtar_satiri = re.compile(rf"^\s*{re.escape(anahtar)}\s*=")
    for i in range(bolum + 1, son):
        if anahtar_satiri.match(satirlar[i]):
            satirlar[i] = satir
            break
    else:
        satirlar.insert(bolum + 1, satir)
    return "\n".join(satirlar) + "\n"


def _toml_metin(deger: str) -> str:
    return '"' + deger.replace("\\", "\\\\").replace('"', '\\"') + '"'


def varsayilan_yap(dosya: Path, motor: str, ses: str | None = None) -> str:
    """Yazdıysa "yazildi: ...", dokunmadıysa nedenini döndürür."""
    metin = dosya.read_text(encoding="utf-8") if dosya.is_file() else ""
    mevcut = tomllib.loads(metin)
    if mevcut.get("genel", {}).get("cihaz") == "cpu":
        return "dokunulmadi: genel.cihaz = cpu"
    yazilan = []
    yeni = metin
    if "motor" not in mevcut.get("ses", {}):
        yeni = _ses_bolumune_yaz(yeni, "motor", motor)
        yazilan.append(f"motor={motor}")
    if ses:
        yeni = _ses_bolumune_yaz(yeni, "voxcpm2_ses", ses)
        yazilan.append(f"voxcpm2_ses={ses}")
    if not yazilan:
        return f"dokunulmadi: ses.motor zaten {mevcut['ses']['motor']!r}"
    sonuc = tomllib.loads(yeni)  # yazmadan önce sonucun geçerli TOML olduğunu ve değerleri doğrula
    if (ses and sonuc["ses"].get("voxcpm2_ses") != ses) or "motor" not in sonuc["ses"]:
        raise RuntimeError("kullanici.toml beklenen biçimde güncellenemedi")
    dosya.parent.mkdir(parents=True, exist_ok=True)
    dosya.write_text(yeni, encoding="utf-8", newline="\n")
    return "yazildi: " + ", ".join(yazilan)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--motor", required=True)
    p.add_argument("--ses", help='VoxCPM2 sesi: "hazir/<ad>", "<ad>/<çeşit>" ya da ses klasörü yolu')
    p.add_argument("--dosya", type=Path, default=KULLANICI)
    a = p.parse_args()
    sonuc = varsayilan_yap(a.dosya, a.motor, a.ses)
    print(f"VARSAYILAN_MOTOR {a.motor}: {sonuc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
