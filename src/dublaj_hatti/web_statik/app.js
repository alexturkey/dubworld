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
function bildir(metin, { geriAl } = {}) {
  const kutu = $("bildirim"), geri = $("bildirim-geri");
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
  const v = await api("/api/ayarlar?dil=" + encodeURIComponent(DIL));
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
  } catch (hata) { hataGoster(hata.message); }
});
function dosyaAdresi(yol) { return "/dosya?yol=" + encodeURIComponent(yol); }

// --- sekmeler ---------------------------------------------------------------------------------------
function cekmece(acik) {
  $("gelismis").hidden = !acik; $("perde").hidden = !acik;
  document.querySelector('.sekme[data-sekme="gelismis"]').setAttribute("aria-expanded", String(acik));
  if (acik) $("ayar-ara").focus();
}
function sayfaAc(ad) {
  document.querySelectorAll(".sekme").forEach((x) => { if (x.dataset.sekme !== "gelismis") x.classList.toggle("etkin", x.dataset.sekme === ad); });
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("etkin", p.id === ad));
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
    let bolumde = 0;
    fs.querySelectorAll(".alan").forEach((a) => {
      const uygun = !aranan || a.textContent.toLocaleLowerCase(DIL).includes(aranan)
        || fs.querySelector("legend").textContent.toLocaleLowerCase(DIL).includes(aranan);
      a.hidden = !uygun; if (uygun) bolumde++;
    });
    fs.hidden = !bolumde; gorunen += bolumde;
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
  const bolumler = {};
  form.forEach((alan) => {
    if (!bolumler[alan.bolum]) {
      const fs = document.createElement("fieldset");
      const lg = document.createElement("legend");
      lg.textContent = cevir("bolum", alan.bolum, alan.bolum.replace("_", " "));
      fs.appendChild(lg);
      kok.appendChild(fs);
      bolumler[alan.bolum] = fs;
    }
    bolumler[alan.bolum].appendChild(alanCiz(alan));
  });
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
}
let gozdenBaglandi = false;
$("sifirla").addEventListener("click", formCiz);

// --- yükleme ------------------------------------------------------------------------------------------
function dosyaYukle(dosya) {
  hataGoster("");
  yuklenen = null; yenidenKaynak = null; izlenenIs = null; baglananAnahtar = "";
  oynaticiYukle({ orijinal: URL.createObjectURL(dosya), yerel: true });
  $("dublajla").disabled = $("transkript").disabled = true;
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
    let veri = {};
    try { veri = JSON.parse(istek.responseText); } catch (_) { /* boş */ }
    if (istek.status !== 200) { hataGoster(veri.hata || t("web.yukleme_basarisiz")); yaz($("dosya-yazi"), "web.tekrar_sec"); return; }
    yuklenen = veri.kimlik;
    baglanti = ""; $("baglanti").value = "";
    yaz($("dosya-yazi"), "web.yuklendi", { ad: dosya.name, mb: (dosya.size / 1048576).toFixed(1) });
    cubuk.hidden = true;
    $("dublajla").disabled = $("transkript").disabled = false;
  };
  istek.onerror = () => hataGoster(t("web.yukleme_koptu"));
  istek.send(dosya);
}
function baglantiHazir() { return /^https:\/\/\S+$/i.test(baglanti); }
const baslatilabilir = () => !!(yuklenen || baglantiHazir() || yenidenKaynak);
$("baglanti").addEventListener("input", (e) => {
  baglanti = e.target.value.trim();
  $("dublajla").disabled = $("transkript").disabled = !baslatilabilir();
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
  $("dublajla").disabled = $("transkript").disabled = calisiyor || !baslatilabilir();
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
function listeyiAc() { inc.satirlar.forEach((s) => { otoBuyut(s.oge.orj); otoBuyut(s.oge.cev); satirGuncelle(s); }); }

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
    bulSay(); incelemeDurumYaz();
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
    s.oge.cev.value = sonuc; otoBuyut(s.oge.cev); satirGuncelle(s);
  });
  if (!adet) return;
  kayitPlanla(); bulSay();
  bildir(t("inceleme.degisti", { adet }), { geriAl: () => {
    onceki.forEach(([s, eski]) => { s.oge.cev.value = eski; otoBuyut(s.oge.cev); satirGuncelle(s); });
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
function incelemeDiliYenile() { inc.satirlar.forEach((s) => { if (s.oge) { s.zamanBaslik(); satirGuncelle(s); } }); bulSay(); incelemeDurumYaz(); }

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
  $("dublajla").disabled = false;
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
dilYukle(yerelDil()).catch(() => {}).then(() => { izle(); kurulumDenetle(); acilistaIsiBagla(); return formYukle(); }).catch((e) => hataGoster(e.message));

