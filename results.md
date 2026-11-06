# SuperDrag end-to-end test — 25/44 passed

| # | Where | Scenario | Result | Detail | Time |
|---|---|---|---|---|---|
| 1 | explorer | JPG → PNG | ✅ | Photo.png · 2400×1600 | 9.6s |
| 2 | explorer | JPG → WEBP | ✅ | Photo.webp · 2400×1600 | 6.0s |
| 3 | explorer | JPG → HEIC | ✅ | Photo.heic · 2400×1600 | 7.2s |
| 4 | explorer | JPG → TIFF | ✅ | Photo.tiff · 2400×1600 | 5.4s |
| 5 | explorer | JPG → AVIF | ✅ | Photo.avif · 2400×1600 | 6.3s |
| 6 | explorer | JPG → BMP | ✅ | Photo.bmp · 2400×1600 | 5.4s |
| 7 | explorer | JPG → PDF | ✅ | Photo.pdf · 1 page(s) | 5.4s |
| 8 | explorer | JPG → ICO | ✅ | Photo.ico · 128×86 | 5.4s |
| 9 | explorer | JPG → GIF | ✅ | Photo.gif · 2400×1600 | 5.6s |
| 10 | explorer | PNG → JPG | ✅ | Graphic.jpg · 800×533 | 5.4s |
| 11 | explorer | PDF → JPG (3 pages) | ✅ | 3 × .jpg | 6.5s |
| 12 | explorer | PDF → PNG (3 pages) | ✅ | 3 × .png | 6.8s |
| 13 | explorer | PDF → DOCX | ✅ | Report.docx | 5.7s |
| 14 | explorer | PDF → TXT | ✅ | Report.txt | 5.4s |
| 15 | explorer | DOCX → PDF | ✅ | Letter.pdf · 1 page(s) | 5.4s |
| 16 | explorer | DOCX → TXT | ✅ | Letter.txt | 5.4s |
| 17 | explorer | TXT → PDF | ✅ | Notes.pdf · 1 page(s) | 5.4s |
| 18 | explorer | TXT → DOCX | ✅ | Notes.docx | 5.4s |
| 19 | explorer | 2 images → 1 PDF | ✅ | 2 images → 2-page PDF | 7.4s |
| 20 | explorer | Compress to 200 KB | ❌ | RuntimeError: window not found: Compress.* | 18.5s |
| 21 | explorer | Resize 50% | ❌ | RuntimeError: window not found: Resize.* | 18.5s |
| 22 | explorer | Crop 1:1 | ❌ | RuntimeError: window not found: Crop Image.* | 18.6s |
| 23 | explorer | Edit: auto + rotate | ❌ | RuntimeError: window not found: Edit.* | 18.4s |
| 24 | explorer | Annotate | ❌ | RuntimeError: window not found: Annotate.* | 19.2s |
| 25 | explorer | Redact | ❌ | RuntimeError: window not found: Redact.* | 18.4s |
| 26 | explorer | Add BG 1:1 | ❌ | RuntimeError: window not found: Add BG.* | 18.5s |
| 27 | explorer | Metadata: remove location | ❌ | RuntimeError: window not found: Metadata.* | 18.6s |
| 28 | explorer | Metadata: remove all | ❌ | RuntimeError: window not found: Metadata.* | 18.7s |
| 29 | explorer | PDF Compress | ✅ | 227 KB → 232 KB | 6.4s |
| 30 | explorer | PDF Split | ❌ | AssertionError: 0 PDFs | 12.0s |
| 31 | explorer | PDF Rotate | ❌ | AssertionError:  | 9.1s |
| 32 | explorer | PDF Protect | ❌ | RuntimeError: window not found: Password-protect.* | 18.6s |
| 33 | explorer | PDF Extract images | ❌ | AssertionError:  | 7.0s |
| 34 | explorer | PDF Metadata | ❌ | RuntimeError: window not found: Metadata.* | 18.5s |
| 35 | explorer | Merge 2 PDFs | ❌ | AssertionError: 1 pages, expected 5 | 10.6s |
| 36 | send-to | Send To → PNG | ✅ | Photo.png · 2400×1600 | 5.6s |
| 37 | desktop | Desktop: JPG → PNG | ✅ | D-Photo.png · 2400×1600 | 5.9s |
| 38 | desktop | Desktop: PDF → TXT | ✅ | D-Report.txt | 5.0s |
| 39 | desktop | Desktop: DOCX → PDF | ✅ | D-Letter.pdf · 1 page(s) | 5.1s |
| 40 | desktop | Desktop: Compress | ❌ | RuntimeError: window not found: Compress.* | 18.2s |
| 41 | desktop | Desktop: Crop | ❌ | RuntimeError: window not found: Crop Image.* | 18.2s |
| 42 | desktop | Desktop: Add BG | ❌ | RuntimeError: window not found: Add BG.* | 18.1s |
| 43 | desktop | Desktop: 2 PDFs merge | ❌ | AssertionError: 1 pages, expected 5 | 9.7s |
| 44 | all | Drag picture kept out of the glass | ✅ | hidden during 42 menu captures | 0s |