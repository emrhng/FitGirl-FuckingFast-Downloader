# FitGirl FuckingFast Downloader

One script. Run it, paste the link of the page that holds the
**fuckingfast.co** links, and it downloads the whole repack for you — setup,
link scraping, Cloudflare Turnstile bypass and parallel downloading included.

```bash
python fitgirl.py
```

```
==============================================================
 FitGirl FuckingFast Downloader
==============================================================
 Paste the link of the page that holds the fuckingfast.co links
 (a pastebin link, a FitGirl paste page, ...) and press ENTER.

 Link: https://pastebin.com/XXXXXXXX
```

That's all you have to do. On the first run it installs what it needs
(`requests`, `playwright` and Chromium) by itself.

## What it does

1. Reads the page you gave it and collects every `fuckingfast.co` link.
2. Opens Chromium and passes the Turnstile challenge for each link. Leave the
   window alone — it closes itself.
3. Downloads the files **while** the remaining links are still being resolved,
   using the original filenames, into `downloads/<game name>/`.

## Requirements

Python 3.8 or newer. Nothing else — packages install themselves on first run.

Prefer to install them yourself, or hit a permissions error?

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Resuming

Stop it any time with `Ctrl+C` and run it again — finished files are skipped
and a half-downloaded file continues where it left off. Failed or unresolved
links are retried automatically, and running the program again picks up
whatever is still missing.

## Options

You never need these, but they're there:

| Option | Description | Default |
| --- | --- | --- |
| `-o, --output-dir` | Where to save files | `downloads/<game name>` |
| `-w, --workers` | Parallel downloads | `6` |
| `--wait` | Seconds given to the Turnstile challenge | `6` |
| `--no-rename` | Keep the server's hashed filenames | off |

You can also skip the prompt, or feed it a file that already contains links:

```bash
python fitgirl.py https://pastebin.com/XXXXXXXX
python fitgirl.py links.txt -o "D:/Games" -w 8
```

## Notes

- Chromium has to be **visible** for the Turnstile challenge to pass, so run
  this on a machine with a desktop.
- More than ~8 parallel downloads tends to trigger rate limiting.
- When it's done, extract the `.rar` files with WinRAR or 7-Zip.

---

## Türkçe

Tek dosya. Çalıştır, fuckingfast.co linklerinin bulunduğu sayfanın linkini
yapıştır, gerisini kendi yapar — kurulum, link bulma, Cloudflare Turnstile
aşma ve paralel indirme dahil.

```bash
python fitgirl.py
```

Sonra sadece linki yapıştırıp ENTER'a bas. İlk çalıştırmada gerekenleri
(`requests`, `playwright`, Chromium) kendisi kurar. **Python 3.8+** dışında
hiçbir şeye gerek yok.

**Ne yapıyor:** Verdiğin sayfadaki tüm `fuckingfast.co` linklerini toplar →
Chromium açıp her biri için Turnstile'ı geçer (pencereye dokunma, kendi
kapanır) → dosyaları orijinal isimleriyle `downloads/<oyun adı>/` klasörüne
indirir. Kalan linkler çözülürken indirme aynı anda sürer, o yüzden bekleme
süresi neredeyse yarıya iner.

**Yarıda kalırsa:** `Ctrl+C` ile durdurup tekrar çalıştır — inmiş dosyalar
atlanır, yarım kalan dosya kaldığı yerden devam eder. Başarısız linkler
otomatik tekrar denenir.

**İsteğe bağlı:** İndirme klasörünü değiştirmek için
`python fitgirl.py -o "D:/Oyunlar"`, paralel indirme sayısı için `-w 8`.
Linki komut satırından da verebilirsin:
`python fitgirl.py https://pastebin.com/XXXXXXXX`

İndikten sonra `.rar` dosyalarını WinRAR / 7-Zip ile aç.
