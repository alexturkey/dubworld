# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_ASSETS_ROOT = PROJECT_ROOT / "runtime_assets"


def runtime_asset_root() -> Path:
    return RUNTIME_ASSETS_ROOT


def huggingface_home() -> Path:
    env_path = os.environ.get("DUBLAJ_HF_HOME", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    return RUNTIME_ASSETS_ROOT / "model_cache" / "huggingface"


def huggingface_hub_cache(cache_dir: str | Path | None = None) -> Path:
    home = Path(cache_dir).expanduser().resolve() if cache_dir else huggingface_home()
    return home / "hub"


def torch_home() -> Path:
    env_path = os.environ.get("DUBLAJ_TORCH_HOME", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    return RUNTIME_ASSETS_ROOT / "model_cache" / "torch"


def modelscope_model_cache_root() -> Path:
    return RUNTIME_ASSETS_ROOT / "model_cache" / "modelscope" / "hub" / "models"


def apply_huggingface_env() -> Path:
    home = huggingface_home()
    os.environ["HF_HOME"] = str(home)
    os.environ["TRANSFORMERS_CACHE"] = str(huggingface_hub_cache(home))
    os.environ["HF_HUB_CACHE"] = str(huggingface_hub_cache(home))
    return home


def build_model_cache_env(cache_dir: str | Path | None = None) -> dict[str, str]:
    home = Path(cache_dir).expanduser().resolve() if cache_dir else huggingface_home()
    env = os.environ.copy()
    env["HF_HOME"] = str(home)
    env["TRANSFORMERS_CACHE"] = str(huggingface_hub_cache(home))
    env["HF_HUB_CACHE"] = str(huggingface_hub_cache(home))
    env["TORCH_HOME"] = str(torch_home())
    return env


def apply_torch_env() -> Path:
    home = torch_home()
    os.environ["TORCH_HOME"] = str(home)
    return home


def parakeet_unified_en_int8_model_dir() -> Path:
    return (
        RUNTIME_ASSETS_ROOT
        / "model_cache"
        / "sherpa_onnx"
        / "sherpa-onnx-nemo-parakeet-unified-en-0.6b-int8-non-streaming"
    )
