from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


# Neden: 1.0 sn hizalamanin dogal bosluk kurali; 150 kelime ceviri cikti tavanina carpmamak icin (ADR 0006). bkz. docs/engineering/pinned-values.md#dub-segmentation
BOSLUK_ESIGI_SANIYE = 1.0
MAKSIMUM_KELIME_SAYISI = 150
NOKTALAMA_ONCELIGI = (".", "?", "!", ",")
ZAMAN_KARSILASTIRMA_TOLERANSI = 1e-9


@dataclass(frozen=True)
class SegmentUretimRaporu:
    girdi_kelime_sayisi: int
    ana_segment_sayisi: int
    nihai_segment_sayisi: int
    bolunen_ana_segment_sayisi: int
    maksimum_nihai_segment_kelime_sayisi: int
    bosluk_esigi_saniye: float


@dataclass
class NihaiDublajSegmenti:
    index: int
    start: float
    end: float
    text: str
    gender: str = ""
    speaker: str = ""
    pitch: str = "+0Hz"
    protected_terms: Optional[List[str]] = None
    words: Optional[List[Dict[str, Any]]] = None


def _kelime_metni(kelime: Dict[str, Any]) -> str:
    return str(kelime.get("word", "")).strip()


def _kelime_baslangici(kelime: Dict[str, Any]) -> float:
    return float(kelime["start"])


def _kelime_bitisi(kelime: Dict[str, Any]) -> float:
    return float(kelime["end"])


def kelime_listesini_dogrula(kelimeler: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not kelimeler:
        raise ValueError("Nihai segment uretimi icin hizalanmis kelime listesi zorunludur")

    dogrulanmis = []
    onceki_baslangic = None
    for sira, ham_kelime in enumerate(kelimeler, start=1):
        if not isinstance(ham_kelime, dict):
            raise TypeError(f"Kelime kaydi sozluk olmali: sira={sira}")
        if not _kelime_metni(ham_kelime):
            raise ValueError(f"Kelime metni bos olamaz: sira={sira}")
        if "start" not in ham_kelime or "end" not in ham_kelime:
            raise ValueError(f"Kelime start/end zamani eksik: sira={sira}")
        try:
            baslangic = _kelime_baslangici(ham_kelime)
            bitis = _kelime_bitisi(ham_kelime)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Kelime zamani sayisal olmali: sira={sira}") from exc
        if baslangic < 0 or bitis < baslangic:
            raise ValueError(f"Kelime zaman araligi gecersiz: sira={sira} start={baslangic} end={bitis}")
        if onceki_baslangic is not None and baslangic < onceki_baslangic:
            raise ValueError(f"Kelime sirasi kronolojik degil: sira={sira}")
        onceki_baslangic = baslangic
        dogrulanmis.append(dict(ham_kelime))
    return dogrulanmis


def zaman_araligina_gore_ana_segmentleri_olustur(
    kelimeler: Sequence[Dict[str, Any]],
    bosluk_esigi_saniye: float = BOSLUK_ESIGI_SANIYE,
) -> List[List[Dict[str, Any]]]:
    ana_segmentler: List[List[Dict[str, Any]]] = []
    mevcut: List[Dict[str, Any]] = []

    for kelime in kelimeler:
        if mevcut:
            bosluk = _kelime_baslangici(kelime) - _kelime_bitisi(mevcut[-1])
            if bosluk > bosluk_esigi_saniye + ZAMAN_KARSILASTIRMA_TOLERANSI:
                ana_segmentler.append(mevcut)
                mevcut = []
        mevcut.append(kelime)

    if mevcut:
        ana_segmentler.append(mevcut)
    return ana_segmentler


def _isaretle_dogal_parcalara_ayir(
    kelimeler: Sequence[Dict[str, Any]],
    isaret: str,
) -> List[List[Dict[str, Any]]]:
    parcalar: List[List[Dict[str, Any]]] = []
    mevcut: List[Dict[str, Any]] = []
    for kelime in kelimeler:
        mevcut.append(kelime)
        isaretler = {'.': ('.', '。', '．'), '?': ('?', '？'), '!': ('!', '！'), ',': (',', '、', '，')}.get(isaret, (isaret,))
        if _kelime_metni(kelime).rstrip('"\'”’)]}').endswith(isaretler):
            parcalar.append(mevcut)
            mevcut = []
    if mevcut:
        parcalar.append(mevcut)
    return parcalar


def _dogal_birimleri_uret(
    kelimeler: Sequence[Dict[str, Any]],
    oncelik_sirasi: int = 0,
    maksimum_kelime_sayisi: int = MAKSIMUM_KELIME_SAYISI,
) -> List[List[Dict[str, Any]]]:
    if len(kelimeler) <= maksimum_kelime_sayisi:
        return [list(kelimeler)]
    if oncelik_sirasi >= len(NOKTALAMA_ONCELIGI):
        return [
            list(kelimeler[baslangic:baslangic + maksimum_kelime_sayisi])
            for baslangic in range(0, len(kelimeler), maksimum_kelime_sayisi)
        ]

    isaret = NOKTALAMA_ONCELIGI[oncelik_sirasi]
    parcalar = _isaretle_dogal_parcalara_ayir(kelimeler, isaret)
    if len(parcalar) == 1:
        return _dogal_birimleri_uret(
            kelimeler,
            oncelik_sirasi + 1,
            maksimum_kelime_sayisi,
        )

    birimler: List[List[Dict[str, Any]]] = []
    for parca in parcalar:
        if len(parca) <= maksimum_kelime_sayisi:
            birimler.append(parca)
        else:
            birimler.extend(
                _dogal_birimleri_uret(
                    parca,
                    oncelik_sirasi + 1,
                    maksimum_kelime_sayisi,
                )
            )
    return birimler


def _dogal_birimleri_paketle(
    birimler: Sequence[Sequence[Dict[str, Any]]],
    maksimum_kelime_sayisi: int = MAKSIMUM_KELIME_SAYISI,
) -> List[List[Dict[str, Any]]]:
    segmentler: List[List[Dict[str, Any]]] = []
    mevcut: List[Dict[str, Any]] = []
    for birim in birimler:
        if len(birim) > maksimum_kelime_sayisi:
            raise RuntimeError("Dogal birim maksimum kelime sinirini asti")
        if mevcut and len(mevcut) + len(birim) > maksimum_kelime_sayisi:
            segmentler.append(mevcut)
            mevcut = []
        mevcut.extend(birim)
    if mevcut:
        segmentler.append(mevcut)
    return segmentler


def uzun_ana_segmenti_mantikli_bol(
    kelimeler: Sequence[Dict[str, Any]],
    maksimum_kelime_sayisi: int = MAKSIMUM_KELIME_SAYISI,
) -> List[List[Dict[str, Any]]]:
    if len(kelimeler) <= maksimum_kelime_sayisi:
        return [list(kelimeler)]
    dogal_birimler = _dogal_birimleri_uret(
        kelimeler,
        maksimum_kelime_sayisi=maksimum_kelime_sayisi,
    )
    return _dogal_birimleri_paketle(dogal_birimler, maksimum_kelime_sayisi)


def ana_segmentleri_nihai_segmentlere_bol(
    ana_segmentler: Sequence[Sequence[Dict[str, Any]]],
    maksimum_kelime_sayisi: int = MAKSIMUM_KELIME_SAYISI,
) -> Tuple[List[List[Dict[str, Any]]], int]:
    nihai_segmentler: List[List[Dict[str, Any]]] = []
    bolunen_ana_segment_sayisi = 0
    for ana_segment in ana_segmentler:
        if len(ana_segment) <= maksimum_kelime_sayisi:
            nihai_segmentler.append(list(ana_segment))
            continue
        bolunen_ana_segment_sayisi += 1
        nihai_segmentler.extend(
            uzun_ana_segmenti_mantikli_bol(
                ana_segment,
                maksimum_kelime_sayisi,
            )
        )
    return nihai_segmentler, bolunen_ana_segment_sayisi


def _segment_speaker_bilgisi(kelimeler: Sequence[Dict[str, Any]]) -> str:
    speaker_degerleri = {
        str(kelime.get("speaker") or "")
        for kelime in kelimeler
        if str(kelime.get("speaker") or "")
    }
    return next(iter(speaker_degerleri)) if len(speaker_degerleri) == 1 else ""


def zamanli_kelimeleri_metne_birlestir(kelimeler: Sequence[Dict[str, Any]]) -> str:
    parcalar = []
    onceki_dil = None
    for kelime in kelimeler:
        dil = kelime.get('detected_language')
        ayirac = '' if dil == onceki_dil and dil in {'ja', 'zh', 'yue', 'th', 'lo', 'my'} else ' '
        parcalar.append((ayirac if parcalar else '') + _kelime_metni(kelime))
        onceki_dil = dil
    return ''.join(parcalar)


def segment_kaydini_olustur(
    kelimeler: Sequence[Dict[str, Any]],
    sira: int,
) -> Dict[str, Any]:
    return {
        "index": sira,
        "start": _kelime_baslangici(kelimeler[0]),
        "end": _kelime_bitisi(kelimeler[-1]),
        "text": zamanli_kelimeleri_metne_birlestir(kelimeler),
        "speaker": _segment_speaker_bilgisi(kelimeler),
        "words": [dict(kelime) for kelime in kelimeler],
        "word_count": len(kelimeler),
    }


def segment_uretimini_dogrula(
    girdi_kelimeleri: Sequence[Dict[str, Any]],
    segment_kayitlari: Sequence[Dict[str, Any]],
    maksimum_kelime_sayisi: int = MAKSIMUM_KELIME_SAYISI,
) -> None:
    cikti_kelimeleri = [
        kelime
        for segment in segment_kayitlari
        for kelime in segment["words"]
    ]
    if cikti_kelimeleri != list(girdi_kelimeleri):
        raise RuntimeError("Nihai segment uretiminde kelime kaybi, tekrari veya sira degisikligi olustu")
    if any(int(segment["word_count"]) > maksimum_kelime_sayisi for segment in segment_kayitlari):
        raise RuntimeError("Nihai segment maksimum kelime sinirini asti")


def nihai_dublaj_segmentlerini_olustur(
    kelimeler: Sequence[Dict[str, Any]],
    segment_factory: Callable[..., Any] = NihaiDublajSegmenti,
    bosluk_esigi_saniye: float = BOSLUK_ESIGI_SANIYE,
    maksimum_kelime_sayisi: int = MAKSIMUM_KELIME_SAYISI,
) -> Tuple[List[Any], Dict[str, Any], SegmentUretimRaporu]:
    dogrulanmis_kelimeler = kelime_listesini_dogrula(kelimeler)
    ana_segmentler = zaman_araligina_gore_ana_segmentleri_olustur(
        dogrulanmis_kelimeler,
        bosluk_esigi_saniye,
    )
    nihai_kelime_gruplari, bolunen_ana_segment_sayisi = ana_segmentleri_nihai_segmentlere_bol(
        ana_segmentler,
        maksimum_kelime_sayisi,
    )
    segment_kayitlari = [
        segment_kaydini_olustur(kelime_grubu, sira)
        for sira, kelime_grubu in enumerate(nihai_kelime_gruplari, start=1)
    ]
    segment_uretimini_dogrula(
        dogrulanmis_kelimeler,
        segment_kayitlari,
        maksimum_kelime_sayisi,
    )
    segmentler = [
        segment_factory(
            index=kayit["index"],
            start=kayit["start"],
            end=kayit["end"],
            text=kayit["text"],
            speaker=kayit["speaker"],
            words=list(kayit["words"]),
        )
        for kayit in segment_kayitlari
    ]
    alignment = {
        "segments": [
            {
                "start": kayit["start"],
                "end": kayit["end"],
                "text": kayit["text"],
                "words": list(kayit["words"]),
            }
            for kayit in segment_kayitlari
        ]
    }
    rapor = SegmentUretimRaporu(
        girdi_kelime_sayisi=len(dogrulanmis_kelimeler),
        ana_segment_sayisi=len(ana_segmentler),
        nihai_segment_sayisi=len(segmentler),
        bolunen_ana_segment_sayisi=bolunen_ana_segment_sayisi,
        maksimum_nihai_segment_kelime_sayisi=max(
            (len(kayit["words"]) for kayit in segment_kayitlari),
            default=0,
        ),
        bosluk_esigi_saniye=float(bosluk_esigi_saniye),
    )
    return segmentler, alignment, rapor
