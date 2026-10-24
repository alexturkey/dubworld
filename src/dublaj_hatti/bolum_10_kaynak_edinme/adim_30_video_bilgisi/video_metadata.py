
'''
Video Metadata Extraction

ffprobe ile video metadata bilgilerini alir ve loglar.
'''
import json
import os
import subprocess
from typing import Any, Dict, Optional

def get_video_metadata(video_path = None):
    """
    ffprobe ile video metadata al

    Args:
        video_path: Video dosya yolu

    Returns:
        {
            'width': 1080,
            'height': 1920,
            'aspect_ratio': '9:16',
            'display_aspect_ratio': '9:16',
            'codec_name': 'h264',
            'codec_long_name': 'H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10',
            'pixel_aspect_ratio': '1:1',
            'sample_aspect_ratio': '1:1',
            'rotation': 0,
            'duration': 15.5,
            'bitrate': 2500000,
            'fps': 30.0,
            'container': 'mp4'
        }

    Raises:
        FileNotFoundError: Video dosyasi bulunamazsa
        RuntimeError: ffprobe hatasi
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f'''Video bulunamadi: {video_path}''')
    cmd = [
        None,
        '-v',
        'quiet',
        '-print_format',
        'json',
        '-show_streams',
        '-show_format',
        video_path]
# WARNING: Decompyle incomplete


def log_video_metadata(video_path = None, label = None, logger = None):
    '''
    Video metadata\'sini logla

    Args:
        video_path: Video dosya yolu
        label: "ORIJINAL VIDEO (Download sonrasi)" veya "ISLENMIŞ VIDEO (Encode sonrasi)"
        logger: Logger objesi

    Example:
        log_video_metadata("/path/to/video.mp4", "ORIJINAL VIDEO", logger)
    '''
    pass
# WARNING: Decompyle incomplete

