"""Istege bagli URL indirici (yt-dlp).

yt-dlp ayri bir istege bagli pakettir; kurulu degilse yalniz yerel video dosyasi kullanilir.
Yalniz hakkina sahip oldugunuz ya da indirme izni olan icerigi indirin; platform kullanim kosullari sizin sorumlulugunuzdadir.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

from dublaj_hatti.bolum_00_omurga.runtime.internet_gateway import run_with_internet_gateway
from dublaj_hatti.bolum_10_kaynak_edinme.adim_10_dosya_adi_guvenligi.filename_sanitizer import sanitize_filename

ALLOWED_HOST_SUFFIXES = (
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "dailymotion.com",
)
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov")
MAX_DOWNLOAD_BYTES = 4 * 1024 * 1024 * 1024
RETRY_DELAY_SECONDS = 5


class YtDlpYokHatasi(RuntimeError):
    pass


def _host_allowed(host: str) -> bool:
    host = host.split(":", 1)[0].strip(".").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_HOST_SUFFIXES)


def is_url(text: str) -> bool:
    if not text:
        return False
    text = text.strip()
    if text.startswith("www."):
        text = "https://" + text
    if not text.startswith(("http://", "https://")):
        return False
    parsed = urlparse(text)
    return bool(parsed.netloc) and _host_allowed(parsed.netloc)


def _load_yt_dlp():
    try:
        import yt_dlp
    except ImportError as exc:
        raise YtDlpYokHatasi(
            "URL'den indirme icin istege bagli 'yt-dlp' paketi kurulu degil. "
            "Kurulum: scripts\\kur.ps1 -Adim youtube (ya da yerel video dosyasi verin)."
        ) from exc
    return yt_dlp


def _format_string(max_height: int) -> str:
    return (
        f"bestvideo[vcodec^=avc1][height<={max_height}]+bestaudio/"
        f"bestvideo[height<={max_height}]+bestaudio/"
        f"best[height<={max_height}]/best"
    )


def download_video(
    url: str,
    download_dir: Path,
    max_height: int = 1080,
    progress_callback: Optional[Callable[[int, str, str], None]] = None,
    logger: Optional[Any] = None,
) -> Dict[str, Any]:
    if not is_url(url):
        raise ValueError("Desteklenmeyen adres: yalniz https YouTube/Vimeo/Dailymotion baglantisi kabul edilir")
    yt_dlp = _load_yt_dlp()
    download_dir = Path(download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    def progress_hook(event: Dict[str, Any]) -> None:
        if not progress_callback:
            return
        if event.get("status") == "downloading":
            total = event.get("total_bytes") or event.get("total_bytes_estimate") or 0
            done = event.get("downloaded_bytes") or 0
            speed = event.get("speed")
            eta = event.get("eta")
            progress_callback(
                int(done * 100 / total) if total else 0,
                f"{speed / 1048576:.1f} MB/s" if speed else "",
                f"{int(eta) // 60}:{int(eta) % 60:02d}" if eta else "",
            )
        elif event.get("status") == "finished":
            progress_callback(100, "", "")

    base_options = {"quiet": True, "no_warnings": True, "noplaylist": True, "max_filesize": MAX_DOWNLOAD_BYTES}

    def run(options: Dict[str, Any], download: bool, proxy_url: Optional[str]):
        current = dict(options)
        if proxy_url:
            current["proxy"] = proxy_url
        with yt_dlp.YoutubeDL(current) as ydl:
            return ydl.extract_info(url, download=download)

    info = run_with_internet_gateway(lambda route: run(base_options, False, route.proxy_url), "video_metadata", logger, download_dir)
    original_name = str(info.get("title") or "video")
    source_lang = info.get("language")
    safe_title = sanitize_filename(original_name, keep_case=False, source_lang=source_lang)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    options = {
        **base_options,
        "format": _format_string(max_height),
        "outtmpl": str(download_dir / f"{safe_title}_{stamp}.%(ext)s"),
        "progress_hooks": [progress_hook],
    }
    before = set(download_dir.glob("*"))
    try:
        run_with_internet_gateway(lambda route: run(options, True, route.proxy_url), "video_download", logger, download_dir)
    except Exception as error:
        text = str(error)
        if "Read timed out" not in text and "403" not in text:
            raise
        if logger:
            logger.warning("[INDIRME] gecici hata, %d sn sonra bir kez daha denenecek: %s", RETRY_DELAY_SECONDS, text)
        time.sleep(RETRY_DELAY_SECONDS)
        run_with_internet_gateway(lambda route: run(options, True, route.proxy_url), "video_download_retry", logger, download_dir)

    new_files = [f for f in set(download_dir.glob("*")) - before if f.suffix.lower() in VIDEO_EXTENSIONS]
    if not new_files:
        raise RuntimeError("Indirilen video dosyasi bulunamadi")
    video_path = max(new_files, key=lambda f: f.stat().st_mtime)
    if logger:
        logger.info("[INDIRME] tamam: %s", video_path.name)
    return {"video_path": video_path, "original_name": original_name, "source_lang": source_lang}
