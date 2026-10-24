"""Ceviri istemleri hedef dile gore (ADR 0014): tr bayt esitligi, yer tutucu, dil eki, konusma hizi, cikti dili.

Model cagrisi yok; istemler yalniz birlestirilir ve dogrulayici sentetik metinlerle sinanir.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

KOK = Path(__file__).resolve().parents[1]
CEVIRI = KOK / "src" / "dublaj_hatti" / "bolum_40_ceviri"
ALTIN = KOK / "tests" / "veri" / "ceviri_istem_tr_altin.json"

llm = importlib.import_module("dublaj_hatti.bolum_40_ceviri.llm_kopru.scripts.bridge_worker")
claude = importlib.import_module("dublaj_hatti.bolum_40_ceviri.claude_code_cli.scripts.bridge_worker")
nb = importlib.import_module("dublaj_hatti.bolum_40_ceviri.llm_kopru.scripts.natural_blocks_chain_contract")
hd = importlib.import_module("dublaj_hatti.bolum_40_ceviri.llm_kopru.scripts.hedef_dil")
engine = importlib.import_module("dublaj_hatti.bolum_40_ceviri.bridge_motor_orkestratoru.engine")

LLM_BACKENDS = ["codex", "gemini_flash", "gemini_31_flash_lite", "gemma", "groq", "cerebras", "mistral"]
MODLAR = [
    "", "full_text_translation", "supertonic_tts", "supertonic_single_pass_1_natural", "supertonic_natural_blocks_1",
    "supertonic_whole_chain_master", "supertonic_whole_chain_candidates", "supertonic_whole_chain_repair",
    "vtt_transcript_segments",
]
SABLONLAR = sorted(
    p for p in CEVIRI.rglob("*")
    if "backends" in p.parts and p.suffix in {".md", ".json"} and p.name != "README.md"
    and not p.name.endswith("_config.json")
)


def ornek_is(mod: str, dil: str) -> dict:
    if mod == "full_text_translation":
        return {
            "job_id": "k18_full", "task_type": "full_text_translation", "source_lang": "en", "target_lang": dil,
            "source_text": "In 2026 the 4K model shipped. It costs $10? yes it does.",
            "options": {"prompt_mode": mod},
        }
    is_ = {
        "job_id": "k18_seg", "task_type": "translation_candidates", "source_lang": "en", "target_lang": dil,
        "voice": {"engine": "supertonic_tts"}, "options": {"candidate_count": 3},
        "segments": [
            {"id": 0, "text": "This is going to be the new PC.", "duration": 2.1, "hard_minimum_word_count": 3},
            {"id": 1, "text": "to use", "duration": 0.6},
        ],
        "context_before": [{"id": 9, "text": "Hello there."}],
        "context_after": [{"id": 2, "text": "Sam Altman's OpenAI API."}],
    }
    if mod:
        is_["options"]["prompt_mode"] = mod
    return is_


def tr_istem_dokumu(monkeypatch, dil: str = "tr") -> dict[str, str]:
    """Altin veriyle ayni adlar ve ayni ornek islerle birlesik istem ve onarim metinleri."""
    cikti: dict[str, str] = {}
    for backend in LLM_BACKENDS:
        monkeypatch.setenv("CODEX_BRIDGE_BACKEND", backend)
        for mod in MODLAR:
            is_ = ornek_is(mod, dil)
            cikti[f"llm_kopru/{backend}/{mod or 'modsuz'}.txt"] = llm.build_prompt(is_)
            if backend == "codex":
                cikti[f"llm_kopru/codex_sema/{mod or 'modsuz'}.json"] = json.dumps(
                    llm.codex_output_schema_payload(is_), ensure_ascii=False, indent=2)
    monkeypatch.setenv("CODEX_BRIDGE_BACKEND", "codex")
    kok = CEVIRI / "llm_kopru/backends/codex_exec"
    for dosya in sorted([kok / "prompt.md", *sorted((kok / "prompts").glob("*.md"))]):
        cikti[f"llm_kopru/dogrudan/{dosya.name}.txt"] = llm.build_prompt(ornek_is("", dil), prompt_file=dosya)
    for mod in MODLAR:
        is_ = ornek_is(mod, dil)
        cikti[f"claude/{mod or 'modsuz'}_system.txt"] = claude.build_system_prompt(is_)
        cikti[f"claude/{mod or 'modsuz'}_stdin.txt"] = claude.build_stdin_payload(is_)
    is_ = ornek_is("", dil)
    sonuc = {"job_id": "k18_seg", "status": "success", "translations": [{"id": 0, "candidates": ["a"]}]}

    def js(deger) -> str:
        return json.dumps(deger, ensure_ascii=False, indent=2)

    cikti["python/llm_contract_retry.json"] = js(llm.build_contract_retry_job(is_, sonuc, [{"id": "0", "reason": "x"}], 1))
    cikti["python/llm_discourse.json"] = js(llm.discourse_context_payload(is_))
    cikti["python/nb_retry.json"] = js(nb.build_natural_blocks_review_retry_job(is_, sonuc, [{"failed_segment_ids": ["0"]}], 1))
    t = engine.BridgeMotorOrkestratoruTranslator(target_lang=dil, source_lang="en", candidate_count=3,
                                                  prompt_mode="supertonic_natural_blocks_1")
    segler = [
        SimpleNamespace(start=0.0, end=2.4, text="This is going to be the new PC, and you could talk to it."),
        SimpleNamespace(start=2.4, end=3.0, text="to use"),
        SimpleNamespace(start=3.0, end=9.5, text="Great content sitting around, old blog posts, a few PDFs, some notes and more things here."),
    ]
    cikti["python/engine_build_job.json"] = js(t._build_job(segler, "k18_job"))
    cikti["python/engine_timing_repair.json"] = js(t._build_timing_repair_job({"voice": {}}, [{"id": 0}], 1, "k18_r", 3))
    sorun = {
        "segment_id": "0", "source_duration": 2.4, "selected_processed_duration": 1.5, "problem": "too_short_audio",
        "selected_text": "Yeni PC bu olacak.",
        "candidates": [{"text": "Yeni PC bu.", "processed_duration": 1.2, "status": "too_short_audio"}],
    }
    seg = t._build_real_tts_repair_segment(segler[0], sorun, ["Yeni PC bu."], "a", "b")
    cikti["python/engine_real_tts_segment_short.json"] = js(seg)
    sorun2 = dict(sorun, problem="too_long_audio", selected_processed_duration=4.0)
    cikti["python/engine_real_tts_segment_long.json"] = js(t._build_real_tts_repair_segment(segler[0], sorun2, ["Yeni PC bu."]))
    cikti["python/engine_real_tts_job.json"] = js(t._build_real_tts_repair_job([seg], 1, "k18_rt", 3))
    return cikti


@pytest.fixture(autouse=True)
def _ortam(monkeypatch):
    for ad in ("CODEX_BRIDGE_WORKER_BACKEND", "CODEX_BRIDGE_GEMINI_PROMPT_FILE",
               "CODEX_BRIDGE_GEMINI_31_FLASH_LITE_PROMPT_FILE", "CODEX_BRIDGE_GEMINI_STRICT_SEGMENT_CONTRACT",
               "CODEX_BRIDGE_GROUP_SIZE", "CODEX_BRIDGE_CONTEXT_SIZE", "CODEX_BRIDGE_MAX_PARALLEL_JOBS"):
        monkeypatch.delenv(ad, raising=False)


# ------------------------------------------------------------------ tr bayt esitligi

def test_tr_birlesik_istemler_altin_veriyle_bayt_esit(monkeypatch):
    altin = json.loads(ALTIN.read_text(encoding="utf-8"))["ozetler"]
    dokum = tr_istem_dokumu(monkeypatch)
    assert set(dokum) == set(altin)
    farkli = [ad for ad, metin in dokum.items() if hashlib.sha256(metin.encode("utf-8")).hexdigest() != altin[ad]]
    assert farkli == []


def test_kopyalar_bayt_esit():
    for ad in ("hedef_dil.py", "natural_blocks_chain_contract.py", "istem_guvenligi.py"):
        assert (CEVIRI / "llm_kopru/scripts" / ad).read_bytes() == (CEVIRI / "claude_code_cli/scripts" / ad).read_bytes()


# ------------------------------------------------------------------ yer tutucu ve dil eki

@pytest.mark.parametrize("dil", sorted(hd.DIL_ADLARI))
def test_hicbir_dilde_yer_tutucu_ya_da_isaret_kalmaz(dil):
    for sablon in SABLONLAR:
        metin = sablon.read_text(encoding="utf-8")
        cikti = hd.istem_isle(metin, dil) if sablon.suffix == ".md" else hd.yer_tutuculari_doldur(metin, dil)
        assert "{target_lang" not in cikti, (dil, sablon.name)
        assert "<!-- dil" not in cikti and "<!-- /dil" not in cikti, (dil, sablon.name)
        if sablon.suffix == ".json":
            json.loads(cikti)


def test_tr_disi_govdede_turkce_ad_kalmaz():
    for sablon in SABLONLAR:
        if sablon.suffix != ".md":
            continue
        govde = hd.istem_isle(sablon.read_text(encoding="utf-8"), "fr")
        govde = govde.replace(hd.dil_eki_metni("fr"), "")
        assert not re.search(r"Türk|Turkce", govde), sablon.name


def test_sablondaki_her_ek_anahtari_genel_ekte_var():
    genel = hd.dil_eki_bolumleri("_genel")
    assert "genel" in genel
    for sablon in SABLONLAR:
        for anahtar in re.findall(r"<!-- dil:tr ek=([a-z0-9_]+) -->", sablon.read_text(encoding="utf-8")):
            assert anahtar in genel, (sablon.name, anahtar)


def test_dil_eki_secimi():
    assert hd.dil_eki_metni("tr") == ""
    fr = hd.dil_eki_metni("fr")
    assert "HEDEF DİL EKİ (Fransızca / French, `target_lang=fr`)" in fr and "virgule" in fr
    sw = hd.dil_eki_metni("sw")  # dile ozel dosya yok: yalniz genel ek
    assert "Svahilice" in sw and "virgule" not in sw
    assert hd.dil_eki_metni("pt-BR") == hd.dil_eki_metni("pt")
    # dile ozel bolum genel bolumun yerini alir
    assert "deux mille" in hd.istem_isle("<!-- dil:tr ek=sayi_tarih_ornegi -->\nx\n<!-- /dil -->\n", "fr")
    assert hd.istem_isle("<!-- dil:tr ek=sayi_tarih_ornegi -->\nx\n<!-- /dil -->\n", "sw").startswith("\n") is False


def test_sablon_soz_dizimi_hatalari():
    with pytest.raises(hd.IstemSablonuHatasi):
        hd.istem_isle("<!-- dil:tr -->\nx\n", "fr")
    with pytest.raises(hd.IstemSablonuHatasi):
        hd.istem_isle("<!-- /dil -->\n", "fr")
    with pytest.raises(hd.IstemSablonuHatasi):
        hd.istem_isle("<!-- dil:tr ek=olmayan_anahtar -->\nx\n<!-- /dil -->\n", "fr")


def test_ek_ses_uyumu_ve_adlar():
    assert hd.dil_adi("tr", "de") == "Türkçede"
    assert hd.dil_adi("fr", "de") == "Fransızcada"
    assert hd.dil_adi("fr", "yi") == "Fransızcayı"
    assert hd.dil_adi("zh", "ye") == "Çinceye"
    assert hd.dil_adi("ja", "sini") == "Japoncasını"
    assert hd.dil_adi_ascii("tr") == "Turkce"
    assert hd.konusma_slug("tr") == "turkish"
    for kod, (ad, _en) in hd.DIL_ADLARI.items():
        assert ad[-1] in "ae", kod  # ses uyumu kurali son unluyu a/e varsayar


def test_bilinmeyen_kod_ve_bos_kod():
    assert hd.dil_kodu("") == "tr"
    assert hd.dil_kodu("ZH_cn") == "zh"
    assert hd.dil_adi("xx") == "XX"


# ------------------------------------------------------------------ konusma hizi ve sayim

def test_tr_hizi_degismedi():
    assert hd.saniye_per_kelime("tr") == engine.TURKISH_AVERAGE_WORD_SECONDS == 0.43
    assert hd.saniye_per_kelime("xx") == 0.43
    assert hd.kelime_esdegeri("Yeni PC bu olacak.", "tr") == 4


def test_japonca_karakter_tabanli_sayim():
    metin = "コードをテストしています"  # 12 karakter, bosluksuz
    assert len(metin.split()) == 1
    assert hd.kelime_esdegeri(metin, "ja") == round(12 / 2.5)
    assert hd.kelime_esdegeri("OpenAI APIを使います", "ja") == 2 + round(5 / 2.5)
    assert hd.karakter_tabanli("zh") and not hd.karakter_tabanli("de")


def test_natural_blocks_japonca_aday_yanlis_kisa_sayilmaz():
    is_ = {"job_id": "j", "source_lang": "en", "target_lang": "ja", "options": {"prompt_mode": "supertonic_natural_blocks_1"},
           "segments": [{"id": 0, "text": "I am testing the code today to make sure the right value is set."}]}
    sonuc = {"translations": [{"id": 0, "candidates": ["正しい値が設定されていることを確認するために、今日コードをテストしています。"]}]}
    assert nb.natural_blocks_candidate_sanity_violations(is_, sonuc) == []
    # ayni aday bosluk bolmeyle 1 kelime sayilir ve 14 kaynak kelimesine gore asiri kisa gorunurdu
    assert nb.natural_blocks_word_count(sonuc["translations"][0]["candidates"][0]) == 1


# ------------------------------------------------------------------ cikti dili denetimi

DOGRU = {
    "tr": ["Yeni PC bu olacak.", "Ortada duran harika içerikler var: eski blog yazıları, birkaç PDF ve notlar.",
           "Bu, kullanacak kadar akılsız olan herkese bir uyarı.", "Onunla konuşabileceksiniz.",
           "The Last of Us oyunu bence çok iyi."],
    "en": ["This is going to be the new PC.", "You could talk to it and it would answer right away."],
    "de": ["Das wird der neue PC sein, und du kannst mit ihm sprechen.", "Heute verstehen wir diese Ereignisse besser."],
    "fr": ["Ce sera le nouveau PC, et vous pourrez lui parler.", "Aujourd'hui, nous comprenons mieux ces événements."],
    "es": ["Este va a ser el nuevo PC y podrás hablar con él.", "¿Qué hacemos ahora con todo esto?"],
    "it": ["Questo sarà il nuovo PC e potrai parlarci.", "Oggi capiamo meglio quegli eventi."],
    "pt": ["Este vai ser o novo PC e você vai poder falar com ele.", "Hoje entendemos melhor esses acontecimentos."],
    "ru": ["Это будет новый компьютер, и с ним можно будет говорить.", "Сегодня мы лучше понимаем эти события."],
    "ar": ["سيكون هذا الحاسوب الجديد، ويمكنك التحدث إليه.", "اليوم نفهم هذه الأحداث بشكل أفضل."],
    "ja": ["これが新しいPCになります。", "OpenAI APIを使うつもりです。", "東京大学。"],
    "zh": ["这将是新的电脑，你可以和它说话。", "今天我们更好地理解了这些事件。"],
}
YANLIS = [
    ("fr", "Bu yeni bilgisayar olacak ve onunla konuşabileceksiniz."),   # Turkce sizinti
    ("de", "This is going to be the new PC and you can talk to it."),   # cevrilmemis kaynak
    ("ja", "这将是新的电脑，你可以和它说话，我们今天都很高兴。"),           # Cince
    ("zh", "これが新しいパソコンになりますので、話しかけてください。"),       # Japonca
    ("fr", "Это будет новый компьютер, и с ним можно говорить."),        # Kiril
    ("ru", "Ce sera le nouveau PC, et vous pourrez lui parler."),        # Latin
    ("en", "Bu, kullanacak kadar akılsız olan herkese bir uyarı."),      # Turkce
]
KISA = [("fr", "OK."), ("de", "Danke!"), ("ja", "はい。"), ("ru", "Да."), ("fr", "Bu iyi."), ("zh", "好")]


@pytest.mark.parametrize("dil,metin", [(d, m) for d, liste in DOGRU.items() for m in liste])
def test_dogru_dil_alarm_vermez(dil, metin):
    assert hd.metin_dili_sorunu(metin, dil, "This is going to be the new PC. OpenAI API. The Last of Us") == ""


@pytest.mark.parametrize("dil,metin", YANLIS)
def test_yanlis_dil_yakalanir(dil, metin):
    assert hd.metin_dili_sorunu(metin, dil, "This is going to be the new PC.") != ""


@pytest.mark.parametrize("dil,metin", KISA)
def test_kisa_segmentte_alarm_yok(dil, metin):
    assert hd.metin_dili_sorunu(metin, dil) == ""


def test_isci_dogrulayicisi_yeniden_denenebilir_hata(monkeypatch):
    is_ = ornek_is("", "fr")
    sonuc = {"job_id": "k18_seg", "status": "success", "translations": [
        {"id": 0, "candidates": ["Bu yeni bilgisayar olacak ve onunla konuşabileceksiniz."], "kept_terms": []},
        {"id": 1, "candidates": ["utiliser"], "kept_terms": []},
    ]}
    for modul in (llm, claude):
        with pytest.raises(modul.BridgeError) as hata:
            modul.validate_output_language(is_, sonuc)
        assert hata.value.retryable is True
        assert hata.value.error_type == "translation_result_wrong_language"
    sonuc["translations"][0]["candidates"] = ["Ce sera le nouveau PC, et vous pourrez lui parler."]
    llm.validate_output_language(is_, sonuc)
    claude.validate_output_language(is_, sonuc)


def test_tam_metin_dili():
    is_ = ornek_is("full_text_translation", "de")
    assert hd.cikti_dili_ihlalleri(is_, {"translated_text": "Das neue Modell ist da, und es kostet zehn Dollar."}) == []
    assert hd.cikti_dili_ihlalleri(is_, {"translated_text": "Yeni model çıktı ve on dolar tutuyor, bu çok iyi bir şey."})
