"""CUDA torch'a bağlı her ek kilidin işlemci profili için `_cpu` kardeşi vardır.

Temiz işlemci kurulumunda `-Adim demucs` GPU kilidindeki `torch==...+cu` sürümünü çözemeyip duruyordu;
kur.ps1 işlemci profilinde `ek_<ad>_cpu.txt`'yi seçer, kilitle.ps1 bunu üretir.
"""
import re
from pathlib import Path

REQ = Path(__file__).resolve().parents[1] / "requirements"
CUDA_TORCH = re.compile(r"^torch==\S+\+cu\d+", re.M)


def _torch_surumu(metin: str) -> str:
    m = re.search(r"^torch==(\S+?)(\+\S+)?\s", metin, re.M)
    return m.group(1) if m else ""


def test_cuda_ek_kilitlerinin_cpu_kardesi_var():
    eksik = []
    for kilit in sorted(REQ.glob("ek_*.txt")):
        if kilit.stem.endswith("_cpu"):
            continue
        metin = kilit.read_text(encoding="utf-8")
        if not CUDA_TORCH.search(metin):
            continue
        kardes = REQ / f"{kilit.stem}_cpu.txt"
        if not kardes.is_file():
            eksik.append(kardes.name)
            continue
        cpu = kardes.read_text(encoding="utf-8")
        assert not CUDA_TORCH.search(cpu), f"{kardes.name} CUDA torch içeriyor"
        assert "--hash=sha256:" in cpu, f"{kardes.name} hash kilitli değil"
        assert _torch_surumu(cpu) == _torch_surumu(metin), f"{kardes.name} torch sürümü GPU kilidinden farklı"
    assert not eksik, f"işlemci kardeşi eksik: {eksik} (scripts/kilitle.ps1 üretir)"


def test_kur_ps1_cpu_profilinde_kardes_secer():
    kur = (REQ.parent / "scripts" / "kur.ps1").read_text(encoding="utf-8-sig")
    assert '"cpu.txt"' in kur and "_cpu.txt" in kur
