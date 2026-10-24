---
name: devam-ve-sorunlu-isler
description: "Find failed, stopped or queued dubbing jobs and resume them from where they stopped, from a chosen stage, or with changed settings; recover jobs after a crash or power loss; see the GPU queue. Use when the user says 'it stopped', 'resume', 'continue the job', 'devam et', 'kaldığı yerden', 'sorunlu işler', 'job failed', 'rerun only the translation', 'the computer shut down', 'which jobs are running', or a run exits with code 1, 75 or 130."
---

# Resume and failed jobs / Devam ve sorunlu işler

Türkçe özet en altta. / Turkish summary at the end.

## When to use

A job failed, was stopped (Ctrl+C, closed window, power loss) or waits for the GPU; or a finished job must be redone
from a later stage with different settings (no need to transcribe again).

## Facts

- Every job is recorded in a local SQLite job store (`is_yonetimi/`); each stage writes a checkpoint
  ([ADR 0012](../../../docs/adr/0012-stage-checkpoints-and-resume.md)).
- States: `queued`, `deferred` (GPU busy, retried automatically), `preparing`, `processing`, `completed`, `failed`,
  `cancelled`. `failed` and `cancelled` can be resumed. Archiving only hides a job; files stay.
- Two kinds of resume: **in place** (same job, same folder, finished stages are skipped) and **copy to a new job**
  (when you choose a stage, change a setting, pass `--yeni-is`, or rerun a finished job; the old job stays untouched
  and the new one is linked in the lineage).
- Each setting knows the first stage it affects (e.g. `altyazi.mod` → subtitles, `genel.hedef_dil` → translation);
  only that stage and later ones rerun. `genel.is_turu` cannot change on resume.

## Steps

1. List problems and the valid resume options:
   ```powershell
   dubla sorunlu                 # failed / stopped jobs with suggested commands
   dubla isler                   # recent jobs (archive hidden); --hepsi to include archived
   dubla isler --kuyruk          # waiting jobs in order
   ```
2. Resume:
   ```powershell
   dubla devam 7                              # in place, from the stopped stage
   dubla devam 7 --asama ceviri               # from translation, copied to a new job
   dubla devam 7 --ayar altyazi.mod=word      # change a setting, rerun from the first stage it affects
   dubla devam 7 --yeni-is                    # copy, keep the old job untouched
   ```
   `--asama` takes the stage id (`ceviri`), its Turkish name or its number; `dubla sorunlu` lists them.
   Old form still works: `dubla video.mp4 --devam <job folder>`.
3. After a crash or power loss: `dubla isler --kurtar` marks jobs whose process is gone as `failed`, then step 2.
   The desktop and web UIs do this automatically when they open (**İşler** tab → **Devam et**).
4. Housekeeping: `dubla isler --soyagaci 9` (lineage), `--arsivle 7` / `--arsivden-cikar 7`, `--iptal 7`,
   `--bayat-iptal 720` (cancel jobs idle for 720 minutes whose process is dead).
5. GPU queue: one GPU job at a time machine-wide; others wait up to `DUBLAJ_KILIT_BEKLEME_SN` (default 6 hours), then
   become `deferred`. Who holds the lock:
   ```powershell
   python -m dublaj_hatti.bolum_00_omurga.runtime.kaynak_kilidi durum
   ```
   Locks are tied to process ids; a crashed program's lock drops by itself.

Exit codes: `0` done, `1` failed (`dubla sorunlu`), `2` usage, `75` resource busy (deferred), `130` stopped by the user.
All listing commands accept `--json`.

## Common errors

| Symptom | Fix |
|---|---|
| `bu klasör iş deposunda kayıtlı değil` | the folder is not a job of this store; use `dubla sorunlu` to get the job number |
| A job stays `processing` after a crash | `dubla isler --kurtar` |
| Stage reruns although "nothing changed" | its recorded input changed (e.g. model file or setting); this is intended |
| `deferred` for a long time | another GPU program holds the lock; check `kaynak_kilidi durum` |

## Related

[docs/tarifler/devam_ve_sorunlu_isler.md](../../../docs/tarifler/devam_ve_sorunlu_isler.md) (full guide, Turkish) ·
[docs/engineering/video_subtitles_and_resume.md](../../../docs/engineering/video_subtitles_and_resume.md) ·
[docs/engineering/gpu_memory_and_isolation.md](../../../docs/engineering/gpu_memory_and_isolation.md) §7 ·
[docs/adr/0012-stage-checkpoints-and-resume.md](../../../docs/adr/0012-stage-checkpoints-and-resume.md)

## Türkçe özet

`dubla sorunlu` hata alan/kesilen işleri ve devam seçeneklerini gösterir. `dubla devam <no>` kaldığı yerden aynı
klasörde sürdürür; `--asama <ad>`, `--ayar ...` ya da `--yeni-is` ile eski işe dokunmadan yeni işe kopyalayıp seçilen
aşamadan (ya da değişen ayarın etkilediği ilk aşamadan) yeniden çalıştırır. Bilgisayar kapanınca `dubla isler --kurtar`
(arayüzler açılışta kendisi yapar). GPU'ya makine genelinde aynı anda tek iş; sıra `kaynak_kilidi durum` ile görülür.
Ayrıntı: `docs/tarifler/devam_ve_sorunlu_isler.md`.
