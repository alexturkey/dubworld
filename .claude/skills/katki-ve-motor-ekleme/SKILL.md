---
name: katki-ve-motor-ekleme
description: "Contribute to this repository: add a new speech-to-text engine, translation backend or TTS engine through the engine registry (kayit.py), write its engine page, add tests, and pass the CI gates (pytest without GPU, ruff, legal and privacy audit). Use when the user says 'add an engine', 'add a model', 'new backend', 'contribute', 'open a PR', 'motor ekle', 'katkı', 'run the tests', 'yasal denetim', 'CI fails'."
---

# Contributing and adding an engine / Katkı ve motor ekleme

Türkçe özet en altta. / Turkish summary at the end.

## When to use

Any code change meant for a pull request, especially a new engine. Read
[CONTRIBUTING.md](../../../CONTRIBUTING.md) and the engineering page of the stage you touch first
([docs/engineering/README.md](../../../docs/engineering/README.md)).

## Ground rules

- **Official sources only.** Every engine needs an official, documented source and a readable license
  ([THIRD_PARTY.md](../../../THIRD_PARTY.md)). No unofficial endpoints, no real-person voices, no voice cloning of
  others ([ETHICS.md](../../../ETHICS.md)).
- **No weights, media or binaries in the repo.** Downloads are pinned (commit/tag + sha256) in
  `scripts/modeller.json` (fetched by `scripts/modelleri_indir.py`) or an installer step in `scripts/kur.ps1`.
- **No personal data:** no personal paths, names, accounts, e-mails, keys, usage statistics or dates of your own runs.
- **No silent fallback**; changing a stage's behaviour bumps its checkpoint contract version
  ([ADR 0009](../../../docs/adr/0009-fail-closed-no-silent-fallback.md), [ADR 0012](../../../docs/adr/0012-stage-checkpoints-and-resume.md)).

## Steps: add an engine

1. **Code:** put the engine in its stage folder:
   - STT: `src/dublaj_hatti/bolum_20_transkripsiyon/<name>_motoru/` (see `faster_whisper_motoru/`); adapters that run
     in another environment go to `src/dublaj_hatti/bolum_00_omurga/runtime/<name>_runtime.py`; output the common
     segment + word-timing format; entry point: a `_transcribe_<name>` branch in
     `src/dublaj_hatti/bolum_00_omurga/core/dubber.py`.
   - Translation: `src/dublaj_hatti/bolum_40_ceviri/llm_kopru/backends/<name>/` (see `codex_exec/`); register in
     `KOPRU_ADI` and the key variable in `API_ANAHTARI_DEGISKENLERI` (`bolum_40_ceviri/arka_uc_secimi.py`).
   - TTS: `src/dublaj_hatti/bolum_50_seslendirme/<name>_tts/` (see `supertonic_tts/`); branch in
     `bolum_50_seslendirme/tts_orkestratoru/service.py`.
2. **Register** one `Motor(...)` row in `MOTORLAR` of [src/dublaj_hatti/kayit.py](../../../src/dublaj_hatti/kayit.py):
   kind, setting value, display name, license (read from the official source), commercial use
   (`evet` / `hayır` / `şartlı` / `hizmet şartları`), official URL, install step, device, `kurulu` check; then a
   `_DONANIM_DIL` row (`vram_mb`, `cpu`, `bellek`, `kanit` = `ölçüldü` / `belgeye göre` / `tahmin`, `diller`).
   The settings schema, `dubla kontrol`, the GUI and the web UI read this registry. Non-commercial or conditional
   engines automatically get the first-use license gate (`kayit.lisans_uyarisi`).
3. **Install:** pinned extra in `pyproject.toml` (`stt-<name>` style) and, if needed, a `-Adim <name>` step in
   `scripts/kur.ps1`; weights in `scripts/modeller.json` with sha256. Lock files: edit `requirements/*.in`, regenerate
   with `scripts/kilitle.ps1`, commit both.
4. **Docs:** `docs/motorlar/<name>.md` (the registry's `belge` path; copy the layout of an existing page: what it does,
   license, hardware, install, settings, common errors), a row in [docs/donanim.md](../../../docs/donanim.md) (a test
   fails if an engine is missing there), languages in [docs/diller.md](../../../docs/diller.md), a
   [THIRD_PARTY.md](../../../THIRD_PARTY.md) row with the official source, and a `CHANGELOG.md` "Unreleased" line.
5. **Tests** (no GPU, no network; mark others `gpu` / `slow`): add a fake-model test next to the existing ones in
   `tests/` (e.g. `tests/test_istege_bagli_ozellikler.py` pattern).

## Steps: before every PR (same gates as CI)

```bash
python -m pip install --no-deps -e .
python -m pip install pytest ruff pre-commit
python -m pytest -m "not gpu and not slow"
ruff check --select E9,F63,F7,F82 src tests
python scripts/yasal_denetim.py            # legal + privacy gate: must print 0 findings
```

`scripts/yasal_denetim.py` blocks unofficial endpoints, real-voice folders, media files, secrets, personal paths,
e-mails, Telegram ids/tokens, usage traces and time-zone hints. A real false positive goes into
`scripts/yasal_denetim_izin.txt` with a narrow rule + path + reason; never widen it to hide a real finding.

## Common errors

| Symptom | Fix |
|---|---|
| `test_donanim_belgesi_her_motoru_listeler` fails | add the engine row to `docs/donanim.md` |
| Engine missing from `dubla kontrol` | no `Motor` row in `kayit.py`, or its `kurulu` check imports a missing module |
| `yasal_denetim` finding `kisisel_yol` / `kullanim_izi` | remove the path / personal statistic from the text |
| CI passes locally but fails in CI | CI has only the standard library; heavy imports must be lazy or the test must use `importorskip` |

## Related

[CONTRIBUTING.md](../../../CONTRIBUTING.md) · [src/dublaj_hatti/kayit.py](../../../src/dublaj_hatti/kayit.py) ·
[docs/mimari.md](../../../docs/mimari.md) · [docs/adr/README.md](../../../docs/adr/README.md) ·
[docs/engineering/README.md](../../../docs/engineering/README.md) · [THIRD_PARTY.md](../../../THIRD_PARTY.md) ·
[CODE_OF_CONDUCT.md](../../../CODE_OF_CONDUCT.md) · [SECURITY.md](../../../SECURITY.md)

## Türkçe özet

Yeni motor: kodu ilgili `bolum_*` klasörüne koy, `kayit.py` `MOTORLAR`'a bir `Motor` satırı + `_DONANIM_DIL` satırı
ekle (lisans resmî kaynaktan, kanıt düzeyiyle), `dubber.py` / `tts_orkestratoru` / `arka_uc_secimi` dalını bağla,
sabit sürümlü extra ve sha256'lı model satırı ekle, `docs/motorlar/<ad>.md`, `docs/donanim.md`, `docs/diller.md`,
`THIRD_PARTY.md`, `CHANGELOG.md` güncelle, GPU'suz test yaz. PR öncesi: `pytest -m "not gpu and not slow"`,
`ruff check --select E9,F63,F7,F82 src tests`, `python scripts/yasal_denetim.py` (0 bulgu). Ağırlık, medya, kişisel
bilgi ve resmî olmayan uç repoya girmez.
