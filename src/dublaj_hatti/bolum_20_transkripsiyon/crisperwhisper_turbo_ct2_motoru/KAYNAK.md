# Provenance / Kaynak

**What this folder is.** The CrisperWhisper 2.0 Turbo (CTranslate2) engine box ("engine 13") as it runs in the
pipeline this repository was extracted from: window planning on VAD boundaries, coverage recovery, language
identification modes, native softmax kernel, dubbing-ready result contract. It is kept here as a copy on purpose.

**Relation to the sibling STT repository** (README "Family", `crisperwhisper-turkce-kelime-zamani`, pinned commit
`2ca4b160e4bf9254185df01b21b281db4b209c19`):

| Part | Where it comes from |
|---|---|
| model download + CTranslate2 conversion | the sibling repo's own installer, run by `scripts/crisper_kur.py` at the pinned commit (no conversion is redistributed here) |
| engine code (this folder) | copy, see above; the sibling repo ships a slimmer engine (`transkript/motor_isci.py`) with a different request/response contract |
| word timing | this repo's shared CTC aligner (`bolum_30_hizalama_ve_segment/ctc_kelime_hizalama`) |

**Why not a pip dependency yet.** The sibling repo is not an installable Python package (no `pyproject.toml`), so
`pip install "pkg @ git+...@<sha>"` is not possible, and its engine API is not the one the pipeline calls. Replacing
this copy with a thin adapter needs (a) a `pyproject.toml` in the sibling repo exposing `transkript` with a stable
worker contract and (b) an A/B measurement on the same audio showing equal text and timing quality. Until then the
copy stays, and changes here should be mirrored upstream when they affect transcription quality.

**License.** Code Apache-2.0 (this repository). Model weights `nyralabs/CrisperWhisper2.0_turbo`: **non-commercial**
(model card). Weights are never stored in this repository; the installer asks for explicit acceptance
(`scripts/kur.ps1 -Adim crisper -TicariOlmayanKabul`). See THIRD_PARTY.md.

---

**TR:** Bu klasör 13. motorun üretimde çalışan kopyasıdır. Kardeş STT reposu pip paketi olmadığı ve motor sözleşmesi
farklı olduğu için bağımlılığa çevrilmedi; model indirme ve dönüşüm o reponun sabit commit'teki kurulum betiğiyle
yapılır. Ağırlık lisansı ticari olmayan kullanımdır.
