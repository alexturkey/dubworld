// DubWorld web arayüzü. Dış kaynak yok; bütün metin textContent ile yazılır (HTML enjeksiyonu yok).
"use strict";
const BELIRTEC = document.querySelector('meta[name="dublaj-belirtec"]').content;
const $ = (id) => document.getElementById(id);
let form = [];
let degisiklik = {};
let yuklenen = null;
let baglanti = "";  // https bağlantısı; sunucu türüne göre gereken aracı denetler
let izleyici = null;

async function api(yol, govde) {
  const secenek = govde === undefined
    ? { headers: { "X-Dublaj-Belirtec": BELIRTEC } }
    : { method: "POST", headers: { "X-Dublaj-Belirtec": BELIRTEC, "Content-Type": "application/json" },
        body: JSON.stringify(govde) };
  const yanit = await fetch(yol, secenek);
  const veri = await yanit.json().catch(() => ({}));
  if (!yanit.ok) {
    const hata = new Error(veri.hata || ("HTTP " + yanit.status));
    hata.veri = veri;
    throw hata;
  }
  return veri;
}

// Hata satırı sayfada hep yer tutar (CSS: min-height); görünür/gizli olması düzeni kaydırmaz.
function hataGoster(metin) { const h = $("hata"); h.textContent = metin || ""; h.classList.toggle("gorunur", !!metin); }

// Tek onay penceresi (<dialog id="onay">): Promise<boolean>. Esc, perdeye tıklama ve "Vazgeç" = false.
// tehlike:true → kırmızı eylem düğmesi; varsayılan odak her zaman "Vazgeç"te.
function onayIste({ baslik, metin, tamam, tehlike }) {
  const pencere = $("onay"), tamamDugme = $("onay-tamam"), vazgec = $("onay-vazgec");
  const onceki = document.activeElement;
  $("onay-baslik").textContent = baslik || "";
  $("onay-metin").textContent = metin || "";
  tamamDugme.textContent = tamam || t("onay.tamam");
  tamamDugme.className = tehlike ? "tehlike-dolu" : "ana";
  return new Promise((coz) => {
    let sonuc = false;
    const tamamTik = () => { sonuc = true; pencere.close(); };
    const perdeTik = (e) => {
      if (e.target !== pencere) return;
      const k = pencere.getBoundingClientRect();
      if (e.clientX < k.left || e.clientX > k.right || e.clientY < k.top || e.clientY > k.bottom) pencere.close();
    };
    const kapandi = () => {
      tamamDugme.removeEventListener("click", tamamTik);
      vazgec.removeEventListener("click", vazgecTik);
      pencere.removeEventListener("click", perdeTik);
      pencere.removeEventListener("close", kapandi);
      if (onceki && onceki.isConnected && onceki.focus) onceki.focus({ preventScroll: true });
      coz(sonuc);
    };
    const vazgecTik = () => pencere.close();
    tamamDugme.addEventListener("click", tamamTik);
    vazgec.addEventListener("click", vazgecTik);
    pencere.addEventListener("click", perdeTik);
    pencere.addEventListener("close", kapandi);
    if (pencere.open) pencere.close();
    pencere.showModal();
    vazgec.focus();
  });
}

// Küçük bildirim (başarı): ekranın tek yerinde, 4 sn sonra kendiliğinden kaybolur; sayfayı kaydırmaz.
let bildirimSayaci = null;
// Dar ekranda (telefon) bildirim ALTTA değil, en üstteki katmanın başlığının altında çıkar: alttaki Başlat düğmesinin nedeni,
// ses seçici ve form satırları örtülmez. Katman: açık Ayarlar çekmecesi > tam ekran inceleme paneli > sayfa başlığı.
function bildirimYeri(kutu) {
  if (!matchMedia("(max-width: 640px)").matches) { kutu.classList.remove("ustte"); kutu.style.top = ""; return; }
  let baslik = document.querySelector(".ust");
  if (!$("gelismis").hidden) baslik = $("gelismis").querySelector(".cekmece-ust") || baslik;
  else if (!$("inceleme").hidden && innerWidth < 450) baslik = $("inceleme").firstElementChild || baslik;
  kutu.classList.add("ustte");
  kutu.style.top = Math.round(baslik.getBoundingClientRect().bottom + 8) + "px";
}
function bildir(metin, { geriAl } = {}) {
  const kutu = $("bildirim"), geri = $("bildirim-geri");
  bildirimYeri(kutu);
  $("bildirim-metin").textContent = metin;
  geri.hidden = !geriAl;
  geri.textContent = geriAl ? t("toast.geri_al") : "";
  geri.onclick = geriAl ? () => { kutu.classList.remove("gorunur"); geriAl(); } : null;
  kutu.classList.add("gorunur");
  clearTimeout(bildirimSayaci);
  bildirimSayaci = setTimeout(() => kutu.classList.remove("gorunur"), 4000);
}

// --- arayüz dili: sözlük sunucudan (arayuz_dilleri/<dil>.json); sayfadaki seçim bu tarayıcıda hatırlanır ----------
let SOZLUK = {};
let DIL = "tr";
let sonDurum = null;
const YEREL_DIL = "dubworld.arayuz_dili";
function t(anahtar, degerler) {
  const metin = SOZLUK[anahtar];
  if (metin === undefined) return anahtar;
  return degerler ? metin.replace(/\{(\w+)\}/g, (m, k) => (k in degerler ? String(degerler[k]) : m)) : metin;
}
// Kimlikten arayüz dilindeki ad (durum, aşama, komut); sözlükte yoksa sunucunun verdiği ad.
function cevir(onek, kimlik, yedek) { const a = onek + "." + kimlik; return kimlik && a in SOZLUK ? SOZLUK[a] : (yedek || kimlik || ""); }
// Değişen yazılar da dil değişince yeniden yazılsın diye anahtar ve değerleri öğede tutulur.
function yaz(oge, anahtar, degerler) {
  oge.dataset.t = anahtar;
  oge.dataset.tDeger = JSON.stringify(degerler || {});
  oge.textContent = t(anahtar, degerler);
}
function dilUygula() {
  document.documentElement.lang = DIL;
  document.querySelectorAll("[data-t]").forEach((o) => { o.textContent = t(o.dataset.t, JSON.parse(o.dataset.tDeger || "{}")); });
  document.querySelectorAll("[data-t-ipucu]").forEach((o) => {
    o.placeholder = t(o.dataset.tIpucu);
    if (o.hasAttribute("aria-label")) o.setAttribute("aria-label", t(o.dataset.tIpucu));
  });
  document.querySelectorAll("[data-t-baslik]").forEach((o) => {
    const metin = t(o.dataset.tBaslik);
    if (o.tagName === "BUTTON" || o.hasAttribute("title")) o.title = metin;
    o.setAttribute("aria-label", metin);
  });
}
function baslikYaz(oge, anahtar) { oge.dataset.tBaslik = anahtar; const m = t(anahtar); oge.title = m; oge.setAttribute("aria-label", m); }
function yerelDil() { try { return localStorage.getItem(YEREL_DIL) || ""; } catch (_) { return ""; } }
function yerelDilYaz(kod) { try { localStorage.setItem(YEREL_DIL, kod); } catch (_) { /* gizli pencere: yalnız bu sayfa */ } }
async function dilYukle(secim) {
  const tarayici = (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || ""]).join(",");
  const v = await api("/api/arayuz_dili?secim=" + encodeURIComponent(secim || "") + "&tarayici=" + encodeURIComponent(tarayici));
  SOZLUK = v.sozluk; DIL = v.dil;
  document.documentElement.dir = v.yon || "ltr";
  const secici = $("arayuz-dili");
  secici.replaceChildren(...v.diller.map((d) => { const o = document.createElement("option"); o.value = d.kod; o.textContent = d.ad; return o; }));
  secici.value = DIL;
  dilUygula();
  temaDugmesi();
}
async function formYukle(oncekiDegisiklik) {
  const [v] = await Promise.all([api("/api/ayarlar?dil=" + encodeURIComponent(DIL)), motorlariYukle()]);
  form = v.form;
  formCiz();
  // dil değişince Gelişmiş'te yapılan değişiklikler korunur (form sırasıyla: ses.motor önce, süzülen dil sonra)
  form.filter((a) => oncekiDegisiklik && a.anahtar in oncekiDegisiklik).forEach((a) => {
    const g = $("a_" + a.anahtar);
    if (!g) return;
    if (g.type === "checkbox") g.checked = !!oncekiDegisiklik[a.anahtar]; else g.value = oncekiDegisiklik[a.anahtar];
    g.dispatchEvent(new Event("change"));
  });
}
$("arayuz-dili").addEventListener("change", async (e) => {
  const onceki = Object.assign({}, degisiklik);
  try {
    yerelDilYaz(e.target.value);
    await dilYukle(e.target.value);
    await formYukle(onceki);
    islerYukle();
    if (sonDurum) durumCiz(sonDurum);
    incelemeDiliYenile();
    sesHepsiniCiz();
  } catch (hata) { hataGoster(hata.message); }
});
function dosyaAdresi(yol) { return "/dosya?yol=" + encodeURIComponent(yol); }

// --- sekmeler ---------------------------------------------------------------------------------------
function cekmece(acik) {
  $("gelismis").hidden = !acik; $("perde").hidden = !acik;
  document.querySelector('.sekme[data-sekme="gelismis"]').setAttribute("aria-expanded", String(acik));
  if (acik) { $("ayar-ara").focus(); motorlariTazele(); }
}
function sayfaAc(ad) {
  document.querySelectorAll(".sekme").forEach((x) => { if (x.dataset.sekme !== "gelismis") x.classList.toggle("etkin", x.dataset.sekme === ad); });
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("etkin", p.id === ad));
  if (ad === "sesler") sesleriYukle();
}
document.querySelectorAll(".sekme").forEach((d) => d.addEventListener("click", () => {
  if (d.dataset.sekme === "gelismis") cekmece($("gelismis").hidden); else { cekmece(false); sayfaAc(d.dataset.sekme); }
}));
$("ayarlar-kapat").addEventListener("click", () => cekmece(false));
$("perde").addEventListener("click", () => cekmece(false));
$("ayar-ara").addEventListener("input", (e) => {  // anahtar, açıklama ya da bölüm adında arar
  const aranan = e.target.value.trim().toLocaleLowerCase(DIL);
  let gorunen = 0;
  document.querySelectorAll("#form fieldset").forEach((fs) => {
    if (fs.classList.contains("motor-bolum")) {  // seçici: kendi metninde arar (motor adı, güçlü yan, lisans, donanım)
      const uygun = !aranan || fs.textContent.toLocaleLowerCase(DIL).includes(aranan);
      fs.hidden = !uygun; if (uygun) gorunen++;
      return;
    }
    let bolumde = 0;
    fs.querySelectorAll(".alan:not(.motor-gizli)").forEach((a) => {
      const uygun = !aranan || a.textContent.toLocaleLowerCase(DIL).includes(aranan)
        || fs.querySelector("legend").textContent.toLocaleLowerCase(DIL).includes(aranan);
      a.hidden = !uygun; if (uygun) bolumde++;
    });
    fs.hidden = !bolumde; gorunen += bolumde;
  });
  document.querySelectorAll("#form details.gelismis-motor").forEach((d) => {  // eşleşme varsa açılır; arama bitince eski haline döner
    const eslesen = !!d.querySelector("fieldset:not([hidden])");
    if (aranan) {
      if (d.dataset.once === undefined) d.dataset.once = d.open ? "1" : "0";
      d.hidden = !eslesen; d.open = eslesen;
    } else {
      d.hidden = false;
      if (d.dataset.once !== undefined) { d.open = d.dataset.once === "1"; delete d.dataset.once; }
    }
  });
  $("ayar-sonuc-yok").hidden = gorunen > 0;
});

// --- tema: bilgisayarın ayarı ya da elle seçim (bu tarayıcıda hatırlanır) -------------------------------
const YEREL_TEMA = "dubworld.tema";
const koyuMu = () => (document.documentElement.dataset.tema || (matchMedia("(prefers-color-scheme: dark)").matches ? "koyu" : "acik")) === "koyu";
function temaDugmesi() { baslikYaz($("tema"), koyuMu() ? "ust.tema_acik" : "ust.tema_koyu"); }
try { const k = localStorage.getItem(YEREL_TEMA); if (k === "acik" || k === "koyu") document.documentElement.dataset.tema = k; } catch (_) { /* yok */ }
$("tema").addEventListener("click", () => {
  const yeni = koyuMu() ? "acik" : "koyu";
  document.documentElement.dataset.tema = yeni;
  try { localStorage.setItem(YEREL_TEMA, yeni); } catch (_) { /* gizli pencere */ }
  temaDugmesi();
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", temaDugmesi);

// --- yardım penceresi ------------------------------------------------------------------------------------
$("yardim-ac").addEventListener("click", () => $("yardim").showModal());
$("yardim-kapat").addEventListener("click", () => $("yardim").close());

// --- Gelişmiş: şemadan üretilen form ------------------------------------------------------------------
function alanCiz(alan) {
  const kutu = document.createElement("div");
  kutu.className = "alan";
  const etiket = document.createElement("label");
  etiket.textContent = alan.anahtar;
  etiket.htmlFor = "a_" + alan.anahtar;
  let girdi;
  if (alan.tur === "secim") {
    girdi = document.createElement("select");
    secenekleriYaz(girdi, alan.secenekler, alan.etiketler || {});
    girdi.value = alan.deger;
  } else if (alan.tur === "evet_hayir") {
    girdi = document.createElement("input"); girdi.type = "checkbox"; girdi.checked = !!alan.deger;
  } else {
    girdi = document.createElement("input");
    girdi.type = (alan.tur === "tam_sayi" || alan.tur === "ondalik") ? "number" : "text";
    if (alan.tur === "ondalik") girdi.step = "0.05";
    girdi.value = alan.deger === null || alan.deger === undefined ? "" : alan.deger;
  }
  girdi.id = "a_" + alan.anahtar;
  girdi.addEventListener("change", () => {
    let deger = alan.tur === "evet_hayir" ? girdi.checked : girdi.value;
    if (alan.tur === "tam_sayi") deger = parseInt(deger, 10);
    if (alan.tur === "ondalik") deger = parseFloat(deger);
    if (deger === alan.deger) delete degisiklik[alan.anahtar]; else degisiklik[alan.anahtar] = deger;
    kutu.classList.toggle("degisti", alan.anahtar in degisiklik);
  });
  const aciklama = document.createElement("div");
  aciklama.className = "aciklama";
  aciklama.textContent = alan.aciklama;
  if (alan.ses_secenekleri) {  // konuşmacı başına ses: seçili motorun sesleri (docs/sesler.md)
    aciklama.textContent += " · " + t("ayar.sesler") + ": " + Object.entries(alan.ses_secenekleri)
      .filter(([, v]) => v.length).map(([tts, v]) => tts + ": " + v.join(", ")).join("; ");
  }
  kutu.append(etiket, girdi, aciklama);
  return kutu;
}

// Seçeneğin yanında donanım etiketi ("CPU'da yavaş", "VRAM yetmez" ...); motor gizlenmez (docs/donanim.md).
function secenekleriYaz(girdi, secenekler, etiketler) {
  girdi.replaceChildren();
  secenekler.forEach((s) => {
    const o = document.createElement("option");
    o.value = s;
    o.textContent = etiketler[s] ? s + "  ·  " + etiketler[s] : s;
    girdi.appendChild(o);
  });
}

// Hedef dil listesi seçili TTS'e göre süzülür (docs/diller.md); denenmemiş dil etiketle görünür.
function suzgecleriBagla() {
  form.filter((a) => a.suzgec).forEach((alan) => {
    const hedef = $("a_" + alan.anahtar);
    const kaynak = $("a_" + alan.suzgec.anahtar);
    if (!hedef || !kaynak) return;
    const uygula = () => {
      const v = alan.suzgec.degerler[kaynak.value];
      if (!v) return;
      const onceki = hedef.value;
      const etiketler = {};
      v.denenmemis.forEach((d) => { etiketler[d] = t("ayar.denenmedi_uyari"); });
      secenekleriYaz(hedef, v.izinli, etiketler);
      Array.from(hedef.options).forEach((o) => { if (v.denenmemis.includes(o.value)) o.dataset.denenmedi = "1"; });
      hedef.value = v.izinli.includes(onceki) ? onceki : v.izinli[0];
      if (hedef.value !== onceki) hedef.dispatchEvent(new Event("change"));
    };
    kaynak.addEventListener("change", uygula);
    uygula();
  });
}

// Önerilen sekmesindeki "Dublaj dili" = Gelişmiş'teki genel.hedef_dil (tek kaynak: o alanın değeri ve süzülmüş
// seçenekleri). Ad arayüz dilinde, farklıysa yanında dilin kendi adı (sunucu: dil_adlari): "German (Deutsch)";
// ana düğme sözlükteki tam cümle: "Dub into German", "Almanca dublajla".
const DIL_ANAHTARI = "genel.hedef_dil";
function kendiAdi(kod) {
  const alan = form.find((a) => a.anahtar === DIL_ANAHTARI);
  return (alan && alan.dil_adlari && alan.dil_adlari[kod]) || kod;
}
function dilAdi(kod) { return SOZLUK["dil." + kod] || kendiAdi(kod); }
function dilSecenegi(kod) {
  const ad = dilAdi(kod), kendi = kendiAdi(kod);
  return ad === kendi ? ad : t("dil.iki_ad", { ad, kendi });
}
function onerilenDiliEsitle() {
  const kaynak = $("a_" + DIL_ANAHTARI);
  const secici = $("hedef-dil");
  if (!kaynak) { secici.disabled = true; return; }
  secici.disabled = false;
  secici.replaceChildren();
  Array.from(kaynak.options).forEach((o) => {
    const yeni = document.createElement("option");
    yeni.value = o.value;
    yeni.textContent = dilSecenegi(o.value) + (o.dataset.denenmedi ? "  ·  " + t("dil.denenmedi") : "");
    secici.appendChild(yeni);
  });
  secici.value = kaynak.value;
  yaz($("dublajla"), "dugme.dublajla", { hedef: dilAdi(kaynak.value) });
}
$("hedef-dil").addEventListener("change", (e) => {
  const kaynak = $("a_" + DIL_ANAHTARI);
  if (!kaynak || kaynak.value === e.target.value) return;
  kaynak.value = e.target.value;
  kaynak.dispatchEvent(new Event("change"));  // Gelişmiş alanının kendi kaydı (degisiklik) çalışır
});

function formCiz() {
  const kok = $("form");
  kok.replaceChildren();
  degisiklik = {};
  const bolumler = {}, gelismisBolumler = {};
  const gelismis = new Set(MOTORLAR ? MOTORLAR.advanced_keys : []);
  const motorAnahtarlari = MOTORLAR ? [MOTORLAR.stt.key, MOTORLAR.tts.key] : [];
  const gelismisKap = document.createElement("details");
  gelismisKap.className = "gelismis-motor";
  const ozet = document.createElement("summary");
  ozet.textContent = t("motor.gelismis.baslik");
  const gelismisYardim = document.createElement("p");
  gelismisYardim.className = "not"; gelismisYardim.textContent = t("motor.gelismis.yardim");
  gelismisKap.append(ozet, gelismisYardim);
  const bolumKur = (hedef, kayit, anahtar) => {
    if (!kayit[anahtar]) {
      const fs = document.createElement("fieldset");
      const lg = document.createElement("legend");
      lg.textContent = cevir("bolum", anahtar, anahtar.replace("_", " "));
      fs.appendChild(lg);
      hedef.appendChild(fs);
      kayit[anahtar] = fs;
    }
    return kayit[anahtar];
  };
  form.forEach((alan) => {
    const oge = alanCiz(alan);
    if (motorAnahtarlari.includes(alan.anahtar)) { oge.classList.add("motor-gizli"); oge.hidden = true; }  // seçici yazar
    if (gelismis.has(alan.anahtar)) bolumKur(gelismisKap, gelismisBolumler, alan.bolum).appendChild(oge);
    else bolumKur(kok, bolumler, alan.bolum).appendChild(oge);
  });
  if (Object.keys(gelismisBolumler).length) kok.appendChild(gelismisKap);
  if (MOTORLAR) kok.prepend(motorGrubuCiz());
  else { const n = document.createElement("p"); n.className = "not"; n.textContent = t("motor.yuklenemedi"); kok.prepend(n); }
  suzgecleriBagla();
  const dilKaynagi = $("a_" + DIL_ANAHTARI);
  if (dilKaynagi) dilKaynagi.addEventListener("change", onerilenDiliEsitle);
  // ses.motor değişince süzgeç seçenekleri yeniden yazar (değer aynı kalsa da): Önerilen listesi de yenilensin
  form.filter((a) => a.suzgec && a.anahtar === DIL_ANAHTARI).forEach((a) => {
    const motor = $("a_" + a.suzgec.anahtar);
    if (motor) motor.addEventListener("change", onerilenDiliEsitle);
  });
  onerilenDiliEsitle();
  gozdenKutusunuBagla(!gozdenBaglandi); gozdenBaglandi = true;
  sesSecimiUygula();
}
let gozdenBaglandi = false;
$("sifirla").addEventListener("click", formCiz);

// --- Motorlar: yazıya dökme ve seslendirme seçicileri -------------------------------------------------------------
// Veri /api/motorlar (kayit.py bilgi satırı + bu bilgisayarın durumu). Seçim Ayarlar'daki a_ alanına yazılır (change olayı:
// kalıcılık ve "değişti" işareti eskisiyle aynı); o iki alan gizlidir, seçici açılamazsa görünür kalır.
let MOTORLAR = null;
async function motorlariYukle() { try { MOTORLAR = await api("/api/motorlar"); } catch (_) { MOTORLAR = null; } }
async function motorlariTazele() {  // çekmece her açılışında: kurulum bu arada değiştiyse seçici güncel görünür
  const eski = MOTORLAR ? JSON.stringify(MOTORLAR) : "";
  await motorlariYukle();
  if (!MOTORLAR || JSON.stringify(MOTORLAR) === eski) return;
  const eskiGrup = document.querySelector("#form .motor-bolum");
  if (eskiGrup) eskiGrup.replaceWith(motorGrubuCiz());
}
// Dinamik anahtarlar (neden kodu, engel, tür): tests/test_motor_secici.py hepsinin iki dilde var olduğunu denetler.
const motorMetni = (anahtar, degerler) => t(anahtar, degerler);
const motorAdi = (e) => cevir("motor.ad", e.id, e.name);
const motorKurulumKomutu = (e) => e.install || "scripts/kur.ps1";
function motorCipi(metin, tur, simge) {
  const c = document.createElement("span");
  c.className = "motor-cip" + (tur ? " " + tur : "");
  if (simge) { const sv = document.createElementNS("http://www.w3.org/2000/svg", "svg"); sv.setAttribute("aria-hidden", "true"); const u = document.createElementNS("http://www.w3.org/2000/svg", "use"); u.setAttribute("href", "#" + simge); sv.appendChild(u); c.appendChild(sv); }
  c.appendChild(document.createTextNode(metin));
  return c;
}
function motorNotu(metin, komut) {  // düz metin; kurulum komutu <code> içinde
  const p = document.createElement("span");
  p.className = "motor-not";
  const parcalar = metin.split("{komut}");
  p.append(parcalar[0]);
  if (komut && parcalar.length > 1) { const k = document.createElement("code"); k.textContent = komut; p.append(k, parcalar[1]); }
  return p;
}
function motorSatiriCiz(grup, e, ad) {
  const etiket = document.createElement("label");
  etiket.className = "motor-secenek"; etiket.dataset.motor = e.id;
  const radyo = document.createElement("input");
  radyo.type = "radio"; radyo.name = "motor-" + grup.tur; radyo.value = e.id;
  radyo.addEventListener("change", () => { if (radyo.checked) motorSec(grup, e.id); });
  const ust = document.createElement("span");
  ust.className = "motor-ust";
  const adi = document.createElement("span");
  adi.className = "motor-ad";
  adi.textContent = e.id === "auto" ? t("motor.auto.ad") : motorAdi(e);
  const isaret = motorCipi(t("motor.cip.secili"), "motor-secili-isareti", "s-tamam");
  ust.append(adi, isaret);
  etiket.append(radyo, ust);
  if (e.id === "auto") {
    const a = grup.veri.auto, secilen = grup.veri.engines.find((x) => x.id === a.engine);
    const satir = document.createElement("span");
    satir.className = "motor-satir";
    satir.textContent = t("motor.auto.burada", { ad: secilen ? motorAdi(secilen) : a.engine });
    const neden = document.createElement("span");
    neden.className = "motor-not";
    neden.textContent = motorMetni("motor.auto." + grup.tur + "." + a.reason) + " " + t("motor.auto.sonra");
    etiket.append(satir, neden);
    if (secilen && !a.installed) etiket.append(motorNotu(t("motor.auto.kurulu_degil_ek", { ad: motorAdi(secilen), komut: "{komut}" }), motorKurulumKomutu(secilen)));
    return etiket;
  }
  const guc = (e.strength && (e.strength[DIL] || e.strength.en)) || "";
  const satir = document.createElement("span");
  satir.className = "motor-satir"; satir.textContent = guc;
  const cipler = document.createElement("span");
  cipler.className = "motor-cipler";
  cipler.append(e.installed ? motorCipi(t("motor.cip.kurulu"), "motor-cip-tamam", "s-tamam") : motorCipi(t("motor.cip.kurulu_degil"), "motor-cip-uyari", "s-uyari"));
  cipler.append(motorCipi(t(e.licence_commercial ? "motor.cip.ticari_evet" : "motor.cip.ticari_hayir")));
  cipler.append(motorCipi(cevir("motor.donanim", e.id, e.hardware)));
  cipler.append(motorCipi(cevir("motor.diller", e.id, e.languages)));
  if (e.deprecated) cipler.append(motorCipi(t("motor.cip.kalkiyor"), "motor-cip-uyari", "s-uyari"));
  if (e.experimental) cipler.append(motorCipi(t("motor.cip.deneysel"), "motor-cip-uyari"));
  etiket.append(satir, cipler);
  if (e.deprecated) etiket.append(motorNotu(t("motor.kalkiyor_not")));
  if (e.blocked_by) etiket.append(motorNotu(motorMetni("motor.engel." + e.blocked_by, { komut: "{komut}" }), motorKurulumKomutu(e)));
  etiket.dataset.engel = e.blocked_by || "";
  return etiket;
}
function motorSec(grup, deger) {
  // Kitaplık/XTTS sesi seçiliyken motor onunla uyumsuz seçilirse ses Otomatik'e döner (sessiz çelişki olmaz)
  const sesMotoru = sesSecimi.startsWith("kitaplik/") ? "voxcpm2" : (sesSecimi.startsWith("xtts/") ? "xtts" : "");
  if (grup.veri.key === "ses.motor" && sesMotoru && deger !== sesMotoru) { sesSec(""); bildir(t("motor.kitaplik_birakildi")); }
  ayarYaz(grup.veri.key, deger);
}
function motorlariEsitle() {  // a_ alanı = tek kaynak; seçici onu yansıtır (ses seçici ya da Varsayılana dön de değiştirir)
  document.querySelectorAll("#form .motor-liste").forEach((liste) => {
    const girdi = $("a_" + liste.dataset.anahtar);
    if (!girdi) return;
    liste.querySelectorAll(".motor-secenek").forEach((satir) => {
      const secili = satir.dataset.motor === girdi.value;
      satir.classList.toggle("secili", secili);
      const r = satir.querySelector("input");
      r.checked = secili;
      const engelli = satir.dataset.engel;
      r.disabled = !!engelli && !secili;  // seçili olan hiç pasif olmaz (dosyadan gelmiş olabilir); iş başlamayınca neden yazar
      satir.classList.toggle("pasif", r.disabled);
      satir.classList.toggle("secili-ama-engelli", secili && !!engelli);
    });
    liste.querySelector(".motor-degisti").style.visibility = (liste.dataset.anahtar in degisiklik) ? "visible" : "hidden";
  });
}
function motorGrubuCiz() {
  const grup = document.createElement("fieldset");
  grup.className = "motor-bolum";
  const lg = document.createElement("legend");
  lg.textContent = t("motor.grup");
  const yardim = document.createElement("p");
  yardim.className = "not"; yardim.textContent = t("motor.grup_yardim");
  grup.append(lg, yardim);
  [["stt", MOTORLAR.stt], ["tts", MOTORLAR.tts]].forEach(([tur, veri]) => {
    const g = { tur, veri };
    const liste = document.createElement("div");
    liste.className = "motor-liste"; liste.setAttribute("role", "radiogroup"); liste.dataset.anahtar = veri.key;
    const baslik = document.createElement("h3");
    baslik.className = "motor-baslik"; baslik.id = "motor-baslik-" + tur;
    const bt = document.createElement("span"); bt.textContent = motorMetni("motor." + tur + ".baslik");
    const dg = document.createElement("span"); dg.className = "motor-degisti"; dg.textContent = t("motor.degisti"); dg.style.visibility = "hidden";
    baslik.append(bt, dg);
    liste.setAttribute("aria-labelledby", baslik.id);
    liste.append(baslik, motorSatiriCiz(g, { id: "auto" }), ...veri.engines.map((e) => motorSatiriCiz(g, e)));
    grup.append(liste);
    const girdi = $("a_" + veri.key);
    if (girdi) girdi.addEventListener("change", motorlariEsitle);
  });
  queueMicrotask(motorlariEsitle);
  return grup;
}

// --- yükleme ------------------------------------------------------------------------------------------
function dosyaYukle(dosya) {
  hataGoster("");
  yuklenen = null; yenidenKaynak = null; izlenenIs = null; baglananAnahtar = "";
  oynaticiYukle({ orijinal: URL.createObjectURL(dosya), yerel: true });
  yukleniyor = true; baslatGuncelle();
  yaz($("dosya-yazi"), "web.yukleniyor", { ad: dosya.name });
  const cubuk = $("yukleme-cubugu");
  cubuk.hidden = false;
  const istek = new XMLHttpRequest();
  istek.open("POST", "/api/yukle");
  istek.setRequestHeader("X-Dublaj-Belirtec", BELIRTEC);
  istek.setRequestHeader("X-Dosya-Adi", encodeURIComponent(dosya.name));
  istek.setRequestHeader("Content-Type", "application/octet-stream");
  istek.upload.onprogress = (e) => { if (e.lengthComputable) cubuk.firstElementChild.style.width = (100 * e.loaded / e.total) + "%"; };
  istek.onload = () => {
    yukleniyor = false;
    let veri = {};
    try { veri = JSON.parse(istek.responseText); } catch (_) { /* boş */ }
    if (istek.status !== 200) { hataGoster(veri.hata || t("web.yukleme_basarisiz")); yaz($("dosya-yazi"), "web.tekrar_sec"); baslatGuncelle(); return; }
    yuklenen = veri.kimlik;
    baglanti = ""; $("baglanti").value = "";
    yaz($("dosya-yazi"), "web.yuklendi", { ad: dosya.name, mb: (dosya.size / 1048576).toFixed(1) });
    cubuk.hidden = true;
    baslatGuncelle();
  };
  istek.onerror = () => { yukleniyor = false; hataGoster(t("web.yukleme_koptu")); baslatGuncelle(); };
  istek.send(dosya);
}
function baglantiHazir() { return /^https:\/\/\S+$/i.test(baglanti); }
const baslatilabilir = () => !!(yuklenen || baglantiHazir() || yenidenKaynak);
// Başlat düğmelerinin tek kapısı: düğmeyi pasif yapan her neden burada ve altındaki satırda düz sözlerle yazılır
// (yerleşim kaymaz: satırın yeri hep ayrılı). Pasif neden sırası: iş sürüyor, dosya yükleniyor, video yok, VoxCPM2 yok.
let yukleniyor = false;
function baslatNedeni(dublaj) {
  if (sonDurum && sonDurum.durum === "calisiyor") return "calisiyor";
  if (yukleniyor) return "yukleniyor";
  if (!baslatilabilir()) return "video";
  if (dublaj && sesSecimi.startsWith("kitaplik/") && !kit.voxcpm2.kurulu) return "voxcpm2";
  return "";
}
function baslatGuncelle() {
  const dn = baslatNedeni(true), tn = baslatNedeni(false);
  $("dublajla").disabled = !!dn; $("transkript").disabled = !!tn;
  const satir = $("baslat-neden"), anahtar = dn ? "baslat.neden." + dn : "";
  if (anahtar) yaz(satir, anahtar); else { delete satir.dataset.t; satir.textContent = ""; }
}
$("baglanti").addEventListener("input", (e) => {
  baglanti = e.target.value.trim();
  baslatGuncelle();
});
$("dosya").addEventListener("change", (e) => { if (e.target.files[0]) dosyaYukle(e.target.files[0]); });
$("baska-video").addEventListener("click", () => $("dosya").click());
const alan = $("dosya-alani");
alan.addEventListener("dragover", (e) => { e.preventDefault(); alan.classList.add("uzerinde"); });
alan.addEventListener("dragleave", () => alan.classList.remove("uzerinde"));
alan.addEventListener("drop", (e) => { e.preventDefault(); alan.classList.remove("uzerinde"); if (e.dataTransfer.files[0]) dosyaYukle(e.dataTransfer.files[0]); });

// --- iş -----------------------------------------------------------------------------------------------
async function baslat(isTuru) {
  hataGoster("");
  const ayarlar = Object.assign({}, degisiklik, { "genel.is_turu": isTuru });
  if (yenidenKaynak && !yuklenen && !baglantiHazir()) {  // bitmiş işi başka dile: çeviriden yeniden, yazıya dökme tekrarlanmaz
    const no = yenidenKaynak; yenidenKaynak = null;
    ayarlar["genel.hedef_dil"] = $("hedef-dil").value;
    if (await devamEt({ is: no, asama: "ceviri", yeni_is: true, ayarlar })) bildir(t("inceleme.devam_basladi"));
    return;
  }
  const govde = baglantiHazir() ? { baglanti, ayarlar } : { yuklenen, ayarlar };
  try {
    try {
      await api("/api/baslat", govde);
    } catch (e) {
      // Ticari olmayan / şartlı motor ilk kez seçildi: iki dilli uyarı + açık onay; onay sunucuda hatırlanır.
      const bekleyen = e.veri && e.veri.lisans_onayi;
      if (!bekleyen) throw e;
      const metin = bekleyen.map((b) => b.metin).join("\n\n");
      const kabul = await onayIste({ baslik: t("onay.lisans_baslik"), metin, tamam: t("onay.kabul_et"), tehlike: false });
      if (!kabul) return;
      await api("/api/baslat", Object.assign({}, govde, { lisans_onay: true }));
    }
    bekleyenYerel = yerelVideo && yuklenen ? { onceki: sonDurum ? sonDurum.is : null } : null;
    $("sonuc").hidden = true;
    gosterilenSonuc = "";
    izle();
    $("ilerleme").hidden = false;
    $("ilerleme").scrollIntoView({ block: "nearest", behavior: hareketAz() ? "auto" : "smooth" });
  } catch (e) { hataGoster(e.message); }
}
$("dublajla").addEventListener("click", () => baslat("dublaj"));
$("transkript").addEventListener("click", () => baslat("transkript"));
$("durdur").addEventListener("click", async () => {
  const evet = await onayIste({ baslik: t("onay.durdur_baslik"), metin: t("onay.durdur_metin"), tamam: t("dugme.durdur"), tehlike: true });
  if (!evet) return;
  api("/api/durdur", {}).then(() => bildir(t("toast.durduruldu"))).catch((e) => hataGoster(e.message));
});
$("gunluk-ac").addEventListener("click", () => {
  $("gunluk").hidden = !$("gunluk").hidden;
  yaz($("gunluk-ac"), $("gunluk").hidden ? "dugme.gunluk_goster" : "dugme.gunluk_gizle");
});
$("klasor-ac").addEventListener("click", () => api("/api/klasor_ac", { yol: $("klasor-ac").dataset.yol || "" }).catch((e) => hataGoster(e.message)));

function saatYaz(sn) {  // kronometre: 3:07, 1:02:45 (her dilde aynı)
  sn = Math.max(0, Math.floor(sn));
  const s = Math.floor(sn / 3600), d = Math.floor(sn / 60) % 60, n = String(sn % 60).padStart(2, "0");
  return s ? `${s}:${String(d).padStart(2, "0")}:${n}` : `${d}:${n}`;
}
function kalanYaz(sn) {
  if (sn == null) return "";
  return sn < 60 ? t("ilerleme.kalan_az") : t("ilerleme.kalan", { dk: Math.round(sn / 60) });
}
let saatTaban = null;  // {sn, an}: sunucunun söylediği geçen süre + o an; kronometre arada saniye saniye akar
let saatSayaci = null;
function kronometreCiz() {
  if (!saatTaban) return;
  $("kronometre").textContent = saatYaz(saatTaban.sn + (saatTaban.akiyor ? (Date.now() - saatTaban.an) / 1000 : 0));
}
const hareketAz = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function konfeti() {
  if (hareketAz()) return;
  for (let i = 0; i < 16; i++) {  // tek seferlik, kısa; renkler tema belirteçlerinden (CSS .konfeti.k0-k2)
    const o = document.createElement("span");
    o.className = "konfeti k" + (i % 3); o.setAttribute("aria-hidden", "true");
    o.style.left = Math.random() * 100 + "vw"; o.style.animationDelay = Math.random() * 0.4 + "s";
    document.body.appendChild(o);
    setTimeout(() => o.remove(), 2200);
  }
}
function anlatiYaz(s) {
  return t("anlati." + s.anahtar, s.asama ? { asama: cevir("asama", s.asama, s.asama) } : {});
}

// Durak simgeleri sayfadaki SVG sprite'ından (emoji yok; temanın yazı rengini alır).
const DURAK_SIMGELERI = { video: "s-dublaj", ses: "s-ses", yazi: "s-altyazi", ceviri: "s-dil", seslendirme: "s-mikrofon", birlestirme: "s-isler" };
function simgeOlustur(kimlik) {
  const SVG = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(SVG, "svg"), kullan = document.createElementNS(SVG, "use");
  svg.setAttribute("aria-hidden", "true");
  kullan.setAttribute("href", "#" + kimlik);
  svg.append(kullan);
  return svg;
}

function durumCiz(d) {
  const oncekiDurum = sonDurum && sonDurum.durum;
  sonDurum = d;
  const calisiyor = d.durum === "calisiyor";
  if (d.is && d.durum !== "bos") isiDurumdanBagla(d);
  $("ilerleme").hidden = d.durum === "bos";
  $("durdur").disabled = !calisiyor;
  baslatGuncelle();
  if (d.durum !== "bos") yaz($("ilerleme-baslik"), "ilerleme." + d.durum);
  $("ilerleme-cubugu").style.width = d.yuzde + "%";
  $("ilerleme").classList.toggle("bitti", d.durum === "bitti");
  $("ilerleme-yuzde").textContent = t("ilerleme.yuzde", { yuzde: d.yuzde });
  const cerceve = $("ilerleme-cerceve");
  cerceve.setAttribute("aria-valuenow", d.yuzde);
  cerceve.setAttribute("aria-label", t("ilerleme.cubuk_adi"));
  cerceve.classList.toggle("canli", calisiyor);
  cerceve.classList.toggle("tamam", d.durum === "bitti");
  saatTaban = { sn: d.gecen_sn || 0, an: Date.now(), akiyor: calisiyor };
  kronometreCiz();
  if (calisiyor && !saatSayaci) saatSayaci = setInterval(kronometreCiz, 1000);
  if (!calisiyor && saatSayaci) { clearInterval(saatSayaci); saatSayaci = null; }
  $("kalan").textContent = kalanYaz(d.kalan_sn);
  const parcalar = [];
  if (d.bekleme) parcalar.push(d.bekleme);
  if (d.is) parcalar.push(t("ilerleme.is_no", { no: d.is }));
  $("ilerleme-yazi").textContent = parcalar.join(" · ");
  $("duraklar").replaceChildren(...(d.duraklar || []).map((o) => {
    const li = document.createElement("li");
    li.className = o.durum;
    const simge = document.createElement("span");
    simge.className = "simge"; simge.setAttribute("aria-hidden", "true");
    simge.append(simgeOlustur(o.durum === "bitti" ? "s-tamam" : (DURAK_SIMGELERI[o.id] || "s-isler")));
    const ad = document.createElement("span");
    ad.className = "ad"; ad.textContent = t("durak." + o.id);
    li.append(simge, ad);
    return li;
  }));
  const pano = $("anlati");
  const panoAltta = pano.scrollTop + pano.clientHeight >= pano.scrollHeight - 4;
  pano.replaceChildren(...(d.anlati || []).map((s) => {
    const li = document.createElement("li");
    const zaman = document.createElement("time");
    zaman.textContent = saatYaz(s.sn);
    li.append(zaman, anlatiYaz(s));
    return li;
  }));
  if (panoAltta) pano.scrollTop = pano.scrollHeight;
  if (oncekiDurum === "calisiyor" && d.durum === "bitti") konfeti();
  const gunluk = $("gunluk");
  const altta = gunluk.scrollTop + gunluk.clientHeight >= gunluk.scrollHeight - 4;
  gunluk.textContent = (d.gunluk || []).join("\n");
  if (altta) gunluk.scrollTop = gunluk.scrollHeight;
  if (d.durum === "hata") hataGoster(d.hata);
  if (d.durum === "inceleme_bekliyor" && d.is) incelemeBaslat(d.is, { otomatik: true });
  else if (incelemeIs && d.is === incelemeIs) incelemeBitir(incelemeIs);
  if (d.durum === "bitti") sonucCiz(d.sonuc || {}, d.ciktilar || [], d.orijinal);
}

let gosterilenSonuc = "";
function sonucCiz(sonuc, ciktilar, kaynak) {
  $("sonuc").hidden = false;
  const video = sonuc.dubbed_video || sonuc.output_video;
  const srt = sonuc.srt_path || (ciktilar.find((c) => /\.srt$/i.test(c.yol)) || {}).yol;
  if (video && gosterilenSonuc !== video) {  // her yoklamada yeniden yüklenmesin
    gosterilenSonuc = video;
    const orijinal = oynatici.orijinal || (kaynak ? dosyaAdresi(kaynak) : "");
    oynaticiYukle({ orijinal, dublaj: dosyaAdresi(video), srt: srt ? dosyaAdresi(srt) : "" });
    const indir = $("indir");
    indir.href = dosyaAdresi(video); indir.setAttribute("download", video.split(/[\\/]/).pop());
  }
  const liste = $("sonuc-dosyalari");
  const yollar = new Set(Object.entries(sonuc).filter(([k]) => k !== "run_dir").map(([, v]) => v));
  ciktilar.forEach((c) => yollar.add(c.yol));
  liste.replaceChildren(...[...yollar].map((yol) => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = dosyaAdresi(yol); a.target = "_blank"; a.rel = "noopener";
    a.textContent = yol.split(/[\\/]/).pop();
    li.appendChild(a);
    return li;
  }));
  $("klasor-ac").dataset.yol = sonuc.run_dir || "";
}

function izle() {
  if (izleyici) clearInterval(izleyici);
  const bekleSonu = Date.now() + 6000;  // iş kuyruktan alınana kadar kısa süre izlemeyi sürdür
  const tur = async () => {
    try {
      const d = await api("/api/durum");
      durumCiz(d);
      if (d.durum !== "calisiyor" && Date.now() > bekleSonu) { clearInterval(izleyici); izleyici = null; islerYukle(); }
    } catch (e) { hataGoster(e.message); }
  };
  tur();
  izleyici = setInterval(tur, 1500);
}

// --- İşler: geçmiş, sorunlu, devam, aşamadan yeniden çalıştır, klasör aç, arşivle ------------------------
// İş satırı düğmesi: simge + görünür yazı + aynı sözlerle ipucu (title). tehlike:true → kırmızıya yatkın (Durdur/İptal).
function dugme(yazi, islev, simge, tehlike) {
  const b = document.createElement("button");
  b.type = "button"; b.title = yazi;
  if (tehlike) b.className = "tehlike";
  if (simge) b.append(simgeOlustur(simge));
  const m = document.createElement("span"); m.textContent = yazi;
  b.append(m);
  b.addEventListener("click", islev);
  return b;
}
const hataBildir = (e) => hataGoster(e.message);
async function isIptalEt(no) {
  const evet = await onayIste({ baslik: t("onay.is_iptal_baslik", { no }), metin: t("onay.is_iptal_metin"), tamam: t("onay.is_iptal_tamam"), tehlike: true });
  if (!evet) return;
  api("/api/is_iptal", { is: no }).then(islerYukle).then(() => bildir(t("toast.is_iptal", { no }))).catch(hataBildir);
}
async function isArsivle(no) {
  const evet = await onayIste({ baslik: t("onay.arsiv_baslik", { no }), metin: t("onay.arsiv_metin"), tamam: t("isler.arsivle"), tehlike: false });
  if (!evet) return;
  api("/api/is_arsivle", { is: no }).then(islerYukle).then(() => bildir(t("toast.arsivlendi", { no }))).catch(hataBildir);
}

async function devamEt(govde) {
  hataGoster("");
  try {
    const v = await api("/api/devam", govde);
    $("is-secenek").hidden = true;
    $("sonuc").hidden = true;
    izle();
    islerYukle();
    return v;
  } catch (e) { hataGoster(e.message); return null; }
}

async function secenekAc(no) {
  try {
    const v = await api("/api/is?no=" + no);
    const sec = $("is-asama");
    sec.replaceChildren(...(v.yeniden_calistir || []).map((s) => {
      const o = document.createElement("option"); o.value = s.restart_stage_id; o.textContent = cevir("asama", s.restart_stage_id, s.ad); return o; }));
    if (!sec.options.length) { hataGoster(t("isler.checkpoint_yok_is", { no })); return; }
    sec.selectedIndex = sec.options.length - 1;
    yaz($("is-secenek-baslik"), "isler.baslik_kisa", { no, kaynak: v.kaynak_adi });
    $("is-yeniden").dataset.no = no;
    $("is-secenek").hidden = false;
  } catch (e) { hataGoster(e.message); }
}
$("is-yeniden").addEventListener("click", () => devamEt({
  is: Number($("is-yeniden").dataset.no), asama: $("is-asama").value, yeni_is: true,
  ayarlar: $("is-gelismis").checked ? degisiklik : {} }));
$("is-secenek-kapat").addEventListener("click", () => { $("is-secenek").hidden = true; });

function isSatiri(o, sorunlu) {
  const kutu = document.createElement("div");
  kutu.className = "is";
  const no = document.createElement("strong"); no.textContent = "#" + o.is;
  const durum = document.createElement("span"); durum.className = "durum-" + o.durum; durum.textContent = cevir("durum", o.durum, o.durum_adi);
  const ad = document.createElement("span");
  ad.textContent = o.kaynak_adi + " · " + cevir("komut", o.komut, o.komut) + (o.ebeveyn ? " (← #" + o.ebeveyn + ")" : "");
  const dugmeler = document.createElement("span"); dugmeler.className = "dugmeler";
  const sorunluMu = o.durum === "failed" || o.durum === "cancelled";
  const devamVar = !sorunlu || (o.devam_secenekleri || []).length > 0;
  if (sorunluMu && o.komut === "dubla" && devamVar) dugmeler.append(dugme(t("isler.devam"), () => devamEt({ is: o.is }), "s-oynat"));
  if ((sorunluMu || o.durum === "completed") && o.komut === "dubla") dugmeler.append(dugme(t("isler.asamadan_dugme"), () => secenekAc(o.is), "s-ileri"));
  if (o.durum === "inceleme_bekliyor" && o.komut === "dubla") dugmeler.append(dugme(t("inceleme.ac"), () => {
    sayfaAc("onerilen"); isBagla(o, true); incelemeBaslat(o.is);
  }, "s-kalem"));
  if (o.video) dugmeler.append(dugme(t("dugme.videoyu_ac"), () => { sayfaAc("onerilen"); isBagla(o, true); }, "s-dublaj"));
  if (o.klasor) dugmeler.append(dugme(t("isler.klasor"), () => api("/api/klasor_ac", { yol: o.klasor }).catch(hataBildir), "s-klasor"));
  // Sıra: kullan, aç, yönet; yıkıcı/durdurucu olan hep sonda.
  if (!["queued", "deferred", "preparing", "processing"].includes(o.durum) && !o.arsiv)
    dugmeler.append(dugme(t("isler.arsivle"), () => isArsivle(o.is), "s-arsiv"));
  if (o.durum === "queued" || o.durum === "deferred")
    dugmeler.append(dugme(t("isler.iptal"), () => isIptalEt(o.is), "s-durdur", true));
  const ayrinti = document.createElement("div"); ayrinti.className = "ayrinti";
  const parcalar = [];
  if (o.son_asama_adi) parcalar.push(t("isler.son_asama", { ad: cevir("asama", o.son_asama, o.son_asama_adi) }));
  if (sorunluMu) parcalar.push(t("isler.kesildigi_yer", { ad: cevir("asama", o.basarisiz_asama, o.basarisiz_asama_adi) || "-" }) + (o.hata ? " · " + o.hata : ""));
  if (sorunlu && !devamVar) parcalar.push(t("isler.checkpoint_yok_kisa"));
  if (o.bitti || o.eklendi) parcalar.push((o.bitti || o.eklendi));
  ayrinti.textContent = parcalar.join(" · ");
  kutu.append(no, durum, ad, dugmeler, ayrinti);
  return kutu;
}

async function islerYukle() {
  try {
    const [s, h] = await Promise.all([api("/api/sorunlu"), api("/api/isler" + ($("arsiv-goster").checked ? "?hepsi=1" : ""))]);
    const bos = (metin) => { const p = document.createElement("p"); p.className = "not"; p.textContent = metin; return p; };
    $("sorunlu-liste").replaceChildren(...(s.isler.length ? s.isler.map((o) => isSatiri(o, true)) : [bos(t("isler.sorunlu_yok"))]));
    $("is-listesi").replaceChildren(...(h.isler.length ? h.isler.map((o) => isSatiri(o, false)) : [bos(t("isler.is_yok"))]));
  } catch (e) { hataGoster(e.message); }
}
$("isler-yenile").addEventListener("click", islerYukle);
$("arsiv-goster").addEventListener("change", islerYukle);
document.querySelector('.sekme[data-sekme="isler"]').addEventListener("click", islerYukle);

// --- oynatıcı: sabit kutu, köşe tam ekran düğmesi, altta saklanan kontrol çubuğu, orijinal / dublajlı geçişi ----------
const video = $("video");
const kutuOynatici = $("oynatici");
const oynatici = { orijinal: "", dublaj: "", cumleler: [], izAdresi: "" };
let izlenenIs = null;       // oynatıcının gösterdiği işin numarası (iş sürerken ve bitince hep o işin videosu)
let baglananAnahtar = "";   // aynı video ikinci kez yüklenmesin
let yerelVideo = false;     // bu sayfada seçilen dosya (blob) oynuyor: sunucudaki kopyasıyla değiştirilmez
const YEREL_SES = "dubworld.ses";

function srtCoz(metin) {  // SRT → [{bas, son, yazi}] (saniye)
  const sn = (z) => { const [s, d, r] = z.replace(",", ".").split(":"); return (+s) * 3600 + (+d) * 60 + parseFloat(r); };
  return metin.replace(/\r/g, "").split(/\n\s*\n/).map((blok) => {
    const satirlar = blok.trim().split("\n");
    const i = satirlar.findIndex((x) => x.includes("-->"));
    if (i < 0) return null;
    const [a, b] = satirlar[i].split("-->").map((x) => x.trim().split(" ")[0]);
    return { bas: sn(a), son: sn(b), yazi: satirlar.slice(i + 1).join(" ") };
  }).filter(Boolean);
}
function vttYap(cumleler) {  // line:-4 → altyazı kontrol çubuğunun üstünde kalır
  const z = (x) => new Date(x * 1000).toISOString().slice(11, 23);
  return "WEBVTT\n\n" + cumleler.map((c) => `${z(c.bas)} --> ${z(c.son)} line:-4\n${c.yazi}`).join("\n\n") + "\n";
}
// Alanın üç hali: "bos" (yükleme alanı), "video", "mesaj" (kaynak gösterilemiyor: kısa açıklama).
function oynaticiHali(hal) {
  $("yeniden-oynat").hidden = true;
  $("dosya-alani").hidden = hal !== "bos";
  video.hidden = hal !== "video";
  $("kontroller").hidden = hal !== "video";
  $("video-mesaj").hidden = hal !== "mesaj";
  $("baska-video").hidden = hal === "bos";
  if (hal !== "video") { beklemeGoster(false); $("yeniden-oynat").hidden = true; }
  tamEkranDugmeleri();
  kontrolGoster();
}
function videoMesaji(anahtar) {
  video.pause(); video.removeAttribute("src"); video.load();
  oynatici.orijinal = oynatici.dublaj = "";
  yaz($("video-mesaj"), anahtar);
  oynaticiHali("mesaj");
}
function surumSec(ad) {
  const adres = ad === "orijinal" ? oynatici.orijinal : oynatici.dublaj;
  if (!adres) return;
  const an = video.currentTime, oynuyor = !video.paused;
  video.src = adres;
  video.addEventListener("loadedmetadata", () => { video.currentTime = Math.min(an, video.duration || an); if (oynuyor) video.play(); }, { once: true });
  $("surum-orijinal").classList.toggle("secili", ad === "orijinal");
  $("surum-dublaj").classList.toggle("secili", ad === "dublaj");
  $("surum-orijinal").setAttribute("aria-pressed", String(ad === "orijinal"));
  $("surum-dublaj").setAttribute("aria-pressed", String(ad === "dublaj"));
}
async function oynaticiYukle(v) {
  if (v.orijinal !== undefined) oynatici.orijinal = v.orijinal;
  oynatici.dublaj = v.dublaj || "";
  oynatici.cumleler = [];
  yerelVideo = !!v.yerel;
  video.querySelectorAll("track").forEach((x) => x.remove());
  if (oynatici.izAdresi) { URL.revokeObjectURL(oynatici.izAdresi); oynatici.izAdresi = ""; }
  oynaticiHali("video");
  $("surum").hidden = !(oynatici.orijinal && oynatici.dublaj);
  video.src = oynatici.dublaj || oynatici.orijinal;
  surumSec(oynatici.dublaj ? "dublaj" : "orijinal");
  $("altyazi").hidden = true;
  if (v.srt) {
    try {
      const yanit = await fetch(v.srt);
      oynatici.cumleler = srtCoz(await yanit.text());
      oynatici.izAdresi = URL.createObjectURL(new Blob([vttYap(oynatici.cumleler)], { type: "text/vtt" }));
      const iz = document.createElement("track");
      iz.kind = "subtitles"; iz.src = oynatici.izAdresi; iz.srclang = DIL; iz.default = true;
      video.appendChild(iz);
      $("altyazi").hidden = false;
      kutuOynatici.classList.add("altyazi-acik");
    } catch (_) { /* altyazı yoksa video yine oynar */ }
  }
  isaretleriCiz();
}

// Bir işin videosunu alana bağlar: bitmişse sonuç (orijinal de varsa geçiş), sürüyorsa kaynak; sunulamıyorsa kısa mesaj.
function isBagla(o, zorla) {
  if (!o) return;
  const anahtar = [o.is, o.orijinal, o.video].join("|");
  if (!zorla && anahtar === baglananAnahtar) return;
  if (!zorla && yerelVideo && izlenenIs === o.is && !o.video) return;  // yeni yüklenen dosya zaten oynuyor
  baglananAnahtar = anahtar; izlenenIs = o.is;
  if (o.video) oynaticiYukle({ orijinal: o.orijinal ? dosyaAdresi(o.orijinal) : "", dublaj: dosyaAdresi(o.video), srt: o.srt ? dosyaAdresi(o.srt) : "" });
  else if (o.orijinal) oynaticiYukle({ orijinal: dosyaAdresi(o.orijinal) });
  else videoMesaji(/:\/\//.test(o.kaynak_yolu || "") ? "oynatici.baglanti_bekle" : "oynatici.kaynak_yok");
}

function isaretleriCiz() {
  const uzunluk = video.duration;
  $("isaretler").replaceChildren(...(uzunluk ? oynatici.cumleler.map((c) => {
    const o = document.createElement("span"); o.style.left = (100 * c.bas / uzunluk) + "%"; return o; }) : []));
}
function sureCiz() {
  const u = video.duration || 0;
  $("sure").textContent = saatYaz(video.currentTime) + " / " + saatYaz(u);
  if (!konumTutuluyor) $("konum").value = u ? Math.round(1000 * video.currentTime / u) : 0;
  suanSatiriIsaretle();
}
let konumTutuluyor = false;

// Kontrol çubuğu: oynarken ~3 sn hareketsizlikte (imleçle birlikte) saklanır; hareket, dokunma, tuş, odak, duraklatma geri getirir.
let gizleSayaci = null;
function kontrolGoster() {
  kutuOynatici.classList.remove("kontrol-gizli");
  clearTimeout(gizleSayaci);
  if (!video.hidden && !video.paused && !video.ended) gizleSayaci = setTimeout(kontrolGizleDene, 3000);
}
function kontrolGizleDene() {
  const k = $("kontroller"), a = document.activeElement;
  const odakta = k.contains(a) && a.matches(":focus-visible");
  if (video.paused || video.ended || k.matches(":hover") || odakta) { kontrolGoster(); return; }
  kutuOynatici.classList.add("kontrol-gizli");
}
let sonImlec = [0, 0], ilkDokunusGizliydi = false;
kutuOynatici.addEventListener("pointermove", (e) => {
  if (Math.abs(e.clientX - sonImlec[0]) + Math.abs(e.clientY - sonImlec[1]) < 3) return;  // yerleşim değişince gelen sahte hareket sayılmaz
  sonImlec = [e.clientX, e.clientY]; kontrolGoster();
});
kutuOynatici.addEventListener("pointerdown", (e) => {
  ilkDokunusGizliydi = e.pointerType === "touch" && kutuOynatici.classList.contains("kontrol-gizli");
  kontrolGoster();
});
kutuOynatici.addEventListener("keydown", kontrolGoster);
kutuOynatici.addEventListener("focusin", kontrolGoster);

function beklemeGoster(ac) { $("bekleme").hidden = !ac; }
function oynatDuraklat() { if (video.paused) video.play(); else video.pause(); }
function tamEkranDegistir() { if (document.fullscreenElement) document.exitFullscreen(); else kutuOynatici.requestFullscreen().catch(() => {}); }
function tamEkranDugmeleri() {
  const tam = document.fullscreenElement === kutuOynatici;
  $("tam-ekran").hidden = video.hidden || tam;
  $("tam-cik").hidden = !tam;
}
document.addEventListener("fullscreenchange", () => { tamEkranDugmeleri(); kontrolGoster(); });
function sesiHatirla() { try { localStorage.setItem(YEREL_SES, JSON.stringify({ v: video.volume, m: video.muted })); } catch (_) { /* gizli pencere */ } }
function sesiAnimsa() {
  try {
    const k = JSON.parse(localStorage.getItem(YEREL_SES) || "null");
    if (k && typeof k.v === "number") { video.volume = Math.min(1, Math.max(0, k.v)); video.muted = !!k.m; }
  } catch (_) { /* kayıt yok */ }
}

video.addEventListener("loadedmetadata", () => { sureCiz(); isaretleriCiz(); beklemeGoster(false); });
video.addEventListener("loadeddata", () => beklemeGoster(false));
video.addEventListener("loadstart", () => { if (video.currentSrc) beklemeGoster(true); });
video.addEventListener("waiting", () => beklemeGoster(true));
video.addEventListener("seeking", () => { if (video.readyState < 3) beklemeGoster(true); });
["playing", "canplay", "seeked", "error"].forEach((o) => video.addEventListener(o, () => beklemeGoster(false)));
video.addEventListener("timeupdate", sureCiz);
video.addEventListener("play", () => { kutuOynatici.classList.add("oynatiyor"); baslikYaz($("oynat"), "oynatici.duraklat"); $("yeniden-oynat").hidden = true; kontrolGoster(); });
video.addEventListener("pause", () => { kutuOynatici.classList.remove("oynatiyor"); baslikYaz($("oynat"), "oynatici.oynat"); kontrolGoster(); });
video.addEventListener("ended", () => { kutuOynatici.classList.remove("oynatiyor"); $("yeniden-oynat").hidden = false; kontrolGoster(); });
video.addEventListener("volumechange", () => {
  kutuOynatici.classList.toggle("sessizde", video.muted || video.volume === 0);
  baslikYaz($("sessiz"), video.muted ? "oynatici.sesi_ac" : "oynatici.sessiz");
  $("ses").value = video.muted ? 0 : video.volume;
  sesiHatirla();
});
video.addEventListener("error", () => { if (video.getAttribute("src")) hataGoster(t("oynatici.hazir_degil")); });
video.addEventListener("click", () => {
  if (ilkDokunusGizliydi) { ilkDokunusGizliydi = false; return; }  // dokunmatik: ilk dokunuş yalnız kontrolleri gösterir
  oynatDuraklat();
});
video.addEventListener("dblclick", tamEkranDegistir);
$("yeniden-oynat").addEventListener("click", () => { video.currentTime = 0; video.play(); });
$("oynat").addEventListener("click", oynatDuraklat);
$("geri").addEventListener("click", () => { video.currentTime = Math.max(0, video.currentTime - 5); });
$("ileri").addEventListener("click", () => { video.currentTime = Math.min(video.duration || 0, video.currentTime + 5); });
$("sessiz").addEventListener("click", () => { video.muted = !video.muted; });
$("ses").addEventListener("input", (e) => { video.volume = +e.target.value; video.muted = +e.target.value === 0; });
$("hiz").addEventListener("change", (e) => { video.playbackRate = +e.target.value; });
$("surum-orijinal").addEventListener("click", () => surumSec("orijinal"));
$("surum-dublaj").addEventListener("click", () => surumSec("dublaj"));
$("altyazi").addEventListener("click", () => {
  const iz = video.textTracks[0];
  if (!iz) return;
  iz.mode = iz.mode === "showing" ? "hidden" : "showing";
  kutuOynatici.classList.toggle("altyazi-acik", iz.mode === "showing");
});
$("tam-ekran").addEventListener("click", tamEkranDegistir);
$("tam-cik").addEventListener("click", tamEkranDegistir);
const konum = $("konum");
konum.addEventListener("pointerdown", () => { konumTutuluyor = true; });
konum.addEventListener("change", () => { konumTutuluyor = false; });
konum.addEventListener("input", () => { if (video.duration) video.currentTime = video.duration * konum.value / 1000; });
konum.addEventListener("mousemove", (e) => {  // üstüne gelince o andaki cümle
  const kutu = konum.getBoundingClientRect();
  const oran = Math.min(1, Math.max(0, (e.clientX - kutu.left) / kutu.width));
  const an = oran * (video.duration || 0);
  const c = oynatici.cumleler.find((x) => an >= x.bas && an <= x.son);
  const balon = $("balon");
  balon.hidden = !video.duration;
  balon.textContent = saatYaz(an) + (c ? " · " + c.yazi : "");
  balon.style.left = (oran * 100) + "%";
});
konum.addEventListener("mouseleave", () => { $("balon").hidden = true; });
sesiAnimsa();

// Klavye: yazı alanındayken çalışmaz. Oynatıcı odaktayken, tam ekranda ya da hiçbir şey odakta değilken geçerlidir.
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (!$("gelismis").hidden) { cekmece(false); return; }
    if (!$("inceleme").hidden && $("inceleme").contains(e.target) && !document.querySelector("dialog[open]")) { incelemeKapat(); return; }
  }
  const hedef = e.target;
  if (e.ctrlKey || e.altKey || e.metaKey || /^(INPUT|SELECT|TEXTAREA)$/.test(hedef.tagName) || hedef.isContentEditable) return;
  if (document.querySelector("dialog[open]")) return;
  if (video.hidden || !$("onerilen").classList.contains("etkin") || !$("gelismis").hidden) return;
  if (!(document.fullscreenElement || kutuOynatici.contains(hedef) || hedef === document.body)) return;
  const k = e.key.toLowerCase();
  const islem = {
    " ": oynatDuraklat, "k": oynatDuraklat,
    "arrowleft": () => { video.currentTime = Math.max(0, video.currentTime - 5); },
    "arrowright": () => { video.currentTime = Math.min(video.duration || 0, video.currentTime + 5); },
    "arrowup": () => { video.muted = false; video.volume = Math.min(1, video.volume + 0.1); },
    "arrowdown": () => { video.volume = Math.max(0, video.volume - 0.1); },
    "m": () => { video.muted = !video.muted; }, "f": tamEkranDegistir, "c": () => $("altyazi").click(),
  }[k];
  if (islem && !(hedef.tagName === "BUTTON" && k === " ")) { e.preventDefault(); kontrolGoster(); islem(); }
});

// --- seslendirmeden önce gözden geçirme: yan panel (dar ekranda alt sayfa), otomatik kayıt, bul-değiştir -------------
const SAAT_SINIRI = 15;          // karakter / saniye: üstü "süresine sığmayabilir"
const OTO_KAYIT_MS = 1500;
const METIN_ENFAZLA = 2000;
const inc = { no: 0, satirlar: [], kilit: false, tekSatir: true, kayit: "", kayitSinif: "", sayac: null, suren: null, tekrar: false,
  yuklenenNo: 0, yuklendi: false, hata: "" };
const incelemeAcilanlar = new Set();   // paneli bir kez açılan işler (kullanıcı kapattıysa kendiliğinden yeniden açılmaz)
const incelemeBitenler = new Set();    // "Dublaja devam et" denilen işler
let incelemeIs = null;
const darEkran = window.matchMedia("(max-width: 699px)");

// Metin temizliği: baştaki/sondaki boşluk, art arda boşluk, tam genişlik rakam; denetim karakterleri sunucuya hiç gitmez.
const DENETIM = /[\u0000-\u001f\u007f]/g;
function metinTemizle(m) {
  return m.replace(DENETIM, " ").replace(/[０-９]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xFEE0)).replace(/\s+/g, " ").trim();
}
function zamanYaz(sn) { const s = Math.floor(sn); return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0"); }
function sayiYaz(x) { return x.toLocaleString(DIL, { maximumFractionDigits: 1 }); }
function sureKisa(sn) {
  const dk = Math.floor(sn / 60), s = Math.round(sn % 60);
  return dk ? `${dk} ${t("birim.dk")} ${s} ${t("birim.sn")}` : `${Math.max(1, s)} ${t("birim.sn")}`;
}
function otoBuyut(ta) { ta.style.height = "auto"; ta.style.height = Math.max(44, ta.scrollHeight + 2) + "px"; }
// Çok alan birden (Hepsini değiştir, geri al, liste açılışı): önce hepsi sıfırlanır, sonra tek okumayla ölçülür, sonra tek yazmayla verilir;
// ara hal çizilmez, satırlar iki kez zıplamaz (yerleşim kayması).
function otoBuyutToplu(alanlar) {
  alanlar.forEach((ta) => { ta.style.height = "auto"; });
  const boylar = alanlar.map((ta) => Math.max(44, ta.scrollHeight + 2));
  alanlar.forEach((ta, i) => { ta.style.height = boylar[i] + "px"; });
}
function incelemeIsYaz() {
  const yazi = $("inceleme-is-yazi");
  const metin = !incelemeIs ? "" : (inc.yuklendi && inc.no === incelemeIs ? t("inceleme.is_satiri", { no: incelemeIs, adet: inc.satirlar.length }) : t("inceleme.yukleniyor"));
  yazi.textContent = metin; yazi.title = metin;
}

// -- durum satırı (panelin altında, yeri ayrılmış): neden pasif, kaydediliyor, kaydedildi, hata
function incelemeDurumYaz() {
  const o = $("inceleme-durum");
  let metin = "", sinif = "";
  if (inc.kilit) { metin = t("inceleme.kilitli"); sinif = "uyari-mesaji"; }
  else if (inc.hata) { metin = inc.hata; sinif = "hata-mesaji"; }
  else if (bosSatir()) { metin = t("inceleme.neden_bos"); sinif = "uyari-mesaji"; }
  else if (inc.kayit) { metin = inc.kayit === "kaydediliyor" ? t("inceleme.kaydediliyor") : t("inceleme.kaydedildi"); sinif = inc.kayit === "kaydedildi" ? "tamam" : ""; }
  o.textContent = metin;
  o.className = "inceleme-durum " + sinif;
  o.setAttribute("role", sinif === "hata-mesaji" ? "alert" : "status");
  const pasif = inc.kilit || !!bosSatir();
  document.querySelectorAll(".devam-dugmesi").forEach((b) => { b.disabled = pasif; });
}
const bosSatir = () => inc.satirlar.find((s) => s.gecersiz);

// -- bir satır
function satirDurumu(s) {
  const o = metinTemizle(s.oge.orj.value), c = metinTemizle(s.oge.cev.value);
  const orjDegisti = o !== s.orj0, cevDegisti = c !== s.cev0;
  return orjDegisti && !cevDegisti ? "eskidi" : (orjDegisti || cevDegisti ? "duzenlendi" : "tamam");
}
function satirGuncelle(s) {
  const durum = satirDurumu(s), cevir = metinTemizle(s.oge.cev.value);
  const isaret = s.oge.isaret;
  isaret.className = "isaret " + durum;
  const IS = { tamam: ["s-tamam", "inceleme.durum_tamam"], eskidi: ["s-uyari", "inceleme.durum_eskidi"], duzenlendi: ["s-kalem", "inceleme.durum_duzenlendi"] }[durum];
  isaret.replaceChildren(simgeOlustur(IS[0]), document.createTextNode(t(IS[1])));
  s.oge.bilgi.textContent = t("inceleme.satir_bilgi", { harf: s.oge.cev.value.length, sure: sayiYaz(s.sure_sn) });
  const uzun = s.sure_sn > 0.3 && cevir.length / s.sure_sn > SAAT_SINIRI;
  const m = s.oge.mesaj;
  m.className = "mesaj";
  if (s.gecersiz) { m.textContent = t("inceleme.bos_mesaj"); m.classList.add("hata-mesaji"); }
  else if (uzun) m.textContent = t("inceleme.uzun");
  else if (durum === "eskidi") m.textContent = t("inceleme.eskidi_yardim");
  else m.textContent = "";
  s.oge.orj.classList.toggle("gecersiz", !!s.gecersiz && !metinTemizle(s.oge.orj.value));
  s.oge.cev.classList.toggle("gecersiz", !!s.gecersiz && !cevir);
}
function alanKur(s, tur, etiketAnahtar, deger) {
  const et = document.createElement("label");
  const yazi = document.createElement("span"); yaz(yazi, etiketAnahtar);
  const ta = document.createElement("textarea");
  ta.value = deger; ta.rows = 1; ta.maxLength = METIN_ENFAZLA; ta.spellcheck = true; ta.enterKeyHint = "done";
  ta.id = `inc-${tur}-${s.no}`;
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); ta.blur(); } });
  ta.addEventListener("input", () => {
    if (/[\u0000-\u001f\u007f]/.test(ta.value)) ta.value = ta.value.replace(DENETIM, " ");  // yapıştırılan satır sonları vb.
    if (s.gecersiz && metinTemizle(ta.value)) { s.gecersiz = false; incelemeDurumYaz(); }
    otoBuyut(ta); satirGuncelle(s); kayitPlanla();
  });
  ta.addEventListener("blur", () => {  // alandan çıkınca: sessiz düzeltme + doğrulama (yazarken değil)
    const temiz = metinTemizle(ta.value);
    if (temiz !== ta.value) { ta.value = temiz; otoBuyut(ta); }
    const taban = tur === "orj" ? s.orj0 : s.cev0;
    s.gecersiz = !temiz && !!taban;
    satirGuncelle(s); incelemeDurumYaz(); kayitPlanla();
  });
  et.append(yazi, ta);
  return [et, ta];
}
function satirKur(s) {
  const kok = document.createElement("article");
  kok.className = "irow"; kok.dataset.no = s.no;
  const ust = document.createElement("div"); ust.className = "irow-ust";
  const zaman = document.createElement("button");
  zaman.type = "button"; zaman.className = "zaman"; zaman.textContent = zamanYaz(s.bas);
  const zamanBaslik = () => { const m = t("inceleme.satir_git", { zaman: zamanYaz(s.bas) }); zaman.title = m; zaman.setAttribute("aria-label", m); };
  zamanBaslik(); s.zamanBaslik = zamanBaslik;
  zaman.addEventListener("click", () => { if (!video.hidden) { video.currentTime = s.bas; kontrolGoster(); } });
  const isaret = document.createElement("span");
  const bilgi = document.createElement("span"); bilgi.className = "bilgi";
  ust.append(zaman, isaret, bilgi);
  const [orjEt, orj] = alanKur(s, "orj", "inceleme.orijinal", s.orijinal);
  const [cevEt, cev] = alanKur(s, "cev", "inceleme.ceviri", s.ceviri);
  const yeniden = document.createElement("button");
  yeniden.type = "button"; yeniden.className = "yeniden";
  yeniden.append(simgeOlustur("s-yenile")); const yy = document.createElement("span"); yaz(yy, "inceleme.yeniden_cevir"); yeniden.append(yy);
  yeniden.addEventListener("click", () => satirYenidenCevir(s));
  yeniden.hidden = !inc.tekSatir;
  const mesaj = document.createElement("p"); mesaj.className = "mesaj"; mesaj.setAttribute("aria-live", "polite");
  kok.append(ust, orjEt, cevEt, yeniden, mesaj);
  s.oge = { kok, orj, cev, isaret, bilgi, mesaj, yeniden, yy };
  s.orj0 = s.kayitliO = metinTemizle(s.orijinal); s.cev0 = s.kayitliC = metinTemizle(s.ceviri);
  return kok;
}
function listeyiAc() { otoBuyutToplu(inc.satirlar.flatMap((s) => [s.oge.orj, s.oge.cev])); inc.satirlar.forEach(satirGuncelle); }

// -- yükleme (son boyutunda iskelet satırlar) ve çizim
async function incelemeYukle(no) {
  if (inc.yuklenenNo === no && inc.yuklendi) return true;
  inc.no = no; inc.yuklendi = false; inc.hata = ""; inc.kilit = false; inc.satirlar = []; inc.kayit = "";
  const liste = $("inceleme-liste");
  liste.replaceChildren(...Array.from({ length: 5 }, () => { const d = document.createElement("div"); d.className = "iskelet"; d.setAttribute("aria-hidden", "true"); return d; }));
  $("inceleme-durum").textContent = t("inceleme.yukleniyor");
  try {
    const v = await api("/api/duzenle?is=" + no);
    if (no !== inc.no) return false;
    inc.satirlar = v.satirlar.map((s) => Object.assign({ gecersiz: false }, s));
    inc.kilit = v.durum !== "inceleme_bekliyor";
    liste.replaceChildren(...inc.satirlar.map(satirKur));
    inc.yuklenenNo = no; inc.yuklendi = true;
    if (!$("inceleme").hidden) listeyiAc();
    inc.satirlar.forEach((s) => { if (inc.kilit) { s.oge.orj.readOnly = s.oge.cev.readOnly = true; s.oge.yeniden.hidden = true; } });
    bulSay(); incelemeDurumYaz(); incelemeIsYaz();
    return true;
  } catch (e) {
    liste.replaceChildren();
    inc.hata = t("inceleme.yuklenemedi", { neden: e.message });
    incelemeDurumYaz();
    return false;
  }
}

// -- otomatik kayıt: son düzenlemeden 1,5 sn sonra; yalnız değişen ve boş olmayan satırlar gider
function kayitPlanla() { clearTimeout(inc.sayac); inc.sayac = setTimeout(incelemeKaydet, OTO_KAYIT_MS); }
function degisenler() {
  const dizi = [];
  inc.satirlar.forEach((s) => {
    const o = metinTemizle(s.oge.orj.value), c = metinTemizle(s.oge.cev.value);
    const p = { no: s.no };
    if (o && o !== s.kayitliO) p.orijinal = o;
    if (c && c !== s.kayitliC) p.ceviri = c;
    if (p.orijinal !== undefined || p.ceviri !== undefined) dizi.push([s, p]);
  });
  return dizi;
}
function incelemeKaydet() {
  clearTimeout(inc.sayac);
  if (inc.suren) { inc.tekrar = true; return inc.suren; }  // süren kayıt bitince bir tur daha
  inc.suren = kaydetTurlari().finally(() => { inc.suren = null; });
  return inc.suren;
}
async function kaydetTurlari() {
  let tamam = true;
  do {
    inc.tekrar = false;
    if (inc.kilit || !inc.yuklendi) return true;
    const dizi = degisenler();
    if (!dizi.length) return tamam;
    inc.hata = ""; inc.kayit = "kaydediliyor"; incelemeDurumYaz();
    try {
      await api("/api/duzenle", { is: inc.no, satirlar: dizi.map(([, p]) => p) });
      dizi.forEach(([s, p]) => { if (p.orijinal !== undefined) s.kayitliO = p.orijinal; if (p.ceviri !== undefined) s.kayitliC = p.ceviri; });
      inc.kayit = "kaydedildi"; tamam = true;
    } catch (e) {
      inc.kayit = ""; tamam = false;
      if (e.veri && e.veri.anahtar === "is_inceleme_degil") { inc.kilit = true; inc.satirlar.forEach((s) => { s.oge.orj.readOnly = s.oge.cev.readOnly = true; }); }
      else inc.hata = t("inceleme.kaydedilemedi", { neden: e.message });
      inc.tekrar = false;
    }
    incelemeDurumYaz();
  } while (inc.tekrar);
  return tamam;
}

// -- tek satırı yeniden çevir (sunucu desteklemiyorsa düğmeler kalkar)
async function satirYenidenCevir(s) {
  if (s.mesgul || inc.kilit) return;
  const metin = metinTemizle(s.oge.orj.value);
  if (!metin) { s.gecersiz = true; satirGuncelle(s); incelemeDurumYaz(); s.oge.orj.focus(); return; }
  s.mesgul = true; s.oge.kok.classList.add("mesgul"); s.oge.yeniden.disabled = true; yaz(s.oge.yy, "inceleme.cevriliyor");
  try {
    const v = await api("/api/cevir_satir", { is: inc.no, no: s.no, metin });
    s.oge.cev.value = metinTemizle(v.ceviri || ""); otoBuyut(s.oge.cev); s.gecersiz = !s.oge.cev.value && !!s.cev0;
    satirGuncelle(s); kayitPlanla(); incelemeDurumYaz();
  } catch (e) {
    if (e.veri && e.veri.anahtar === "tek_satir_desteklenmiyor") {
      inc.tekSatir = false;
      inc.satirlar.forEach((x) => { x.oge.yeniden.hidden = true; });
      s.oge.mesaj.className = "mesaj"; s.oge.mesaj.textContent = t("inceleme.tek_satir_yok");
    } else {
      s.oge.mesaj.className = "mesaj hata-mesaji"; s.oge.mesaj.textContent = t("inceleme.cevir_basarisiz", { neden: e.message });
    }
  }
  s.mesgul = false; s.oge.kok.classList.remove("mesgul"); s.oge.yeniden.disabled = false; yaz(s.oge.yy, "inceleme.yeniden_cevir");
}

// -- bul ve değiştir (yalnız çeviri metni; ses çeviriyi okur)
function kacis(m) { return m.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
function bulRegex() { const q = $("bul-ara").value.replace(DENETIM, " "); return q.trim() ? new RegExp(kacis(q.trim()), "giu") : null; }
function bulSay() {
  const re = bulRegex(), sayi = $("bul-sayi"), dugme = $("bul-degistir");
  if (!re) { sayi.textContent = t("inceleme.bul_bos"); dugme.disabled = true; return; }
  let adet = 0, satir = 0;
  inc.satirlar.forEach((s) => { const n = (s.oge.cev.value.match(re) || []).length; adet += n; if (n) satir++; });
  sayi.textContent = adet ? t("inceleme.bul_var", { adet, satir }) + ($("bul-yeni").value.trim() ? "" : " " + t("inceleme.bul_yerine_bos")) : t("inceleme.bul_yok");
  dugme.disabled = !adet || inc.kilit;
}
function hepsiniDegistir() {
  const re = bulRegex();
  if (!re || inc.kilit) return;
  const yeni = $("bul-yeni").value.replace(DENETIM, " ").trim();
  const onceki = [];
  let adet = 0;
  inc.satirlar.forEach((s) => {
    const eski = s.oge.cev.value, n = (eski.match(re) || []).length;
    if (!n) return;
    const sonuc = metinTemizle(eski.replace(re, () => yeni));
    if (!sonuc) return;  // satırı tamamen boşaltacak değişiklik uygulanmaz
    onceki.push([s, eski]); adet += n;
    s.oge.cev.value = sonuc; satirGuncelle(s);
  });
  if (!adet) return;
  otoBuyutToplu(onceki.map(([s]) => s.oge.cev));
  kayitPlanla(); bulSay();
  bildir(t("inceleme.degisti", { adet }), { geriAl: () => {
    onceki.forEach(([s, eski]) => { s.oge.cev.value = eski; satirGuncelle(s); });
    otoBuyutToplu(onceki.map(([s]) => s.oge.cev));
    kayitPlanla(); bulSay();
  } });
}
$("bul-ara").addEventListener("input", bulSay);
$("bul-yeni").addEventListener("input", bulSay);
["bul-ara", "bul-yeni"].forEach((k) => $(k).addEventListener("blur", (e) => { e.target.value = e.target.value.replace(DENETIM, " ").trim().replace(/\s+/g, " "); bulSay(); }));
$("bul-degistir").addEventListener("click", hepsiniDegistir);

// -- panel açma / kapama
function incelemeSeridiGoster(ac) { $("inceleme-seridi").hidden = !ac; }
async function incelemePaneliAc(no, odakla) {
  const panel = $("inceleme");
  incelemeIs = no;
  incelemeIsYaz();
  panel.hidden = false;
  $("yan").classList.add("panel-acik");
  $("inceleme-perde").hidden = !darEkran.matches;
  if (odakla && darEkran.matches) $("inceleme-kapat").focus();
  const tamam = await incelemeYukle(no);
  if (tamam) listeyiAc();
}
function incelemeKapat() {
  incelemeKaydet();
  $("inceleme").hidden = true; $("yan").classList.remove("panel-acik"); $("inceleme-perde").hidden = true;
  const ac = $("inceleme-ac"); if (incelemeIs && !$("inceleme-seridi").hidden && ac.isConnected) ac.focus({ preventScroll: true });
}
function incelemeBaslat(no, { otomatik } = {}) {
  if (incelemeBitenler.has(no)) return;
  incelemeIs = no;
  incelemeSeridiGoster(true);
  if (otomatik && incelemeAcilanlar.has(no)) return;  // kullanıcı kapattıysa kendiliğinden açılmaz
  incelemeAcilanlar.add(no);
  incelemePaneliAc(no, !otomatik);
}
function incelemeBitir(no) {
  incelemeBitenler.add(no);
  if (incelemeIs === no) incelemeIs = null;
  incelemeSeridiGoster(false);
  $("inceleme").hidden = true; $("yan").classList.remove("panel-acik"); $("inceleme-perde").hidden = true;
}
$("inceleme-kapat").addEventListener("click", incelemeKapat);
$("inceleme-perde").addEventListener("click", incelemeKapat);
$("inceleme-ac").addEventListener("click", () => { if (incelemeIs) incelemePaneliAc(incelemeIs, true); });
darEkran.addEventListener("change", () => { if (!$("inceleme").hidden) $("inceleme-perde").hidden = !darEkran.matches; });
function incelemeDiliYenile() { inc.satirlar.forEach((s) => { if (s.oge) { s.zamanBaslik(); satirGuncelle(s); } }); bulSay(); incelemeDurumYaz(); incelemeIsYaz(); }

// -- "Dublaja devam et": önce bekleyen kayıt, sonra tek onay (bedel özeti), sonra sunucuya
async function incelemeDevam() {
  const no = incelemeIs;
  if (!no || inc.kilit) return;
  if (!(await incelemeYukle(no))) return;
  inc.satirlar.forEach((s) => {  // alandan çıkmadan basıldıysa da boş satır yakalanır
    const bos = !metinTemizle(s.oge.orj.value) && !!s.orj0 || !metinTemizle(s.oge.cev.value) && !!s.cev0;
    if (bos) { s.gecersiz = true; satirGuncelle(s); }
  });
  if (bosSatir()) {
    incelemeDurumYaz();
    if ($("inceleme").hidden) incelemePaneliAc(no, true);
    bosSatir().oge.cev.focus();
    return;
  }
  if (!(await incelemeKaydet())) return;
  const adet = inc.satirlar.length, toplam = inc.satirlar.reduce((a, s) => a + (s.sure_sn || 0), 0);
  const metin = toplam >= 1 ? t("onay.devam_metin", { adet, sure: sureKisa(toplam) }) : t("onay.devam_metin_az", { adet });
  const evet = await onayIste({ baslik: t("onay.devam_baslik"), metin, tamam: t("inceleme.devam"), tehlike: false });
  if (!evet) return;
  try {
    await api("/api/devam", { is: no, asama: "tts_ve_segment_sesleri" });
  } catch (e) {
    if (e.veri && e.veri.anahtar === "is_inceleme_degil") { inc.kilit = true; incelemeDurumYaz(); }
    else { inc.hata = e.message; incelemeDurumYaz(); }
    return;
  }
  incelemeBitir(no);
  bildir(t("inceleme.devam_basladi"));
  $("sonuc").hidden = true; gosterilenSonuc = "";
  izle(); islerYukle();
}
document.querySelectorAll(".devam-dugmesi").forEach((b) => b.addEventListener("click", incelemeDevam));

// oynatılırken o anki satır çerçevelenir (kaydırma yok: kullanıcı istemeden sayfa oynamaz)
let suanNo = null;
function suanSatiriIsaretle() {
  if ($("inceleme").hidden || !inc.yuklendi) return;
  const an = video.currentTime;
  const s = inc.satirlar.find((x) => an >= x.bas && an < x.son);
  const no = s ? s.no : null;
  if (no === suanNo) return;
  suanNo = no;
  inc.satirlar.forEach((x) => x.oge.kok.classList.toggle("suan", x.no === no));
}

// -- "Dublajda gözden geçir" kutusu ↔ Ayarlar'daki genel.gozden_gecir (tek kaynak: o alan); seçim bu tarayıcıda hatırlanır
const YEREL_GOZDEN = "dubworld.gozden_gecir";
function gozdenKutusunuBagla(ilk) {
  const kaynak = $("a_genel.gozden_gecir"), kutu = $("gozden-kutusu");
  if (!kaynak) { kutu.disabled = true; return; }
  kutu.disabled = false;
  if (ilk) {
    let hatirla = false;
    try { hatirla = localStorage.getItem(YEREL_GOZDEN) === "1"; } catch (_) { /* gizli pencere */ }
    if (hatirla !== kaynak.checked) { kaynak.checked = hatirla; kaynak.dispatchEvent(new Event("change")); }
  }
  kutu.checked = kaynak.checked;
  kaynak.addEventListener("change", () => {
    kutu.checked = kaynak.checked;
    try { localStorage.setItem(YEREL_GOZDEN, kaynak.checked ? "1" : "0"); } catch (_) { /* gizli pencere */ }
  });
}
$("gozden-kutusu").addEventListener("change", (e) => {
  const kaynak = $("a_genel.gozden_gecir");
  if (!kaynak) return;
  kaynak.checked = e.target.checked;
  kaynak.dispatchEvent(new Event("change"));
});

// -- bitiş kartı: "Başka dile dubla" aynı işin çevirisinden başlayan yeni işe kopyalar (yazıya dökme tekrarlanmaz)
let yenidenKaynak = null;
$("baska-dil").addEventListener("click", () => {
  if (!izlenenIs) return;
  yenidenKaynak = izlenenIs;
  baslatGuncelle();
  $("hedef-dil").scrollIntoView({ block: "center", behavior: hareketAz() ? "auto" : "smooth" });
  $("hedef-dil").focus({ preventScroll: true });
  bildir(t("bitti.dil_sec"));
});

// Sunucunun izlediği iş ya da (sayfa yenilendiyse / iş başka yerden başladıysa) iş deposundaki sürmekte olan iş:
// video alanı hep o işin videosunu gösterir. Sürmekte olan, bu sunucunun dışında (komut satırı) yürüyen işler 4 sn'de bir izlenir.
let sonIsler = [];
let baglaniyor = null;
let bekleyenYerel = null;  // {onceki}: sayfadan yeni başlatılan işin henüz görünmediği an
const SURUYOR = ["queued", "deferred", "preparing", "processing"];
async function islerCek() { sonIsler = (await api("/api/isler")).isler; return sonIsler; }
function isiDurumdanBagla(d) {
  if (d.is === izlenenIs || baglaniyor === d.is) return;
  if (bekleyenYerel) {  // az önce bu sayfadan başlatılan iş: seçilen dosya zaten oynuyor, sunucudaki kopyayla değiştirilmez
    if (d.is !== bekleyenYerel.onceki) { bekleyenYerel = null; izlenenIs = d.is; }
    return;
  }
  baglaniyor = d.is;
  islerCek().then((l) => isBagla(l.find((x) => x.is === d.is))).catch(() => {}).finally(() => { baglaniyor = null; });
}
async function acilistaIsiBagla() {
  try {
    const l = await islerCek();
    const o = l.find((x) => !x.arsiv && x.komut === "dubla" && (SURUYOR.includes(x.durum) || x.durum === "inceleme_bekliyor"));
    if (!o) return;
    isBagla(o);
    if (o.durum === "inceleme_bekliyor") incelemeBaslat(o.is, { otomatik: true });
    else isTakip();
  } catch (_) { /* iş yoksa yükleme alanı kalır */ }
}
let takipSayaci = null;
function isTakip() {
  clearInterval(takipSayaci);
  takipSayaci = setInterval(async () => {
    if (document.hidden || !izlenenIs) return;
    try {
      const o = (await islerCek()).find((x) => x.is === izlenenIs);
      if (!o) return;
      isBagla(o);
      if (o.durum === "inceleme_bekliyor") incelemeBaslat(o.is, { otomatik: true });
      if (o.durum === "completed" && o.video) { sonucCiz({ dubbed_video: o.video, srt_path: o.srt, run_dir: o.klasor }, [], o.orijinal); }
      if (!SURUYOR.includes(o.durum)) { clearInterval(takipSayaci); takipSayaci = null; }
    } catch (_) { /* geçici hata: bir sonraki turda */ }
  }, 4000);
}

// --- Sesler: ses kitaplığı (rızalı klon sesleri), ses ekle sayfası, Dublaj kartındaki ses seçici ---------------------
// Sunucu: /api/sesler, /api/ses_ekle, /api/ses_guncelle, /api/ses_sil, /api/xtts_lisans (ses_kitapligi.py). Ses yalnız bu bilgisayarda kalır.
const SES_KATEGORILERI = ["kadin", "erkek", "cocuk", "genc", "yasli", "diger"];
const YEREL_SES_SECIMI = "dubworld.ses_secimi";
const kit = {
  liste: [], yuklendi: false, hata: "", imza: "", ara: "", kategori: "", kartlar: new Map(), bekleyen: null, cal: null, calan: "",
  sinirlar: { en_kisa_sn: 3, en_uzun_sn: 30, ad: 60, metin: 600, dosya_mb: 50, uzantilar: [".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".webm"] },
  voxcpm2: { kurulu: true }, xtts: { kurulu: false, lisans_onayli: false },
};
let sesSecimi = "";    // "" = Otomatik; "kitaplik/<kimlik>" = VoxCPM2 ile; "xtts/<kimlik>" = XTTS ile
let sesOnceki = null;  // Otomatik'e dönünce geri yazılacak motor / ses değerleri
try {
  const k = JSON.parse(localStorage.getItem(YEREL_SES_SECIMI) || "null");
  if (k && typeof k.secim === "string") { sesSecimi = k.secim; sesOnceki = k.once || null; }
} catch (_) { /* kayıt yok */ }
function sesSecimiKaydet() { try { localStorage.setItem(YEREL_SES_SECIMI, JSON.stringify({ secim: sesSecimi, once: sesOnceki })); } catch (_) { /* gizli pencere */ } }

const hataMetni = (e) => (e.veri && e.veri.anahtar && ("sesler.hata." + e.veri.anahtar) in SOZLUK)
  ? cevir("sesler.hata", e.veri.anahtar) : t("sesler.hata.genel", { neden: e.message });
function tarihYaz(iso) { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleDateString(DIL, { day: "numeric", month: "short", year: "numeric" }); }
function etiketle(dugme, metin) { dugme.title = metin; dugme.setAttribute("aria-label", metin); }
function ogeKur(etiket, sinif, metin) { const o = document.createElement(etiket); if (sinif) o.className = sinif; if (metin !== undefined) o.textContent = metin; return o; }
function dugmeKur(sinif, simge, metin) {
  const b = ogeKur("button", sinif); b.type = "button";
  if (simge) b.append(simgeOlustur(simge));
  if (metin !== undefined) b.append(ogeKur("span", "", metin));
  return b;
}
function simgeDegistir(dugme, kimlik) { const u = dugme.querySelector("use"); if (u) u.setAttribute("href", "#" + kimlik); }
const sesIdsi = (s) => "kitaplik/" + s.kimlik;

// -- Dublaj ayarlarına yazma (Ayarlar'daki a_ alanları + change olayı: tek kaynak o alanlar)
function ayarYaz(anahtar, deger) {
  const g = $("a_" + anahtar);
  if (!g || deger === undefined || deger === null) return false;
  if (g.type === "checkbox") g.checked = !!deger; else g.value = deger;
  g.dispatchEvent(new Event("change"));
  return true;
}
const ayarOku = (anahtar) => { const g = $("a_" + anahtar); return g ? g.value : undefined; };
function ayarAnlik() { return { motor: ayarOku("ses.motor"), ses: ayarOku("ses.voxcpm2_ses"), xtts: ayarOku("ses.xtts_referans_ses") }; }
function sesAyarlariniYaz() {  // seçili sesi Ayarlar alanlarına yazar (form yeniden kurulunca da çağrılır)
  if (sesSecimi.startsWith("kitaplik/")) { ayarYaz("ses.motor", "voxcpm2"); ayarYaz("ses.voxcpm2_ses", sesSecimi); }
  else if (sesSecimi.startsWith("xtts/")) {
    const s = kit.liste.find((x) => x.kimlik === sesSecimi.slice(5));
    if (s) { ayarYaz("ses.motor", "xtts"); ayarYaz("ses.xtts_referans_ses", s.yol); }
  }
}
function sesSecimiUygula() { if (sesSecimi && !sesOnceki) sesOnceki = ayarAnlik(); sesAyarlariniYaz(); sesSeciciCiz(); }

function sesSec(deger, o = {}) {
  const once = sesSecimi;
  if (deger) {
    if (!sesOnceki) sesOnceki = ayarAnlik();
    sesSecimi = deger; sesAyarlariniYaz();
  } else {
    sesSecimi = "";
    if (sesOnceki) {
      ayarYaz("ses.motor", sesOnceki.motor); ayarYaz("ses.voxcpm2_ses", sesOnceki.ses); ayarYaz("ses.xtts_referans_ses", sesOnceki.xtts);
      sesOnceki = null;
    }
  }
  sesSecimiKaydet(); sesSeciciCiz(); sesKartlariniGuncelle();
  if (o.bildir) bildir(deger ? t(deger.startsWith("xtts/") ? "sesler.xtts_secildi" : "sesler.kullanilacak", { ad: o.ad }) : t("ses.otomatige_donuldu"), { geriAl: () => sesSec(once, { ad: o.ad }) });
}

// -- Dublaj kartındaki "Ses" seçici: Otomatik + kitaplık sesleri (kategoriye göre gruplu) + "Sesleri yönet"
function sesSeciciCiz() {
  const sec = $("ses-secici"), not = $("ses-secici-not");
  const secenek = (deger, metin, pasif) => { const o = ogeKur("option", "", metin); o.value = deger; o.disabled = !!pasif; return o; };
  const ogeler = [secenek("", t("ses.otomatik"))];
  SES_KATEGORILERI.forEach((k) => {
    const sesler = kit.liste.filter((s) => s.kategori === k);
    if (!sesler.length) return;
    const grup = ogeKur("optgroup"); grup.label = cevir("sesler.kategori", k);
    sesler.forEach((s) => grup.append(secenek(sesIdsi(s), kit.voxcpm2.kurulu ? s.ad : s.ad + " · " + t("ses.gerekir"), !kit.voxcpm2.kurulu)));
    ogeler.push(grup);
  });
  const xtts = sesSecimi.startsWith("xtts/") ? kit.liste.find((s) => s.kimlik === sesSecimi.slice(5)) : null;
  if (xtts) { const g = ogeKur("optgroup"); g.label = "XTTS"; g.append(secenek(sesSecimi, xtts.ad)); ogeler.push(g); }
  sec.replaceChildren(...ogeler);
  sec.value = sesSecimi;
  if (sec.value !== sesSecimi) sec.value = "";
  const secili = sec.value ? kit.liste.find((s) => s.kimlik === sec.value.split("/")[1]) : null;
  baslatGuncelle();
  not.classList.remove("uyari-mesaji");
  if (!kit.voxcpm2.kurulu && kit.liste.length) { not.textContent = t("ses.voxcpm2_yok"); not.classList.add("uyari-mesaji"); }
  else not.textContent = secili ? t("ses.secili_not", { ad: secili.ad }) : t("ses.otomatik_not");
}
$("ses-secici").addEventListener("change", (e) => {
  const deger = e.target.value, s = deger ? kit.liste.find((x) => x.kimlik === deger.split("/")[1]) : null;
  sesSec(deger, { bildir: !!deger, ad: s && s.ad });
});
$("ses-yonet").addEventListener("click", () => { sayfaAc("sesler"); window.scrollTo(0, 0); });

// -- liste: süzgeç çipleri, arama, kartlar (anahtarlı eşitleme: tek satır değişince bütün liste yeniden çizilmez)
function ciplariKur() {
  const kap = $("ses-cipler");
  kap.replaceChildren(...[["", "sesler.tumu"], ...SES_KATEGORILERI.map((k) => [k, "sesler.kategori." + k])].map(([deger, anahtar]) => {
    const b = dugmeKur("cip", null);
    b.dataset.kategori = deger; b.dataset.anahtar = anahtar;
    const nokta = ogeKur("span", "nokta"); nokta.setAttribute("aria-hidden", "true"); nokta.append(simgeOlustur("s-tamam"));
    b.append(nokta, ogeKur("span", "yazi"), ogeKur("span", "sayi"));
    b.addEventListener("click", () => { kit.kategori = kit.kategori === deger ? "" : deger; ciplariCiz(); sesListeCiz(); });
    return b;
  }));
}
function ciplariCiz() {
  document.querySelectorAll("#ses-cipler .cip").forEach((b) => {
    const k = b.dataset.kategori;
    b.querySelector(".yazi").textContent = t(b.dataset.anahtar);
    b.querySelector(".sayi").textContent = k ? kit.liste.filter((s) => s.kategori === k).length : kit.liste.length;
    b.setAttribute("aria-pressed", String(kit.kategori === k));
  });
}
$("ses-ara").addEventListener("input", (e) => { kit.ara = e.target.value.replace(DENETIM, " "); sesListeCiz(); });
$("ses-ara").addEventListener("blur", (e) => { e.target.value = kit.ara = e.target.value.replace(DENETIM, " ").trim().replace(/\s+/g, " "); sesListeCiz(); });

function listeEsitle(kap, istenen) {
  let imlec = kap.firstElementChild;
  istenen.forEach((el) => { if (el === imlec) imlec = imlec.nextElementSibling; else kap.insertBefore(el, imlec); });
  while (imlec) { const sonraki = imlec.nextElementSibling; imlec.remove(); imlec = sonraki; }
}
function gorunenSesler() {
  const q = kit.ara.trim().toLocaleLowerCase(DIL);
  return kit.liste.filter((s) => (!kit.kategori || s.kategori === kit.kategori) && (!q || s.ad.toLocaleLowerCase(DIL).includes(q)));
}
function sesDurumYaz(metin, hata) { const o = $("ses-durum"); o.textContent = metin || ""; o.classList.toggle("hata", !!hata); o.setAttribute("role", hata ? "alert" : "status"); }
// Süzgeç/arama kartları eler ya da yeniden dizer; kalanlar yukarı kaymasın diye (yerleşim kayması): liste yüksekliği
// 400 ms tutulur ve kalan kartlar eski yerinden yeni yerine transform ile süzülür (hareket azaltma açıksa süzülmez).
function listeKaymasiz(kap, guncelle) {
  const once = new Map(Array.from(kap.children).map((el) => [el, el.getBoundingClientRect()]));
  const yukseklik = kap.offsetHeight;
  guncelle();
  if (!once.size) return;
  kap.style.minHeight = yukseklik + "px";
  clearTimeout(kit.tutma); kit.tutma = setTimeout(() => { kap.style.minHeight = ""; }, 400);
  const tasinan = [];
  Array.from(kap.children).forEach((el) => {
    const e = once.get(el); if (!e) return;
    const y = el.getBoundingClientRect(), dx = e.left - y.left, dy = e.top - y.top;
    if (!dx && !dy) return;
    el.style.transition = "none"; el.style.transform = "translate(" + dx + "px," + dy + "px)"; tasinan.push(el);
  });
  if (!tasinan.length) return;
  kap.getBoundingClientRect();  // eski konumu boyatır
  tasinan.forEach((el) => { el.style.transition = hareketAz() ? "none" : "transform .18s ease-out"; el.style.transform = ""; });
  setTimeout(() => tasinan.forEach((el) => { el.style.transition = ""; }), 260);
}
function sesListeCiz() {
  const kap = $("ses-liste");
  kap.classList.toggle("xtts-var", kit.xtts.kurulu);
  if (!kit.yuklendi) { sesDurumYaz(t("sesler.yukleniyor")); return; }
  const bos = kit.liste.length === 0 && !kit.bekleyen;
  $("ses-bos").hidden = !bos; kap.hidden = bos;
  const gorunen = gorunenSesler(), istenen = [];
  if (kit.bekleyen) istenen.push(kit.bekleyen.el);
  gorunen.forEach((s) => {
    let r = kit.kartlar.get(s.kimlik);
    if (!r) { r = sesKartiKur(s.kimlik); kit.kartlar.set(s.kimlik, r); }
    sesKartiGuncelle(r, s);
    istenen.push(r.kok);
  });
  [...kit.kartlar.keys()].forEach((k) => { if (!kit.liste.some((s) => s.kimlik === k)) kit.kartlar.delete(k); });
  listeKaymasiz(kap, () => listeEsitle(kap, istenen));
  if (kit.hata) sesDurumYaz(kit.hata, true);
  else sesDurumYaz(kit.liste.length && !gorunen.length ? t("sesler.filtre_bos") : "");
}
function sesKartlariniGuncelle() { kit.liste.forEach((s) => { const r = kit.kartlar.get(s.kimlik); if (r) sesKartiGuncelle(r, s); }); }
function sesHepsiniCiz() {
  $("ses-voxcpm2-uyari").hidden = kit.voxcpm2.kurulu || !kit.yuklendi;
  $("ses-voxcpm2-uyari").textContent = t("ses.voxcpm2_yok");
  ciplariCiz(); sesListeCiz(); sesSeciciCiz();
}

async function sesleriYukle() {
  try {
    const v = await api("/api/sesler");
    const imza = JSON.stringify(v);
    if (imza !== kit.imza || !kit.yuklendi) {
      kit.imza = imza; kit.liste = v.sesler; kit.sinirlar = v.sinirlar; kit.voxcpm2 = v.voxcpm2; kit.xtts = v.xtts;
    }
    kit.hata = "";
  } catch (e) { kit.hata = t("sesler.yuklenemedi", { neden: e.message }); }
  kit.yuklendi = true;
  if (sesSecimi && !kit.liste.some((s) => s.kimlik === sesSecimi.split("/")[1])) {  // seçili ses silinmiş
    if (kit.imza) { sesSec("", {}); bildir(t("ses.silinmis")); }
  }
  sesHepsiniCiz();
  if (sesSecimi.startsWith("xtts/")) sesAyarlariniYaz();  // XTTS referans yolu liste yüklenince bilinir
}

// -- bir kart: avatar, ad (satır içi düzenleme), kategori, süre, rıza satırı, dinle + eylemler (sabit sıra: kullan, adı değiştir, kategori, sil)
function sesKartiKur(kimlik) {
  const r = { kimlik, duzenle: false };
  r.kok = ogeKur("article", "ses-karti"); r.kok.dataset.kimlik = kimlik;
  r.avatar = ogeKur("span", "avatar"); r.avatar.setAttribute("aria-hidden", "true");
  r.adSatiri = ogeKur("div", "ses-adi-satiri");
  r.ad = ogeKur("strong", "ses-adi");
  r.adSatiri.append(r.ad);
  r.rozet = ogeKur("span", "rozet"); r.sure = ogeKur("span", "ses-sure"); r.metinli = ogeKur("span", "ses-sure");
  r.etiketler = ogeKur("div", "ses-etiketler"); r.etiketler.append(r.rozet, r.sure, r.metinli);
  r.riza = ogeKur("p", "riza-satiri");
  const orta = ogeKur("div"); orta.style.minWidth = "0"; orta.append(r.adSatiri, r.etiketler, r.riza);
  r.dinle = dugmeKur("simge-dugme", "s-oynat");
  const ust = ogeKur("div", "ses-kart-ust"); ust.append(r.avatar, orta, r.dinle);
  r.kullan = dugmeKur("ana", "s-dublaj", ""); r.kullan.lastChild.textContent = "";
  r.adDegistir = dugmeKur("simge-dugme", "s-kalem");
  r.katEtiket = ogeKur("label", "kat-secici"); r.katYazi = ogeKur("span"); r.kat = ogeKur("select");
  SES_KATEGORILERI.forEach((k) => { const o = ogeKur("option"); o.value = k; r.kat.append(o); });
  r.katEtiket.append(r.katYazi, r.kat);
  r.sil = dugmeKur("simge-dugme tehlike", "s-sil");
  const satir = ogeKur("div", "ses-eylem-satir"); satir.append(r.adDegistir, r.katEtiket, r.sil);
  r.xtts = dugmeKur("ses-xtts", "s-mikrofon", ""); r.xtts.hidden = true;
  const eylemler = ogeKur("div", "ses-eylemler"); eylemler.append(r.kullan, satir, r.xtts);
  r.kok.append(ust, eylemler);
  r.dinle.addEventListener("click", () => sesCal(kit.liste.find((s) => s.kimlik === kimlik)));
  r.kullan.addEventListener("click", () => {
    const s = kit.liste.find((x) => x.kimlik === kimlik);
    if (s) sesSec(sesSecimi === sesIdsi(s) ? "" : sesIdsi(s), { bildir: true, ad: s.ad });
  });
  r.adDegistir.addEventListener("click", () => sesAdiDuzenle(r, true));
  r.kat.addEventListener("change", () => sesKategoriDegistir(kit.liste.find((s) => s.kimlik === kimlik), r.kat.value, r));
  r.sil.addEventListener("click", () => sesSil(kit.liste.find((s) => s.kimlik === kimlik)));
  r.xtts.addEventListener("click", () => sesXttsKullan(kit.liste.find((s) => s.kimlik === kimlik)));
  return r;
}
function sesKartiGuncelle(r, s) {
  r.avatar.textContent = (Array.from(s.ad)[0] || "?").toLocaleUpperCase(DIL);
  if (!r.duzenle) r.ad.textContent = s.ad;
  r.ad.title = s.ad;
  r.rozet.textContent = cevir("sesler.kategori", s.kategori);
  r.sure.textContent = t("sesler.sure", { sn: Math.max(1, Math.round(s.sure_sn)) });
  r.metinli.textContent = s.metin ? t("sesler.metinli") : ""; r.metinli.hidden = !s.metin;
  if (!r.duzenle) { r.riza.textContent = t("sesler.satir_riza", { riza: cevir("sesler.riza", (s.riza && s.riza.tur) || "kendi"), tarih: tarihYaz(s.eklendi) }); r.riza.classList.remove("hata"); }
  const calan = kit.calan === s.kimlik;
  simgeDegistir(r.dinle, calan ? "s-duraklat" : "s-oynat");
  etiketle(r.dinle, t(calan ? "sesler.duraklat" : "sesler.dinle", { ad: s.ad }));
  const secili = sesSecimi === sesIdsi(s);
  r.kok.classList.toggle("secili", secili || sesSecimi === "xtts/" + s.kimlik);
  r.kullan.setAttribute("aria-pressed", String(secili));
  simgeDegistir(r.kullan, secili ? "s-tamam" : "s-dublaj");
  r.kullan.lastChild.textContent = t(secili ? "sesler.kullaniliyor" : "sesler.kullan");
  etiketle(r.adDegistir, t("sesler.adi_degistir") + ": " + s.ad);
  r.katYazi.textContent = t("sesler.kategori_degistir");
  Array.from(r.kat.options).forEach((o) => { o.textContent = cevir("sesler.kategori", o.value); });
  r.kat.value = s.kategori; r.kat.setAttribute("aria-label", t("sesler.kategori_degistir") + ": " + s.ad);
  etiketle(r.sil, t("sesler.sil") + ": " + s.ad);
  r.xtts.hidden = !kit.xtts.kurulu; r.xtts.lastChild.textContent = t("sesler.xtts_kullan");
}

// -- dinleme: tek ses nesnesi; aynı karta ikinci basış duraklatır
function sesCal(s) {
  if (!s) return;
  if (!kit.cal) {
    kit.cal = new Audio();
    kit.cal.addEventListener("ended", () => { kit.calan = ""; sesKartlariniGuncelle(); });
    kit.cal.addEventListener("pause", () => { if (kit.cal.paused) { kit.calan = ""; sesKartlariniGuncelle(); } });
  }
  if (kit.calan === s.kimlik) { kit.cal.pause(); return; }
  kit.cal.src = dosyaAdresi(s.yol); kit.calan = s.kimlik;
  kit.cal.play().catch(() => { kit.calan = ""; sesKartlariniGuncelle(); });
  sesKartlariniGuncelle();
}
function sesDinlemeyiDurdur() { if (kit.cal && !kit.cal.paused) kit.cal.pause(); kit.calan = ""; }

// -- adı değiştir: satır içi; Enter kaydeder, Esc vazgeçer; kaydet ve vazgeç simgeleri görünür
function sesAdiDuzenle(r, ac) {
  const s = kit.liste.find((x) => x.kimlik === r.kimlik);
  if (!s) return;
  r.duzenle = ac;
  if (!ac) { r.adSatiri.replaceChildren(r.ad); sesKartiGuncelle(r, s); return; }
  const girdi = ogeKur("input"); girdi.type = "text"; girdi.maxLength = kit.sinirlar.ad; girdi.value = s.ad; girdi.autocomplete = "off";
  girdi.enterKeyHint = "done"; girdi.setAttribute("aria-label", t("sesler.ad_etiket") + ": " + s.ad);
  girdi.placeholder = t("sesler.ad_ipucu");
  const kaydet = dugmeKur("simge-dugme kaydet", "s-tamam"), vazgec = dugmeKur("simge-dugme", "s-kapat");
  etiketle(kaydet, t("sesler.adi_kaydet")); etiketle(vazgec, t("onay.vazgec"));
  r.adSatiri.replaceChildren(girdi, kaydet, vazgec);
  r.riza.textContent = t("sesler.ad_ipucu_satir"); r.riza.classList.remove("hata");
  girdi.focus(); girdi.select();
  girdi.addEventListener("input", () => { const temiz = girdi.value.replace(DENETIM, " "); if (temiz !== girdi.value) girdi.value = temiz; });
  girdi.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); kaydet.click(); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); vazgec.click(); }
  });
  vazgec.addEventListener("click", () => { sesAdiDuzenle(r, false); r.adDegistir.focus({ preventScroll: true }); });
  kaydet.addEventListener("click", async () => {
    const yeni = girdi.value.replace(DENETIM, " ").trim().replace(/\s+/g, " ");
    if (!yeni) { r.riza.textContent = t("sesler.ad_bos"); r.riza.classList.add("hata"); girdi.focus(); return; }
    const eski = s.ad;
    if (yeni === eski) { sesAdiDuzenle(r, false); r.adDegistir.focus({ preventScroll: true }); return; }
    kaydet.disabled = vazgec.disabled = true;
    try {
      const v = await api("/api/ses_guncelle", { kimlik: s.kimlik, ad: yeni });
      Object.assign(s, v); sesAdiDuzenle(r, false); sesSeciciCiz(); r.adDegistir.focus({ preventScroll: true });
      bildir(t("sesler.ad_kaydedildi"), { geriAl: () => api("/api/ses_guncelle", { kimlik: s.kimlik, ad: eski }).then((g) => { Object.assign(s, g); sesHepsiniCiz(); }).catch((e) => sesDurumYaz(hataMetni(e), true)) });
    } catch (e) { kaydet.disabled = vazgec.disabled = false; r.riza.textContent = hataMetni(e); r.riza.classList.add("hata"); }
  });
}
async function sesKategoriDegistir(s, yeni, r) {
  if (!s || s.kategori === yeni) return;
  const eski = s.kategori;
  try {
    Object.assign(s, await api("/api/ses_guncelle", { kimlik: s.kimlik, kategori: yeni }));
    sesHepsiniCiz();
    bildir(t("sesler.kategori_kaydedildi"), { geriAl: () => api("/api/ses_guncelle", { kimlik: s.kimlik, kategori: eski }).then((g) => { Object.assign(s, g); sesHepsiniCiz(); }).catch((e) => sesDurumYaz(hataMetni(e), true)) });
  } catch (e) { r.kat.value = eski; sesDurumYaz(hataMetni(e), true); }
}

// -- sil: tek onay (adıyla); kart hemen çıkar, istek arkada gider, olmazsa geri gelir
async function sesSil(s) {
  if (!s) return;
  const evet = await onayIste({ baslik: t("sesler.sil_baslik", { ad: s.ad }), metin: t("sesler.sil_metin"), tamam: t("sesler.sil"), tehlike: true });
  if (!evet) return;
  const eskiListe = kit.liste.slice(), r = kit.kartlar.get(s.kimlik);
  kit.liste = kit.liste.filter((x) => x.kimlik !== s.kimlik);
  if (kit.calan === s.kimlik) sesDinlemeyiDurdur();
  if (sesSecimi && sesSecimi.split("/")[1] === s.kimlik) sesSec("", {});
  if (r && !hareketAz()) { r.kok.classList.add("cikiyor"); setTimeout(() => { sesHepsiniCiz(); }, 150); } else sesHepsiniCiz();
  ciplariCiz(); sesSeciciCiz();
  try {
    await api("/api/ses_sil", { kimlik: s.kimlik });
    bildir(t("sesler.silindi", { ad: s.ad }));
  } catch (e) {
    kit.liste = eskiListe; sesHepsiniCiz(); sesDurumYaz(hataMetni(e), true);
    if (e.veri && (e.veri.anahtar === "ses_yok" || e.veri.anahtar === "kimlik_gecersiz")) sesleriYukle();
  }
}

// -- XTTS (yalnız kuruluysa): ticari olmayan lisans tek onayla kabul edilir, sonra bu ses referans olur
async function sesXttsKullan(s) {
  if (!s) return;
  if (!kit.xtts.lisans_onayli) {
    const kabul = await onayIste({ baslik: t("sesler.xtts_lisans_baslik"), metin: t("sesler.xtts_lisans_metin"), tamam: t("onay.kabul_et"), tehlike: false });
    if (!kabul) return;
    try { kit.xtts = (await api("/api/xtts_lisans", { kabul: true })).xtts; } catch (e) { sesDurumYaz(hataMetni(e), true); return; }
  }
  sesSec("xtts/" + s.kimlik, { bildir: true, ad: s.ad });
}

// -- ses ekle sayfası -------------------------------------------------------------------------------------------
const sf = { dosya: null, sure: null, dosyaHata: false, ad: "", kategori: "", riza: "", taklit: false, gonderiliyor: false, istek: null, url: "" };
function sfMesaj(oge, metin, seviye) { oge.textContent = metin || ""; oge.classList.toggle("uyari-mesaji", seviye === "uyari"); oge.classList.toggle("hata-mesaji", seviye === "hata"); }
function sfKategoriCipleri() {
  const kap = $("ses-kategori-secimi");
  kap.replaceChildren(...SES_KATEGORILERI.map((k) => {
    const b = dugmeKur("cip", null); b.dataset.kategori = k;
    const nokta = ogeKur("span", "nokta"); nokta.setAttribute("aria-hidden", "true"); nokta.append(simgeOlustur("s-tamam"));
    b.append(nokta, ogeKur("span", "yazi", cevir("sesler.kategori", k)));
    b.setAttribute("aria-pressed", String(sf.kategori === k));
    b.addEventListener("click", () => { sf.kategori = k; sfKategoriCipleri(); sfDurum(); });
    return b;
  }));
}
function sfDurum() {
  const neden = !sf.dosya ? "dosya" : sf.dosyaHata ? "dosya_hata" : !sf.ad.trim() ? "ad" : !sf.kategori ? "kategori" : !sf.riza ? "riza" : !sf.taklit ? "taklit" : "";
  const o = $("ses-neden");
  if (!sf.gonderiliyor && !o.dataset.hata) o.textContent = cevir("sesler", "neden_" + (neden || "hazir"));
  o.classList.toggle("hata-mesaji", !!o.dataset.hata);
  $("ses-kaydet").disabled = !!neden;
  return !neden;
}
function sfSayac() { $("ses-ad-sayac").textContent = `${Array.from(sf.ad).length}/${kit.sinirlar.ad}`; $("ses-metin-sayac").textContent = `${Array.from($("ses-metin").value).length}/${kit.sinirlar.metin}`; }
function sfSifirla() {
  sfDosyaTemizle(true);
  sf.ad = ""; sf.kategori = ""; sf.riza = ""; sf.taklit = false; sf.gonderiliyor = false; sf.istek = null;
  $("ses-ad").value = ""; $("ses-metin").value = ""; $("ses-taklit").checked = false;
  document.querySelectorAll('input[name="ses-riza"]').forEach((x) => { x.checked = false; });
  sfMesaj($("ses-ad-mesaj"), ""); delete $("ses-neden").dataset.hata;
  $("ses-metin").maxLength = kit.sinirlar.metin; $("ses-ad").maxLength = kit.sinirlar.ad;
  const k = $("ses-kaydet"); k.classList.remove("ilerliyor"); k.style.removeProperty("--yuzde"); yaz($("ses-kaydet-yazi"), "sesler.kaydet");
  document.querySelectorAll("#ses-form .sayfa-govde input, #ses-form .sayfa-govde textarea, #ses-form .sayfa-govde button").forEach((x) => { x.disabled = false; });
  sfKategoriCipleri(); sfSayac(); sfDurum();
}
function sfDosyaTemizle(tam) {
  const a = $("ses-onizleme-ses");
  a.pause(); a.removeAttribute("src"); a.load();
  if (sf.url) { URL.revokeObjectURL(sf.url); sf.url = ""; }
  sf.dosya = null; sf.sure = null; sf.dosyaHata = false;
  $("ses-onizleme-ic").hidden = true; $("ses-onizleme-bos").hidden = false; $("ses-sure").textContent = "";
  sfMesaj($("ses-dosya-mesaj"), "");
  if (tam) $("ses-dosya").value = "";
}
function sfSureDegerlendir() {
  const sn = sf.sure, s = kit.sinirlar;
  $("ses-sure").textContent = t("sesler.sure_etiket", { sn: sayiYaz(sn) });
  let anahtar = "sesler.sure_iyi", seviye = "";
  sf.dosyaHata = false;
  if (sn < s.en_kisa_sn) { anahtar = "sesler.sure_cok_kisa"; seviye = "hata"; sf.dosyaHata = true; }
  else if (sn > s.en_uzun_sn) { anahtar = "sesler.sure_cok_uzun"; seviye = "hata"; sf.dosyaHata = true; }
  else if (sn < 6) { anahtar = "sesler.sure_kisa"; seviye = "uyari"; }
  else if (sn > 15) { anahtar = "sesler.sure_uzun"; seviye = "uyari"; }
  sfMesaj($("ses-dosya-mesaj"), t(anahtar), seviye);
  sfDurum();
}
function sfDosya(dosya) {
  sfDosyaTemizle(false);
  delete $("ses-neden").dataset.hata;
  if (!dosya) { sfDurum(); return; }
  const uz = ((dosya.name.match(/\.[^.]+$/) || [""])[0]).toLowerCase();
  if (!kit.sinirlar.uzantilar.includes(uz)) { sf.dosyaHata = true; sfMesaj($("ses-dosya-mesaj"), t("sesler.dosya_uzanti", { liste: kit.sinirlar.uzantilar.join(", ") }), "hata"); sfDurum(); return; }
  if (dosya.size > kit.sinirlar.dosya_mb * 1048576) { sf.dosyaHata = true; sfMesaj($("ses-dosya-mesaj"), t("sesler.dosya_buyuk", { mb: kit.sinirlar.dosya_mb }), "hata"); sfDurum(); return; }
  sf.dosya = dosya; sf.url = URL.createObjectURL(dosya);
  const a = $("ses-onizleme-ses");
  $("ses-onizleme-bos").hidden = true; $("ses-onizleme-ic").hidden = false;
  a.onerror = () => { if (!sf.dosya) return; sf.sure = null; sfMesaj($("ses-dosya-mesaj"), t("sesler.dosya_onizlenemedi"), "uyari"); sfDurum(); };
  a.onloadedmetadata = () => {
    if (Number.isFinite(a.duration)) { sf.sure = a.duration; sfSureDegerlendir(); return; }
    const sonra = () => { if (!Number.isFinite(a.duration)) return; a.removeEventListener("durationchange", sonra); a.currentTime = 0; sf.sure = a.duration; sfSureDegerlendir(); };
    a.addEventListener("durationchange", sonra); a.currentTime = 1e101;  // süresi bilinmeyen (webm): sona sar, süreyi öğren
  };
  a.src = sf.url;
  sfDurum();
}
function sesFormuAc() {
  sesDinlemeyiDurdur(); sesKartlariniGuncelle();
  sfSifirla();
  $("ses-form").showModal();
  $("ses-dosya").focus({ preventScroll: true });
}
function sesFormuKapat() { $("ses-form").close(); }

$("ses-ekle-ac").addEventListener("click", sesFormuAc);
$("ses-bos").querySelector(".ses-bos-ekle").addEventListener("click", sesFormuAc);
$("ses-form-kapat").addEventListener("click", sesFormuKapat);
$("ses-form-vazgec").addEventListener("click", sesFormuKapat);
$("ses-form").addEventListener("close", () => {
  if (sf.gonderiliyor && sf.istek) { sf.istek.abort(); }
  const a = $("ses-onizleme-ses"); a.pause();
});
$("ses-dosya").addEventListener("change", (e) => { sfDosya(e.target.files[0]); });
const sesBirak = $("ses-birak");
sesBirak.addEventListener("dragover", (e) => { e.preventDefault(); sesBirak.classList.add("uzerinde"); });
sesBirak.addEventListener("dragleave", () => sesBirak.classList.remove("uzerinde"));
sesBirak.addEventListener("drop", (e) => { e.preventDefault(); sesBirak.classList.remove("uzerinde"); if (e.dataTransfer.files[0]) sfDosya(e.dataTransfer.files[0]); });
$("ses-ad").addEventListener("input", (e) => {
  const temiz = e.target.value.replace(DENETIM, " "); if (temiz !== e.target.value) e.target.value = temiz;
  sf.ad = e.target.value; if (sf.ad.trim()) sfMesaj($("ses-ad-mesaj"), ""); sfSayac(); sfDurum();
});
$("ses-ad").addEventListener("blur", (e) => {  // alandan çıkınca: sessiz düzeltme + doğrulama (yazarken değil)
  e.target.value = sf.ad = e.target.value.replace(DENETIM, " ").trim().replace(/\s+/g, " ");
  sfMesaj($("ses-ad-mesaj"), sf.ad ? "" : t("sesler.ad_bos"), sf.ad ? "" : "uyari"); sfSayac(); sfDurum();
});
$("ses-metin").addEventListener("input", () => sfSayac());
$("ses-metin").addEventListener("blur", (e) => { e.target.value = metinTemizle(e.target.value); sfSayac(); });
document.querySelectorAll('input[name="ses-riza"]').forEach((x) => x.addEventListener("change", () => { sf.riza = x.value; sfDurum(); }));
$("ses-taklit").addEventListener("change", (e) => { sf.taklit = e.target.checked; sfDurum(); });

function sfGonder() {
  if (sf.gonderiliyor || !sfDurum()) return;
  sf.ad = metinTemizle($("ses-ad").value);
  const ad = sf.ad, metin = metinTemizle($("ses-metin").value);
  sf.gonderiliyor = true; delete $("ses-neden").dataset.hata;
  document.querySelectorAll("#ses-form .sayfa-govde input, #ses-form .sayfa-govde textarea, #ses-form .sayfa-govde button").forEach((x) => { x.disabled = true; });
  const k = $("ses-kaydet"); k.classList.add("ilerliyor"); k.style.setProperty("--yuzde", "0%");
  yaz($("ses-kaydet-yazi"), "sesler.kaydediliyor", { yuzde: 0 });
  $("ses-neden").textContent = t("sesler.ekleniyor");
  // yer tutucu kart hemen listenin başına girer (gerçek kartla aynı boyda): gelince yerinde değişir, liste kaymaz
  const yer = ogeKur("article", "ses-karti bekleyen"); yer.setAttribute("aria-busy", "true");
  const cubuk = ogeKur("div", "cubuk ince"); cubuk.append(ogeKur("div"));
  const ustYer = ogeKur("div", "ses-kart-ust"); ustYer.append(ogeKur("span", "avatar", Array.from(ad)[0] ? Array.from(ad)[0].toLocaleUpperCase(DIL) : "?"), ogeKur("strong", "ses-adi", ad), ogeKur("span"));
  yer.append(ustYer, ogeKur("p", "riza-satiri", t("sesler.ekleniyor")), cubuk);
  kit.bekleyen = { el: yer }; sesListeCiz();
  const bitir = () => { kit.bekleyen = null; sf.istek = null; sf.gonderiliyor = false; };
  const hataGoster2 = (metinHata) => {
    bitir(); sesListeCiz();
    k.classList.remove("ilerliyor"); yaz($("ses-kaydet-yazi"), "sesler.kaydet");
    document.querySelectorAll("#ses-form .sayfa-govde input, #ses-form .sayfa-govde textarea, #ses-form .sayfa-govde button").forEach((x) => { x.disabled = false; });
    const n = $("ses-neden"); n.textContent = metinHata; n.dataset.hata = "1"; n.setAttribute("role", "alert"); sfDurum();
  };
  const istek = new XMLHttpRequest();
  sf.istek = istek;
  istek.open("POST", "/api/ses_ekle");
  const bas = { "X-Dublaj-Belirtec": BELIRTEC, "X-Dosya-Adi": sf.dosya.name, "X-Ses-Adi": ad, "X-Ses-Kategori": sf.kategori, "X-Ses-Riza": sf.riza, "X-Ses-Taklit-Yok": "1", "X-Ses-Metin": metin };
  Object.entries(bas).forEach(([a, d]) => istek.setRequestHeader(a, encodeURIComponent(d)));
  istek.setRequestHeader("Content-Type", "application/octet-stream");
  istek.upload.onprogress = (e) => {
    if (!e.lengthComputable) return;
    const y = Math.round(100 * e.loaded / e.total);
    k.style.setProperty("--yuzde", y + "%"); cubuk.firstElementChild.style.width = y + "%";
    yaz($("ses-kaydet-yazi"), "sesler.kaydediliyor", { yuzde: y });
  };
  istek.onload = () => {
    let v = {};
    try { v = JSON.parse(istek.responseText); } catch (_) { /* boş */ }
    if (istek.status !== 200) { hataGoster2(hataMetni({ veri: v, message: v.hata || ("HTTP " + istek.status) })); return; }
    bitir();
    kit.liste = [v, ...kit.liste.filter((x) => x.kimlik !== v.kimlik)]; kit.imza = "";
    sesHepsiniCiz();
    $("ses-form").close();
    bildir(t("sesler.eklendi", { ad: v.ad }));
  };
  istek.onerror = () => hataGoster2(t("sesler.baglanti_koptu"));
  istek.onabort = () => { if (sf.gonderiliyor) { bitir(); sesListeCiz(); } };
  istek.send(sf.dosya);
}
$("ses-kaydet").addEventListener("click", sfGonder);
ciplariKur();
document.querySelector("#ses-liste").replaceChildren(...Array.from({ length: 3 }, () => { const d = ogeKur("div", "iskelet ses-iskelet"); d.setAttribute("aria-hidden", "true"); return d; }));

// Kurulum eksikse sayfanın üstünde açık uyarı (dubla kontrol ile aynı ölçüt).
async function kurulumDenetle() {
  try {
    const v = await api("/api/kurulum");
    const uyari = $("kurulum-uyari");
    if (v.eksik && v.eksik.length) yaz(uyari, "kurulum.eksik", { eksik: v.eksik.join(", ") });
    uyari.hidden = !(v.eksik && v.eksik.length);
  } catch (_) { /* denetim sayfayı hiçbir zaman düşürmez */ }
}

// Açılış: önce dil (sözlük gelmezse sayfadaki Türkçe yedek kalır), sonra o dilde ayar formu.
// Masaüstü penceresi (dubla-gui) kapandı mı: sayfa açık oldukça sunucu nabız görür. İş sürerken kapatmadan önce sorulur.
setInterval(() => { api("/api/nabiz").catch(() => {}); }, 10000);
window.addEventListener("beforeunload", (e) => { if (sonDurum && sonDurum.durum === "calisiyor") { e.preventDefault(); e.returnValue = ""; } });
temaDugmesi();
dilYukle(yerelDil()).catch(() => {}).then(() => { izle(); kurulumDenetle(); acilistaIsiBagla(); sesleriYukle(); return formYukle(); }).catch((e) => hataGoster(e.message));

