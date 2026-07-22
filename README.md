# FitGirl FuckingFast Downloader

Bulk-download every file from a FitGirl repack **fuckingfast.co** paste, with
original filenames restored. Works on Windows, macOS and Linux.

*Türkçe açıklama aşağıda.*

---

## How it works

fuckingfast.co puts every download behind a Cloudflare Turnstile challenge, so
you can't grab the files with a plain HTTP request. The tool solves this in two
steps:

1. **`extract_links.py`** opens a real Chromium browser, passes the Turnstile
   challenge for each link, and writes the direct download URLs to
   `direct_links.txt`.
2. **`download.py`** downloads those direct URLs in parallel and saves each file
   under its original name (`.part001.rar`, etc.).

## Requirements

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Python 3.8+ is required.

## Usage

### 1. Add your links

Copy `urls.example.txt` to `urls.txt` and paste your fuckingfast.co links into
it (one per line):

```bash
cp urls.example.txt urls.txt      # Windows: copy urls.example.txt urls.txt
```

Open the FitGirl paste page in your browser, copy every `fuckingfast.co` link,
and paste them into `urls.txt`.

### 2. Extract the direct links

```bash
python extract_links.py
```

A Chromium window opens and solves the Turnstile challenge for each link.
Expect roughly 8–10 seconds per link. Results are written to `direct_links.txt`
as they succeed, so it's safe to stop and resume.

Re-run only the links that failed:

```bash
python extract_links.py --retry-failed
```

### 3. Download

```bash
python download.py
```

Files are saved to a `downloads/` folder next to the scripts, using 8 parallel
downloads. Already-downloaded files are skipped, so you can re-run it to resume.

## Options

Both scripts take command-line options — no need to edit the code.

**extract_links.py**

| Option | Description | Default |
| --- | --- | --- |
| `-i, --input` | Input file with fuckingfast.co links | `urls.txt` |
| `-o, --output` | Output file for direct links | `direct_links.txt` |
| `--retry-failed` | Re-run only the URLs in the failed file | off |
| `--headless` | Run the browser hidden (may fail Turnstile) | off |
| `--wait` | Seconds to wait for the Turnstile challenge | `6` |

**download.py**

| Option | Description | Default |
| --- | --- | --- |
| `-o, --output-dir` | Folder to save files into | `downloads` |
| `-w, --workers` | Number of parallel downloads | `8` |
| `-i, --input` | File with direct links | `direct_links.txt` |
| `--no-rename` | Keep the hashed filenames | off |

Example — download to a custom folder with 4 workers:

```bash
python download.py -o "D:/Games/Spider-Man" -w 4
```

## After downloading

Open the `.rar` files with WinRAR / 7-Zip and run the extracted `setup.exe`.

## Notes

- The browser must be visible (not headless) for the Turnstile challenge to
  pass reliably, so run `extract_links.py` on a machine with a desktop.
- Once `direct_links.txt` exists you don't need to run `extract_links.py`
  again — the direct links stay valid for a while.
- More than ~8 parallel downloads tends to hit rate limiting; 8 is a good
  default.

---

## Türkçe

FitGirl repack **fuckingfast.co** paste linklerindeki tüm dosyaları, orijinal
isimleriyle toplu indirir. Windows, macOS ve Linux'ta çalışır.

### Nasıl çalışır?

fuckingfast.co her linki Cloudflare Turnstile'ın arkasına koyar, bu yüzden
dosyaları düz bir HTTP isteğiyle alamazsın. Araç bunu iki adımda çözer:

1. **`extract_links.py`** gerçek bir Chromium tarayıcı açar, her link için
   Turnstile'ı geçer ve direkt indirme linklerini `direct_links.txt`'ye yazar.
2. **`download.py`** bu linkleri paralel olarak indirir ve her dosyayı orijinal
   ismiyle kaydeder.

### Kurulum

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### Kullanım

1. `urls.example.txt` dosyasını `urls.txt` olarak kopyala ve fuckingfast.co
   linklerini (her satıra bir tane) içine yapıştır.
2. `python extract_links.py` çalıştır → tarayıcı açılır, direkt linkler
   `direct_links.txt`'ye çıkar. Başarısız olanları `python extract_links.py
   --retry-failed` ile tekrar dene.
3. `python download.py` çalıştır → dosyalar `downloads/` klasörüne iner.
   Yarım kalanları atlar, tekrar çalıştırınca kaldığı yerden devam eder.

İndirme klasörünü değiştirmek için: `python download.py -o "D:/Oyunlar"`

### İndirme sonrası

Tüm `.rar` dosyalarını WinRAR / 7-Zip ile aç, çıkan `setup.exe`'yi çalıştır.
