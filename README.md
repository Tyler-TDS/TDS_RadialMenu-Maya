[![Watch Demo](https://img.shields.io/badge/-Watch%20Demo-red?style=for-the-badge&logo=vimeo&logoColor=white&labelColor=555555)](https://vimeo.com/1113096256)

# TDS-Radial Menu for Maya

A fast, JSON‑driven radial menu for Autodesk Maya with an optional editor UI and RMB‑hold summoning. Built with PySide2 and plain Maya `cmds`.

## Features
- **Inner / outer ring** with nested children; hover to reveal children, release to run.
- **Preset system** (scroll wheel to swap presets) with per‑preset colours, global size controls.
- **Editor UI** to add/remove/reorder sectors and edit commands and descriptions.

> ⚠️ **Note:** The included editor UI is still a *work in progress*.  
> The radial menu itself is fully functional, but expect changes and improvements to the UI in future updates.

---

## Installation

> Works on Maya 2020+ (PySide2). Tested on Windows.

1) Download and place the folder `TDS_library/TDS_radialMenu` in Maya Python Path (`Documents/maya/scripts`).  
2) Run Quick Start

---

## Quick Start

- Activate Radial Menu:
```python
from TDS_library.TDS_radialMenu import radialMenu_main as rm
rm.install_rmb_hold_detector()
```

- Toggle or force the active state:
```python
rm.launch_or_toggle_radial()        # toggle
rm.launch_or_toggle_radial(True)    # force ON
rm.launch_or_toggle_radial(False)   # force OFF
```

- Uninstall from current Maya:
```python
rm.uninstall_radial_menu()
```

Swap presets on the fly:
```python
from TDS_library.TDS_radialMenu.radialMenu_main import select_preset
select_preset("Rigging")
```

### Editor UI

```python
from TDS_library.TDS_radialMenu import show_window
show_window()
```
The editor lets you change labels, descriptions, commands, colours and global size (radius, ring gap, outer width, child angle multiplier).

---

See `CHANGELOG.md` for released changes.

---

## License
MIT — see [LICENSE](LICENSE).
