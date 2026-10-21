# Contributing to SuperDrag

Thank you for your interest in contributing to SuperDrag! Whether you're fixing a bug, adding support for new file formats, improving hardware acceleration, or refining the liquid-glass UI, your help is welcome.

---

## Ways to Contribute

- **Report Bugs**: If you encounter crashes, rendering issues, or failed conversions, open an issue with reproduction steps.
- **Suggest Features**: Propose new conversion formats, faster encoders, or action shortcuts.
- **Submit Pull Requests**: Fix issues or implement new capabilities.
- **Improve Documentation**: Enhance guides, code docstrings, and setup steps.
- **Financial Sponsorship**: If you find SuperDrag useful, support ongoing development on [Buy Me a Coffee](https://buymeacoffee.com/officialgodgoku).

---

## Development Setup

### Prerequisites
- **Python 3.11+**
- **Git**
- Optional (for full video conversion tests): System `ffmpeg` (the bundled release includes embedded ffmpeg).

### Step-by-Step Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/<your-username>/SuperDrag.git
   cd SuperDrag
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # macOS / Linux:
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install pytest
   ```

4. **Run SuperDrag in development mode**:
   ```bash
   python run.py
   ```

5. **Run the test suite**:
   ```bash
   pytest
   ```

---

## Code Architecture

- **`run.py`**: Fast IPC hand-off and application launcher.
- **`dragshift/app.py`**: Main application logic, tray icon management, IPC server, window coordinator.
- **`dragshift/radial.py`**: 3D Liquid-Glass radial wheel, spring physics, and typography.
- **`dragshift/liquid.py`**: Chromatic dispersion, signed distance fields (SDF), and glass refraction.
- **`dragshift/trigger.py`**: Low-level mouse drag and modifier key detection (<kbd>Shift</kbd>, <kbd>Ctrl</kbd>, <kbd>Alt</kbd>).
- **`dragshift/convert.py`**: Central conversion dispatch for images, documents, audio, and archives.
- **`dragshift/video.py`**: FFmpeg video compression, GPU hardware acceleration (Intel QuickSync, NVIDIA NVENC, AMD AMF), and CPU fallbacks.
- **`dragshift/settings.py`**: Persistent settings, Settings window, Welcome window, and Hub window.

---

## Pull Request Guidelines

1. **Fork the repo** and create a feature branch (`git checkout -b feature/my-cool-feature`).
2. **Keep originals safe**: SuperDrag has a strict guarantee that source files are never modified or overwritten in-place.
3. **Verify tests**: Ensure `pytest` passes before opening a PR.
4. **Follow conventions**:
   - Clean, readable Python.
   - Preserve backward compatibility with Windows, macOS, and Linux where possible.
5. **Submit your PR** with a clear description of the problem solved and testing steps.
