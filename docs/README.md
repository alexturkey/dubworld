# Documentation index / Belge fihristi

English is the primary language; Turkish engineering notes mirror the English ones. Legal texts: [../LICENSE](../LICENSE),
[../NOTICE](../NOTICE), [../THIRD_PARTY.md](../THIRD_PARTY.md), [../ETHICS.md](../ETHICS.md), [../PRIVACY.md](../PRIVACY.md).

## Start here / Başlangıç

| Document | What it covers |
|---|---|
| [getting-started.md](getting-started.md) · [baslarken.md](baslarken.md) | For people who do not program: let an AI assistant install it, first dub, plain words, common problems |
| [installation.md](installation.md) · [kurulum.md](kurulum.md) | Installation, environment map, optional engines, update, uninstall, common errors |
| [mimari.md](mimari.md) | Architecture: every stage as a building block (CLI sub-command, Python API) |
| [tarifler/kombinasyonlar.md](tarifler/kombinasyonlar.md) | Ready-made setting combinations and tuning guide (TR) |
| [diller.md](diller.md) | Languages: which source / target language works with which engine |
| [sesler.md](sesler.md) | Voices |
| [donanim.md](donanim.md) | Engine × hardware matrix (GPU / CPU, memory) |
| [olcumler.md](olcumler.md) | Measurements |

## Recipes / Tarifler

| Document | What it covers |
|---|---|
| [tarifler/devam_ve_sorunlu_isler.md](tarifler/devam_ve_sorunlu_isler.md) | Resume, failed jobs, re-run (TR) |
| [tarifler/dil_tespiti.md](tarifler/dil_tespiti.md) | Source-language detection |
| [tarifler/telegram_botu.md](tarifler/telegram_botu.md) | Setting up the optional Telegram bot (TR) |

## Optional engines and features / İsteğe bağlı motorlar

[akilli_kare](motorlar/akilli_kare.md) · [gallery_dl](motorlar/gallery_dl.md) ·
[kapak_gorseli](motorlar/kapak_gorseli.md) · [rvc](motorlar/rvc.md) ·
[segment_cinsiyet_kipi](motorlar/segment_cinsiyet_kipi.md) · [telegram_botu](motorlar/telegram_botu.md) ·
[xtts](motorlar/xtts.md) · [youtube_translate](motorlar/youtube_translate.md)

Every engine's license, commercial-use status and source are listed in [../THIRD_PARTY.md](../THIRD_PARTY.md) and
in `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows which of them are installed). Non-commercial or conditional
engines ask for an explicit, remembered acceptance on first use (CLI `--lisans-onay`, GUI dialog, web confirm); the
same gate guards every entry point (stage commands, `dubla devam`, Python API `lisans_onay=True`).

## All engines and agent skills / Bütün motorlar ve ajan becerileri

Every engine has a page `motorlar/<setting value>.md`; the full list and the task → skill table for AI coding
agents (Claude Code, Codex, Cursor, ...) are in [beceriler/README.md](beceriler/README.md).

## Engineering / Mühendislik

- English: [engineering/README.md](engineering/README.md)
- Türkçe: [muhendislik/README.md](muhendislik/README.md)
- Pinned values / Sabit değerler: [engineering/pinned-values.md](engineering/pinned-values.md) · [muhendislik/sabit_degerler.md](muhendislik/sabit_degerler.md)
- End-to-end pipeline flow / Uçtan uca hat akışı: [engineering/pipeline-flow.md](engineering/pipeline-flow.md) · [muhendislik/hat_akisi.md](muhendislik/hat_akisi.md)

## Decisions (ADR) / Kararlar

[adr/README.md](adr/README.md) (Context / Decision / Consequences / Alternatives; Turkish summaries in
[muhendislik/kararlar.md](muhendislik/kararlar.md)).
