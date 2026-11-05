# SuperDrag macOS end-to-end — 11/17 passed

| # | Scenario | Result | Detail | Time |
|---|---|---|---|---|
| 1 | JPG → PNG | ✅ | D-Photo.png · 2400×1600 | 11.0s |
| 2 | JPG → WEBP | ✅ | D-Photo.webp · 2400×1600 | 8.7s |
| 3 | JPG → HEIC | ✅ | D-Photo.heic · 2400×1600 | 10.5s |
| 4 | JPG → PDF | ✅ | D-Photo.pdf · 1 page(s) | 9.4s |
| 5 | PNG → JPG | ✅ | D-Graphic.jpg · 800×533 | 9.2s |
| 6 | PDF → JPG (3 pages) | ✅ | 3 × .jpg | 10.0s |
| 7 | PDF → TXT | ✅ | D-Report.txt | 9.3s |
| 8 | DOCX → PDF | ✅ | D-Letter.pdf · 1 page(s) | 9.2s |
| 9 | PDF Split | ❌ | AssertionError: 0 PDFs | 12.7s |
| 10 | PDF Rotate | ❌ | AssertionError:  | 10.5s |
| 11 | PDF Compress | ✅ | 227 KB → 232 KB | 10.5s |
| 12 | Merge 2 PDFs | ❌ | AssertionError: 1 pages, expected 5 | 14.0s |
| 13 | Compress (window, Enter) | ❌ | AssertionError:  | 12.2s |
| 14 | Resize 50% (window, Enter) | ❌ | AssertionError: (2400, 1600) → (2400, 1600) | 12.5s |
| 15 | Add BG (window, Enter) | ❌ | UnidentifiedImageError: cannot identify image file '/Users/runner/SuperDragTest/D-Graphic.pdf' | 12.7s |
| 16 | Metadata: remove all (Enter) | ✅ | 0 metadata fields left | 12.6s |
| 17 | Slices filled before the mouse moves | ✅ | files read from the drag pasteboard | 0s |