# Codex Exec Backend Kutusu

Bu klasor, bridge_motor_orkestratoru icinde `codex` backend seciminin kendi bagimsiz kutusudur.

Bu kutunun sahibi oldugu dosyalar:

- `backend_config.json`: Model adi, provider, runner, API key env adlari, request spacing/retry ve fallback davranisi.
- `prompts/supertonic.md`: Varsayilan prompt (Supertonic ve diger TTS akislari); ozel isimleri korur, fonetik terim raporu uretmez.
- `prompts/full_text_translation.md`, `prompts/supertonic_single_pass_1_natural.md`, `prompts/supertonic_whole_chain_*.md`,
  `prompts/vtt_transcript_segments.md`: `backend_config.json` `prompt_files` eslemesindeki ozel modlarin promptlari.
- `prompts/v4_en_supertonic_natural_blocks_.md`: Natural Blocks tek aday akisinda ayni ID anlam sahipligini ve segment bazli kanit denetimini tanimlar.
- `README.md`: Bu kutunun ne oldugunu anlatan kisa belge.
- `output_schema.json`: Sadece Codex Exec icin dogrudan `codex exec --output-schema` ile kullanilan cikti semasi.
- `output_schema_natural_blocks_v2.json`: Natural Blocks icin her ID'de `ownership_check`, kaynak/hedef kanit parcasi ve komsu anlam aktarimi bayraklarini zorunlu tutar.

Bu kutu baska backendlerin config, prompt veya schema dosyalarina bagli olmadan okunabilmelidir.

Prompt seciminde once `options.prompt_mode`, ozel mod yoksa `voice.engine`
alani kullanilir:

- `options.prompt_mode=supertonic_natural_blocks_1` gelirse Natural Blocks promptu ve kendi semasi okunur.
- Ozel prompt modu yokken `supertonic_tts` gelirse `prompts/supertonic.md` okunur.
- Diger durumlarda `prompt_files.default` (`prompts/supertonic.md`) okunur.

Codex Exec proje kokunde calistirilmaz. Worker Windows gecici dizinindeki
`dublaj_hatti_codex_exec` klasorunu hem alt surec `cwd` degeri hem de `--cd`
hedefi yapar; `--skip-git-repo-check` ve `--sandbox read-only` kullanir. Bu
ayrim saf ceviri istegine proje `AGENTS.md` talimatlarinin eklenmesini engeller.
Ceviride kullanilmayan shell, browser, apps, plugins, skills, multi-agent,
image, hooks ve workspace ozellikleri de yalniz bu alt surec komutunda kapatilir.
Kimlik doğrulama kaydedilmiş ChatGPT/Codex CLI oturumudur. Worker global veya
parent ortamı değiştirmez; `OPENAI_API_KEY` ve `CODEX_API_KEY` değerlerini
yalnız Codex child environment kopyasından çıkarır ve değerlerini loglamaz.

Kullanilan gercek model: `gpt-5.6-luna`
Runner: `codex_exec`
Fallback: `False`
