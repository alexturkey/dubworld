"""CrisperWhisper 2.0 Turbo (13. motor) kurulumu: kardeş STT reposunun indirme + CT2 dönüşüm yolu.

Ağırlık lisansı TİCARİ OLMAYAN kullanımdır (nyralabs/CrisperWhisper2.0_turbo model kartı). Bu betik yalnız
`scripts/kur.ps1 -Adim crisper -TicariOlmayanKabul` tarafından çağrılır. Gerekenler: WSL2 + Ubuntu, NVIDIA sürücüsü.

Adımlar:
  1. STT reposu sabit commit ile `runtime_assets/transkripsiyon_motorlari/stt_repo` altına alınır.
  2. O reponun kendi kurulum betiği (python, model adımları) ağırlığı Hugging Face'ten sabit commit + sha256 ile
     indirir ve CTranslate2'ye dönüştürür.
  3. Motor kodu (bu paketten) ve dönüştürülmüş model `runtime_assets/transkripsiyon_motorlari/crisperwhisper_turbo_ct2`
     altına konur; dosyalar motor profilindeki sha256 değerleriyle doğrulanır.
  4. Motorun WSL sanal ortamı kilit dosyasından kurulur.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VARLIK = REPO / "runtime_assets" / "transkripsiyon_motorlari"
MOTOR_KAYNAK = REPO / "src" / "dublaj_hatti" / "bolum_20_transkripsiyon" / "crisperwhisper_turbo_ct2_motoru"
MOTOR_KOK = VARLIK / "crisperwhisper_turbo_ct2"
CT2_DOSYALARI = ("model.bin", "config.json", "added_tokens.json", "merges.txt", "preprocessor_config.json",
                 "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json", "vocab.json", "vocabulary.json")
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def calistir(komut: list[str], **kw) -> None:
    print("  $ " + " ".join(komut), flush=True)
    subprocess.run(komut, check=True, creationflags=NO_WINDOW, **kw)


def sha256(yol: Path) -> str:
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


def wsl_yolu(yol: Path) -> str:
    yol = yol.resolve()
    return f"/mnt/{yol.drive[0].lower()}{yol.as_posix()[2:]}"


WSL_PYTHON_EN_AZ = (3, 12)  # kilitteki numpy==2.5.2 PyPI'de Requires-Python >=3.12 (Ubuntu 22.04 = 3.10, düşer)


def wsl_on_denetim(dagitim: str) -> None:
    """İndirmeden önce: WSL var mı, dağıtım açılıyor mu, python3 sürümü kilide yetiyor mu (açık mesajla durur)."""
    if not shutil.which("wsl.exe"):
        raise SystemExit("WSL bulunamadı. CrisperWhisper Turbo WSL2 + Ubuntu 24.04 ister: "
                         "`wsl --install -d Ubuntu-24.04` (docs/installation.md, crisper adımı).")
    sonuc = subprocess.run(["wsl.exe", "-d", dagitim, "--", "python3", "-c",
                            "import sys; print('%d %d' % sys.version_info[:2])"],
                           capture_output=True, text=True, creationflags=NO_WINDOW)
    parcalar = sonuc.stdout.split()
    if sonuc.returncode != 0 or len(parcalar) < 2 or not all(p.isdigit() for p in parcalar[-2:]):
        raise SystemExit(f"WSL dağıtımı '{dagitim}' içinde python3 çalıştırılamadı (çıkış {sonuc.returncode}). "
                         "Dağıtım adını --dagitim ile verin ya da Ubuntu 24.04 kurun: `wsl --install -d Ubuntu-24.04`.")
    surum = (int(parcalar[-2]), int(parcalar[-1]))
    if surum < WSL_PYTHON_EN_AZ:
        raise SystemExit(f"WSL '{dagitim}' python3 {surum[0]}.{surum[1]}; motor kilidi Python "
                         f"{WSL_PYTHON_EN_AZ[0]}.{WSL_PYTHON_EN_AZ[1]}+ ister (numpy 2.5.2). Ubuntu 24.04 kullanın: "
                         "`wsl --install -d Ubuntu-24.04` ve `--dagitim Ubuntu-24.04`.")
    print(f"  WSL '{dagitim}' python3 {surum[0]}.{surum[1]}: uygun", flush=True)


def main(argv=None) -> int:
    ayr = argparse.ArgumentParser()
    ayr.add_argument("--stt-repo", required=True)
    ayr.add_argument("--stt-commit", required=True)
    ayr.add_argument("--dagitim", default="Ubuntu")
    args = ayr.parse_args(argv)
    wsl_on_denetim(args.dagitim)

    stt = VARLIK / "stt_repo"
    stt_kok = VARLIK / "stt_kok"
    if not (stt / ".git").is_dir():
        calistir(["git", "clone", "--quiet", args.stt_repo, str(stt)])
    calistir(["git", "-C", str(stt), "fetch", "--quiet", "origin", args.stt_commit])
    calistir(["git", "-C", str(stt), "checkout", "--quiet", args.stt_commit])
    bas = subprocess.run(["git", "-C", str(stt), "rev-parse", "HEAD"], capture_output=True, text=True,
                         creationflags=NO_WINDOW).stdout.strip()
    if bas != args.stt_commit:
        raise SystemExit(f"STT reposu commit doğrulanamadı: {bas}")

    calistir(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(stt / "scripts" / "kur.ps1"),
              "-Kok", str(stt_kok), "-Adim", "python,model", "-Dagitim", args.dagitim])

    for alt in ("config", "src", "requirements"):
        hedef = MOTOR_KOK / alt
        if hedef.exists():
            shutil.rmtree(hedef)
        shutil.copytree(MOTOR_KAYNAK / alt, hedef, ignore=shutil.ignore_patterns("__pycache__"))
    model_hedef = MOTOR_KOK / "model_assets" / "ct2_float16_align"
    model_hedef.mkdir(parents=True, exist_ok=True)
    ct2 = stt_kok / "model" / "ct2_turbo"
    profil = json.loads((MOTOR_KOK / "config" / "runtime_profile.json").read_text(encoding="utf-8"))
    commit = profil["model"]["resolved_commit"]
    kaynaklar = {ad: ct2 / ad for ad in CT2_DOSYALARI}
    kaynaklar["generation_config.json"] = stt_kok / "model" / f"hf_turbo_{commit}" / "generation_config.json"
    for ad, kaynak in kaynaklar.items():
        hedef = model_hedef / ad
        if not hedef.is_file() or hedef.stat().st_size != kaynak.stat().st_size:
            shutil.copy2(kaynak, hedef)
    for ad, beklenen in profil["model"]["files"].items():
        gelen = sha256(model_hedef / ad)
        if gelen != beklenen["sha256"]:
            raise SystemExit(f"CT2 dosyası motor profiline uymuyor: {ad}\n  beklenen {beklenen['sha256']}\n  gelen    {gelen}")
    print("  CT2 model dosyaları doğrulandı", flush=True)

    venv = wsl_yolu(MOTOR_KOK / ".venv_wsl_ct2")
    kilit = wsl_yolu(MOTOR_KOK / "requirements" / "requirements_wsl_ct2.lock.txt")
    calistir(["wsl.exe", "-d", args.dagitim, "--", "bash", "-lc",
              f"test -x '{venv}/bin/python' || python3 -m venv '{venv}'; "
              f"'{venv}/bin/python' -m pip install --quiet --disable-pip-version-check -r '{kilit}' && "
              f"'{venv}/bin/python' -m pip check"])
    print("CRISPER_MOTOR_OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
