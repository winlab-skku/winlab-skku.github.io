# WIn Lab website

Wireless Intelligence Lab, Sungkyunkwan University — https://winlab-skku.github.io/

This repository holds both the published site and the tools to edit it.
GitHub Pages is set to serve the **`docs/`** folder (Settings → Pages → Branch: main, Folder: /docs).

```
docs/                    the website (generated — do not edit by hand)
data/site.json           members, alumni, news, research areas, site text, settings
data/publications.json   publication list
docs/assets/photos/      member photos (<english-name-lowercase>.jpg, auto-resized on build)
build.py                 turns data/ into docs/
admin.py + admin/        local editing UI; WInLabAdmin.exe is the same thing packaged
make-exe.bat / .sh       builds WInLabAdmin.exe (once, on a PC with Python)
```

## How to update the site
1. Get the latest copy of this repository (GitHub Desktop → Fetch/Pull, or Code → Download ZIP).
2. Double-click `WInLabAdmin.exe` (or `python admin.py` with Python 3 + `pip install pillow`).
3. Edit in the browser and click **저장 + 빌드** (Ctrl+S). Preview at http://localhost:8765/.
4. Commit and push the whole folder (or upload the changed files: `data/*.json`, `docs/**`).

Always start from the latest copy — `data/*.json` is the source of truth, and it lives here in the repo,
so whoever edited last, the next person continues from their version.
