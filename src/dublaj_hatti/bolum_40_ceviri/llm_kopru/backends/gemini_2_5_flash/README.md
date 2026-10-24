# Gemini 2.5 Flash Backend Kutusu

Bu klasor, bridge_motor_orkestratoru icinde `gemini_flash` backend seciminin kendi bagimsiz kutusudur.

Bu kutunun sahibi oldugu dosyalar:

- `backend_config.json`: Model adi, provider, runner, API key env adlari, request spacing/retry ve fallback davranisi.
- `prompt.md`: Bu backend secildiginde kullanilan prompt.
- `README.md`: Bu kutunun ne oldugunu anlatan kisa belge.

Bu kutu baska backendlerin config, prompt veya schema dosyalarina bagli olmadan okunabilmelidir.

Kullanilan gercek model: `gemini-2.5-flash`
Runner: `gemini_generate_content`
Fallback: `False`
