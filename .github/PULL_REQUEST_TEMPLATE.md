## Ne değişti / What changed

<!-- Tek konu, kısa açıklama. İlgili issue: #... / One topic, short description. Related issue: #... -->

## Nasıl test edildi / How it was tested

<!-- Komut ve sonuç; donanım (CPU / GPU, bellek), işletim sistemi. / Command and result; hardware, OS. -->

- [ ] `ruff check --select E9,F63,F7,F82 src tests`
- [ ] `python -m pytest -m "not gpu and not slow"`
- [ ] GPU ya da gerçek video ile denendi (varsa yazın) / Tried on GPU or a real video (describe if so)

## Kontrol listesi / Checklist

- [ ] Ağırlık, model, video, ses kaydı ya da ikili dosya eklenmedi. / No weights, models, media or binaries added.
- [ ] Yeni indirme varsa sabit sürüm/commit + sha256 ile ve resmî kaynaktan. / Any new download is pinned (version/commit + sha256) and official.
- [ ] Yeni bağımlılık `pyproject.toml` içinde doğru isteğe bağlı gruba eklendi, lisansı `THIRD_PARTY.md`'de. / New dependency is in the right extra and listed in `THIRD_PARTY.md`.
- [ ] Kişisel yol, ad, e-posta, hesap ya da API anahtarı yok. / No personal paths, names, e-mails, accounts or API keys.
- [ ] Yeni ayar `src/dublaj_hatti/varsayilan.toml` içinde yorumuyla; varsayılan davranış değiştiyse `CHANGELOG.md` güncellendi. / New setting documented in the defaults file; `CHANGELOG.md` updated if behaviour changed.
- [ ] Ağ çağrısı, alt süreç ya da CI değişikliği varsa aşağıda açıklandı. / Network calls, subprocesses or CI changes are explained below.

## Notlar / Notes
