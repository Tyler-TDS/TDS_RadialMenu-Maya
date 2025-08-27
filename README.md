[![Watch Demo](https://img.shields.io/badge/-Watch%20Demo-1ab7ea?style=for-the-badge&logo=vimeo&logoColor=white&labelColor=555555)](https://vimeo.com/1113096256) [![Fuel My Code](https://img.shields.io/badge/-Fuel%20My%20Code%20-yellow?style=for-the-badge&logo=buymeacoffee&logoColor=white&labelColor=555555)](https://www.buymeacoffee.com/TDS_Tyler)


# TDS-Radial Menu for Maya

*A fast radial menu for Maya to trigger your own tools and commands with a right-click hold.*


## Features
- **Inner / outer ring** with nested children; hover to reveal children, release to run.
- **Preset system** (scroll wheel to swap presets) with per‑preset colours, global size controls.
- **Editor UI** to add/remove/reorder sectors and edit commands and descriptions.

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
