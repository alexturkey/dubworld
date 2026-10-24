# ADR 0011: Automatic encoder selection by trial encode; CQ 26 default

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0011)

## Context
NVENC is fast but unavailable on CPU-only machines and on drivers older than the pinned FFmpeg's NVENC API. Its quality
per byte on Pascal depends on content: equivalent on GPU-rendered scenes, worse than x264 on flat drawn video.

## Decision
A 0.1 s trial encode decides once per process: `h264_nvenc` if it works, else `libx264`; override with
`DUBLAJ_VIDEO_KODLAYICI`. Default output policy CQ 26 (measured SSIM ≈ 0.995–0.997 against CQ 23 with ≈ 28–30 % smaller
files). Subtitles are burned in the single batch encode; there is no second full encode.

## Consequences
Runs on any machine; users with flat or drawn content may prefer `x264`. Re-measure on newer GPUs.

## Alternatives considered
Hard-coded NVENC (failed on CPU machines); always x264 (slower on long videos); a second encode for subtitles and size
(13 of 27 minutes on a long video, and it hid a frame-shortage defect).
