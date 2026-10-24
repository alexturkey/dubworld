from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np


@dataclass
class SegmentAudio:
    index: int
    wav_array: np.ndarray
    start_time: float
    engine_name: str
    raw_duration: float = 0.0
    word_boundaries: List[dict] = field(default_factory=list)
    trim_meta: dict = field(default_factory=dict)
    spoken_text: str = ""
