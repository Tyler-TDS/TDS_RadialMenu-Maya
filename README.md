# TDS Radial Menu for Maya (PySide2)

A fast, JSON‑driven radial menu for Autodesk Maya with an optional editor UI and RMB‑hold summoning. Built with PySide2 and plain Maya `cmds`. Presets are stored as ordered JSON so teams can version and review changes easily.

https://user-images.githubusercontent.com/placeholder/demo.gif  <!-- Replace with your GIF/MP4 -->

## Features
- **Inner / outer ring** with nested children; hover to reveal children, release to run.
- **Preset system** (scroll wheel to swap presets) with per‑preset colours, global size controls.
- **Editor UI** to add/remove/reorder sectors and edit commands and descriptions.

---

## Installation (module style)

> Works on Maya 2020+ (PySide2). Tested on Windows.

1) Place the folder `TDS_library/TDS_radialMenu` somewhere on disk (e.g. a pipeline repo).  
2) Add that parent folder to `PYTHONPATH` or Maya's `maya.module` search via a `.mod`:

Example `.mod` file (drop into e.g. `Documents/maya/modules/TDS_RadialMenu.mod`):

```
+ TDS_RadialMenu 1.0.0 any C:/path/to
PYTHONPATH +:= C:/path/to
```

Your package import path ends up as `TDS_library.TDS_radialMenu`.

---

## Quick start

### A) One‑time: install the RMB‑hold detector

```python
from TDS_library.TDS_radialMenu import radialMenu_main as rm
rm.install_rmb_hold_detector()   # adds global event filter
```

- Toggle or force the active state:
```python
rm.launch_or_toggle_radial()        # toggle
rm.launch_or_toggle_radial(True)    # force ON
rm.launch_or_toggle_radial(False)   # force OFF
```
- Remove it completely:
```python
rm.uninstall_radial_menu()
```
These utilities live in `radialMenu_main.py`. fileciteturn0file1

### B) Open the Editor UI

```python
from TDS_library.TDS_radialMenu import show_window
show_window()
```
The editor lets you change labels, descriptions, commands, colours and global size (radius, ring gap, outer width, child angle multiplier). fileciteturn0file3

### C) Presets and JSON

- Active preset is stored at the top level of `radialMenu_info.json` under `active_preset`.
- Global UI size lives under `ui.size` (radius/ring_gap/outer_ring_width/child_angle_multiplier).
- Each preset keeps its own colour block and `inner_section` structure with child commands.
This schema is loaded and backfilled by `_load_data()` and helpers in `radialWidget.py`. fileciteturn0file2 fileciteturn0file0

---

## Shelf / Hotkey snippets

Add a shelf button for the editor:
```python
from TDS_library.TDS_radialMenu import show_window
show_window()
```

Add a shelf toggle for the radial:
```python
from TDS_library.TDS_radialMenu import radialMenu_main as rm
rm.launch_or_toggle_radial()    # toggle
```

Force ON/OFF:
```python
rm.launch_or_toggle_radial(True)   # ON
rm.launch_or_toggle_radial(False)  # OFF
```

Swap presets on the fly:
```python
from TDS_library.TDS_radialMenu.radialMenu_main import select_preset
select_preset("Rigging")
```

---

## Configuration details

- **Live‑reload:** set the Maya optionVar `TDS_RadialLiveReload` to `1` to enable dev‑mode module reloads for `radialWidget`. Use `fresh_radial_cls()` to fetch a reloaded class. fileciteturn0file2
- **Colours:** per‑preset colour keys include `inner_colour`, `innerHighlight_colour`, `innerLine_colour`, `child_colour`, `childLine_colour`, `child_text_color`, `child_textOutline_color`, and `child_outline_thickness`. fileciteturn0file0
- **Sizing:** global `ui.size` keys are `radius`, `ring_gap`, `outer_ring_width`, `child_angle_multiplier`. fileciteturn0file0

---

## Development

Run the editor, tweak JSON, and use the RMB‑hold menu. With live‑reload enabled, the widget will reimport when invoked via the hold callback. Core class is `RadialMenuWidget`. fileciteturn0file2

---

## Roadmap / Ideas
- Optional icons per child.
- Key‑repeat or pie selection by gesture.
- Per‑preset sizing overrides.

See `CHANGELOG.md` for released changes.

---

## License
MIT — see [LICENSE](LICENSE).
