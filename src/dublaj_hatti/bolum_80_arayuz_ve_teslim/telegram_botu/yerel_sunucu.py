"""Yerel Telegram Bot API sunucusu (isteğe bağlı): bulut Bot API'nin 50 MB gönderme sınırı yerine 2000 MB.

Ne: Telegram'ın resmî açık kaynak Bot API sunucusu (`tdlib/telegram-bot-api`, Boost Software License) bu
bilgisayarda çalışır; bot isteklerini `https://api.telegram.org` yerine `http://127.0.0.1:<port>` adresine yollar.
Sunucu dosyayı Telegram veri merkezine kendisi taşır; bulut uç noktasındaki 50 MB (gönderme) ve 20 MB (indirme)
sınırları kalkar, tek dosya sınırı 2000 MB olur.

Kurulum yolları (`dubla-telegram sunucu kur`, kip `auto` sırayla dener):
- `docker`: Docker varsa (gerekirse Docker Desktop gizli başlatılır) IPv4+IPv6 köprü ağında tek kapsayıcı.
  Hazır imaj sabit özetle (digest) çekilir; `--kaynaktan` ile imaj resmî kaynaktan sabit commit'te derlenir.
- `derleme`: Docker yoksa resmî kaynak sabit commit'te derlenir (Linux/macOS doğrudan, Windows'ta WSL içinde) ve
  sunucu gizli başlatılır.

Ayar (.env, değerler yalnız orada): `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` (my.telegram.org), `TELEGRAM_YEREL_SUNUCU`
(kurulum yazar; boşsa bulut uç noktası). Kimlik değerleri komut satırına yazılmaz: kapsayıcıya ortam değişkeni adıyla
(`-e AD`), WSL'ye `WSLENV` ile geçer. Belge: docs/tarifler/telegram_buyuk_dosya.md, ADR 0018.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu.guvenlik import (
    BELIRTEC_DEGISKENI,
    TelegramAyarHatasi,
    gizle,
)

MB = 1024 * 1024
BULUT_ADRESI = "https://api.telegram.org"
BULUT_GONDERME_SINIRI = 50 * MB  # bulut Bot API: bot en çok 50 MB gönderir
BULUT_INDIRME_SINIRI = 20 * MB  # bulut Bot API: bot en çok 20 MB indirir
YEREL_SINIR = 2000 * MB  # yerel sunucu (--local): tek dosya en çok 2000 MB
BELIRSIZ_TESLIM_ESIGI = 50 * MB  # tamamı gidip cevabı gelmeyen bu boyun üstü yeniden yüklenmez

ADRES_DEGISKENI = "TELEGRAM_YEREL_SUNUCU"
API_ID_DEGISKENI = "TELEGRAM_API_ID"
API_HASH_DEGISKENI = "TELEGRAM_API_HASH"
KAPSAYICI_DEGISKENI = "TELEGRAM_YEREL_KAPSAYICI"

VARSAYILAN_PORT = 8081
PORT_ARALIGI = range(8081, 8091)
KAPSAYICI = "dubworld-telegram-bot-api"
AG = "dubworld-telegram-dualstack"
KAPSAYICI_IS_KLASORU = "/var/lib/telegram-bot-api"
KAPSAYICI_GECICI_KLASOR = "/tmp/telegram-bot-api"  # noqa: S108 (kapsayıcının içindeki yol)
# Hazır imaj: resmî kaynağı derleyen topluluk imajı (MIT tarif), etiket değil sabit özet; değişirse burada güncellenir.
HAZIR_IMAJ = "aiogram/telegram-bot-api@sha256:49fb5d9f71dddbd9a5b466761a2a8a89e2cf13008b256cd02f6923135175376b"
KAYNAK_DEPO = "https://github.com/tdlib/telegram-bot-api.git"
KAYNAK_COMMIT = "e3e9dd8e5b3d7ab8537cd5a10dc31d5ffa8f82d1"
YEREL_IMAJ = f"dubworld/telegram-bot-api:{KAYNAK_COMMIT[:12]}"
HAZIRLIK_SN = 60  # gerçek getMe cevabı bu sürede gelmezse sunucu hazır sayılmaz
DOCKER_BEKLE_SN = 90
# Sunucunun indirdiği dosyaların durduğu alt klasörler (bot veritabanı td.binlog vb. ASLA silinmez).
INDIRME_ALT_KLASORLERI = ("documents", "videos", "video_notes", "photos", "voice", "music", "animations",
                          "stickers", "temp", "thumbnails", "profile_photos", "wallpapers", "stories")
YUKLEME_PAYI = 1.1  # yükleme sırasında sunucu dosyanın bir kopyasını geçici klasörde tutar (+%10 pay)

_GIZLI = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
_PAKET_KOKU = Path(__file__).resolve().parents[2]
PROJE_KOKU = _PAKET_KOKU.parents[1]
DERLEME_KOKU = PROJE_KOKU / "runtime_assets" / "araclar" / "telegram-bot-api"
DERLEME_BETIGI = PROJE_KOKU / "scripts" / "telegram_bot_api_derle.sh"
DOCKERFILE = PROJE_KOKU / "scripts" / "telegram_bot_api.Dockerfile"
WSL_KURULUM = "/opt/dubworld-telegram-bot-api"  # Windows: WSL içinde root olarak kurulur (sudo parolası sorulmaz)


# --- ayar ----------------------------------------------------------------------------------------------
def yerel_adres(deger: str | None = None) -> str:
    """`TELEGRAM_YEREL_SUNUCU` (boş = bulut). Düz http yalnız bu bilgisayara (127.0.0.1, localhost, ::1) izinli:
    belirteç istek adresinde taşındığı için şifresiz bağlantı ağa çıkmaz."""
    ham = (os.environ.get(ADRES_DEGISKENI, "") if deger is None else deger).strip().rstrip("/")
    if not ham:
        return ""
    parca = urllib.parse.urlsplit(ham)
    if parca.scheme not in ("http", "https") or not parca.hostname:
        raise TelegramAyarHatasi(f"{ADRES_DEGISKENI} biçimi geçersiz (örnek: http://127.0.0.1:8081)")
    if parca.scheme == "http" and parca.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise TelegramAyarHatasi(f"{ADRES_DEGISKENI}: http yalnız 127.0.0.1 için; uzak sunucu https ister")
    if parca.path not in ("", "/"):
        raise TelegramAyarHatasi(f"{ADRES_DEGISKENI} yalnız adres:port olur (sonuna /bot eklenmez)")
    return f"{parca.scheme}://{parca.netloc}"


def gonderme_siniri(adres: str) -> int:
    return YEREL_SINIR if adres else BULUT_GONDERME_SINIRI


def indirme_siniri(adres: str) -> int:
    return YEREL_SINIR if adres else BULUT_INDIRME_SINIRI


def boyut_denetimi(boyut: int, adres: str) -> tuple[bool, str]:
    """Göndermeden önce: (gönderilebilir mi, açıklama). Sınırı aşan dosya hiç denenmez (boşuna yükleme olmaz)."""
    if boyut <= 0:
        return False, "dosya boş (0 bayt)"
    if boyut > YEREL_SINIR:
        return False, (f"dosya {boyut / MB:.0f} MB: Telegram tek dosyada en çok 2000 MB kabul eder (yerel sunucu "
                       "dahil); dosya bilgisayarda kalır. Daha küçük kodlayın ya da parçalara bölün.")
    if boyut > BULUT_GONDERME_SINIRI and not adres:
        return False, (f"dosya {boyut / MB:.0f} MB: bulut Bot API en çok 50 MB gönderir. 2 GB'a kadar göndermek için "
                       "yerel sunucuyu kurun: dubla-telegram sunucu kur (docs/tarifler/telegram_buyuk_dosya.md)")
    return True, ""


# --- ağ yoklamaları (stdlib; python-telegram-bot gerekmez) ------------------------------------------------
def _host_port(adres: str) -> tuple[str, int]:
    parca = urllib.parse.urlsplit(adres)
    return parca.hostname or "127.0.0.1", parca.port or (443 if parca.scheme == "https" else 80)


def port_acik_mi(host: str, port: int, sure: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=sure):
            return True
    except OSError:
        return False


def bos_port(aralik: range = PORT_ARALIGI) -> int | None:
    for port in aralik:
        if not port_acik_mi("127.0.0.1", port):
            return port
    return None


def get_me(adres: str, belirtec: str, sure: float = 5.0) -> dict[str, Any] | None:
    """Gerçek Bot API çağrısı. Açık port ya da çalışan süreç hazırlık kanıtı değildir (sunucu ayakta ama Telegram'a
    çıkamıyor olabilir); hazırlık yalnız `getMe` ok cevabıyla kabul edilir. Hata metni belirteci taşımaz."""
    if not adres or not belirtec:
        return None
    try:
        with urllib.request.urlopen(f"{adres}/bot{belirtec}/getMe", timeout=sure) as cevap:  # noqa: S310 (adres doğrulandı)
            veri = json.loads(cevap.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return None
    sonuc = veri.get("result") if isinstance(veri, dict) and veri.get("ok") else None
    return sonuc if isinstance(sonuc, dict) and sonuc.get("id") else None


def bot_api_mi(adres: str) -> bool:
    """Belirteçsiz yoklama: adres bir Bot API sunucusu gibi cevap veriyor mu (bilinmeyen yol → JSON ok=false)."""
    try:
        urllib.request.urlopen(f"{adres}/bot0:x/getMe", timeout=3)  # noqa: S310
    except urllib.error.HTTPError as hata:
        try:
            veri = json.loads(hata.read().decode("utf-8"))
        except ValueError:
            return False
        return isinstance(veri, dict) and veri.get("ok") is False and "error_code" in veri
    except (OSError, urllib.error.URLError):
        return False
    return False


def kontrol_ozeti(belirtec: str | None = None) -> dict[str, Any]:
    """`dubla kontrol` satırı: Docker'a dokunmaz, yalnız ayar + port + (belirteç varsa) getMe; en çok ~5 sn."""
    try:
        adres = yerel_adres()
    except TelegramAyarHatasi as hata:
        return {"durum": "ayar_hatasi", "mesaj": str(hata), "sinir_mb": BULUT_GONDERME_SINIRI // MB}
    if not adres:
        return {"durum": "kapali", "adres": "", "sinir_mb": BULUT_GONDERME_SINIRI // MB}
    host, port = _host_port(adres)
    if not port_acik_mi(host, port):
        return {"durum": "calismiyor", "adres": adres, "sinir_mb": BULUT_GONDERME_SINIRI // MB}
    belirtec = os.environ.get(BELIRTEC_DEGISKENI, "").strip() if belirtec is None else belirtec
    if belirtec:
        hazir = get_me(adres, belirtec) is not None
        return {"durum": "hazir" if hazir else "telegrama_ulasamiyor", "adres": adres,
                "sinir_mb": (YEREL_SINIR if hazir else BULUT_GONDERME_SINIRI) // MB}
    return {"durum": "port_acik_belirtec_yok", "adres": adres, "sinir_mb": YEREL_SINIR // MB}


KONTROL_METINLERI = {
    "kapali": "kapalı (bulut Bot API, en çok 50 MB; 2 GB için: dubla-telegram sunucu kur)",
    "calismiyor": "AYARLI AMA ÇALIŞMIYOR: {adres} cevap vermiyor; başlatın: dubla-telegram sunucu baslat",
    "telegrama_ulasamiyor": "{adres} açık ama getMe başarısız (sunucu Telegram'a çıkamıyor ya da belirteç yanlış): "
                            "dubla-telegram sunucu durum",
    "port_acik_belirtec_yok": "{adres} açık; belirteç yok, getMe sınanmadı",
    "hazir": "HAZIR {adres} (en çok 2000 MB)",
    "ayar_hatasi": "AYAR HATASI: {mesaj}",
}


def kontrol_metni(ozet: dict[str, Any]) -> str:
    return KONTROL_METINLERI.get(ozet.get("durum", ""), "{durum}").format(**{"adres": "", "mesaj": "", **ozet})


# --- .env -----------------------------------------------------------------------------------------------
def env_yolu() -> Path:
    return Path(os.environ.get("DUBLAJ_ENV_DOSYASI") or PROJE_KOKU / ".env")


def env_yaz(ad: str, deger: str, yol: Path | None = None) -> Path:
    """`.env`'de tek anahtarı ekler ya da değiştirir (öbür satırlar aynen kalır); geçici dosya + os.replace."""
    yol = yol or env_yolu()
    satirlar = yol.read_text(encoding="utf-8").splitlines() if yol.exists() else []
    yeni, bulundu = [], False
    for satir in satirlar:
        if satir.split("=", 1)[0].strip() == ad and not satir.lstrip().startswith("#"):
            yeni.append(f"{ad}={deger}")
            bulundu = True
        else:
            yeni.append(satir)
    if not bulundu:
        yeni.append(f"{ad}={deger}")
    gecici = yol.with_name(yol.name + ".yaziliyor")
    gecici.write_text("\n".join(yeni) + "\n", encoding="utf-8")
    os.replace(gecici, yol)
    return yol


def env_yukle() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_yolu())


def kimlik_denetimi() -> None:
    api_id = os.environ.get(API_ID_DEGISKENI, "").strip()
    api_hash = os.environ.get(API_HASH_DEGISKENI, "").strip()
    if not api_id or not api_hash:
        raise TelegramAyarHatasi(
            f"{API_ID_DEGISKENI} ve {API_HASH_DEGISKENI} .env'de boş: my.telegram.org → API development tools "
            "(adım adım: docs/tarifler/telegram_buyuk_dosya.md §2)")
    if not api_id.isdigit() or len(api_hash) != 32 or any(c not in "0123456789abcdef" for c in api_hash.lower()):
        raise TelegramAyarHatasi(f"{API_ID_DEGISKENI} sayı, {API_HASH_DEGISKENI} 32 karakterlik onaltılık metin "
                                 "olmalı; my.telegram.org'dan yeniden kopyalayın")


# --- Docker yolu ----------------------------------------------------------------------------------------
def docker_yolu() -> str | None:
    bulunan = shutil.which("docker")
    if bulunan:
        return bulunan
    if os.name == "nt":
        aday = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe"
        if aday.exists():
            return str(aday)
    return None


def _kos(komut: list[str], sure: float = 120, ortam: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(komut, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=sure,
                          env=ortam, **_GIZLI)


def _docker(*args: str, sure: float = 120, ortam: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    docker = docker_yolu()
    if not docker:
        raise TelegramAyarHatasi("docker bulunamadı")
    return _kos([docker, *args], sure=sure, ortam=ortam)


def docker_hazir() -> bool:
    try:
        return _docker("info", "--format", "{{.ServerVersion}}", sure=20).returncode == 0
    except (TelegramAyarHatasi, subprocess.TimeoutExpired, OSError):
        return False


def docker_desktop_baslat(bekle: float = DOCKER_BEKLE_SN) -> bool:
    """Docker hazır değilse Windows'ta Docker Desktop'ı gizli başlatır ve servisi bekler."""
    if docker_hazir():
        return True
    if os.name == "nt":
        exe = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe"
        if exe.exists() and not _surec_var("Docker Desktop.exe"):
            print("Docker Desktop arka planda başlatılıyor (pencere açılmaz)...")
            _kos(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
                  f"Start-Process -FilePath '{exe}' -WindowStyle Hidden"], sure=30)
    son = time.monotonic() + bekle
    while time.monotonic() < son:
        if docker_hazir():
            return True
        time.sleep(2)
    return False


def _surec_var(ad: str) -> bool:
    try:
        import psutil
    except ImportError:
        return False
    return any((p.info.get("name") or "").lower() == ad.lower() for p in psutil.process_iter(["name"]))


def ag_kur(ag: str = AG) -> None:
    """IPv4+IPv6 köprü ağı. Varsayılan Docker köprüsü IPv6 rotası vermez: yalnız IPv6 ile dışarı çıkabilen bir
    ağda kapsayıcı çalışır, port açıktır ama Telegram'a ulaşamaz. Ağın sözleşmesi doğrulanır, tahminle geçilmez."""
    if ag not in _docker("network", "ls", "--format", "{{.Name}}").stdout.split():
        sonuc = _docker("network", "create", "--driver", "bridge", "--ipv6", ag)
        if sonuc.returncode != 0:
            raise TelegramAyarHatasi(f"Docker ağı kurulamadı: {sonuc.stderr.strip()[:300]}")
    sozlesme = _docker("network", "inspect", ag, "--format", "{{.Driver}}|{{.EnableIPv6}}").stdout.strip()
    if sozlesme != "bridge|true":
        raise TelegramAyarHatasi(f"Docker ağı {ag} köprü + IPv6 değil ({sozlesme}); ağı silip yeniden kurun: "
                                 f"docker network rm {ag}")


def kapsayici_bilgisi(ad: str = KAPSAYICI) -> dict[str, Any] | None:
    sonuc = _docker("inspect", ad, "--format", "{{json .}}")
    if sonuc.returncode != 0:
        return None
    try:
        veri = json.loads(sonuc.stdout)
    except ValueError:
        return None
    baglar = (veri.get("HostConfig") or {}).get("PortBindings") or {}
    bag = (baglar.get("8081/tcp") or [{}])[0]
    ortam = (veri.get("Config") or {}).get("Env") or []
    return {
        "calisiyor": bool((veri.get("State") or {}).get("Running")),
        "ag": (veri.get("HostConfig") or {}).get("NetworkMode", ""),
        "yerel_kip": "TELEGRAM_LOCAL=1" in ortam,
        "host_ip": bag.get("HostIp", ""),
        "host_port": int(bag.get("HostPort") or 0),
        "yeniden_baslama": ((veri.get("HostConfig") or {}).get("RestartPolicy") or {}).get("Name", ""),
    }


def sozlesme_uygun(bilgi: dict[str, Any], port: int, ag: str = AG) -> bool:
    return (bilgi.get("ag") == ag and bilgi.get("yerel_kip") and bilgi.get("host_ip") == "127.0.0.1"
            and bilgi.get("host_port") == port)


def imaj_hazirla(kaynaktan: bool) -> str:
    if not kaynaktan:
        sonuc = _docker("pull", HAZIR_IMAJ, sure=1800)
        if sonuc.returncode != 0:
            raise TelegramAyarHatasi(f"imaj indirilemedi (internet?): {sonuc.stderr.strip()[:300]}")
        return HAZIR_IMAJ
    if _docker("image", "inspect", YEREL_IMAJ).returncode == 0:
        return YEREL_IMAJ
    print("Resmî kaynaktan imaj derleniyor (ilk kez 10-30 dk sürebilir)...")
    sonuc = _docker("build", "-t", YEREL_IMAJ, "--build-arg", f"COMMIT={KAYNAK_COMMIT}",
                    "-f", str(DOCKERFILE), str(DOCKERFILE.parent), sure=7200)
    if sonuc.returncode != 0:
        raise TelegramAyarHatasi(f"imaj derlenemedi: {sonuc.stderr.strip()[-500:]}")
    return YEREL_IMAJ


def kapsayici_kur(port: int, kaynaktan: bool = False, ad: str = KAPSAYICI) -> None:
    """Tek, adlı kapsayıcı. Sözleşmesi doğruysa dokunulmaz (kimliği değişmez); ağ/port/yerel kip uyuşmuyorsa bir
    kez yeniden yaratılır. Port yalnız 127.0.0.1'e açılır. Kimlik değerleri `-e AD` ile süreç ortamından geçer."""
    ag_kur()
    bilgi = kapsayici_bilgisi(ad)
    if bilgi and not sozlesme_uygun(bilgi, port):
        print("Eski kapsayıcının ağı/portu uyuşmuyor; yeniden kuruluyor.")
        _docker("rm", "-f", ad)
        bilgi = None
    if bilgi is None:
        imaj = imaj_hazirla(kaynaktan)
        ortam = {**os.environ}
        sonuc = _docker("run", "-d", "--name", ad, "--network", AG, "-p", f"127.0.0.1:{port}:8081",
                        "--restart", "unless-stopped", "-e", API_ID_DEGISKENI, "-e", API_HASH_DEGISKENI,
                        "-e", "TELEGRAM_LOCAL=1", imaj, ortam=ortam)
        if sonuc.returncode != 0:
            raise TelegramAyarHatasi(f"kapsayıcı başlatılamadı: {gizle(sonuc.stderr.strip())[:300]}")
    else:
        if bilgi.get("yeniden_baslama") != "unless-stopped":
            _docker("update", "--restart", "unless-stopped", ad)
        if not bilgi.get("calisiyor"):
            _docker("start", ad)


# --- Docker'sız yol: resmî kaynaktan derleme ---------------------------------------------------------------
def wsl_var() -> bool:
    if os.name != "nt" or not shutil.which("wsl.exe"):
        return False
    try:
        sonuc = _kos(["wsl.exe", "-e", "true"], sure=60)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return sonuc.returncode == 0


def wsl_yolu(yol: Path) -> str:
    """C:\\a\\b → /mnt/c/a/b (WSL'nin varsayılan bağlama noktası)."""
    surucu, kalan = yol.drive.rstrip(":").lower(), yol.as_posix().split(":", 1)[-1]
    return f"/mnt/{surucu}{kalan}"


def derleme_komutu() -> list[str]:
    """Windows'ta WSL içinde (root, /opt), diğerlerinde doğrudan (runtime_assets/araclar). Kurulum hedefi WSL'nin
    kendi dosya sisteminde: /mnt/c üzerinden derleme çok yavaştır."""
    if os.name == "nt":
        return ["wsl.exe", "-u", "root", "-e", "bash", wsl_yolu(DERLEME_BETIGI), KAYNAK_COMMIT, WSL_KURULUM]
    return ["bash", str(DERLEME_BETIGI), KAYNAK_COMMIT, str(DERLEME_KOKU)]


def derlenmis_ikili() -> str:
    if os.name == "nt":
        return f"{WSL_KURULUM}/bin/telegram-bot-api"
    return str(DERLEME_KOKU / "bin" / "telegram-bot-api")


def pid_dosyasi() -> Path:
    return PROJE_KOKU / "runtime_assets" / "telegram-bot-api.pid"


def derlemeyle_baslat(port: int) -> int:
    """Gizli, tek örnek. İş ve geçici klasör yalnız sunucunun kendi alanında; port yalnız 127.0.0.1."""
    if port_acik_mi("127.0.0.1", port):
        raise TelegramAyarHatasi(f"port {port} dolu")
    if os.name == "nt":
        kabuk = (f"mkdir -p $HOME/.local/dubworld-telegram-bot-api/is $HOME/.local/dubworld-telegram-bot-api/gecici && "
                 f"exec {derlenmis_ikili()} --local --http-ip-address=127.0.0.1 --http-port={port} "
                 f"--dir=$HOME/.local/dubworld-telegram-bot-api/is --temp-dir=$HOME/.local/dubworld-telegram-bot-api/gecici")
        komut = ["wsl.exe", "-e", "bash", "-c", kabuk]
        ortam = {**os.environ, "WSLENV": f"{API_ID_DEGISKENI}:{API_HASH_DEGISKENI}:" + os.environ.get("WSLENV", "")}
    else:
        (DERLEME_KOKU / "is").mkdir(parents=True, exist_ok=True)
        (DERLEME_KOKU / "gecici").mkdir(parents=True, exist_ok=True)
        komut = [derlenmis_ikili(), "--local", "--http-ip-address=127.0.0.1", f"--http-port={port}",
                 f"--dir={DERLEME_KOKU / 'is'}", f"--temp-dir={DERLEME_KOKU / 'gecici'}"]
        ortam = dict(os.environ)
    ek: dict[str, Any] = dict(_GIZLI)
    if os.name == "nt":
        ek["creationflags"] |= getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        ek["start_new_session"] = True
    surec = subprocess.Popen(komut, env=ortam, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, **ek)
    pid_dosyasi().parent.mkdir(parents=True, exist_ok=True)
    pid_dosyasi().write_text(str(surec.pid), encoding="ascii")
    return surec.pid


# --- hazırlık, kurulum, durum -----------------------------------------------------------------------------
def hazir_bekle(adres: str, belirtec: str, sure: float = HAZIRLIK_SN) -> bool:
    son = time.monotonic() + sure
    host, port = _host_port(adres)
    while time.monotonic() < son:
        if port_acik_mi(host, port):
            if belirtec and get_me(adres, belirtec):
                return True
            if not belirtec and bot_api_mi(adres):
                return True
        time.sleep(1)
    return False


def kip_sec(istenen: str = "auto") -> str:
    if istenen != "auto":
        return istenen
    if docker_yolu():
        return "docker"
    if os.name != "nt" or wsl_var():
        return "derleme"
    raise TelegramAyarHatasi(
        "Ne Docker ne WSL bulundu. Birini kurun ve yeniden çalıştırın: winget install -e --id Docker.DockerDesktop "
        "(yeniden başlatma isteyebilir) ya da wsl --install -d Ubuntu (docs/tarifler/telegram_buyuk_dosya.md §4)")


def kur(kip: str = "auto", kaynaktan: bool = False, port: int | None = None, kuru: bool = False) -> dict[str, Any]:
    """Tek komutluk kurulum: kimlik → port → kip → başlat → getMe → .env. Tekrar çalıştırmak güvenlidir."""
    env_yukle()
    kimlik_denetimi()
    belirtec = os.environ.get(BELIRTEC_DEGISKENI, "").strip()
    istenen_port = port or VARSAYILAN_PORT
    adres = f"http://127.0.0.1:{istenen_port}"
    if port_acik_mi("127.0.0.1", istenen_port):
        calisan = (belirtec and get_me(adres, belirtec)) or (not belirtec and bot_api_mi(adres))
        if calisan:
            print(f"{adres} zaten çalışan bir Bot API sunucusu; yeniden kurulmadan kullanılıyor.")
            if not kuru:
                env_yaz(ADRES_DEGISKENI, adres)
            return {"kip": "mevcut", "adres": adres, "port": istenen_port}
        if kip != "docker" or not _bizim_kapsayici_portu(istenen_port):
            yeni = bos_port(range(istenen_port + 1, istenen_port + 10))
            if yeni is None:
                raise TelegramAyarHatasi(f"{istenen_port}-{istenen_port + 9} portlarının hepsi dolu; --port ile boş "
                                         "bir port verin")
            print(f"Port {istenen_port} başka bir programda; {yeni} kullanılacak.")
            istenen_port, adres = yeni, f"http://127.0.0.1:{yeni}"
    secilen = kip_sec(kip)
    plan = {"kip": secilen, "adres": adres, "port": istenen_port, "kaynaktan": kaynaktan}
    if kuru:
        plan["komut"] = derleme_komutu() if secilen == "derleme" else ["docker", "run", KAPSAYICI]
        return plan
    _disk_denetimi()
    if secilen == "docker":
        if not docker_desktop_baslat():
            raise TelegramAyarHatasi("Docker hizmeti 90 sn'de hazır olmadı; bilgisayarı yeniden başlatıp tekrar "
                                     "deneyin ya da Docker'sız yol: dubla-telegram sunucu kur --kip derleme")
        kapsayici_kur(istenen_port, kaynaktan=kaynaktan)
    else:
        if not _derlenmis_var():
            print("Resmî kaynak derleniyor (ilk kez 10-30 dk; derleme araçları sudo ile kurulabilir)...")
            sonuc = subprocess.run(derleme_komutu(), **_GIZLI)
            if sonuc.returncode != 0:
                raise TelegramAyarHatasi("derleme başarısız (yukarıdaki çıktıya bakın)")
        derlemeyle_baslat(istenen_port)
    if not hazir_bekle(adres, belirtec):
        raise TelegramAyarHatasi(
            f"sunucu {HAZIRLIK_SN} sn'de gerçek getMe cevabı vermedi. Sunucu çalışıyor ama Telegram'a çıkamıyor "
            "olabilir (IPv4/IPv6 ağı, güvenlik duvarı) ya da belirteç/kimlik yanlış: dubla-telegram sunucu durum")
    env_yaz(ADRES_DEGISKENI, adres)
    print(f"HAZIR: {adres} · .env'ye {ADRES_DEGISKENI} yazıldı · sınır 2000 MB")
    return plan


def _bizim_kapsayici_portu(port: int) -> bool:
    try:
        bilgi = kapsayici_bilgisi()
    except TelegramAyarHatasi:
        return False
    return bool(bilgi and bilgi.get("host_port") == port)


def _derlenmis_var() -> bool:
    if os.name == "nt":
        return _kos(["wsl.exe", "-e", "bash", "-c", f"test -x {derlenmis_ikili()}"], sure=60).returncode == 0
    return Path(derlenmis_ikili()).exists()


def _disk_denetimi(gereken_mb: int = 2048) -> None:
    bos = shutil.disk_usage(tempfile.gettempdir()).free
    if bos < gereken_mb * MB:
        raise TelegramAyarHatasi(f"diskte {bos // MB} MB boş; kurulum için en az {gereken_mb} MB gerekir")


def sunucu_bos_alan(ad: str | None = None) -> int | None:
    """Docker kapsayıcısının geçici klasöründe boş bayt (yükleme kopyası buraya yazılır); bilinmiyorsa None."""
    ad = ad or os.environ.get(KAPSAYICI_DEGISKENI) or KAPSAYICI
    if not docker_yolu():
        return None
    try:
        sonuc = _docker("exec", ad, "df", "-Pk", "/tmp", sure=15)  # noqa: S108 (kapsayıcının içi)
    except (subprocess.TimeoutExpired, OSError, TelegramAyarHatasi):
        return None
    satirlar = sonuc.stdout.strip().splitlines()
    if sonuc.returncode != 0 or len(satirlar) < 2:
        return None
    try:
        return int(satirlar[-1].split()[3]) * 1024
    except (IndexError, ValueError):
        return None


def durum() -> dict[str, Any]:
    env_yukle()
    ozet = kontrol_ozeti()
    if docker_yolu():
        try:
            ozet["docker_hazir"] = docker_hazir()
            ozet["kapsayici"] = kapsayici_bilgisi(os.environ.get(KAPSAYICI_DEGISKENI) or KAPSAYICI) if ozet["docker_hazir"] else None
        except (TelegramAyarHatasi, subprocess.TimeoutExpired, OSError):
            ozet["docker_hazir"] = False
    bos = sunucu_bos_alan() if ozet.get("kapsayici") else None
    if bos is not None:
        ozet["sunucu_bos_mb"] = bos // MB
    return ozet


def durdur() -> None:
    ad = os.environ.get(KAPSAYICI_DEGISKENI) or KAPSAYICI
    if docker_yolu() and docker_hazir() and kapsayici_bilgisi(ad):
        _docker("stop", ad)
        print(f"kapsayıcı durdu: {ad} (yeniden: dubla-telegram sunucu baslat)")
    pid = pid_dosyasi()
    if pid.exists():
        import contextlib

        import psutil

        with contextlib.suppress(psutil.Error, ValueError, OSError):  # süreç zaten yoksa
            surec = psutil.Process(int(pid.read_text(encoding="ascii").strip()))
            for cocuk in surec.children(recursive=True):
                cocuk.terminate()
            surec.terminate()
        pid.unlink(missing_ok=True)
        if os.name == "nt":
            _kos(["wsl.exe", "-e", "pkill", "-f", "dubworld-telegram-bot-api/bin/telegram-bot-api"], sure=30)
        print("derlenmiş sunucu durdu")


def baslat() -> None:
    env_yukle()
    adres = yerel_adres()
    if not adres:
        raise TelegramAyarHatasi(f"{ADRES_DEGISKENI} boş: önce dubla-telegram sunucu kur")
    _, port = _host_port(adres)
    ad = os.environ.get(KAPSAYICI_DEGISKENI) or KAPSAYICI
    if docker_yolu() and docker_desktop_baslat() and kapsayici_bilgisi(ad):
        _docker("start", ad)
    elif not port_acik_mi("127.0.0.1", port):
        derlemeyle_baslat(port)
    if not hazir_bekle(adres, os.environ.get(BELIRTEC_DEGISKENI, "").strip()):
        raise TelegramAyarHatasi("sunucu başladı ama getMe cevabı yok: dubla-telegram sunucu durum")
    print(f"HAZIR: {adres}")


def kaldir() -> None:
    """Kapsayıcı ve ağ silinir, .env'deki adres boşaltılır (kimlik değerlerine dokunulmaz). İmaj silinmez (yeniden
    kurulum hızlı olsun); silmek için: docker image rm <imaj>."""
    durdur()
    ad = os.environ.get(KAPSAYICI_DEGISKENI) or KAPSAYICI
    if docker_yolu() and docker_hazir():
        _docker("rm", "-f", ad)
        _docker("network", "rm", AG)
    if env_yolu().exists():
        env_yaz(ADRES_DEGISKENI, "")
    print("yerel sunucu kaldırıldı; bot bulut Bot API'ye (50 MB) döndü")


def temizle_komutu(saat: float) -> str:
    dakika = max(1, int(saat * 60))
    klasorler = " ".join(f"{KAPSAYICI_IS_KLASORU}/*/{k}" for k in INDIRME_ALT_KLASORLERI)
    return (f"for d in {klasorler} {KAPSAYICI_GECICI_KLASOR}; do [ -d \"$d\" ] && "
            f"find \"$d\" -type f -mmin +{dakika} -print -delete; done; true")


def temizle(saat: float = 24, kuru: bool = False) -> list[str]:
    """Sunucunun indirdiği (getFile) ve yarım kalmış yükleme kopyalarını siler; bot veritabanına dokunmaz.
    Yerel kipte sunucu dosyaları kendiliğinden silmez; kapsayıcı katmanı bu yüzden büyür."""
    ad = os.environ.get(KAPSAYICI_DEGISKENI) or KAPSAYICI
    komut = temizle_komutu(saat)
    if kuru:
        komut = komut.replace(" -print -delete", " -print")
    sonuc = _docker("exec", ad, "sh", "-c", komut, sure=300)
    if sonuc.returncode != 0:
        raise TelegramAyarHatasi(f"temizlik çalışmadı: {sonuc.stderr.strip()[:300]}")
    # Yol listesi belirteç içeren klasör adlarını taşır: yalnız sayı döner, yol yazılmaz.
    return [s for s in sonuc.stdout.splitlines() if s.strip()]


def bulut_cikis() -> None:
    """Botu bulut Bot API'den çıkarır (logOut). Resmî belge: yerel sunucuda bütün güncellemelerin (gelen mesaj)
    garanti gelmesi için gerekir; dosya göndermek için gerekmez. Sonraki 10 dk bulut uç noktasına dönülemez."""
    env_yukle()
    belirtec = os.environ.get(BELIRTEC_DEGISKENI, "").strip()
    if not belirtec:
        raise TelegramAyarHatasi(f"{BELIRTEC_DEGISKENI} boş")
    try:
        with urllib.request.urlopen(f"{BULUT_ADRESI}/bot{belirtec}/logOut", timeout=20) as cevap:  # noqa: S310
            veri = json.loads(cevap.read().decode("utf-8"))
    except urllib.error.HTTPError as hata:
        veri = json.loads(hata.read().decode("utf-8") or "{}")
    except (OSError, ValueError) as hata:
        raise TelegramAyarHatasi(f"logOut çağrılamadı: {gizle(str(hata))}") from hata
    print("logOut: " + ("tamam" if veri.get("ok") else gizle(str(veri.get("description", "")))))


# --- komut satırı: dubla-telegram sunucu <eylem> -----------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ayr = argparse.ArgumentParser(prog="dubla-telegram sunucu",
                                  description="Yerel Telegram Bot API sunucusu (2000 MB'a kadar gönderim)")
    alt = ayr.add_subparsers(dest="eylem", required=True)
    k = alt.add_parser("kur", help="kur ve başlat (Docker varsa Docker, yoksa derleme)")
    k.add_argument("--kip", choices=("auto", "docker", "derleme"), default="auto")
    k.add_argument("--kaynaktan", action="store_true", help="Docker imajını resmî kaynaktan derle")
    k.add_argument("--port", type=int)
    k.add_argument("--kuru", action="store_true", help="yalnız planı yaz, hiçbir şey kurma")
    d = alt.add_parser("durum", help="ayar, port, getMe, kapsayıcı, sunucu diski")
    d.add_argument("--json", action="store_true")
    alt.add_parser("baslat")
    alt.add_parser("durdur")
    alt.add_parser("kaldir", help="kapsayıcı + ağ silinir, .env adresi boşaltılır")
    t = alt.add_parser("temizle", help="sunucunun indirdiği eski dosyaları sil")
    t.add_argument("--saat", type=float, default=24)
    t.add_argument("--kuru", action="store_true")
    alt.add_parser("bulut-cikis", help="botu bulut Bot API'den çıkar (logOut; isteğe bağlı)")
    args = ayr.parse_args(argv)
    try:
        if args.eylem == "kur":
            plan = kur(args.kip, args.kaynaktan, args.port, args.kuru)
            if args.kuru:
                print(json.dumps(plan, ensure_ascii=False))
        elif args.eylem == "durum":
            ozet = durum()
            print(json.dumps(ozet, ensure_ascii=False) if args.json else f"telegram yerel sunucu: {kontrol_metni(ozet)}")
            if not args.json and ozet.get("kapsayici") is not None:
                print(f"  kapsayıcı: {ozet['kapsayici']}")
            if not args.json and "sunucu_bos_mb" in ozet:
                print(f"  sunucu geçici alanı boş: {ozet['sunucu_bos_mb']} MB")
        elif args.eylem == "baslat":
            baslat()
        elif args.eylem == "durdur":
            durdur()
        elif args.eylem == "kaldir":
            kaldir()
        elif args.eylem == "temizle":
            env_yukle()
            silinen = temizle(args.saat, args.kuru)
            print(f"{'silinecek' if args.kuru else 'silindi'}: {len(silinen)} dosya ({args.saat:g} saatten eski)")
        elif args.eylem == "bulut-cikis":
            bulut_cikis()
    except TelegramAyarHatasi as hata:
        print(f"Yerel sunucu: {gizle(str(hata))}")
        return 2
    except subprocess.TimeoutExpired as hata:
        print(f"Yerel sunucu: komut zaman aşımına uğradı ({hata.timeout:.0f} sn)")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
