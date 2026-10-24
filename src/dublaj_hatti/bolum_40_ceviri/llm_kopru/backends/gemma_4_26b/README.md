# Gemma 4 26B Backend Kutusu

Bu klasor, bridge_motor_orkestratoru icinde `gemma` backend seciminin kendi bagimsiz kutusudur.

Bu kutunun sahibi oldugu dosyalar:

- `backend_config.json`: Model adi, provider, runner, API key env adlari, request spacing/retry ve fallback davranisi.
- `prompt.md`: Bu backend secildiginde kullanilan prompt.
- `README.md`: Bu kutunun ne oldugunu anlatan kisa belge.

Bu kutu baska backendlerin config, prompt veya schema dosyalarina bagli olmadan okunabilmelidir.

Kullanilan gercek model: `gemma-4-26b-a4b-it`
Runner: `gemini_generate_content`
Fallback: `False`
