# SuperDrag Debian/XFCE end-to-end — 12/19 passed

Xvfb + xfwm4 (compositor off) + Thunar, driving the installed .deb.

| # | Scenario | Result | Detail | Time |
|---|---|---|---|---|
| 1 | JPG → PNG | ✅ | D-Photo.png · 2400×1600 | 10.1s |
| 2 | JPG → WEBP | ✅ | D-Photo.webp · 2400×1600 | 9.1s |
| 3 | JPG → HEIC | ✅ | D-Photo.heic · 2400×1600 | 10.5s |
| 4 | JPG → PDF | ✅ | D-Photo.pdf · 1 page(s) | 8.9s |
| 5 | PNG → JPG | ✅ | D-Graphic.jpg · 800×533 | 8.9s |
| 6 | PDF → JPG (3 pages) | ✅ | 3 × .jpg | 10.0s |
| 7 | PDF → TXT | ✅ | D-Report.txt | 8.8s |
| 8 | DOCX → PDF | ✅ | D-Letter.pdf · 1 page(s) | 8.8s |
| 9 | TXT → PDF | ✅ | D-Notes.pdf · 1 page(s) | 8.8s |
| 10 | PDF Split | ❌ | AssertionError: 0 PDFs | 10.0s |
| 11 | PDF Rotate | ❌ | AssertionError:  | 11.3s |
| 12 | PDF Compress | ✅ | 227 KB → 232 KB | 9.7s |
| 13 | Merge 2 PDFs | ❌ | AssertionError: 1 pages, expected 5 | 10.8s |
| 14 | Compress (window, Enter) | ❌ | AssertionError:  | 12.4s |
| 15 | Resize 50% (window, Enter) | ❌ | AssertionError: (2400, 1600) → (2400, 1600) | 12.4s |
| 16 | Add BG (window, Enter) | ❌ | UnidentifiedImageError: cannot identify image file '/github/home/SuperDragTest/16/D-Graphic.pdf' | 12.9s |
| 17 | Metadata: remove all (Enter) | ✅ | 0 metadata fields left | 12.2s |
| 18 | PDF Protect (password) | ❌ | AssertionError:  | 12.5s |
| 19 | Open With → AVIF (click) | ✅ | D-Photo.avif · 2400×1600 | 8.7s |