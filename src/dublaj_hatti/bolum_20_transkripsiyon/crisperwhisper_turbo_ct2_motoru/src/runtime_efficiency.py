from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from file_integrity import buffered_sha256_file
import time


execution_policy = {
    'model_lifetime': 'one_request_then_process_exit',
    'preparation': 'parallel_cpu_vad_and_model_load_v1',
    'vad_io': 'preallocated_cpu_iobinding_same_graph_v1',
    'encoder_reuse': 'same_window_same_feature_object_v1',
    'integrity_read_buffer_bytes': 8 * 1024 * 1024,
    'integrity_policy': 'fresh_full_sha256_host_python_on_windows_mount_v1',
    'integrity_native_minimum_bytes': 64 * 1024 * 1024,
}



class EncoderReuse:
    def __init__(self, model, counts):
        self.model = model
        self.features = None
        self.encoded = None
        self.counts = counts

    def __getattr__(self, name):
        return getattr(self.model, name)

    def encode(self, features, *args, **kwargs):
        if args or kwargs:
            return self.model.encode(features, *args, **kwargs)
        if features is self.encoded and features is not None:
            return features
        if features is self.features and self.encoded is not None:
            self.counts['encoder_reuse_hits'] += 1
            return self.encoded
        result = self.model.encode(features)
        self.counts['encoder_calls'] += 1
        self.features, self.encoded = features, result
        return result

    def generate(self, features, *args, **kwargs):
        return self.model.generate(self.encode(features), *args, **kwargs)

    def prefill_with_attention(self, features, *args, **kwargs):
        return self.model.prefill_with_attention(self.encode(features), *args, **kwargs)

    def clear(self):
        self.features = None
        self.encoded = None


@contextmanager
def reuse_window_encoder(model, counts):
    native = model._engine.model
    reused = EncoderReuse(native, counts)
    model._engine.model = reused
    try:
        yield
    finally:
        model._engine.model = native
        reused.clear()


def prepare_model_and_audio(model_factory, prepare_audio, timings):
    started = time.perf_counter()

    def load_model():
        load_started = time.perf_counter()
        try:
            return model_factory()
        finally:
            timings['model_load_seconds'] = time.perf_counter() - load_started

    try:
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix='ct2_prepare') as executor:
            future = executor.submit(load_model)
            audio_started = time.perf_counter()
            try:
                prepared = prepare_audio()
            finally:
                timings['vad_seconds'] = time.perf_counter() - audio_started
            wait_started = time.perf_counter()
            try:
                model = future.result()
            finally:
                timings['model_wait_seconds'] = time.perf_counter() - wait_started
        return model, prepared
    finally:
        timings['preparation_total_seconds'] = time.perf_counter() - started
        timings['preparation_overlap_seconds'] = max(
            0.0,
            timings.get('model_load_seconds', 0.0)
            + timings.get('vad_seconds', 0.0)
            - timings['preparation_total_seconds'],
        )
