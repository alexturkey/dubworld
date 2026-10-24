# Bolum 40: Ceviri

Bu bolum, TTS'e hazir kaynak segmentlerden hedef dile uygun dublaj metni
uretilene kadar olan ceviri katmanini tasir. Bolum ve kutu listesinin sahibi
`docs/arac_katalogu.md` belgesidir.

Girdi:

```text
zamanli kaynak segmentler
```

Cikti:

```text
hedef dile cevrilmis ve TTS'e gidecek dublaj metinleri
```

Yapi:

```text
bolum_40_ceviri/
  arka_uc_secimi.py          ceviri.arka_uc secimi: auto -> codex -> claude_code -> yerel (Opus-MT)
  gorunum_adlari.py          ceviri motorlarinin ortak gorunen ad yardimcisi
  bridge_motor_orkestratoru/ dosya tabanli kopru secimini yapan ince orkestrator
  yerel_ceviri/              yerel Opus-MT (tc-big en-tr), anahtarsiz ve cevrimdisi
  claude_code_cli/           Claude Code CLI arka ucu (kullanicinin kendi oturumu)
  llm_kopru/                 LLM kopru: backends/ (codex_exec, gemini_2_5_flash,
                             gemini_3_1_flash_lite_tier_1, gemma_4_26b, groq_llama_4_scout,
                             cerebras_llama_3_1_8b, mistral_nemo), prompt_katmani/,
                             shared_result_contract/, scripts/ (hedef_dil.py: hedef dil
                             sablonu, konusma hizi, cikti dili denetimi; ADR 0014)
  dil_ekleri/                hedef dil ekleri: _genel.md + en, de, fr, es, it, pt, ru, ar, ja, zh
```

Ceviri arka uclari (`ceviri.arka_uc`, tam liste `dublaj_hatti/kayit.py`):

- `yerel`: Opus-MT, kendi makinede, anahtar gerekmez; `auto` baska arka uc bulamazsa bunu secer.
- `codex`, `claude_code`: kullanicinin kendi kurdugu ve kendi hesabiyla oturum actigi CLI.
- `gemini_2_5_flash`, `gemini_3_1_flash_lite_tier_1`, `gemma_4_26b`, `groq_llama_4_scout`,
  `cerebras_llama_3_1_8b`, `mistral_nemo`: kullanicinin kendi API anahtariyla (`.env`) resmi API.

Kural:

- Her ceviri arka ucunun engine, kalite kapisi, kota, prompt, config, schema,
  runtime ve yardimci dosyalari kendi kutusunda tutulur.
- Yeni arka uc eklenirse `src` kokune dosya eklenmez; bu bolum altinda kendi
  klasoru acilir ve `kayit.py`'ye lisans/kaynak satiri yazilir.
- Resmi olmayan ucu kullanan arka uc (ornegin ucretsiz Google Translate kazima
  kutuphaneleri) bu repoya girmez (THIRD_PARTY.md "Never included").

Bu bolum ses uretmez, video isleme yapmaz ve Telegram teslimati yapmaz.
