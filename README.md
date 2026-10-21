# SuperDrag

<p align="center">
  <img src="dragshift/assets/superdrag.png" alt="SuperDrag Icon" width="128" height="128"><br>
  <b>Fluid 3D Liquid-Glass Drag-and-Drop Conversion & Productivity Utility</b><br>
  <i>Created by <b>Manish</b></i>
</p>

<p align="center">
  <a href="https://github.com/officialgodgoku/SuperDrag/releases/latest"><img src="https://img.shields.io/badge/version-1.1.0-blue.svg?style=flat-square" alt="Version 1.1.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg?style=flat-square" alt="License MIT"></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.11+-3776AB.svg?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://buymeacoffee.com/officialgodgoku"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=flat-square&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
</p>

---

SuperDrag lets you convert, compress, edit, and organize files on **Windows, macOS, and Linux** using an intuitive, real-time liquid-glass radial dial. Start dragging any file, press **Shift** (or **Ctrl** / **Alt**), and drop it onto a slice. 

Original files are **never overwritten or altered** — outputs are always cleanly generated next to the source.

---

## 🌟 Visual Showcase

### Liquid-Glass Radial Menu
Refracts desktop windows with real-time chromatic dispersion and adaptive frosted glass:
![SuperDrag Radial Menu](docs/preview.png)

### SuperDrag Hub
A dedicated desktop drop zone and control center for fast conversions:
![SuperDrag Hub](docs/hub_window.png)

### AI Background Removal ("Remove BG")
Isolate subjects and cut out backgrounds with ONNX neural segmentation and instant transparency checkerboard preview:
![SuperDrag Remove BG Tool](docs/remove_bg_tool.png)

### About & Support
![About SuperDrag](docs/about_window.png)

---

## 🚀 Key Features

- **Liquid-Glass Radial Dial**:
  - **Convert Ring (`Shift + Drag`)**: Universal conversion across 40+ file formats (Images, Video, Audio, PDF, Office documents, Archives).
  - **Actions Ring (`Ctrl + Drag`)**: LocalSend / AirDrop sharing, Floating Desktop Shelf, Clipboard Copy, Terminal Open, Path Copy.
  - **Tools Ring (`Alt + Drag`)**: Compress, Resize, Crop, Edit, Annotate, Redact, Add BG, and Remove BG.
  - Multi-file center dwell ring switching with smooth 900–1200ms debounce.
- **AI Background Removal**:
  - Deep-learning salient object detection (`u2netp` ONNX model bundled offline).
  - High-performance Color Key & Chroma Matting with custom click-to-pick eyedropper.
  - Real-time Sensitivity, Edge Softness (Gaussian feathering), and Defringing/Erosion controls.
  - One-click copy transparent PNG to clipboard or save to disk.
- **Hardware-Accelerated Video Processing**:
  - Optional GPU encoding with NVIDIA NVENC (`h264_nvenc`, `hevc_nvenc`), Intel QuickSync (`h264_qsv`), AMD AMF (`h264_amf`), and Apple VideoToolbox (`h264_videotoolbox`).
  - Video presets configurable from `veryfast` down to `slower` for precise speed vs file-size balance.
- **Audio & Media Suite**:
  - Peak volume normalization, waveform visualizer generation, audio bleep tone censorship, mono/stereo conversion.
- **PDF & Document Tools**:
  - Lossless and lossy PDF compression, AES-256 encryption, page rotation, splitting, and multi-file PDF merging.
- **Universal Archive Management**:
  - Extract archives with one click; compress folders into standard ZIP, TAR, TAR.GZ, BZIP2, or LZMA ultra.

---

## 📥 Download & Install

From the [**Latest Releases**](https://github.com/officialgodgoku/SuperDrag/releases/latest):

### Windows (Recommended)
- **`SuperDrag-Setup.exe`**: Per-user silent or wizard installation (no administrator privileges required). Adds Start Menu shortcut, autostart option, and Explorer integration.
- **`SuperDrag.exe`**: Portable standalone executable. Run anywhere without installing.

### macOS (macOS 11+)
- **`SuperDrag-mac-apple-silicon.dmg`**: For M1, M2, M3, M4 Macs.
- **`SuperDrag-mac-intel.dmg`**: For Intel Macs.
- Or install via Terminal:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/officialgodgoku/SuperDrag/main/install-mac.sh | bash
  ```

### Linux (Debian, Ubuntu, Mint, XFCE/KDE/GNOME)
- Download `SuperDrag-linux-amd64.deb` and install:
  ```bash
  sudo apt install ./SuperDrag-linux-amd64.deb
  ```

---

## ⌨ Shortcuts & Usage

| Trigger | Dial / Action | Capabilities |
|---|---|---|
| **`Shift + Drag`** | **Convert Dial** | Image formats (PNG, JPG, WEBP, HEIC, AVIF, TIFF, BMP, ICO), Video formats (MP4, WEBM, MOV, MKV), Audio (MP3, WAV, FLAC, M4A), Docs (DOCX, PDF, TXT) |
| **`Ctrl + Drag`** | **Actions Dial** | Send via LocalSend, Pin to Floating Shelf, Copy to Clipboard, Reveal Path, Open Terminal |
| **`Alt + Drag`** | **Tools Dial** | Compress, Resize, Crop, Annotate, Redact, Add BG, Remove BG, Metadata Cleaner |
| **Double-Click Tray** | **SuperDrag Hub** | Quick desktop drag-and-drop workspace and preferences |

---

## ☕ Support & Contribute

SuperDrag is free and open-source software created by **Manish**.

If SuperDrag saves you time or boosts your workflow, consider supporting development:

<p align="center">
  <a href="https://buymeacoffee.com/officialgodgoku">
    <img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Support on Buy Me a Coffee">
  </a>
</p>

You can also contribute code, report bugs, or propose new features:
- Read our [**Contributing Guide**](CONTRIBUTING.md)
- Submit a [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) or [Feature Request](.github/ISSUE_TEMPLATE/feature_request.md)

---

## 🛠 Run from Source

```bash
# Clone the repository
git clone https://github.com/officialgodgoku/SuperDrag.git
cd SuperDrag

# Install dependencies
pip install -r requirements.txt

# Run SuperDrag
python run.py
```

Run test suite:
```bash
python -m pytest tests/
```

---

## 👤 Author

Created by **Manish** ([@officialgodgoku](https://github.com/officialgodgoku))

## 📄 License

Licensed under the [MIT License](LICENSE). Free to use, modify, and distribute.

