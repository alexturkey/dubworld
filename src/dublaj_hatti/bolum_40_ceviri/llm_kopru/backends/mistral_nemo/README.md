# Mistral Nemo Backend Kutusu

Bu klasor, bridge_motor_orkestratoru icinde `mistral` backend seciminin kendi bagimsiz kutusudur.

Bu kutunun sahibi oldugu dosyalar:

- `backend_config.json`: Model adi, provider, runner, API key env adlari, request spacing/retry ve fallback davranisi.
- `prompt.md`: Bu backend secildiginde kullanilan prompt.
- `README.md`: Bu kutunun ne oldugunu anlatan kisa belge.

Bu kutu baska backendlerin config, prompt veya schema dosyalarina bagli olmadan okunabilmelidir.

Kullanilan gercek model: `open-mistral-nemo-2407`
Runner: `openai_compatible_chat_completions`
Fallback: `False`
