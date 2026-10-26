#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Akıllı Kurulum Sihirbazı - DubWorld
Sadece Python standart kütüphanesi kullanarak basit bir menü ile kurulum yapar.
mevcut scripts/kur.ps1 mantığını kullanır.
"""

import os
import sys
import platform
import subprocess
from pathlib import Path


class KurulumSihirbazi:
    def __init__(self):
        self.repo_root = Path(__file__).parent.parent
        self.scripts_dir = self.repo_root / "scripts"
        self.kur_ps1 = self.scripts_dir / "kur.ps1"
        
    def calistir(self):
        print("=" * 60)
        print("DubWorld - Akıllı Kurulum Sihirbazı")
        print("=" * 60)
        print()
        
        # İşletim sistemi kontrolü
        sistem = platform.system()
        if sistem == "Windows":
            print("[OK] Windows tespit edildi - Tam destekleniyor")
        elif sistem == "Darwin":
            print("[UYARI] macOS tespit edildi")
            print("Bu işletim sistemi henüz tam desteklenmiyor, manuel kurulum yapın.")
            print("Detaylar için docs/kurulum.md bölüm 11'e bakın.")
            print()
            cevap = input("Yine de devam etmek istiyor musunuz? [E/h]: ").strip().lower()
            if cevap not in ('e', 'evet', 'y', 'yes'):
                print("Kurulum iptal edildi.")
                return
        elif sistem == "Linux":
            print("[UYARI] Linux tespit edildi")
            print("Bu işletim sistemi henüz tam desteklenmiyor, manuel kurulum yapın.")
            print("Detaylar için docs/kurulum.md bölüm 11'e bakın.")
            print()
            cevap = input("Yine de devam etmek istiyor musunuz? [E/h]: ").strip().lower()
            if cevap not in ('e', 'evet', 'y', 'yes'):
                print("Kurulum iptal edildi.")
                return
        else:
            print(f"[UYARI] Bilinmeyen işletim sistemi: {sistem}")
            print("Bu işletim sistemi henüz tam desteklenmiyor, manuel kurulum yapın.")
            return
        
        print()
        
        # Donanım tespiti
        print("Donanım tespiti yapılıyor...")
        gpu_var = self._gpu_tespit()
        if gpu_var:
            print("[OK] NVIDIA GPU tespit edildi - GPU profili önerilir")
        else:
            print("[OK] NVIDIA GPU bulunamadı - CPU profili kullanılacak")
        print()
        
        # Kurulum tipi seçimi
        print("Kurulum tipi seçin:")
        print("1. Hızlı kurulum (sadece temel bileşenler)")
        print("2. Önerilen kurulum (temel + ses temizliği + alternatif sesler)")
        print("3. Tam kurulum (tüm isteğe bağlı bileşenler)")
        print("4. Özel kurulum (bileşenleri kendim seçeceğim)")
        print()
        secim = input("Seçiminiz [1-4]: ").strip()
        
        adimlar = []
        ticari_olmayan_kabul = False
        
        if secim == "1":
            # Hızlı kurulum
            if gpu_var:
                adimlar = ["uv", "python", "paketler", "modeller", "kontrol"]
            else:
                adimlar = ["uv", "python", "paketler", "modeller", "kontrol"]
            print("\n[HIZLI KURULUM] Seçildi")
            
        elif secim == "2":
            # Önerilen kurulum
            if gpu_var:
                adimlar = ["uv", "python", "paketler", "modeller", "demucs", "tts-ema", "voxcpm2", "kontrol"]
                print("\n[ÖNERİLEN KURULUM - GPU] Seçildi")
            else:
                adimlar = ["uv", "python", "paketler", "modeller", "demucs", "tts-ema", "kontrol"]
                print("\n[ÖNERİLEN KURULUM - CPU] Seçildi")
                
        elif secim == "3":
            # Tam kurulum
            if gpu_var:
                adimlar = ["uv", "python", "paketler", "modeller", "demucs", "hizalama-diller", 
                          "parakeet", "akilli-kare", "youtube", "telegram", "tts-ema", "voxcpm2", "kontrol"]
            else:
                adimlar = ["uv", "python", "paketler", "modeller", "demucs", "hizalama-diller", 
                          "parakeet", "akilli-kare", "youtube", "telegram", "tts-ema", "kontrol"]
            print("\n[TAM KURULUM] Seçildi")
            print("[UYARI] Tam kurulum daha fazla disk alanı ve süre gerektirir.")
            
        elif secim == "4":
            # Özel kurulum
            adimlar = self._ozel_kurulum(gpu_var)
            if not adimlar:
                print("Kurulum iptal edildi.")
                return
        else:
            print("Geçersiz seçim. Kurulum iptal edildi.")
            return
        
        # Venv konumu seçimi
        print("\nVenv konumu:")
        print("1) Varsayılan (proje klasörü) - .\\.venv")
        print("2) Özel yol (D/E sürücüsü gibi)")
        print()
        venv_secim = input("Seçiminiz [1-2]: ").strip()
        venv_yolu = ""
        
        if venv_secim == "2":
            while True:
                ozel_yol = input("Venv icin tam yol girin: ").strip().strip('"').strip("'")
                if not ozel_yol:
                    print("Geçersiz yol. Tekrar deneyin.")
                    continue
                try:
                    yol_path = Path(ozel_yol)
                    # Yolun yazılabilir olup olmadığını kontrol et
                    yol_path.mkdir(parents=True, exist_ok=True)
                    test_file = yol_path / ".test_write"
                    test_file.write_text("test")
                    test_file.unlink()
                    venv_yolu = ozel_yol
                    print(f"[OK] Venv konumu: {venv_yolu}")
                    break
                except PermissionError:
                    print("[HATA] Yazma izni yok. Başka bir yol deneyin.")
                except Exception as e:
                    print(f"[HATA] Geçersiz yol: {e}")
        else:
            print("[OK] Venv konumu: Varsayılan (proje klasörü\\.venv)")
            venv_yolu = ""
        
        # Ticari olmayan lisans kontrolü
        if any(adim in adimlar for adim in ["crisper", "tts-xtts"]):
            print("\n" + "=" * 60)
            print("LİSANS ONAYI GEREKLİ")
            print("=" * 60)
            if "crisper" in adimlar:
                print("\n[CrisperWhisper Turbo]")
                print("Model ağırlığı yalnız TİCARİ OLMAYAN kullanım içindir")
                print("(Nyra Health Non-Commercial Research License).")
                print("Ücretli iş, müşteri işi veya gelir getiren kullanımda KULLANMAYIN.")
            if "tts-xtts" in adimlar:
                print("\n[XTTS v2]")
                print("XTTS v2 ağırlıkları Coqui Public Model License altındadır:")
                print("yalnız TİCARİ OLMAYAN kullanım.")
                print("Referans ses yalnız kendi sesiniz ya da sahibinin açık izin verdiği ses olabilir.")
            print("\n" + "=" * 60)
            onay = input("Yukarıdaki ticari olmayan lisans koşullarını kabul ediyor musunuz? [evet/hayır]: ").strip().lower()
            if onay not in ('evet', 'e', 'yes', 'y'):
                print("\nLisans kabul edilmedi. Ticari olmayan bileşenler çıkarılıyor.")
                adimlar = [a for a in adimlar if a not in ["crisper", "tts-xtts"]]
            else:
                ticari_olmayan_kabul = True
                print("\n[Lisans kabul edildi]")
        
        # Özet
        print("\n" + "=" * 60)
        print("KURULUM ÖZETİ")
        print("=" * 60)
        print(f"İşletim Sistemi: {sistem}")
        print(f"GPU: {'Var (NVIDIA)' if gpu_var else 'Yok/Belirlenemedi'}")
        venv_goster = venv_yolu if venv_yolu else 'Varsayılan (proje klasörü\\.venv)'
        print(f"Venv Konumu: {venv_goster}")
        print(f"Kurulum Adımları: {', '.join(adimlar)}")
        if ticari_olmayan_kabul:
            print("Ticari olmayan lisanslar: KABUL EDİLDİ")
        print("=" * 60)
        print()
        
        onay = input("Kurulumu başlatmak istiyor musunuz? [E/h]: ").strip().lower()
        if onay not in ('e', 'evet', 'y', 'yes'):
            print("Kurulum iptal edildi.")
            return
        
        # Kurulumu başlat
        self._kurulumu_baslat(adimlar, ticari_olmayan_kabul, venv_yolu)
    
    def _gpu_tespit(self):
        try:
            sonuc = subprocess.run(['nvidia-smi'], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE, 
                                 timeout=5)
            return sonuc.returncode == 0
        except:
            return False
    
    def _ozel_kurulum(self, gpu_var):
        adimlar = []
        print("\n" + "=" * 60)
        print("ÖZEL KURULUM - Bileşen Seçimi")
        print("=" * 60)
        
        # Temel bileşenler (zorunlu)
        print("\n[TEMEL BİLEŞENLER - ZORUNLU]")
        print("- uv, python, paketler, modeller, kontrol")
        adimlar.extend(["uv", "python", "paketler", "modeller", "kontrol"])
        print("[EKLENDİ]")
        
        # İsteğe bağlı bileşenler
        print("\n[İSTEĞE BAĞLI BİLEŞENLER]")
        
        secenekler = [
            ("demucs", "Ses temizliği (müzik/gürültü ayırma)"),
            ("youtube", "YouTube'dan video indirme"),
            ("parakeet", "Parakeet STT (İngilizce, CPU)"),
            ("akilli-kare", "Akıllı kare kırpma"),
            ("galeri", "Galeri indirme (gallery-dl)"),
            ("telegram", "Telegram botu"),
            ("telegram-sunucu", "Telegram yerel Bot API sunucusu (2000MB)"),
            ("hizalama-diller", "Ek dil modelleri (ja, zh)"),
        ]
        
        if gpu_var:
            secenekler.extend([
                ("tts-ema", "EMA Lightning TTS (Türkçe, alternatif ses)"),
                ("voxcpm2", "VoxCPM2 TTS (Çok dilli, ses klonlama)"),
                ("crisper", "CrisperWhisper Turbo (Daha hassas, TİCARİ OLMAYAN)"),
            ])
        else:
            secenekler.extend([
                ("tts-ema", "EMA Lightning TTS (Türkçe, alternatif ses)"),
            ])
        
        secenekler.append(("tts-xtts", "XTTS v2 (TİCARİ OLMAYAN)"))
        
        for i, (adim_adi, aciklama) in enumerate(secenekler, 1):
            print(f"{i}. {adim_adi} - {aciklama}")
        
        print("\n0. Tamam")
        print()
        
        while True:
            try:
                secim = input("Eklemek istediğiniz bileşen numarası (0 = tamam): ").strip()
                if secim == "0":
                    break
                idx = int(secim) - 1
                if 0 <= idx < len(secenekler):
                    adim_adi = secenekler[idx][0]
                    if adim_adi not in adimlar:
                        adimlar.append(adim_adi)
                        print(f"[EKLENDİ] {adim_adi}")
                    else:
                        print(f"[ZATEN EKLİ] {adim_adi}")
                else:
                    print("Geçersiz numara")
            except ValueError:
                print("Geçersiz numara")
            except EOFError:
                break
        
        # telegram-sunucu seçildiyse telegram da ekle
        if "telegram-sunucu" in adimlar and "telegram" not in adimlar:
            adimlar.append("telegram")
            print("[OTOMATİK EKLENDİ] telegram (telegram-sunucu için gerekli)")
        
        print(f"\nSeçilen adımlar: {', '.join(adimlar)}")
        return adimlar
    
    def _kurulumu_baslat(self, adimlar, ticari_olmayan_kabul, venv_yolu=""):
        print("\n" + "=" * 60)
        print("KURULUM BAŞLATILIYOR")
        print("=" * 60)
        print()
        
        if not self.kur_ps1.exists():
            print(f"HATA: {self.kur_ps1} bulunamadı!")
            return
        
        adim_str = ",".join(adimlar)
        
        # PowerShell komutunu hazırla
        if platform.system() == "Windows":
            cmd = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", str(self.kur_ps1),
                "-Adim", adim_str
            ]
            if ticari_olmayan_kabul:
                cmd.append("-TicariOlmayanKabul")
            if venv_yolu:
                cmd.extend(["-VenvYolu", venv_yolu])
            
            print(f"Çalıştırılan komut: {' '.join(cmd)}")
            print()
            print("Kurulum başlatılıyor... (bu işlem uzun sürebilir)")
            print()
            
            try:
                # Kurulumu çalıştır
                sonuc = subprocess.run(cmd, cwd=str(self.repo_root))
                if sonuc.returncode == 0:
                    print("\n" + "=" * 60)
                    print("KURULUM TAMAMLANDI")
                    print("=" * 60)
                    print("\nWeb arayüzünü açmak için web.cmd dosyasına çift tıklayabilirsiniz.")
                else:
                    print("\n" + "=" * 60)
                    print("KURULUM SIRASINDA HATA OLUŞTU")
                    print("=" * 60)
                    print("Detaylar için yukarıdaki çıktıyı kontrol edin.")
            except Exception as e:
                print(f"HATA: {e}")
        else:
            print("Bu sihirbaz şu anda sadece Windows'ta çalışmaktadır.")
            print(f"Manuel olarak aşağıdaki komutu çalıştırabilirsiniz:")
            venv_param = f" -VenvYolu \"{venv_yolu}\"" if venv_yolu else ""
            print(f"powershell -NoProfile -ExecutionPolicy Bypass -File scripts/kur.ps1 -Adim {adim_str}" +
                  (" -TicariOlmayanKabul" if ticari_olmayan_kabul else "") + venv_param)


def main():
    try:
        sihirbaz = KurulumSihirbazi()
        sihirbaz.calistir()
    except KeyboardInterrupt:
        print("\n\nKurulum kullanıcı tarafından iptal edildi.")
    except Exception as e:
        print(f"\nHATA: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
