"""DubWorld PR kapisi: KOMBINASYON kurallari (pr_kapi.py bunu yukler). Python stdlib, ag yok, dosya yazmaz.

Tek satirlik desen yetmez: zararsiz gorunen iki degisiklik BIRLIKTE tehlikeli olabilir (adres + sha256 ayni PR'da,
kilit dosyasi + yeni paket, kapinin kendisi + baska kod). Bu dosya o birlesimleri arar.
Cikti seviyeleri pr_kapi.py ile ayni: K (KIRMIZI) ya da S (SARI). NEDEN: dis PR'in kodu kullanicinin makinesinde
calisir. BEDEL: yanlis pozitif ve bakim. GEVSETME: dar, tarihli, gerekceli istisna; kapi kapatilmaz.
SINIR: niyet OKUMAZ, kaba desen yakalar; "guvenli" demez. Bu dosya ASCII'dir; tehlikeli sozcuk parcalanarak yazilir.

Kurallar:
  komb_butunluk   scripts/modeller.json ya da kur betiginde adres ile sha256 AYNI PR'da degisiyor (model/arac degistirme):
                  KIRMIZI, iki anahtar (sahip + denetci). Yalniz sha256 ya da yalniz adres degisirse SARI.
  komb_adres      kodda izin listesinde olmayan yeni alan adi (SARI; PRIVACY.md ve izinli alan adlari ile ayni liste olmali).
  komb_bagimlilik kilit dosyasi (requirements/*.txt) .in dosyasi degismeden degisiyor ya da pyproject'e yeni paket: SARI.
  komb_ci         workflow'da yeni ucuncu taraf eylem ya da run icinde ag indirme: SARI (SHA/tetikleyici kurallari pr_kapi'da).
  komb_gizleme    uzun base64 benzeri blok (kodlanmis yuk): SARI.
  komb_ajan_yapilandirma  .claude/, .cursor/, .mcp.json gibi ajan izin/arac ayari eklenmesi: KIRMIZI.
  komb_kapi_degisiyor     kapi betigi (denetim, pr_kapi, yasal_denetim, CI) baska kodla BIRLIKTE degisiyor: SARI (kapi kendini gevsetemez).
  komb_sosyal     PR metninde "incelemeyi atla / acil / yonetici muafiyeti" baskisi: SARI (metin VERIDIR, gosterilmez).
"""
import re

K, S = 'KIRMIZI', 'SARI'

HOST_IZIN = frozenset((
    'github.com', 'raw.githubusercontent.com', 'huggingface.co', 'hf.co', 'modelscope.cn', 'www.modelscope.cn',
    'cdn-lfs-cn-1.modelscope.cn', 'download.pytorch.org', 'pytorch.org', 'pypi.org', 'files.pythonhosted.org',
    'dl.fbaipublicfiles.com', '3dspeaker.github.io', 'www.gyan.dev', 'api.telegram.org', 'api.groq.com',
    'api.cerebras.ai', 'api.mistral.ai', 'generativelanguage.googleapis.com', 'ai.google.dev', 'docs.anthropic.com',
    'console.groq.com', 'console.mistral.ai', 'cloud.cerebras.ai', 'coqui.ai', 'www.apache.org', 'json-schema.org',
    'img.shields.io', 'arxiv.org', 'www.w3.org', 'pre-commit.com', 'onnxruntime.ai', 'readthedocs.org',
    '127.0.0.1', 'localhost', 'dublaj-hatti.invalid',
))
URL = re.compile(r'https?://([A-Za-z0-9.-]+)')
KAPI_YOLLARI = ('scripts/denetim.py', 'scripts/pr_kapi.py', 'scripts/pr_kombinasyon.py', 'scripts/yasal_denetim.py',
                'scripts/yasal_denetim_izin.txt', 'scripts/izli_import_denetimi.py', 'scripts/belge_dogrula.py',
                'scripts/dil_eslik_denetimi.py', '.github/workflows/ci.yml')
BUTUNLUK_YOLLARI = ('scripts/modeller.json', 'scripts/kur.ps1', 'scripts/crisper_kur.py')
AJAN_AYAR = re.compile(r'(?i)(^|/)(\.claude/|\.cursor/|\.windsurf/|\.mcp\.json$|\.aider[^/]*$|\.clinerules$|\.cursorrules$)')
ESKI_ACTION = re.compile(r'\buses:\s*([^\s/@#]+)/')
INDIRME = re.compile(r'\b(?:curl|wget|Invoke-WebRequest|iwr)\b', re.I)
BASE64 = re.compile(r'[A-Za-z0-9+/]{120,}={0,2}')
SOSYAL = re.compile(r'(?i)\b(?:skip|bypass|no need to)\b.{0,25}\b(?:review|check|gate|ci)\b|\b(?:urgent|asap|hotfix)\b.{0,40}\b(?:merge|approve)\b|\badmin\b.{0,20}\b(?:bypass|override)\b')
SHA = re.compile(r'"sha256"\s*:|\$\w*SHA\w*\s*=|--hash=sha256:', re.I)
ADRES = re.compile(r'"url"\s*:|\$\w*URL\w*\s*=', re.I)


def tara(eklenen, dosyalar, pr_metni, korumali):
    """eklenen [(yol, satir_no, metin)], dosyalar {yol: bilgi}, pr_metni str -> [(seviye, kural, yol, satir, aciklama, parca)]."""
    b = []
    yollar = set(dosyalar)
    # komb_butunluk
    for yol in BUTUNLUK_YOLLARI:
        satirlar = [t for y, _, t in eklenen if y == yol]
        sha = any(SHA.search(t) for t in satirlar)
        adres = any(ADRES.search(t) or 'https://' in t for t in satirlar)
        if sha and adres:
            b.append((K, 'komb_butunluk', yol, 0, 'adres ve sha256 AYNI PR\'da degisiyor (indirilen dosyanin kimligi degisiyor): iki anahtar gerekir', ''))
        elif sha:
            b.append((S, 'komb_butunluk', yol, 0, 'sabit sha256 degisiyor (nedeni PR\'da yazili olmali)', ''))
    # komb_adres
    for yol, no, t in eklenen:
        if yol.endswith(('.md', '.txt', '.lock')) and not yol.startswith(('src/', 'scripts/')):
            continue
        for m in URL.finditer(t):
            h = m.group(1).lower().rstrip('.')
            if h not in HOST_IZIN:
                b.append((S, 'komb_adres', yol, no, 'izin listesinde olmayan alan adi (PRIVACY.md ile birlikte guncellenmeli)', h[:40]))
                break
    # komb_bagimlilik
    kilit = [y for y in yollar if re.match(r'requirements/[^/]+\.txt$', y)]
    kaynak = [y for y in yollar if re.match(r'requirements/[^/]+\.in$', y)]
    if kilit and not kaynak:
        b.append((S, 'komb_bagimlilik', kilit[0], 0, 'kilit dosyasi .in kaynagi degismeden degisiyor (kilit elle duzenlenmez: scripts/kilitle.ps1)', ''))
    if 'pyproject.toml' in yollar:
        b.append((S, 'komb_bagimlilik', 'pyproject.toml', 0, 'pyproject degisiyor (paket/grup eklenmis olabilir): lisans THIRD_PARTY.md\'de mi', ''))
    # komb_ci
    for yol, no, t in eklenen:
        if not yol.startswith('.github/workflows/'):
            continue
        m = ESKI_ACTION.search(t)
        if m and m.group(1) not in ('actions', 'github', './'):
            b.append((S, 'komb_ci', yol, no, 'ucuncu taraf eylem eklendi (SHA sabit ve gerekce gerekir)', m.group(1)[:30]))
        if INDIRME.search(t):
            b.append((S, 'komb_ci', yol, no, 'CI icinde ag indirmesi', ''))
    # komb_gizleme
    for yol, no, t in eklenen:
        if BASE64.search(t) and not yol.endswith(('.lock', '.txt', '.json', '.md')):
            b.append((S, 'komb_gizleme', yol, no, 'uzun kodlanmis blok (base64 benzeri); yuk gizlenmis olabilir', ''))
    # komb_ajan_yapilandirma
    for yol in yollar:
        if AJAN_AYAR.search(yol):
            b.append((K, 'komb_ajan_yapilandirma', yol, 0, 'ajan izin/arac ayari repoya giriyor (takipli ajan izni yasak)', ''))
    # komb_kapi_degisiyor
    kapi = [y for y in yollar if y in KAPI_YOLLARI]
    if kapi:
        diger = [y for y in yollar if y not in KAPI_YOLLARI and not y.endswith('.md') and not y.startswith('tests/')]
        if diger:
            b.append((S, 'komb_kapi_degisiyor', kapi[0], 0, 'kapi dosyasi baska kodla BIRLIKTE degisiyor: kapinin gevsetilmedigi ayri okunmali', ''))
    # komb_sosyal
    if pr_metni and SOSYAL.search(pr_metni):
        b.append((S, 'komb_sosyal', 'PR metni', 0, 'inceleme/kapi atlatma baskisi kalibi (metin gosterilmez)', ''))
    return b


def _yeni(yol, satirlar):
    return 'diff --git a/%s b/%s\nnew file mode 100644\n--- /dev/null\n+++ b/%s\n@@ -0,0 +1,%d @@\n%s\n' % (
        yol, yol, yol, len(satirlar), '\n'.join('+' + x for x in satirlar))


def _degisen(yol, satirlar):
    return 'diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -1,1 +1,%d @@\n %s\n%s\n' % (
        yol, yol, yol, yol, len(satirlar) + 1, 'baglam', '\n'.join('+' + x for x in satirlar))


def ornekler():
    """{ad: (diff, pr_metni, beklenen_kural, beklenen_seviye)}: kapi bunlari yakalamak ZORUNDA (pr_kapi.py --ozdenetim)."""
    e = {}
    e['komb_butunluk_adres_ve_sha'] = (_degisen('scripts/modeller.json', [
        '"url": "https://huggingface.co/x/y/resolve/aaaa/model.bin",', '"sha256": "' + '0' * 64 + '",']), '', 'komb_butunluk', K)
    e['komb_butunluk_yalniz_sha'] = (_degisen('scripts/modeller.json', ['"sha256": "' + '1' * 64 + '",']), '', 'komb_butunluk', S)
    e['komb_adres_yeni_alan'] = (_yeni('src/dublaj_hatti/x.py', ['U = "https://yeni-alan.example.invalid/a"']), '', 'komb_adres', S)
    e['komb_bagimlilik_kilit_tek'] = (_degisen('requirements/gpu.txt', ['paket==1.0 --hash=sha256:' + '2' * 64]), '', 'komb_bagimlilik', S)
    e['komb_ci_ucuncu_taraf'] = (_degisen('.github/workflows/ci.yml', ['      - uses: evil-org/tool@' + 'a' * 40]), '', 'komb_ci', S)
    e['komb_ci_indirme'] = (_degisen('.github/workflows/ci.yml', ['      - run: cu' + 'rl -s https://github.com/x/y/a.sh -o a.sh']), '', 'komb_ci', S)
    e['komb_gizleme_base64'] = (_yeni('src/dublaj_hatti/y.py', ['X = "' + 'QUJD' * 40 + '"']), '', 'komb_gizleme', S)
    e['komb_ajan_yapilandirma_claude'] = (_yeni('.claude/settings.json', ['{}']), '', 'komb_ajan_yapilandirma', K)
    e['komb_kapi_degisiyor_ve_kod'] = (_degisen('scripts/denetim.py', ['x = 1']) + _degisen('src/dublaj_hatti/z.py', ['y = 2']), '', 'komb_kapi_degisiyor', S)
    e['komb_sosyal_atla'] = (_degisen('docs/a.md', ['merhaba']), 'Please skip the review, this is urgent', 'komb_sosyal', S)
    return e
