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

function hataGoster(metin) { const h = $("hata"); h.textContent = metin || ""; h.hidden = !metin; }

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
  document.querySelectorAll("[data-t-ipucu]").forEach((o) => { o.placeholder = t(o.dataset.tIpucu); });
}
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
  } catch (hata) { hataGoster(hata.message); }
});
function dosyaAdresi(yol) { return "/dosya?yol=" + encodeURIComponent(yol); }

// --- sekmeler ---------------------------------------------------------------------------------------
document.querySelectorAll(".sekme").forEach((d) => d.addEventListener("click", () => {
  document.querySelectorAll(".sekme").forEach((x) => x.classList.toggle("etkin", x === d));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("etkin", p.id === d.dataset.sekme));
}));

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
}
$("sifirla").addEventListener("click", formCiz);

// --- yükleme ------------------------------------------------------------------------------------------
function dosyaYukle(dosya) {
  hataGoster("");
  yuklenen = null;
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
    $("dublajla").disabled = $("transkript").disabled = false;
  };
  istek.onerror = () => hataGoster(t("web.yukleme_koptu"));
  istek.send(dosya);
}
function baglantiHazir() { return /^https:\/\/\S+$/i.test(baglanti); }
$("baglanti").addEventListener("input", (e) => {
  baglanti = e.target.value.trim();
  $("dublajla").disabled = $("transkript").disabled = !(yuklenen || baglantiHazir());
});
$("dosya").addEventListener("change", (e) => { if (e.target.files[0]) dosyaYukle(e.target.files[0]); });
const alan = $("dosya-alani");
alan.addEventListener("dragover", (e) => { e.preventDefault(); alan.classList.add("uzerinde"); });
alan.addEventListener("dragleave", () => alan.classList.remove("uzerinde"));
alan.addEventListener("drop", (e) => { e.preventDefault(); alan.classList.remove("uzerinde"); if (e.dataTransfer.files[0]) dosyaYukle(e.dataTransfer.files[0]); });

// --- iş -----------------------------------------------------------------------------------------------
async function baslat(isTuru) {
  hataGoster("");
  const ayarlar = Object.assign({}, degisiklik, { "genel.is_turu": isTuru });
  const govde = baglantiHazir() ? { baglanti, ayarlar } : { yuklenen, ayarlar };
  try {
    try {
      await api("/api/baslat", govde);
    } catch (e) {
      // Ticari olmayan / şartlı motor ilk kez seçildi: iki dilli uyarı + açık onay; onay sunucuda hatırlanır.
      const bekleyen = e.veri && e.veri.lisans_onayi;
      if (!bekleyen) throw e;
      const metin = bekleyen.map((b) => b.metin).join("\n\n");
      if (!window.confirm(metin + "\n\nKabul ediyor musunuz? / Do you accept?")) return;
      await api("/api/baslat", Object.assign({}, govde, { lisans_onay: true }));
    }
    $("sonuc").hidden = true;
    izle();
  } catch (e) { hataGoster(e.message); }
}
$("dublajla").addEventListener("click", () => baslat("dublaj"));
$("transkript").addEventListener("click", () => baslat("transkript"));
$("durdur").addEventListener("click", () => api("/api/durdur", {}).catch((e) => hataGoster(e.message)));
$("gunluk-ac").addEventListener("click", () => {
  $("gunluk").hidden = !$("gunluk").hidden;
  yaz($("gunluk-ac"), $("gunluk").hidden ? "dugme.gunluk_goster" : "dugme.gunluk_gizle");
});
$("klasor-ac").addEventListener("click", () => api("/api/klasor_ac", { yol: $("klasor-ac").dataset.yol || "" }).catch((e) => hataGoster(e.message)));

function sureYaz(sn) { return t("ilerleme.sure", { dk: Math.floor(sn / 60), sn: Math.floor(sn % 60) }); }

function durumCiz(d) {
  sonDurum = d;
  const calisiyor = d.durum === "calisiyor";
  $("ilerleme").hidden = d.durum === "bos";
  $("durdur").disabled = !calisiyor;
  $("dublajla").disabled = $("transkript").disabled = calisiyor || !(yuklenen || baglantiHazir());
  if (d.durum !== "bos") yaz($("ilerleme-baslik"), "ilerleme." + d.durum);
  $("ilerleme-cubugu").style.width = d.yuzde + "%";
  const parcalar = [t("ilerleme.yuzde", { yuzde: d.yuzde }),
    d.bekleme || cevir("asama", d.asama, d.asama_adi) || t("ilerleme.hazirlaniyor"), sureYaz(d.gecen_sn)];
  if (d.is) parcalar.push(t("ilerleme.is_no", { no: d.is }));
  $("ilerleme-yazi").textContent = parcalar.join(" · ");
  const liste = $("asamalar");
  liste.replaceChildren(...(d.asamalar || []).map((a) => { const li = document.createElement("li"); li.textContent = cevir("asama", a.id, a.ad); li.className = a.durum; return li; }));
  const gunluk = $("gunluk");
  const altta = gunluk.scrollTop + gunluk.clientHeight >= gunluk.scrollHeight - 4;
  gunluk.textContent = (d.gunluk || []).join("\n");
  if (altta) gunluk.scrollTop = gunluk.scrollHeight;
  if (d.durum === "hata") hataGoster(d.hata);
  if (d.durum === "bitti") sonucCiz(d.sonuc || {}, d.ciktilar || []);
}

function sonucCiz(sonuc, ciktilar) {
  $("sonuc").hidden = false;
  const video = sonuc.dubbed_video || sonuc.output_video;
  const oynatici = $("onizleme");
  if (video) { oynatici.src = dosyaAdresi(video); oynatici.hidden = false; } else { oynatici.hidden = true; }
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
function dugme(yazi, islev) { const b = document.createElement("button"); b.textContent = yazi; b.addEventListener("click", islev); return b; }

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
  if (sorunluMu && o.komut === "dubla" && devamVar) dugmeler.append(dugme(t("isler.devam"), () => devamEt({ is: o.is })));
  if ((sorunluMu || o.durum === "completed") && o.komut === "dubla") dugmeler.append(dugme(t("isler.asamadan_dugme"), () => secenekAc(o.is)));
  if (o.video) dugmeler.append(dugme(t("dugme.videoyu_ac"), () => window.open(dosyaAdresi(o.video), "_blank", "noopener")));
  if (o.klasor) dugmeler.append(dugme(t("isler.klasor"), () => api("/api/klasor_ac", { yol: o.klasor }).catch((e) => hataGoster(e.message))));
  if (o.durum === "queued" || o.durum === "deferred")
    dugmeler.append(dugme(t("isler.iptal"), () => api("/api/is_iptal", { is: o.is }).then(islerYukle).catch((e) => hataGoster(e.message))));
  if (!["queued", "deferred", "preparing", "processing"].includes(o.durum) && !o.arsiv)
    dugmeler.append(dugme(t("isler.arsivle"), () => api("/api/is_arsivle", { is: o.is }).then(islerYukle).catch((e) => hataGoster(e.message))));
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

// Açılış: önce dil (sözlük gelmezse sayfadaki Türkçe yedek kalır), sonra o dilde ayar formu.
dilYukle(yerelDil()).catch(() => {}).then(() => { izle(); return formYukle(); }).catch((e) => hataGoster(e.message));

