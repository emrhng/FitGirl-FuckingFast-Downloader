# FitGirl FuckingFast Downloader

FitGirl repack paste linklerindeki tüm dosyaları otomatik indirme aracı.

## Nasıl Çalışır?

1. **FitGirl paste linkini** tarayıcıda aç, tüm `fuckingfast.co` linklerini kopyala
2. `urls.txt` dosyasına yapıştır (her satıra bir link)
3. `debug.py` çalıştır → Cloudflare aşılır, direkt download linkleri `direct_links.txt`ye yazılır
4. `download_renamed.py` çalıştır → Tüm dosyalar orijinal isimleriyle `E:\f` klasörüne iner

## Gereksinimler

```bash
pip install requests beautifulsoup4 playwright
python -m playwright install chromium
```

## Kullanım

### Adım 1: Linkleri hazırla

FitGirl paste sayfasındaki tüm linkleri `urls.txt` dosyasına kopyala.

### Adım 2: Direkt linkleri çıkar

```bash
python debug.py
```

Bu aşama her link için Chromium açıp Cloudflare Turnstile'ı çözer. 
186 link yaklaşık 25-30 dakika sürer.

### Adım 3: İndir

```bash
python download_renamed.py
```

Tüm dosyalar `E:\f` klasörüne orijinal isimleriyle (`.partXXX.rar`) iner. 
8 paralel indirme, ~15-20 dakika.

### İndirme klasörünü değiştirmek için

`download_renamed.py` içindeki `OUTPUT_DIR` değişkenini değiştir.

## İndirme Sonrası

Tüm `.rar` dosyalarını WinRAR ile aç, içinden `setup.exe` çıkacak.

## NOT

- fuckingfast.co Cloudflare Turnstile kullanır, bu yüzden Playwright/Chromium şart
- `direct_links.txt` bir kere oluştu mu, tekrar `debug.py` çalıştırmaya gerek yok
- `download_renamed.py` zaten inmiş dosyaları skip eder, yarım kalanları tekrar indirir
- 16 thread rate limiting yiyor, 8 thread optimal
