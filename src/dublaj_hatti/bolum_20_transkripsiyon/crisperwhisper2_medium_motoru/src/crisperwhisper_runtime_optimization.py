from __future__ import annotations

import hashlib
from contextlib import AbstractContextManager, nullcontext
from types import MethodType


OPTION12_RUNTIME_OPTIMIZATION_ID = "runtime23_v5_language_route"
OPTION12_CJK_LANGUAGE_CODES = frozenset({"ja", "lo", "my", "th", "yue", "zh"})
OPTION12_PLAIN_CONSENSUS_SEED_COUNT = 4
OPTION12_INTENDED_CONSENSUS_SEEDS = (5, 8, 15)


class _CjkRuntimeRoute(AbstractContextManager):
    def __init__(self, optimizer):
        self.optimizer = optimizer
        self.engine = optimizer.engine
        self.engine_class = type(self.engine)
        self.original_generate = None
        self.original_generate_sampled = None
        self.original_batch = None
        self.had_batch = False

    def __enter__(self):
        self.original_generate = self.engine_class.generate
        self.original_generate_sampled = self.engine_class.generate_sampled
        self.had_batch = hasattr(self.engine, "generate_sampled_batch")
        if self.had_batch:
            self.original_batch = self.engine.generate_sampled_batch

        original_generate = self.original_generate
        original_generate_sampled = self.original_generate_sampled
        optimizer = self.optimizer

        def auxiliary_sdpa_generate(engine, *args, **kwargs):
            return optimizer.with_sdpa(original_generate, engine, *args, **kwargs)

        def auxiliary_sdpa_sampled(engine, *args, **kwargs):
            return optimizer.with_sdpa(
                original_generate_sampled,
                engine,
                *args,
                **kwargs,
            )

        def generate_sampled_batch(
            engine,
            features,
            prompt_tokens,
            *,
            seeds,
            max_length=256,
            temperature=0.8,
            topk=0,
            suppress_tokens=None,
        ):
            return optimizer.with_sdpa(
                optimizer.generate_sampled_batch,
                engine,
                features,
                prompt_tokens,
                seeds=seeds,
                max_length=max_length,
                temperature=temperature,
                topk=topk,
                suppress_tokens=suppress_tokens,
            )

        self.engine_class.generate = auxiliary_sdpa_generate
        self.engine_class.generate_sampled = auxiliary_sdpa_sampled
        self.engine.generate_sampled_batch = MethodType(
            generate_sampled_batch,
            self.engine,
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.engine_class.generate = self.original_generate
        self.engine_class.generate_sampled = self.original_generate_sampled
        if self.had_batch:
            self.engine.generate_sampled_batch = self.original_batch
        else:
            self.engine.__dict__.pop("generate_sampled_batch", None)
        return False


class Option12RuntimeOptimization(AbstractContextManager):
    def __init__(self, model, torch):
        self.model = model
        self.torch = torch
        self.engine = model._engine
        self.model_configs = {
            id(value): value
            for value in (
                self.engine.model.config,
                self.engine.model.model.config,
            )
        }
        self.original_attention_implementations = {}
        self.original_eager_attention = None
        self.encoder = self.engine.model.model.encoder
        self.original_encoder_forward = None
        self.encoder_cache = {
            "key": None,
            "output": None,
            "hits": 0,
            "misses": 0,
        }

    def __enter__(self):
        import transformers.models.whisper.modeling_whisper as whisper_modeling

        self.original_attention_implementations = {
            key: value._attn_implementation
            for key, value in self.model_configs.items()
        }
        self.original_eager_attention = whisper_modeling.eager_attention_forward
        alignment_layers = {
            int(layer_index)
            for layer_index, _head_index in self.engine._resolved_alignment_heads()
        }
        selected_modules = {
            id(self.engine.model.model.decoder.layers[layer_index].encoder_attn)
            for layer_index in alignment_layers
        }
        decoder_cross_modules = {
            id(layer.encoder_attn)
            for layer in self.engine.model.model.decoder.layers
        }
        torch = self.torch

        def eager_attention_without_unit_scale(
            module,
            query,
            key,
            value,
            attention_mask,
            scaling=None,
            dropout=0.0,
            **attention_kwargs,
        ):
            if scaling is None:
                scaling = query.size(-1) ** -0.5
            attention_weights = torch.matmul(query, key.transpose(2, 3))
            if float(scaling) != 1.0:
                attention_weights = attention_weights * scaling
            if attention_mask is not None:
                attention_weights = attention_weights + attention_mask
            attention_weights = torch.nn.functional.softmax(
                attention_weights,
                dim=-1,
            )
            attention_weights = torch.nn.functional.dropout(
                attention_weights,
                p=dropout,
                training=module.training,
            )
            attention_output = torch.matmul(attention_weights, value)
            attention_output = attention_output.transpose(1, 2).contiguous()
            return attention_output, attention_weights

        def selective_attention(
            module,
            query,
            key,
            value,
            attention_mask,
            **attention_kwargs,
        ):
            output_attentions = bool(attention_kwargs.get("output_attentions", False))
            if output_attentions and id(module) in selected_modules:
                return eager_attention_without_unit_scale(
                    module,
                    query,
                    key,
                    value,
                    attention_mask,
                    **attention_kwargs,
                )
            if output_attentions and id(module) in decoder_cross_modules:
                return eager_attention_without_unit_scale(
                    module,
                    query,
                    key,
                    value,
                    attention_mask,
                    **attention_kwargs,
                )
            attention_output, _attention_weights = eager_attention_without_unit_scale(
                module,
                query,
                key,
                value,
                attention_mask,
                **attention_kwargs,
            )
            if output_attentions and id(module) in decoder_cross_modules:
                return attention_output, None
            return attention_output, None

        whisper_modeling.eager_attention_forward = selective_attention
        for value in self.model_configs.values():
            value._attn_implementation = "eager"

        self.original_encoder_forward = self.encoder.forward

        def cached_encoder_forward(*args, **kwargs):
            input_features = args[0] if args else kwargs.get("input_features")
            base_features = input_features[:1]
            if input_features.shape[0] > 1 and not torch.equal(
                input_features,
                base_features.expand_as(input_features),
            ):
                base_features = input_features
            feature_bytes = (
                base_features.detach().to("cpu").contiguous().numpy().tobytes()
            )
            feature_key = (
                tuple(base_features.shape),
                str(input_features.dtype),
                hashlib.sha256(feature_bytes).hexdigest(),
            )
            if feature_key == self.encoder_cache["key"]:
                self.encoder_cache["hits"] += 1
                cached_output = self.encoder_cache["output"]
                if input_features.shape[0] == base_features.shape[0]:
                    return cached_output
                expanded_values = {}
                for key, value in cached_output.items():
                    if (
                        torch.is_tensor(value)
                        and value.ndim > 0
                        and value.shape[0] == 1
                    ):
                        expanded_values[key] = value.expand(
                            input_features.shape[0],
                            *value.shape[1:],
                        )
                    else:
                        expanded_values[key] = value
                return cached_output.__class__(**expanded_values)
            self.encoder_cache["misses"] += 1
            output = self.original_encoder_forward(*args, **kwargs)
            self.encoder_cache["key"] = feature_key
            self.encoder_cache["output"] = output
            return output

        self.encoder.forward = cached_encoder_forward
        self.model._option12_runtime_optimization = self
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        import transformers.models.whisper.modeling_whisper as whisper_modeling

        self.encoder.forward = self.original_encoder_forward
        for key, value in self.model_configs.items():
            value._attn_implementation = self.original_attention_implementations[key]
        whisper_modeling.eager_attention_forward = self.original_eager_attention
        self.model.__dict__.pop("_option12_runtime_optimization", None)
        return False

    def language_route(self, language: str):
        if str(language).lower() in OPTION12_CJK_LANGUAGE_CODES:
            return _CjkRuntimeRoute(self)
        return nullcontext()

    def with_sdpa(self, function, *args, **kwargs):
        previous = {
            key: value._attn_implementation
            for key, value in self.model_configs.items()
        }
        try:
            for value in self.model_configs.values():
                value._attn_implementation = "sdpa"
            return function(*args, **kwargs)
        finally:
            for key, value in self.model_configs.items():
                value._attn_implementation = previous[key]

    def generate_sampled_batch(
        self,
        engine,
        features,
        prompt_tokens,
        *,
        seeds,
        max_length=256,
        temperature=0.8,
        topk=0,
        suppress_tokens=None,
    ) -> dict[int, list[int]]:
        torch = self.torch
        selected_seeds = tuple(int(value) for value in seeds)
        batch_size = len(selected_seeds)
        decoder_input_ids = torch.tensor(
            [list(prompt_tokens)] * batch_size,
            device=engine.device,
            dtype=torch.long,
        )
        batched_features = features.expand(batch_size, *features.shape[1:])
        suppress = engine._resolve_suppress(suppress_tokens)
        generators = []
        for seed in selected_seeds:
            generator = torch.Generator(device=features.device)
            generator.manual_seed(seed)
            generators.append(generator)
        original_multinomial = torch.multinomial

        def row_seeded_multinomial(
            values,
            num_samples,
            replacement=False,
            *,
            generator=None,
            out=None,
        ):
            if values.ndim == 2 and values.shape[0] == batch_size:
                rows = [
                    original_multinomial(
                        values[index],
                        num_samples,
                        replacement,
                        generator=generators[index],
                    )
                    for index in range(batch_size)
                ]
                return torch.stack(rows, dim=0)
            return original_multinomial(
                values,
                num_samples,
                replacement,
                generator=generator,
                out=out,
            )

        try:
            torch.multinomial = row_seeded_multinomial
            with torch.no_grad():
                generated = engine.model.generate(
                    batched_features,
                    decoder_input_ids=decoder_input_ids,
                    max_new_tokens=int(max_length),
                    num_beams=1,
                    do_sample=True,
                    suppress_tokens=list(suppress),
                    temperature=float(temperature),
                    top_k=int(topk),
                )
        finally:
            torch.multinomial = original_multinomial

        pad_token_id = engine.model.generation_config.pad_token_id
        eos_token_ids = engine.model.generation_config.eos_token_id
        if isinstance(eos_token_ids, int):
            eos_token_ids = [eos_token_ids]
        terminal_ids = {
            int(value)
            for value in [pad_token_id, *(eos_token_ids or [])]
            if value is not None
        }
        prefix = list(prompt_tokens)
        results = {}
        for row_index, seed in enumerate(selected_seeds):
            sequence = [int(value) for value in generated[row_index].tolist()]
            if sequence[: len(prefix)] == prefix:
                sequence = sequence[len(prefix) :]
            while sequence and sequence[-1] in terminal_ids:
                sequence.pop()
            results[seed] = sequence
        return results

    def evidence(self) -> dict:
        return {
            "optimization_id": OPTION12_RUNTIME_OPTIMIZATION_ID,
            "encoder_cache_hits": int(self.encoder_cache["hits"]),
            "encoder_cache_misses": int(self.encoder_cache["misses"]),
            "plain_consensus_seed_count": OPTION12_PLAIN_CONSENSUS_SEED_COUNT,
            "intended_consensus_seeds": list(OPTION12_INTENDED_CONSENSUS_SEEDS),
            "intended_consensus_batch_size": len(OPTION12_INTENDED_CONSENSUS_SEEDS),
        }


def option12_language_route(model, language: str):
    optimizer = getattr(model, "_option12_runtime_optimization", None)
    if optimizer is None:
        return nullcontext()
    return optimizer.language_route(language)
