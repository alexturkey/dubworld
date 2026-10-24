__all__ = ["get_custom_align_model_name", "normalize_language_code", "transcribe_audio"]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    from . import worker

    return getattr(worker, name)
