import os
import shutil
from pathlib import Path
from typing import Optional, Tuple

from dublaj_hatti.bolum_10_kaynak_edinme.adim_20_kaynak_alma.youtube_downloader import (
    download_video,
    is_url,
)


def prepare_source_video(source: str, run_dir: str, logger: Optional[object] = None) -> Tuple[str, str, Optional[str]]:
    target_path = os.path.join(run_dir, "video_run.mp4")

    if is_url(source):
        if logger:
            logger.info("Video adresten indiriliyor...")
        try:
            result = download_video(
                url=source,
                download_dir=Path(run_dir),
                max_height=1080,
                progress_callback=None,
                logger=logger,
            )
            downloaded_path = str(result["video_path"])
            video_title = result.get("original_name", "video")
            source_lang = result.get("source_lang", None)
            if logger:
                logger.info("YouTube videosu indirildi: %s", downloaded_path)
                logger.info("Kaynak dil: %s", source_lang or "auto")

            shutil.copy2(downloaded_path, target_path)
            if logger:
                logger.info("Video hazir: %s", target_path)
            return target_path, video_title, source_lang
        except Exception as exc:
            if logger:
                logger.error("YouTube indirme hatasi: %s", exc)
            raise ValueError(f"Video indirilemedi: {exc}") from exc

    from dublaj_hatti.bolum_10_kaynak_edinme.adim_20_kaynak_alma.galeri_indirici import galeri_adresi_mi
    from dublaj_hatti.bolum_10_kaynak_edinme.adim_20_kaynak_alma.galeri_indirici import indir as galeri_indir

    if galeri_adresi_mi(source):
        if logger:
            logger.info("Video galeri baglantisindan indiriliyor (gallery-dl, ayri surec)...")
        try:
            downloaded = galeri_indir(source.strip(), run_dir, logger=logger)
        except Exception as exc:
            raise ValueError(f"Video indirilemedi: {exc}") from exc
        shutil.copy2(downloaded, target_path)
        return target_path, downloaded.stem, None

    if source.strip().lower().startswith(("http://", "https://", "www.")):
        raise ValueError("Desteklenmeyen adres: yalniz https YouTube/Vimeo/Dailymotion (yt-dlp) ya da Instagram (gallery-dl) baglantisi ya da yerel video dosyasi")
    if not os.path.isfile(source):
        raise FileNotFoundError(f"Video bulunamadi: {source}")
    shutil.copy2(source, target_path)

    video_title = os.path.splitext(os.path.basename(source))[0]

    if logger:
        logger.info("Video hazir: %s", target_path)
    return target_path, video_title, None
