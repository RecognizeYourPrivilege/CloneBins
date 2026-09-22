# Baked face models

Release builds download the seven OpenCV zoo ONNX weights into this directory
(`apps/desktop/scripts/fetch-bundled-models.sh`) and copy them into the app:

| Package | Where the weights land |
| --- | --- |
| macOS `.app` | `Contents/Resources/models/` |
| Ubuntu deb, Arch, AppImage | `/usr/share/clonebins/models/` |
| Windows NSIS and portable zip | `models/` next to `CloneBins.exe` |
| Docker | `/opt/clonebins/models` (also seeded into `/models`) |

The files are gitignored (`*.onnx`). A fresh install still uses the user cache
`~/.cache/clonebins/models` (or `CLONEBINS_MODELS_DIR`). On first launch and on
**Verify**, CloneBins copies baked files into that cache and downloads only
what is still missing.
