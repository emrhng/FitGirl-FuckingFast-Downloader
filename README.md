# FitGirl FuckingFast Downloader

Bulk-download every file from a FitGirl repack **fuckingfast.co** paste, with
original filenames restored. Works on Windows, macOS and Linux.

fuckingfast.co hides downloads behind a Cloudflare Turnstile challenge, so the
tool works in two steps: `extract_links.py` opens a real browser to pass the
challenge and collect the direct links, then `download.py` downloads them in
parallel.

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Python 3.8+ required.

## Usage

```bash
cp urls.example.txt urls.txt   # paste your fuckingfast.co links into urls.txt
python extract_links.py        # solve Turnstile, write direct_links.txt
python download.py             # download everything into ./downloads
```

Both steps are resumable — just run them again to continue. Re-run only the
failed links with `python extract_links.py --retry-failed`.

## Options

Set these on the command line; no need to edit the code.

| Script | Option | Description | Default |
| --- | --- | --- | --- |
| extract_links.py | `-i, --input` | Input links file | `urls.txt` |
| extract_links.py | `--retry-failed` | Re-run only failed URLs | off |
| download.py | `-o, --output-dir` | Where to save files | `downloads` |
| download.py | `-w, --workers` | Parallel downloads | `8` |

Run either script with `--help` to see all options.

## Notes

- Run `extract_links.py` on a machine with a desktop — the browser must be
  visible for the Turnstile challenge to pass reliably.
- Once `direct_links.txt` exists you don't need to run `extract_links.py` again.
- When done, extract the downloaded `.rar` files with WinRAR / 7-Zip.

## Türkçe

fuckingfast.co linklerindeki tüm dosyaları orijinal isimleriyle toplu indirir.

```bash
pip install -r requirements.txt
python -m playwright install chromium

cp urls.example.txt urls.txt   # linkleri urls.txt içine yapıştır
python extract_links.py        # Turnstile geçilir, direct_links.txt oluşur
python download.py             # dosyalar ./downloads klasörüne iner
```

İki adım da kaldığı yerden devam eder, tekrar çalıştırman yeterli. Başarısız
linkler için: `python extract_links.py --retry-failed`. İndirme klasörünü
değiştirmek için: `python download.py -o "D:/Oyunlar"`. İndikten sonra `.rar`
dosyalarını WinRAR / 7-Zip ile aç.
