import numpy as np

from .silence_cleanup import clean_unstable_silence_notes
from .synthesis_profile import (
    SUPERTONIC_CFG_SCALE,
    SUPERTONIC_TIME_GRID,
    SUPERTONIC_TOTAL_STEPS,
    SUPERTONIC_TRANSITION_STEP,
)


def prepare_k15_vector_model(model):
    from onnx import numpy_helper

    clock_nodes = [
        (node.name, node.op_type, list(node.input))
        for node in model.graph.node
        if "current_step" in node.input or "total_step" in node.input
    ]
    if clock_nodes != [
        ("/Div", "Div", ["current_step", "total_step"]),
        ("/Reciprocal", "Reciprocal", ["total_step"]),
    ]:
        raise ValueError("Unsupported Supertonic vector clock contract")
    replacements = {
        "/Constant_3_output_0": (4.0, SUPERTONIC_CFG_SCALE),
        "/Constant_4_output_0": (3.0, SUPERTONIC_CFG_SCALE - 1.0),
    }
    found = set()
    for initializer in model.graph.initializer:
        if initializer.name not in replacements:
            continue
        expected, value = replacements[initializer.name]
        current = np.asarray(numpy_helper.to_array(initializer))
        if current.shape != () or float(current) != expected:
            raise ValueError("Unsupported Supertonic embedded CFG value")
        found.add(initializer.name)
        initializer.CopyFrom(numpy_helper.from_array(np.asarray(value, dtype=np.float32), initializer.name))
    if found != set(replacements):
        raise ValueError("Supertonic embedded CFG initializers missing")
    return model


def create_k15_vector_session(runtime):
    from .k15_cache import create_cached_k15_vector_session

    return create_cached_k15_vector_session(runtime)


def resize_latent(latent, length):
    if latent.ndim != 3 or latent.shape[-1] < 1 or length < 1:
        raise ValueError("Nonempty latent and positive target length required")
    old_positions = np.arange(latent.shape[-1], dtype=np.float64)
    new_positions = np.linspace(0, latent.shape[-1] - 1, length)
    flat = latent.reshape(-1, latent.shape[-1])
    resized = np.stack([np.interp(new_positions, old_positions, row) for row in flat])
    return resized.reshape(*latent.shape[:-1], length).astype(np.float32)


def infer_k15(runtime, text_list, lang_list, style, total_step, speed, seed):
    if total_step != SUPERTONIC_TOTAL_STEPS or isinstance(total_step, bool):
        raise ValueError("Supertonic K15 requires 10 steps")
    if len(text_list) != 1 or len(lang_list) != 1:
        raise ValueError("Supertonic K15 requires a single-item batch")
    if not np.isfinite(speed) or speed <= 0:
        raise ValueError("Supertonic speed must be finite and positive")
    prepared = runtime.text_processor.prepare_texts(text_list, lang_list)
    text_ids, text_mask = runtime.text_processor.encode_prepared_texts(prepared)
    duration, = runtime.dp_ort.run(
        runtime.dp_output_names,
        {"text_ids": text_ids, "style_dp": style.dp, "text_mask": text_mask},
        runtime.run_options,
    )
    if not np.isfinite(duration).all() or (duration <= 0).any():
        raise ValueError("Invalid Supertonic predicted duration")
    target_duration = duration / speed
    text_emb, = runtime.text_enc_ort.run(
        runtime.text_enc_output_names,
        {"text_ids": text_ids, "style_ttl": style.ttl, "text_mask": text_mask},
        runtime.run_options,
    )
    latent, source_mask = runtime.sample_noisy_latent(duration, np.random.default_rng(seed))
    target, target_mask = runtime.sample_noisy_latent(target_duration, np.random.default_rng(seed))
    target_frames = target.shape[-1]
    feed = {"text_emb": text_emb, "style_ttl": style.ttl, "text_mask": text_mask, "latent_mask": source_mask}
    session = runtime.get_vector_estimator()
    for step, (start, end) in enumerate(zip(SUPERTONIC_TIME_GRID, SUPERTONIC_TIME_GRID[1:])):
        if step == SUPERTONIC_TRANSITION_STEP:
            if latent.shape[-1] != target_frames:
                latent = resize_latent(latent, target_frames)
            feed["latent_mask"] = target_mask
        delta = end - start
        feed.update({
            "noisy_latent": latent,
            "current_step": np.array([start / delta], dtype=np.float32),
            "total_step": np.array([1 / delta], dtype=np.float32),
        })
        latent, = session.run(runtime.vector_est_output_names, feed, runtime.run_options)
        if not np.isfinite(latent).all():
            raise ValueError("Nonfinite Supertonic latent")
    if latent.shape[-1] != target_frames:
        raise ValueError("Supertonic final latent length mismatch")
    waveform = vocode_latent(runtime, latent)
    cleaned, mask = clean_unstable_silence_notes(latent, waveform, lambda value: vocode_latent(runtime, value))
    if mask.any():
        waveform = vocode_latent(runtime, cleaned)
    return waveform, target_duration


def vocode_latent(runtime, latent):
    waveform, = runtime.vocoder_ort.run(runtime.vocoder_output_names, {"latent": latent}, runtime.run_options)
    if not np.isfinite(waveform).all():
        raise ValueError("Nonfinite Supertonic waveform")
    return waveform
