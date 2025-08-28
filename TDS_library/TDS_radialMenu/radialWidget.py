from PySide2 import QtWidgets, QtCore, QtGui
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance
import math
import maya.cmds as cmds
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
menuInfo_filePath = SCRIPT_DIR / "radialMenu_info.json"
from collections import OrderedDict

class _HoleWheelRedirector(QtCore.QObject):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def eventFilter(self, obj, event):
        if event.type() != QtCore.QEvent.Wheel:
            return False

        if not self.owner.isVisible():
            return False

        center = self.owner.mapToGlobal(
            QtCore.QPoint(self.owner.width() // 2, self.owner.height() // 2)
        )
        pos = event.globalPos()
        dist = math.hypot(pos.x() - center.x(), pos.y() - center.y())

        if dist <= self.owner.inner_hole:
            # hand the wheel to the menu
            self.owner.wheelEvent(event)
            return True

        return False

# ---------- PRESET SUPPORT ----------
def _load_data():
    with open(menuInfo_filePath, 'r') as f:
        data = json.load(f, object_pairs_hook=OrderedDict)

    # migrate legacy -> presets schema
    if "presets" not in data:
        data = OrderedDict([
            ("active_preset", "Default"),
            ("presets", OrderedDict([
                ("Default", OrderedDict([
                    ("inner_section", data.get("inner_section", OrderedDict()))
                ]))
            ]))
        ])
        _save_data(data)

    # ensure active preset valid
    if "active_preset" not in data or data["active_preset"] not in data["presets"]:
        first = next(iter(data["presets"].keys()))
        data["active_preset"] = first
        _save_data(data)

    # ensure global ui.size (including child multiplier default)
    ui = data.setdefault("ui", OrderedDict())
    size = ui.setdefault("size", OrderedDict())
    size.setdefault("radius", 150)
    size.setdefault("ring_gap", 5)
    size.setdefault("outer_ring_width", 25)
    size.setdefault("child_angle_multiplier", 1.0)
    size.setdefault("inner_hole_radius", max(0, int(size.get("radius", 150) * 0.35)))

    # BACKFILL: make sure every preset has a colour block
    changed = False
    default_colour = _default_colour_from_data(data)
    for pname, preset in data.get("presets", {}).items():
        if "colour" not in preset:
            preset["colour"] = OrderedDict(default_colour)
            changed = True
        # also ensure inner_section exists
        preset.setdefault("inner_section", OrderedDict())

    if changed:
        _save_data(data)

    return data
from collections import OrderedDict

def _default_colour_from_data(d):

    # hardcoded fallback (keep in sync with your runtime defaults)
    return OrderedDict([
        ("inner_colour", "#454545"),
        ("innerHighlight_colour", "#282828"),
        ("innerLine_colour", "#1E1E1E"),
        ("child_colour", "#5285a6"),      # or "#0018d1" if you prefer your JSON default
        ("childLine_colour", "#1E1E1E"),
        ("child_text_color", "#FFFFFF"),
        ("child_textOutline_color", "#000000"),
        ("child_outline_thickness", 1),
    ])


def _save_data(data):
    with open(menuInfo_filePath, 'w') as f:
        json.dump(data, f, indent=4)

def _active_preset(data):
    return data["presets"][data["active_preset"]]

def get_active_preset():
    return _load_data()["active_preset"]

def list_presets():
    d = _load_data()
    return list(d["presets"].keys())

def set_active_preset(name: str) -> bool:
    d = _load_data()
    if name in d["presets"]:
        d["active_preset"] = name
        _save_data(d)
        return True
    cmds.warning(f"[RadialMenu] Preset '{name}' not found.")
    return False

def create_preset(name: str, clone_from: str = None) -> bool:
    d = _load_data()
    if name in d["presets"]:
        cmds.warning(f"[RadialMenu] Preset '{name}' already exists.")
        return False

    if clone_from and clone_from in d["presets"]:
        # copy all known top-level fields from the source preset
        src = d["presets"][clone_from]
        new_payload = OrderedDict()
        for key in ("inner_section", "colour", "size"):
            val = src.get(key)
            if isinstance(val, dict):
                new_payload[key] = OrderedDict(val)  # preserve order
            elif val is not None:
                new_payload[key] = val
        new_payload.setdefault("inner_section", OrderedDict())
        new_payload.setdefault("colour", _default_colour_from_data(d))
    else:
        # brand new preset with defaults
        new_payload = OrderedDict([
            ("colour", _default_colour_from_data(d)),
            ("inner_section", OrderedDict()),
            # If you want per-preset size, you can seed it here too, but
            # your app currently reads global ui.size, so it's optional:
            # ("size", OrderedDict(d.get("ui", {}).get("size", {}))),
        ])

    d["presets"][name] = new_payload
    _save_data(d)
    return True


def delete_preset(name: str) -> bool:
    d = _load_data()
    if name not in d["presets"]:
        cmds.warning(f"[RadialMenu] Preset '{name}' not found.")
        return False
    if len(d["presets"]) == 1:
        cmds.warning("[RadialMenu] Can't delete the last preset.")
        return False
    del d["presets"][name]
    if d["active_preset"] == name:
        d["active_preset"] = next(iter(d["presets"].keys()))
    _save_data(d)
    return True
# ---------- /PRESET SUPPORT ----------
def _q(val, default_hex):
    c = QtGui.QColor(val) if val else QtGui.QColor(default_hex)
    return c if c.isValid() else QtGui.QColor(default_hex)

# --- hot reload helpers ---
import sys, importlib
PKGS_TO_RELOAD = [
    "TDS_library.TDS_radialMenu.radialWidget",  # <- update to your module(s)
]
RADIAL_MOD   = "TDS_library.TDS_radialMenu.radialWidget"  # where the class lives
RADIAL_CLASS = "RadialMenu"  # or "RadialMenuWidget" if that's your class name

_OPTION_VAR = "TDS_RadialLiveReload"

def set_live_reload(enabled: bool):
    cmds.optionVar(iv=(_OPTION_VAR, 1 if enabled else 0))

def is_live_reload_enabled() -> bool:
    return cmds.optionVar(q=_OPTION_VAR) if cmds.optionVar(exists=_OPTION_VAR) else 0

def fresh_radial_cls():
    if not is_live_reload_enabled():
        # No reload in “prod”—just import and return the class
        mod = importlib.import_module(RADIAL_MOD)
        return getattr(mod, RADIAL_CLASS)

    # Dev mode: do the hot-reload
    for name in sorted([n for n in sys.modules if any(n.startswith(p) for p in PKGS_TO_RELOAD)], reverse=True):
        try:
            importlib.reload(sys.modules[name])
        except Exception:
            pass
    mod = importlib.import_module(RADIAL_MOD)
    return getattr(mod, RADIAL_CLASS)

def get_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QMainWindow)

class RadialMenuWidget(QtWidgets.QWidget):
    trigger_signal = QtCore.Signal(str)
    preset_changed = QtCore.Signal(str)
    preset_previewed = QtCore.Signal(str)

    def __init__(self, parent=None, label_lineEdit=None, hiddenLabel=None,
                 pos_dropdown=None, scriptEditor=None, hiddenType=None, hiddenParent=None,
                 descEditor=None):
        super().__init__(parent)
        self._pad = 8
        self.label_lineEdit = label_lineEdit
        self.pos_dropdown = pos_dropdown
        self.hiddenLabel = hiddenLabel
        self.scriptEditor = scriptEditor
        self.hiddenType = hiddenType
        self.hiddenParent = hiddenParent
        self.descEditor = descEditor
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setMinimumSize(1, 1)  # keep Maya happy but allow shrinking
        self.setMouseTracking(True)

        self.current_parent_label = ""
        self._dragging_label = None
        self._drag_origin_index = -1
        self._drag_hover_target = None

        self._dragging_child = None
        self._child_drag_origin_index = -1
        self._child_drag_hover_target = None
        self._sticky_parent = None  # remembers a clicked inner slice

        self.child_font = QtGui.QFont("Arial")
        self.child_font.setPixelSize(11)
        self.child_font.setKerning(True)
        self.child_font.setHintingPreference(QtGui.QFont.PreferNoHinting)
        self.child_font.setStyleStrategy(QtGui.QFont.PreferAntialias)

        # --- load data first (gets global size too) ---
        data = _load_data()
        preset = _active_preset(data)
        colour_data = preset.get("colour", {})  # <- per-preset colours

        # accept either the old or new keys for text colors
        child_text_fill_hex = colour_data.get("child_text_color", colour_data.get("child_fill_color", "#FFFFFF"))
        child_text_outline_hex = colour_data.get("child_textOutline_color",
                                                 colour_data.get("child_outline_color", "#141414DC"))

        self.inner_colour = _q(colour_data.get("inner_colour"), "#454545")
        self.innerHighlight_colour = _q(colour_data.get("innerHighlight_colour"), "#282828")
        self.innerLine_colour = _q(colour_data.get("innerLine_colour"), "#1E1E1E")

        self.child_colour = _q(colour_data.get("child_colour"), "#CE00FF")
        self.childLine_colour = _q(colour_data.get("childLine_colour"), "#1E1E1E")
        self.child_fill_color = _q(child_text_fill_hex, "#FFFFFF")
        self.child_outline_color = _q(child_text_outline_hex, "#141414DC")
        self.child_outline_thickness = float(colour_data.get("child_outline_thickness", 1.6))
        # Prefer global size; fall back to any legacy per-preset size; then defaults
        size_data = data.get("ui", {}).get("size", {})
        if not size_data:
            # legacy fallback
            size_data = _active_preset(data).get("size", {})
        self.child_angle_mult = float(size_data.get("child_angle_multiplier", 1.0))
        self.radius = size_data.get("radius", 150)
        self.ring_gap = size_data.get("ring_gap", 5)
        self.outer_ring_width = size_data.get("outer_ring_width", 25)
        self.outer_radius = self.radius + self.ring_gap + self.outer_ring_width
        self.inner_hole = int(size_data.get("inner_hole_radius", max(0, int(self.radius * 0.35))))
        self.display_radius = self.radius  # makes resize math safe
        self._preview_name = get_active_preset()

        self.center_pos = QtGui.QCursor.pos()
        extra_height = 80  # Reserve space for description
        self.move(self.center_pos.x() - self.outer_radius, self.center_pos.y() - self.outer_radius - 20)
        self.resize(self.outer_radius * 2, self.outer_radius * 2 + extra_height)
        # now load sections
        self.inner_sections = _active_preset(data).get("inner_section", OrderedDict())

        self.inner_order = list(self.inner_sections.keys())
        self.inner_angles = self.calculate_angles(self.inner_order)

        self.active_sector = None
        self.outer_active_sector = None

        self.hovered_children = None
        self.hovered_child_angles = {}

        self.trigger_signal.connect(self.execute_action)

    def _preview_preset(self, preset_name: str):
        data = _load_data()
        self._preview_name = preset_name  # <— add this line
        preset_data = data["presets"].get(preset_name, OrderedDict())

        self.inner_sections = preset_data.get("inner_section", OrderedDict())
        self.inner_order = list(self.inner_sections.keys())
        self.inner_angles = self.calculate_angles(self.inner_order)

        # 🔹 important: fully clear any prior selection/hover/lock state
        self._clear_selection_state()

        self._apply_preset_colours(preset_data)
        self.update()

    def sizeHint(self):
        d = int(self.outer_radius * 2 + self._pad * 2)
        return QtCore.QSize(d, d)

    def minimumSizeHint(self):
        return self.sizeHint()
        w.update()

    def resizeEvent(self, e):
        QtWidgets.QWidget.resizeEvent(self, e)
        self._recalc_display_metrics()
        self.update()

    def _recalc_display_metrics(self):
        pad = 12  # keep ring off the edges a bit
        desc_px = 22  # reserve a little vertical space for the description text

        w, h = self.width(), self.height()

        # Horizontal radius budget
        horiz_r = max(20, int(w / 2) - pad)
        # Vertical radius budget: reserve some space for the description line
        vert_r = max(20, int(h / 2) - pad - desc_px)

        max_r = min(horiz_r, vert_r)
        base_r = int(getattr(self, "radius", 150))  # your configured/menu radius
        self.display_radius = min(base_r, max_r)
        scale = self.display_radius / float(getattr(self, "radius", 150) or 1)
        self.display_hole = max(0, int(self.inner_hole * scale))



        # All drawing should use display_radius, not raw radius
        self.outer_radius = (
                self.display_radius
                + getattr(self, "ring_gap", 5)
                + getattr(self, "outer_ring_width", 25)
        )

    def _apply_preset_colours(self, preset):
        colour_data = preset.get("colour", {})

        # accept either the old or new keys for text colors
        child_text_fill_hex = colour_data.get("child_text_color", colour_data.get("child_fill_color", "#FFFFFF"))
        child_text_outline_hex = colour_data.get("child_textOutline_color",
                                                 colour_data.get("child_outline_color", "#141414DC"))

        self.inner_colour = _q(colour_data.get("inner_colour"), "#454545B4")
        self.innerHighlight_colour = _q(colour_data.get("innerHighlight_colour"), "#282828B4")
        self.innerLine_colour = _q(colour_data.get("innerLine_colour"), "#1E1E1E")

        self.child_colour = _q(colour_data.get("child_colour"), "#CE00FF")
        self.childLine_colour = _q(colour_data.get("childLine_colour"), "#1E1E1E")
        self.child_fill_color = _q(child_text_fill_hex, "#FFFFFF")
        self.child_outline_color = _q(child_text_outline_hex, "#141414DC")
        self.child_outline_thickness = float(colour_data.get("child_outline_thickness", 1.6))

    def _clear_selection_state(self):
        self._sticky_parent = None
        self.current_parent_label = ""
        self.active_sector = None
        self.outer_active_sector = None
        self.hovered_children = None
        self.hovered_child_angles = {}

    def wheelEvent(self, event: QtGui.QWheelEvent):
        if self._dragging_label or self._dragging_child:
            event.ignore()
            return
        # Only react if the cursor is inside the menu circle
        pos = event.pos()
        c = QtCore.QPoint(self.width() // 2, self.height() // 2)
        if math.hypot(pos.x() - c.x(), pos.y() - c.y()) > self.outer_radius:
            event.ignore()
            return

        # Determine scroll delta
        delta = event.angleDelta().y() or event.angleDelta().x()
        if delta == 0:
            event.ignore()
            return

        # Need at least 2 presets to cycle
        names = list_presets()
        if not names or len(names) == 1:
            event.accept()
            return

        # Use rolling preview anchor so each tick advances correctly
        cur = getattr(self, "_preview_name", None) or get_active_preset()
        try:
            idx = names.index(cur)
        except ValueError:
            # preview anchor out of sync — fall back to active preset
            fallback = get_active_preset()
            idx = names.index(fallback) if fallback in names else 0

        step = -1 if delta < 0 else 1
        new_name = names[(idx + step) % len(names)]
        self._preview_name = new_name  # advance local anchor

        # Preview ONLY (do not save active preset)
        self._preview_preset(new_name)

        # Tell the editor to mirror the name without committing
        try:
            self.preset_previewed.emit(new_name)  # NOTE: NOT preset_changed
        except Exception:
            pass


        event.accept()

    def _angle_from_pos(self, pt):
        c = QtCore.QPoint(self.width() // 2, self.height() // 2)
        dx = pt.x() - c.x()
        dy = pt.y() - c.y()
        return (math.degrees(math.atan2(dy, dx)) + 360) % 360, math.hypot(dx, dy)
    # --- Right-click context menu on inner sectors ---

    def contextMenuEvent(self, event):
        center = QtCore.QPoint(self.width() // 2, self.height() // 2)
        dx = event.pos().x() - center.x()
        dy = event.pos().y() - center.y()
        dist = math.hypot(dx, dy)

        # Compute angle once
        angle = (math.degrees(math.atan2(dy, dx)) + 360) % 360

        inner_radius = self.radius
        outer_inner_radius = self.radius + self.ring_gap
        outer_outer_radius = self.outer_radius

        menu = QtWidgets.QMenu(self)

        # ---------- INNER RING ----------
        if self.active_sector and dist <= inner_radius:
            act_add_child = menu.addAction(f"Add child to '{self.active_sector}'")
            act_remove_inn = menu.addAction(f"Remove '{self.active_sector}'")
            chosen = menu.exec_(event.globalPos())
            if chosen == act_add_child:
                self._add_child_to_active_inner()
            elif chosen == act_remove_inn:
                self._remove_inner(self.active_sector)
            return

        # ---------- OUTER RING (child) ----------
        # Make sure we have children for current parent to compute segment
        if not self.hovered_children and self.active_sector:
            self.hovered_children = self.inner_sections.get(self.active_sector, {}).get("children", {})

        if outer_inner_radius < dist <= outer_outer_radius and self.hovered_children:
            # Try resolve which child this angle hits
            child_label = self.get_outer_sector_from_angle(angle, self.hovered_child_angles)
            if child_label is None:
                # angles cache may be stale; refresh & try again
                self.hovered_child_angles = self.get_child_angles()
                child_label = self.get_outer_sector_from_angle(angle, self.hovered_child_angles)

            if child_label:
                act_remove_child = menu.addAction(f"Remove child '{child_label}'")
                chosen = menu.exec_(event.globalPos())
                if chosen == act_remove_child:
                    self._remove_child(self.active_sector, child_label)

    def _add_child_to_active_inner(self):
        """Create a new child under the currently hovered/active inner section,
        save to JSON, refresh local data, and populate the editor fields."""

        parent_label = self.active_sector
        if not parent_label:
            return


        data, preset, _ = self._get_preset_for_write()
        inner = preset.get("inner_section", OrderedDict())

        parent = inner.get(parent_label)

        if parent is None:
            cmds.warning(f"[RadialMenu] Inner section '{parent_label}' not found.")
            return

        # Ensure children dict exists and is ordered
        children = parent.get("children")
        if not isinstance(children, dict):
            children = OrderedDict()
            parent["children"] = children

        # Unique child label
        base = "new_child"
        i = 1
        new_label = base
        while new_label in children:
            new_label = f"{base}_{i}"
            i += 1

        # Default payload
        children[new_label] = {
            "description": new_label,
            "command": f"print('{new_label}')"
        }

        _save_data(data)
        data = _load_data()
        self.inner_sections = data["presets"][self._preview_name].get("inner_section", OrderedDict())
        self.inner_order = list(self.inner_sections.keys())
        self.inner_angles = self.calculate_angles(self.inner_order)

        # Refresh local caches
        self.hovered_children = self.inner_sections[parent_label].get("children", OrderedDict())
        self.outer_active_sector = new_label  # highlight the new child
        self.update()

        # Fill editor panel just like a click would
        if self.label_lineEdit:
            self.label_lineEdit.setText(new_label)
        if self.hiddenLabel:
            self.hiddenLabel.setText(new_label)
        if self.pos_dropdown:
            self.pos_dropdown.setCurrentText("outer_section")
        if self.scriptEditor:
            self.scriptEditor.setPlainText(self.hovered_children[new_label].get("command", ""))
        if self.hiddenType:
            self.hiddenType.setText("child")
        if self.hiddenParent:
            self.hiddenParent.setText(parent_label)

        if self.descEditor:  # << NEW
            self.descEditor.setText(self.hovered_children[new_label].get("description", ""))

    def _remove_inner(self, label):
        try:
            data, preset, pname = self._get_preset_for_write()  # <- PREVIEW
            inner = preset.get("inner_section", OrderedDict())

            if label not in inner:
                cmds.warning(f"[RadialMenu] Inner '{label}' not found.")
                return

            del inner[label]
            preset["inner_section"] = inner
            _save_data(data)

            # refresh from the same preview preset
            data = _load_data()
            preset = data["presets"].get(pname, OrderedDict())
            self.inner_sections = preset.get("inner_section", OrderedDict())
            self.inner_order = list(self.inner_sections.keys())
            self.inner_angles = self.calculate_angles(self.inner_order)

            self.active_sector = None
            self.hovered_children = None
            self.hovered_child_angles = {}
            self.outer_active_sector = None
            self.update()

            if self.hiddenLabel and self.hiddenLabel.text() == label:
                if self.label_lineEdit: self.label_lineEdit.clear()
                if self.hiddenLabel:    self.hiddenLabel.clear()
                if self.hiddenType:     self.hiddenType.clear()
                if self.hiddenParent:   self.hiddenParent.clear()
                if self.scriptEditor:   self.scriptEditor.clear()
                if self.descEditor:     self.descEditor.clear()
            if self._sticky_parent == label:
                self._sticky_parent = None

        except Exception as e:
            cmds.warning(f"[RadialMenu] Failed to remove inner '{label}': {e}")

    def _remove_child(self, parent_label, child_label):
        try:
            data, preset, pname = self._get_preset_for_write()  # <- PREVIEW
            inner = preset.get("inner_section", OrderedDict())
            parent = inner.get(parent_label)
            if parent is None:
                cmds.warning(f"[RadialMenu] Parent '{parent_label}' not found.")
                return

            children = parent.get("children", OrderedDict())
            if child_label not in children:
                cmds.warning(f"[RadialMenu] Child '{child_label}' not found under '{parent_label}'.")
                return

            del children[child_label]
            if not children:
                parent.pop("children", None)

            preset["inner_section"] = inner
            _save_data(data)

            # refresh from the same preview preset
            data = _load_data()
            preset = data["presets"].get(pname, OrderedDict())
            self.inner_sections = preset.get("inner_section", OrderedDict())

            self.active_sector = parent_label
            self.hovered_children = self.inner_sections.get(parent_label, {}).get("children", {})
            self.hovered_child_angles = self.get_child_angles() if self.hovered_children else {}
            self.outer_active_sector = None
            self.update()

            if self.hiddenLabel and self.hiddenLabel.text() == child_label:
                if self.hiddenType:   self.hiddenType.setText("inner")
                if self.hiddenParent: self.hiddenParent.setText("")
                if self.hiddenLabel:  self.hiddenLabel.setText(parent_label)
                if self.label_lineEdit: self.label_lineEdit.setText(parent_label)
                parent_cmd = self.inner_sections.get(parent_label, {}).get("command", "")
                if self.scriptEditor is not None:
                    self.scriptEditor.setPlainText(parent_cmd)
                if self.descEditor:
                    parent_desc = self.inner_sections.get(parent_label, {}).get("description", "")
                    self.descEditor.setText(parent_desc)

        except Exception as e:
            cmds.warning(f"[RadialMenu] Failed to remove child '{child_label}': {e}")


    def mousePressEvent(self, event):
        # --- MMB: drag-reorder inner/child (unchanged) ---
        if event.button() == QtCore.Qt.MiddleButton:
            angle, dist = self._angle_from_pos(event.pos())
            outer_inner_radius = self.radius + self.ring_gap
            outer_outer_radius = self.outer_radius

            # start inner drag
            if dist <= self.radius and self.inner_order:
                lab = self.get_sector_from_angle(angle)
                if lab:
                    self._dragging_label = lab
                    self._drag_origin_index = self.inner_order.index(lab)
                    self._drag_hover_target = lab
                    self.active_sector = lab
                    self.hovered_children = None
                    self.outer_active_sector = None
                    self.update()
                    return  # don't treat as a normal click

            # start child drag
            elif outer_inner_radius < dist <= outer_outer_radius and self.hovered_children:
                tgt_child = self.get_outer_sector_from_angle(angle, self.hovered_child_angles)
                if tgt_child:
                    self._dragging_child = tgt_child
                    self._child_drag_origin_index = list(self.hovered_children.keys()).index(tgt_child)
                    self._child_drag_hover_target = tgt_child
                    self.outer_active_sector = tgt_child
                    self.update()
                    return

        # --- LMB: select / toggle select ---
        elif event.button() == QtCore.Qt.LeftButton:
            angle, dist = self._angle_from_pos(event.pos())
            inner_r = self.radius
            outer_inner_r = self.radius + self.ring_gap
            outer_outer_r = self.outer_radius

            # Click in inner ring -> (toggle) lock/unlock this parent
            if dist <= inner_r and self.inner_order:
                lab = self.get_sector_from_angle(angle)
                if lab:
                    # determine current selection state
                    cur_label = self.hiddenLabel.text() if self.hiddenLabel else ""
                    cur_type = self.hiddenType.text() if self.hiddenType else ""
                    cur_parent = self.hiddenParent.text() if self.hiddenParent else ""

                    clicking_same_inner = (cur_type == "inner" and cur_label == lab)

                    if clicking_same_inner:
                        # --- toggle OFF: clear selection & unlock children ---
                        self._sticky_parent = None
                        self.active_sector = None
                        self.hovered_children = None
                        self.hovered_child_angles = {}
                        self.outer_active_sector = None

                        if self.hiddenLabel:  self.hiddenLabel.setText("")
                        if self.hiddenType:   self.hiddenType.setText("")
                        if self.hiddenParent: self.hiddenParent.setText("")
                        if self.label_lineEdit: self.label_lineEdit.clear()
                        if self.scriptEditor:   self.scriptEditor.clear()
                        if getattr(self, "descEditor", None): self.descEditor.clear()

                        self.update()
                        return
                    else:
                        # --- toggle ON to this parent ---
                        self._sticky_parent = lab
                        self.active_sector = lab
                        self.hovered_children = self.inner_sections.get(lab, {}).get("children", {})
                        self.hovered_child_angles = self.get_child_angles() if self.hovered_children else {}
                        self.outer_active_sector = None

                        # populate editor UI for INNER
                        sec = self.inner_sections.get(lab, {})
                        if self.hiddenLabel:  self.hiddenLabel.setText(lab)
                        if self.hiddenType:   self.hiddenType.setText("inner")
                        if self.hiddenParent: self.hiddenParent.setText("")
                        if self.label_lineEdit: self.label_lineEdit.setText(lab)
                        if self.scriptEditor:   self.scriptEditor.setPlainText(sec.get("command", ""))
                        if getattr(self, "descEditor", None): self.descEditor.setText(sec.get("description", ""))

                        self.update()
                        return

            # Click in child ring -> select/toggle child (keep parent locked)
            if outer_inner_r < dist <= outer_outer_r and self.hovered_children:
                tgt_child = self.get_outer_sector_from_angle(angle, self.hovered_child_angles)
                if tgt_child:
                    parent_label = self._sticky_parent or self.active_sector or ""
                    cur_label = self.hiddenLabel.text() if self.hiddenLabel else ""
                    cur_type = self.hiddenType.text() if self.hiddenType else ""
                    cur_parent = self.hiddenParent.text() if self.hiddenParent else ""

                    clicking_same_child = (
                                cur_type == "child" and cur_label == tgt_child and cur_parent == parent_label)

                    if clicking_same_child:
                        # --- toggle OFF child: clear ALL selection (no parent lock) ---
                        if self.hiddenLabel:  self.hiddenLabel.setText("")
                        if self.hiddenType:   self.hiddenType.setText("")
                        if self.hiddenParent: self.hiddenParent.setText("")
                        if self.label_lineEdit: self.label_lineEdit.clear()
                        if self.scriptEditor:   self.scriptEditor.clear()
                        if getattr(self, "descEditor", None): self.descEditor.clear()

                        # drop any sticky/hover state so hovering behaves normally
                        self._clear_selection_state()
                        self.update()
                        return
                    else:
                        # --- select this child ---
                        self.outer_active_sector = tgt_child
                        parent_label = self._sticky_parent or self.active_sector or ""
                        sec = {}
                        if parent_label:
                            sec = self.inner_sections.get(parent_label, {}).get("children", {}).get(tgt_child, {})

                        if self.hiddenLabel:  self.hiddenLabel.setText(tgt_child)
                        if self.hiddenType:   self.hiddenType.setText("child")
                        if self.hiddenParent: self.hiddenParent.setText(parent_label)
                        if self.label_lineEdit: self.label_lineEdit.setText(tgt_child)
                        if self.scriptEditor:   self.scriptEditor.setPlainText(sec.get("command", ""))
                        if getattr(self, "descEditor", None): self.descEditor.setText(sec.get("description", ""))

                        # ensure parent remains locked & children visible
                        self._sticky_parent = parent_label or self._sticky_parent
                        self.active_sector = self._sticky_parent
                        self.hovered_children = self.inner_sections.get(self._sticky_parent, {}).get("children",
                                                                                                     {}) if self._sticky_parent else None
                        self.hovered_child_angles = self.get_child_angles() if self.hovered_children else {}
                        self.update()
                        return

            # Clicked elsewhere -> clear everything
            self._sticky_parent = None
            self.active_sector = None
            self.hovered_children = None
            self.hovered_child_angles = {}
            self.outer_active_sector = None
            if self.hiddenLabel:  self.hiddenLabel.setText("")
            if self.hiddenType:   self.hiddenType.setText("")
            if self.hiddenParent: self.hiddenParent.setText("")
            if self.label_lineEdit: self.label_lineEdit.clear()
            if self.scriptEditor:   self.scriptEditor.clear()
            if getattr(self, "descEditor", None): self.descEditor.clear()
            self.update()
            return

        # default
        QtWidgets.QWidget.mousePressEvent(self, event)

    def calculate_angles(self, order):
        if not order:
            return {}
        start_angle = 270  # 'N' starts at top
        step = 360 / len(order)
        return {label: (start_angle + i * step) % 360 for i, label in enumerate(order)}

    def mouseReleaseEvent(self, event):
        # --- FINISH INNER DRAG ---
        if event.button() == QtCore.Qt.MiddleButton and self._dragging_label:
            angle, dist = self._angle_from_pos(event.pos())
            target = None
            if dist <= self.radius:
                target = self.get_sector_from_angle(angle) or self._drag_hover_target

            if target and target != self._dragging_label:
                # swap in local order
                i = self.inner_order.index(self._dragging_label)
                j = self.inner_order.index(target)
                self.inner_order[i], self.inner_order[j] = self.inner_order[j], self.inner_order[i]

                # persist & reload angles
                data, preset, _ = self._get_preset_for_write()
                inner = preset.get("inner_section", OrderedDict())
                preset["inner_section"] = OrderedDict((k, inner[k]) for k in self.inner_order if k in inner)
                _save_data(data)

                # refresh caches from active preset to be 100% in sync
                data = _load_data()
                pname = getattr(self, "_preview_name", None) or get_active_preset()
                preset = data["presets"].get(pname, OrderedDict())
                self.inner_sections = preset.get("inner_section", OrderedDict())
                self.inner_order = list(self.inner_sections.keys())
                self.inner_angles = self.calculate_angles(self.inner_order)

                # if we were showing children for the active sector, recompute child angles too
                if self.active_sector and "children" in self.inner_sections.get(self.active_sector, {}):
                    self.hovered_children = self.inner_sections[self.active_sector]["children"]
                    self.hovered_child_angles = self.get_child_angles()

            # clear state
            self._dragging_label = None
            self._drag_origin_index = -1
            self._drag_hover_target = None

            # force one more hover resolve at current cursor
            angle, dist = self._angle_from_pos(event.pos())
            if dist <= self.radius:
                self.active_sector = self.get_sector_from_angle(angle)
            self.update()
            return

        # --- FINISH CHILD DRAG ---
        if event.button() == QtCore.Qt.MiddleButton and self._dragging_child:
            angle, dist = self._angle_from_pos(event.pos())
            outer_inner_radius = self.radius + self.ring_gap
            outer_outer_radius = self.outer_radius
            target_child = None
            if outer_inner_radius < dist <= outer_outer_radius:
                target_child = self.get_outer_sector_from_angle(angle, self.hovered_child_angles) \
                               or self._child_drag_hover_target

            moved_ok = False
            if target_child and target_child != self._dragging_child and self.active_sector:
                data, preset, _ = self._get_preset_for_write()
                inner = preset.get("inner_section", OrderedDict())
                parent_label = self.active_sector
                if parent_label in inner:
                    children = inner[parent_label].get("children", OrderedDict())
                    if self._dragging_child in children and target_child in children:
                        order = list(children.keys())
                        i = order.index(self._dragging_child)
                        j = order.index(target_child)
                        order[i], order[j] = order[j], order[i]
                        inner[parent_label]["children"] = OrderedDict((k, children[k]) for k in order)
                        _save_data(data)
                        moved_ok = True

            # clear child-drag state
            self._dragging_child = None
            self._child_drag_origin_index = -1
            self._child_drag_hover_target = None

            # hard refresh from disk so widget mirrors JSON immediately (use PREVIEW preset)
            data = _load_data()
            pname = getattr(self, "_preview_name", None) or get_active_preset()
            preset = data["presets"].get(pname, OrderedDict())
            self.inner_sections = preset.get("inner_section", OrderedDict())
            self.inner_order = list(self.inner_sections.keys())
            self.inner_angles = self.calculate_angles(self.inner_order)

            if self.active_sector and "children" in self.inner_sections.get(self.active_sector, {}):
                self.hovered_children = self.inner_sections[self.active_sector]["children"]
                self.hovered_child_angles = self.get_child_angles()
            else:
                self.hovered_children = None
                self.hovered_child_angles = {}

            # re-resolve which child is under the cursor using the NEW angles
            if moved_ok and outer_inner_radius < dist <= outer_outer_radius and self.hovered_children:
                self.outer_active_sector = self.get_outer_sector_from_angle(angle, self.hovered_child_angles)

            self.update()
            return

        # default behavior for other buttons
        QtWidgets.QWidget.mouseReleaseEvent(self, event)

    def mouseMoveEvent(self, event):
        # --- INNER DRAG (MMB) ---
        if self._dragging_label:
            angle, dist = self._angle_from_pos(event.pos())
            self._drag_hover_target = None
            if dist <= self.radius:
                tgt = self.get_sector_from_angle(angle)
                if tgt:
                    self._drag_hover_target = tgt
            self.update()
            return

        # --- CHILD DRAG (MMB) ---
        if self._dragging_child:
            angle, dist = self._angle_from_pos(event.pos())
            outer_inner_radius = self.radius + self.ring_gap
            outer_outer_radius = self.outer_radius
            self._child_drag_hover_target = None
            if outer_inner_radius < dist <= outer_outer_radius:
                tgt = self.get_outer_sector_from_angle(angle, self.hovered_child_angles)
                if tgt:
                    self._child_drag_hover_target = tgt
            self.update()
            return

        # ---- NORMAL HOVER ----
        global_pos = event.globalPos() if hasattr(event, 'globalPos') else self.mapToGlobal(event.pos())
        widget_center = QtCore.QPoint(self.width() // 2, self.height() // 2)
        global_center = self.mapToGlobal(widget_center)

        dx = global_pos.x() - global_center.x()
        dy = global_pos.y() - global_center.y()
        angle = math.degrees(math.atan2(dy, dx)) % 360
        distance = math.hypot(dx, dy)

        inner_radius = self.radius
        outer_inner_radius = self.radius + self.ring_gap
        outer_outer_radius = self.outer_radius

        # If we have a sticky parent, keep it active and keep its children visible
        if self._sticky_parent:
            self.active_sector = self._sticky_parent
            self.hovered_children = self.inner_sections.get(self._sticky_parent, {}).get("children", {})
            self.hovered_child_angles = self.get_child_angles() if self.hovered_children else {}
            # while sticky, let the outer child highlight follow the cursor
            if outer_inner_radius < distance <= outer_outer_radius and self.hovered_children:
                self.outer_active_sector = self.get_outer_sector_from_angle(angle, self.hovered_child_angles)
            else:
                self.outer_active_sector = None
            self.update()
            return

        # No sticky: behave like pure hover
        if distance <= inner_radius:
            self.active_sector = self.get_sector_from_angle(angle)
            self.outer_active_sector = None

            if self.active_sector and "children" in self.inner_sections[self.active_sector]:
                self.hovered_children = self.inner_sections[self.active_sector]["children"]
                self.hovered_child_angles = self.get_child_angles()
            else:
                self.hovered_children = None
                self.hovered_child_angles = {}

        elif distance <= outer_outer_radius + 50 and self.hovered_children:
            self.outer_active_sector = self.get_outer_sector_from_angle(angle, self.hovered_child_angles)

        else:
            self.active_sector = None
            self.outer_active_sector = None
            self.hovered_children = None
            self.hovered_child_angles = {}

        self.update()

        # ---- HOVER / HILITE (no drag) ----
        global_pos = event.globalPos() if hasattr(event, 'globalPos') else self.mapToGlobal(event.pos())
        widget_center = QtCore.QPoint(self.width() // 2, self.height() // 2)
        global_center = self.mapToGlobal(widget_center)

        dx = global_pos.x() - global_center.x()
        dy = global_pos.y() - global_center.y()
        angle = math.degrees(math.atan2(dy, dx)) % 360
        distance = math.hypot(dx, dy)

        inner_radius = self.radius
        outer_inner_radius = self.radius + self.ring_gap
        outer_outer_radius = self.outer_radius

        if distance <= inner_radius:
            self.active_sector = self.get_sector_from_angle(angle)
            self.outer_active_sector = None

            if self.active_sector and "children" in self.inner_sections[self.active_sector]:
                self.hovered_children = self.inner_sections[self.active_sector]["children"]
                self.hovered_child_angles = self.get_child_angles()
            else:
                self.hovered_children = None
                self.hovered_child_angles = {}

        elif distance <= outer_outer_radius + 50 and self.hovered_children:
            self.outer_active_sector = self.get_outer_sector_from_angle(angle, self.hovered_child_angles)

        else:
            self.active_sector = None
            self.outer_active_sector = None
            self.hovered_children = None
            self.hovered_child_angles = {}

        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # If you need the -20 shift only for the pop-up, make it conditional.
        y_shift = 0  # 0 for embedded preview
        center = QtCore.QPointF(self.width() / 2, self.height() / 2 + y_shift)

        r = getattr(self, "display_radius", self.radius)
        hole = getattr(self, "display_hole", None)
        if not hole:
            hole = getattr(self, "inner_hole", max(0, int(self.radius * 0.35)))
        step = 360 / len(self.inner_angles) if self.inner_angles else 0

        outer_rect = QtCore.QRectF(center.x() - r, center.y() - r, r * 2, r * 2)
        inner_rect = QtCore.QRectF(center.x() - hole, center.y() - hole, hole * 2, hole * 2)

        for label, angle in self.inner_angles.items():
            # annular wedge path
            path = QtGui.QPainterPath()
            path.arcMoveTo(outer_rect, -angle - step / 2.0)
            path.arcTo(outer_rect, -angle - step / 2.0, step)
            path.arcTo(inner_rect, -angle + step / 2.0, -step)
            path.closeSubpath()

            painter.setBrush(self.innerHighlight_colour if label == self.active_sector else self.inner_colour)

            pen = QtGui.QPen(self.innerLine_colour, 2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawPath(path)

            # label at mid radius of the ring
            mid_r = (hole + r) * 0.5
            ang_rad = math.radians(angle)
            lp = QtCore.QPointF(center.x() + math.cos(ang_rad) * mid_r,
                                center.y() + math.sin(ang_rad) * mid_r)
            text = label
            tw = painter.fontMetrics().horizontalAdvance(text)
            painter.setPen(QtGui.QColor(255, 255, 255))
            painter.drawText(lp.x() - tw / 2, lp.y() + 5, text)

        if self.hovered_children:
            outer_r = self.outer_radius  # already based on display_radius
            inner_r = r + self.ring_gap  # r from above
            base_step = 25
            step = base_step * getattr(self, "child_angle_mult", 1.0)
            child_angles = self.get_child_angles()

            outer_rect = QtCore.QRectF(center.x() - outer_r, center.y() - outer_r, outer_r * 2, outer_r * 2)
            inner_rect = QtCore.QRectF(center.x() - inner_r, center.y() - inner_r, inner_r * 2, inner_r * 2)

            labels = list(child_angles.keys())
            n = len(labels)
            total_arc = step * n
            full_wrap = abs((total_arc % 360.0)) < 1e-3  # true if children span a full ring

            for i, (label, angle) in enumerate(child_angles.items()):
                path = QtGui.QPainterPath()
                path.arcMoveTo(outer_rect, -angle)
                path.arcTo(outer_rect, -angle, -step)
                path.arcTo(inner_rect, -angle - step, step)
                path.closeSubpath()

                # gradient FIRST
                gradient = QtGui.QRadialGradient(center, outer_r)
                if label == self.outer_active_sector:
                    base = self.child_colour
                    white = QtGui.QColor(255, 255, 255, base.alpha())
                    light = QtGui.QColor(
                        base.red() + (white.red() - base.red()) * 0.2,
                        base.green() + (white.green() - base.green()) * 0.2,
                        base.blue() + (white.blue() - base.blue()) * 0.2,
                        base.alpha()
                    )
                    gradient.setColorAt(0.0, light)
                    gradient.setColorAt(0.4, light)
                    gradient.setColorAt(0.8, QtGui.QColor(light.red(), light.green(), light.blue(), 80))
                    gradient.setColorAt(1.0, QtGui.QColor(light.red(), light.green(), light.blue(), 0))
                else:
                    base = self.child_colour
                    gradient.setColorAt(0.0, base)
                    gradient.setColorAt(0.4, base)
                    gradient.setColorAt(0.8, QtGui.QColor(base.red(), base.green(), base.blue(), 80))
                    gradient.setColorAt(1.0, QtGui.QColor(base.red(), base.green(), base.blue(), 0))

                painter.setBrush(gradient)
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawPath(path)

                pen = QtGui.QPen(self.childLine_colour, 1, QtCore.Qt.SolidLine,
                                 QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
                pen.setCosmetic(True)  # keep hairline crisp
                painter.setPen(pen)

                # inner arc (unchanged)
                painter.drawArc(inner_rect, int(-(angle + step) * 16), int(step * 16))

                # radial separators: draw each boundary once
                def pt_on_circle(r, deg):
                    rad = math.radians(deg)
                    return QtCore.QPointF(center.x() + r * math.cos(rad),
                                          center.y() + r * math.sin(rad))

                a0 = angle
                a1 = (angle + step) % 360

                # draw the very first leading edge only if not a full 360° wrap.
                if i == 0 and not full_wrap:
                    painter.drawLine(pt_on_circle(inner_r, a0), pt_on_circle(outer_r, a0))

                # always draw the trailing edge
                painter.drawLine(pt_on_circle(inner_r, a1), pt_on_circle(outer_r, a1))

                angle_deg = (angle + step / 2) % 360
                angle_rad = math.radians(angle_deg)
                label_radius = (inner_r + outer_r) / 2
                label_x = center.x() + label_radius * math.cos(angle_rad)
                label_y = center.y() + label_radius * math.sin(angle_rad)
                self._draw_child_label(painter, label_x, label_y, label_radius, angle_deg, label, sweep_deg=step)

        name = getattr(self, "_preview_name", None) or get_active_preset()
        if name:
            self._draw_hole_top_caption(painter, center, hole, name)

        desc = ""
        if self.outer_active_sector:
            # Prefer the current hovered_children dict
            if self.hovered_children and self.outer_active_sector in self.hovered_children:
                desc = self.hovered_children[self.outer_active_sector].get("description", "")
            else:
                # Fallback: search all children
                for p, pdata in self.inner_sections.items():
                    ch = pdata.get("children", {})
                    if self.outer_active_sector in ch:
                        desc = ch[self.outer_active_sector].get("description", "")
                        break
        elif self.active_sector:
            desc = self.inner_sections.get(self.active_sector, {}).get("description", "")

        if desc:
            font = QtGui.QFont("Arial", 10)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(220, 220, 220))
            fm = painter.fontMetrics()
            text_width = fm.horizontalAdvance(desc)
            text_height = fm.height()

            # Outer ring bottom position + small padding
            y = center.y() + self.radius + self.ring_gap + self.outer_ring_width + text_height + 6

            # Make sure it stays in widget bounds
            y = min(self.height() - 4, y)

            painter.drawText(center.x() - text_width / 2, y, desc)

    def _draw_hole_top_caption(self, painter, center, hole_radius, text):
        """Draw text inside the hole, hugged to the top arc, scaled to fit the chord there."""
        if not text or hole_radius <= 0:
            return

        import math
        painter.save()

        pad = max(4, int(hole_radius * 0.3))  # distance from the top arc
        font = QtGui.QFont("Arial")
        font.setBold(True)

        # Start reasonably big; shrink until it fits the chord at that height
        px = max(9, int(hole_radius * 0.30))
        while True:
            font.setPixelSize(px)
            fm = QtGui.QFontMetrics(font)
            h = fm.height()

            # Center line of text placed at y_center from widget center (negative = up)
            y_center = -hole_radius + pad + (h * 0.5)

            # chord width available at that y (inside the circle)
            try:
                chord = 2.0 * math.sqrt(max(0.0, hole_radius * hole_radius - y_center * y_center))
            except ValueError:
                chord = 0.0
            max_w = max(10.0, chord - 2 * pad)
            if fm.horizontalAdvance(text) <= max_w or px <= 8:
                break
            px -= 1

        # Build a centered path so we can outline + fill cleanly
        path = QtGui.QPainterPath()
        path.addText(0, 0, font, text)
        br = path.boundingRect()
        # Place the rect center at (center.x, center.y + y_center)
        path.translate(center.x() - br.center().x(),
                       center.y() + y_center - br.center().y())

        # Use same styling as child labels
        t = float(getattr(self, "child_outline_thickness", 1.6))
        oc = getattr(self, "child_outline_color", QtGui.QColor(20, 20, 20, 220))
        fc = getattr(self, "child_fill_color", QtGui.QColor(255, 255, 255))

        if t > 0.0:
            stroker = QtGui.QPainterPathStroker()
            stroker.setWidth(t * 2.0)
            stroker.setJoinStyle(QtCore.Qt.RoundJoin)
            stroker.setCapStyle(QtCore.Qt.RoundCap)
            painter.fillPath(stroker.createStroke(path), oc)

        painter.fillPath(path, fc)
        painter.restore()

    def _draw_child_label(
            self, painter, cx, cy, label_radius, angle_deg, text, sweep_deg,
            outline_thickness: float = None, fill_color: QtGui.QColor = None,
            outline_color: QtGui.QColor = None, font: QtGui.QFont = None
    ):
        painter.save()
        painter.translate(cx, cy)

        # keep text upright
        rot = angle_deg + 90
        r = rot % 360
        MARGIN = 8
        flip = (90 + MARGIN) < r < (270 - MARGIN)
        if flip:
            rot += 180
        painter.rotate(rot)

        # defaults
        font = font or self.child_font
        fill_color = fill_color or self.child_fill_color
        outline_color = outline_color or self.child_outline_color
        t = outline_thickness if outline_thickness is not None else self.child_outline_thickness

        painter.setFont(font)
        painter.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing, True)

        fm = QtGui.QFontMetricsF(font)

        # fit to arc
        arc_rad = math.radians(max(0.0, sweep_deg - 2.0))
        max_px = label_radius * arc_rad
        s = text
        if fm.horizontalAdvance(s) > max_px:
            s = fm.elidedText(s, QtCore.Qt.ElideRight, int(max_px))

        # build path at (0,0), then center it around origin (no baseline bias)
        path = QtGui.QPainterPath()
        path.addText(0, 0, font, s)
        br = path.boundingRect()
        path.translate(-br.center().x(), -br.center().y())

        # consistent radial inset toward center
        inset = (fm.ascent() + fm.descent()) * -0.10
        painter.translate(0, -inset if not flip else inset)

        # outline
        if t and t > 0.0:
            stroker = QtGui.QPainterPathStroker()
            stroker.setWidth(t * 2.0)
            stroker.setJoinStyle(QtCore.Qt.RoundJoin)
            stroker.setCapStyle(QtCore.Qt.RoundCap)
            painter.fillPath(stroker.createStroke(path), outline_color)

        # fill
        painter.fillPath(path, fill_color)
        painter.restore()

    def _get_preset_for_write(self):
        """Return (data, preset_dict, preset_name) for the preset currently shown in the widget."""
        data = _load_data()
        pname = getattr(self, "_preview_name", None) or data.get("active_preset")
        if pname not in data.get("presets", {}):
            pname = data.get("active_preset")
        preset = data["presets"].setdefault(pname, OrderedDict())
        preset.setdefault("inner_section", OrderedDict())
        return data, preset, pname

    def get_cursor_angle(self, global_pos):
        dx = global_pos.x() - self.center_pos.x()
        dy = global_pos.y() - self.center_pos.y()
        angle = math.degrees(math.atan2(dy, dx))
        return (angle + 360) % 360

    def get_sector_from_angle(self, angle):
        if not self.inner_angles:
            return None
        step = 360 / len(self.inner_angles)
        for key, a in self.inner_angles.items():
            min_a = (a - step / 2) % 360
            max_a = (a + step / 2) % 360
            if min_a < max_a:
                if min_a <= angle < max_a:
                    return key
            else:
                if angle >= min_a or angle < max_a:
                    return key
        return None

    def get_child_angles(self):
        if not self.active_sector or not self.hovered_children:
            return {}

        labels = list(self.hovered_children.keys())
        num = len(labels)
        base_step = 25
        step = base_step * getattr(self, "child_angle_mult", 1.0)
        total_arc = step * num
        center_angle = self.inner_angles[self.active_sector]

        # FIX: Start to the left of center_angle
        start_angle = (center_angle - total_arc / 2) % 360

        return {
            label: (start_angle + i * step) % 360
            for i, label in enumerate(labels)
        }

    def get_outer_sector_from_angle(self, angle, _unused=None):
        base_step = 25
        step = base_step * getattr(self, "child_angle_mult", 1.0)  # <- use multiplier
        child_angles = self.get_child_angles()  # already respects multiplier

        for label, start_angle in child_angles.items():
            end_angle = (start_angle + step) % 360
            min_a = start_angle
            max_a = end_angle

            if min_a < max_a:
                if min_a <= angle < max_a:
                    return label
            else:  # wraps around 360
                if angle >= min_a or angle < max_a:
                    return label
        return None

    def _resolve_child(self, child_label):
        """Return (parent_label, child_info) or (None, None). Also refresh hovered_children."""
        # 1) Prefer current active sector if it has this child
        if self.active_sector:
            p = self.active_sector
            ch = self.inner_sections.get(p, {}).get("children", {})
            if isinstance(ch, dict) and child_label in ch:
                self.hovered_children = ch
                return p, ch[child_label]

        # 2) Fallback: search all inner sections
        for p, pdata in self.inner_sections.items():
            ch = pdata.get("children", {})
            if isinstance(ch, dict) and child_label in ch:
                self.active_sector = p  # keep parent context consistent
                self.hovered_children = ch  # so subsequent ops see correct dict
                return p, ch[child_label]

        return None, None

    def execute_action(self, sector):
        # INNER
        if sector in self.inner_sections:
            info = self.inner_sections[sector]
            sel_type = "inner"
            parent_label = ""
            self.current_parent_label = ""

        # CHILD
        else:
            parent_label, info = self._resolve_child(sector)
            if not info:
                print(f"[Warning] No sector found for '{sector}'")
                return
            sel_type = "child"
            self.current_parent_label = parent_label

        # Populate editor UI
        if self.label_lineEdit:
            self.label_lineEdit.setText(sector)
        if self.hiddenLabel:
            self.hiddenLabel.setText(sector)
        if self.scriptEditor:
            self.scriptEditor.setPlainText(info.get("command", ""))
        if self.descEditor:  # << NEW
            self.descEditor.setText(info.get("description", ""))

        # <-- these two lines are the key for Save() -->
        if self.hiddenType:
            self.hiddenType.setText(sel_type)  # "inner" or "child"
        if self.hiddenParent:
            self.hiddenParent.setText(parent_label)  # "" for inner; parent label for child

class RadialMenu(QtWidgets.QWidget):
    trigger_signal = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.Tool)
        self._parent_anchor = None
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)


        self.inner_colour = QtGui.QColor(69, 69, 69, 180)
        self.innerHighlight_colour = QtGui.QColor(40, 40, 40, 180)
        self.innerLine_colour = QtGui.QColor(30, 30, 30)

        self.child_colour = 206, 0, 255
        self.childLine_colour = QtGui.QColor(30, 30, 30)
        self.child_fill_color = QtGui.QColor(255, 255, 255)
        self.child_outline_color = QtGui.QColor(20, 20, 20, 220)
        self.child_outline_thickness = 1.6  # float, in device pixels

        self.child_font = QtGui.QFont("Arial")
        self.child_font.setPixelSize(11)
        self.child_font.setKerning(True)
        self.child_font.setHintingPreference(QtGui.QFont.PreferNoHinting)
        self.child_font.setStyleStrategy(QtGui.QFont.PreferAntialias)

        self._wheel_filter = _HoleWheelRedirector(self)
        QtWidgets.QApplication.instance().installEventFilter(self._wheel_filter)

        data = _load_data()

        preset = _active_preset(data)
        colour_data = preset.get("colour", {})  # <- per-preset colours

        # accept either the old or new keys for text colors
        child_text_fill_hex = colour_data.get("child_text_color", colour_data.get("child_fill_color", "#FFFFFF"))
        child_text_outline_hex = colour_data.get("child_textOutline_color",
                                                 colour_data.get("child_outline_color", "#141414DC"))

        self.inner_colour = _q(colour_data.get("inner_colour"), "#454545B4")
        self.innerHighlight_colour = _q(colour_data.get("innerHighlight_colour"), "#282828B4")
        self.innerLine_colour = _q(colour_data.get("innerLine_colour"), "#1E1E1E")

        self.child_colour = _q(colour_data.get("child_colour"), "#CE00FF")
        self.childLine_colour = _q(colour_data.get("childLine_colour"), "#1E1E1E")
        self.child_fill_color = _q(child_text_fill_hex, "#FFFFFF")
        self.child_outline_color = _q(child_text_outline_hex, "#141414DC")
        self.child_outline_thickness = float(colour_data.get("child_outline_thickness", 1.6))

        size_data = data.get("ui", {}).get("size", {})
        if not size_data:
            size_data = _active_preset(data).get("size", {})  # legacy fallback
        self.child_angle_mult = float(size_data.get("child_angle_multiplier", 1.0))
        self.radius = size_data.get("radius", 150)
        self.ring_gap = size_data.get("ring_gap", 5)
        self.outer_ring_width = size_data.get("outer_ring_width", 25)
        self.outer_radius = self.radius + self.ring_gap + self.outer_ring_width
        self.inner_hole = int(size_data.get("inner_hole_radius", max(0, int(self.radius * 0.35))))

        self.center_pos = QtGui.QCursor.pos()
        extra_height = 80
        self.move(self.center_pos.x() - self.outer_radius, self.center_pos.y() - self.outer_radius - 20)
        self.resize(self.outer_radius * 2, self.outer_radius * 2 + extra_height)

        geo = self.frameGeometry()
        geo.moveCenter(QtGui.QCursor.pos())
        self.move(geo.topLeft())

        self.inner_sections = _active_preset(data).get("inner_section", OrderedDict())

        self.inner_order = list(self.inner_sections.keys())  # ["N", "NE", "E", "SE", "SW", "W", "NW"]
        self.inner_angles = self.calculate_angles(self.inner_order)

        self.active_sector = None
        self.outer_active_sector = None

        self.hovered_children = None
        self.hovered_child_angles = {}

        self.trigger_signal.connect(self.execute_action)

        self.show()
        self.activateWindow()
        self.raise_()
        QtCore.QTimer.singleShot(0, self.setFocus)
        self.grabMouse()

    def closeEvent(self, e):
        try:
            QtWidgets.QApplication.instance().removeEventFilter(self._wheel_filter)
        except Exception:
            pass
        super().closeEvent(e)
    def _apply_preset_colours(self, preset):
        colour_data = preset.get("colour", {})

        # accept either the old or new keys for text colors
        child_text_fill_hex = colour_data.get("child_text_color", colour_data.get("child_fill_color", "#FFFFFF"))
        child_text_outline_hex = colour_data.get("child_textOutline_color",
                                                 colour_data.get("child_outline_color", "#141414DC"))

        self.inner_colour = _q(colour_data.get("inner_colour"), "#454545B4")
        self.innerHighlight_colour = _q(colour_data.get("innerHighlight_colour"), "#282828B4")
        self.innerLine_colour = _q(colour_data.get("innerLine_colour"), "#1E1E1E")

        self.child_colour = _q(colour_data.get("child_colour"), "#CE00FF")
        self.childLine_colour = _q(colour_data.get("childLine_colour"), "#1E1E1E")
        self.child_fill_color = _q(child_text_fill_hex, "#FFFFFF")
        self.child_outline_color = _q(child_text_outline_hex, "#141414DC")
        self.child_outline_thickness = float(colour_data.get("child_outline_thickness", 1.6))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # Full rect = interactive (do NOT carve out the inner hole)
        self.setMask(QtGui.QRegion(self.rect()))

    def wheelEvent(self, event: QtGui.QWheelEvent):

        delta = event.angleDelta().y() or event.angleDelta().x()
        if not delta:
            event.ignore()
            return

        names = list_presets()
        if not names or len(names) == 1:
            event.accept()
            return

        cur = get_active_preset()
        try:
            idx = names.index(cur)
        except ValueError:
            idx = 0

        step = -1 if delta < 0 else 1
        new_name = names[(idx + step) % len(names)]

        if set_active_preset(new_name):
            data = _load_data()
            self.inner_sections = _active_preset(data).get("inner_section", OrderedDict())
            self.inner_order = list(self.inner_sections.keys())
            self.inner_angles = self.calculate_angles(self.inner_order)
            self.active_sector = None
            self.outer_active_sector = None
            self.hovered_children = None
            self.hovered_child_angles = {}
            self._apply_preset_colours(_active_preset(data))
            self.update()
            try:
                cmds.inViewMessage(amg=f"Preset: <hl>{new_name}</hl>", pos='topCenter', fade=True)
            except Exception:
                pass

        event.accept()
    def calculate_angles(self, order):
        if not order:
            return {}
        start_angle = 270  # 'N' starts at top
        step = 360 / len(order)
        return {label: (start_angle + i * step) % 360 for i, label in enumerate(order)}

    def focusOutEvent(self, event):
        QtCore.QTimer.singleShot(0, self.close)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()

    def mouseMoveEvent(self, event):
        # Get the global mouse position
        global_pos = event.globalPos() if hasattr(event, 'globalPos') else self.mapToGlobal(event.pos())

        # Map widget center to global space
        widget_center = QtCore.QPoint(self.width() // 2, self.height() // 2)
        global_center = self.mapToGlobal(widget_center)

        dx = global_pos.x() - global_center.x()
        dy = global_pos.y() - global_center.y()
        angle = math.degrees(math.atan2(dy, dx)) % 360
        distance = math.hypot(dx, dy)

        inner_radius = self.radius  # outer edge of inner ring (annulus outer radius)
        inner_hole = self.inner_hole  # hole radius
        outer_inner_radius = self.radius + self.ring_gap
        outer_outer_radius = self.outer_radius

        # --- add hysteresis so children don't vanish just outside the ring ---
        HYST = max(12, int(self.outer_ring_width * 0.6))  # feel free to tune
        ring_inner_with_hyst = max(inner_hole, outer_inner_radius - HYST)
        ring_outer_with_hyst = outer_outer_radius + HYST

        sector_at_angle = self.get_sector_from_angle(angle)

        # 1) Inside the hole -> clear everything
        if distance < inner_hole:
            self.active_sector = None
            self.outer_active_sector = None
            self.hovered_children = None
            self.hovered_child_angles = {}
            self._parent_anchor = None
            self.update()
            return

        # 2) Inside the inner ring annulus -> highlight inner + (re)load its children
        if inner_hole <= distance <= inner_radius:
            self.active_sector = sector_at_angle
            self.outer_active_sector = None

            if self.active_sector and "children" in self.inner_sections.get(self.active_sector, {}):
                self.hovered_children = self.inner_sections[self.active_sector]["children"]
                self.hovered_child_angles = self.get_child_angles()
                # set/refresh anchor AFTER children exist
                self._parent_anchor = self.active_sector
            else:
                self.hovered_children = None
                self.hovered_child_angles = {}
                self._parent_anchor = None

            self.update()
            return

        # 3) In/near the outer ring (with hysteresis)
        #    Keep parent anchored; only highlight a child when actually inside the true ring band.
        if (ring_inner_with_hyst <= distance <= ring_outer_with_hyst) and self.hovered_children and self._parent_anchor:
            self.active_sector = self._parent_anchor  # don’t let the parent flicker
            if outer_inner_radius <= distance <= outer_outer_radius:
                # inside the real child ring: resolve child under cursor
                self.outer_active_sector = self.get_outer_sector_from_angle(angle, self.hovered_child_angles)
            else:
                # in the buffer area: keep children visible but no specific child selected
                self.outer_active_sector = None

            self.update()
            return

        # 4) Far outside everything -> clear
        self.active_sector = None
        self.outer_active_sector = None
        self.hovered_children = None
        self.hovered_child_angles = {}
        self._parent_anchor = None
        self.update()

    def mouseReleaseEvent(self, event):
        if self.outer_active_sector is not None:
            self.trigger_signal.emit(f"outer_{self.outer_active_sector}")
        elif self.active_sector:
            self.trigger_signal.emit(self.active_sector)

        self.releaseMouse()
        self.close()

    def paintEvent(self, event):

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        painter.fillRect(self.rect(), QtCore.Qt.transparent)

        # If you need the -20 shift only for the pop-up, make it conditional.
        y_shift = 0  # 0 for embedded preview
        center = QtCore.QPointF(self.width() / 2, self.height() / 2 + y_shift)

        r = getattr(self, "display_radius", self.radius)
        hole = self.inner_hole
        step = 360 / len(self.inner_angles) if self.inner_angles else 0



        outer_rect = QtCore.QRectF(center.x() - r, center.y() - r, r * 2, r * 2)
        inner_rect = QtCore.QRectF(center.x() - hole, center.y() - hole, hole * 2, hole * 2)

        for label, angle in self.inner_angles.items():
            # Build annular wedge path
            path = QtGui.QPainterPath()
            path.arcMoveTo(outer_rect, -angle - step / 2.0)
            path.arcTo(outer_rect, -angle - step / 2.0, step)
            path.arcTo(inner_rect, -angle + step / 2.0, -step)
            path.closeSubpath()

            painter.setBrush(self.innerHighlight_colour if label == self.active_sector else self.inner_colour)

            pen = QtGui.QPen(self.innerLine_colour, 2)
            pen.setCosmetic(True)  # hairline
            painter.setPen(pen)
            painter.drawPath(path)

            # Label at mid-radius of the ring
            mid_r = (hole + r) * 0.5
            angle_rad = math.radians(angle)
            label_pos = QtCore.QPointF(center.x() + math.cos(angle_rad) * mid_r,
                                       center.y() + math.sin(angle_rad) * mid_r)

            text = label
            tw = painter.fontMetrics().horizontalAdvance(text)
            painter.setPen(QtGui.QColor(255, 255, 255))
            painter.drawText(label_pos.x() - tw / 2, label_pos.y() + 5, text)

        if self.hovered_children:
            outer_r = self.outer_radius  # already based on display_radius
            inner_r = r + self.ring_gap  # r from above
            base_step = 25
            step = base_step * getattr(self, "child_angle_mult", 1.0)
            child_angles = self.get_child_angles()

            outer_rect = QtCore.QRectF(center.x() - outer_r, center.y() - outer_r, outer_r * 2, outer_r * 2)
            inner_rect = QtCore.QRectF(center.x() - inner_r, center.y() - inner_r, inner_r * 2, inner_r * 2)

            labels = list(child_angles.keys())
            n = len(labels)
            total_arc = step * n
            full_wrap = abs((total_arc % 360.0)) < 1e-3  # true if children span a full ring

            for i, (label, angle) in enumerate(child_angles.items()):
                path = QtGui.QPainterPath()
                path.arcMoveTo(outer_rect, -angle)
                path.arcTo(outer_rect, -angle, -step)
                path.arcTo(inner_rect, -angle - step, step)
                path.closeSubpath()

                # gradient FIRST
                gradient = QtGui.QRadialGradient(center, outer_r)
                if label == self.outer_active_sector:
                    base = self.child_colour
                    white = QtGui.QColor(255, 255, 255, base.alpha())
                    light = QtGui.QColor(
                        base.red() + (white.red() - base.red()) * 0.2,
                        base.green() + (white.green() - base.green()) * 0.2,
                        base.blue() + (white.blue() - base.blue()) * 0.2,
                        base.alpha()
                    )
                    gradient.setColorAt(0.0, light)
                    gradient.setColorAt(0.4, light)
                    gradient.setColorAt(0.8, QtGui.QColor(light.red(), light.green(), light.blue(), 80))
                    gradient.setColorAt(1.0, QtGui.QColor(light.red(), light.green(), light.blue(), 0))
                else:
                    base = self.child_colour
                    gradient.setColorAt(0.0, base)
                    gradient.setColorAt(0.4, base)
                    gradient.setColorAt(0.8, QtGui.QColor(base.red(), base.green(), base.blue(), 80))
                    gradient.setColorAt(1.0, QtGui.QColor(base.red(), base.green(), base.blue(), 0))

                painter.setBrush(gradient)
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawPath(path)

                pen = QtGui.QPen(self.childLine_colour, 1, QtCore.Qt.SolidLine,
                                 QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
                pen.setCosmetic(True)  # keep hairline crisp
                painter.setPen(pen)

                # inner arc (unchanged)
                painter.drawArc(inner_rect, int(-(angle + step) * 16), int(step * 16))

                # radial separators: draw each boundary once
                def pt_on_circle(r, deg):
                    rad = math.radians(deg)
                    return QtCore.QPointF(center.x() + r * math.cos(rad),
                                          center.y() + r * math.sin(rad))

                a0 = angle
                a1 = (angle + step) % 360

                # draw the very first leading edge only if not a full 360° wrap.
                if i == 0 and not full_wrap:
                    painter.drawLine(pt_on_circle(inner_r, a0), pt_on_circle(outer_r, a0))

                # always draw the trailing edge
                painter.drawLine(pt_on_circle(inner_r, a1), pt_on_circle(outer_r, a1))

                angle_deg = (angle + step / 2) % 360
                angle_rad = math.radians(angle_deg)
                label_radius = (inner_r + outer_r) / 2
                label_x = center.x() + label_radius * math.cos(angle_rad)
                label_y = center.y() + label_radius * math.sin(angle_rad)
                self._draw_child_label(painter, label_x, label_y, label_radius, angle_deg, label, sweep_deg=step)

        name = get_active_preset()
        if name:
            self._draw_hole_top_caption(painter, center, self.inner_hole, name)

        desc = ""
        if self.outer_active_sector:
            # Prefer the current hovered_children dict
            if self.hovered_children and self.outer_active_sector in self.hovered_children:
                desc = self.hovered_children[self.outer_active_sector].get("description", "")
            else:
                # Fallback: search all children
                for p, pdata in self.inner_sections.items():
                    ch = pdata.get("children", {})
                    if self.outer_active_sector in ch:
                        desc = ch[self.outer_active_sector].get("description", "")
                        break
        elif self.active_sector:
            desc = self.inner_sections.get(self.active_sector, {}).get("description", "")

        if desc:
            font = QtGui.QFont("Arial", 10)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(220, 220, 220))
            fm = painter.fontMetrics()
            text_width = fm.horizontalAdvance(desc)
            text_height = fm.height()

            # Outer ring bottom position + small padding
            y = center.y() + self.radius + self.ring_gap + self.outer_ring_width + text_height + 6

            # Make sure it stays in widget bounds
            y = min(self.height() - 4, y)

            painter.drawText(center.x() - text_width / 2, y, desc)

    def _draw_hole_top_caption(self, painter, center, hole_radius, text):
        """Draw text inside the hole, hugged to the top arc, scaled to fit the chord there."""
        if not text or hole_radius <= 0:
            return

        import math
        painter.save()

        pad = max(4, int(hole_radius * 0.3))  # distance from the top arc
        font = QtGui.QFont("Arial")
        font.setBold(True)

        # Start reasonably big; shrink until it fits the chord at that height
        px = max(9, int(hole_radius * 0.30))
        while True:
            font.setPixelSize(px)
            fm = QtGui.QFontMetrics(font)
            h = fm.height()

            # Center line of text placed at y_center from widget center (negative = up)
            y_center = -hole_radius + pad + (h * 0.5)

            # chord width available at that y (inside the circle)
            try:
                chord = 2.0 * math.sqrt(max(0.0, hole_radius * hole_radius - y_center * y_center))
            except ValueError:
                chord = 0.0
            max_w = max(10.0, chord - 2 * pad)
            if fm.horizontalAdvance(text) <= max_w or px <= 8:
                break
            px -= 1

        # Build a centered path so we can outline + fill cleanly
        path = QtGui.QPainterPath()
        path.addText(0, 0, font, text)
        br = path.boundingRect()
        # Place the rect center at (center.x, center.y + y_center)
        path.translate(center.x() - br.center().x(),
                       center.y() + y_center - br.center().y())

        # Use same styling as child labels
        t = float(getattr(self, "child_outline_thickness", 1.6))
        oc = getattr(self, "child_outline_color", QtGui.QColor(20, 20, 20, 220))
        fc = getattr(self, "child_fill_color", QtGui.QColor(255, 255, 255))

        if t > 0.0:
            stroker = QtGui.QPainterPathStroker()
            stroker.setWidth(t * 2.0)
            stroker.setJoinStyle(QtCore.Qt.RoundJoin)
            stroker.setCapStyle(QtCore.Qt.RoundCap)
            painter.fillPath(stroker.createStroke(path), oc)

        painter.fillPath(path, fc)
        painter.restore()

    def _draw_child_label(
            self, painter, cx, cy, label_radius, angle_deg, text, sweep_deg,
            outline_thickness: float = None, fill_color: QtGui.QColor = None,
            outline_color: QtGui.QColor = None, font: QtGui.QFont = None
    ):
        painter.save()
        painter.translate(cx, cy)

        # keep text upright
        rot = angle_deg + 90
        r = rot % 360
        MARGIN = 8
        flip = (90 + MARGIN) < r < (270 - MARGIN)
        if flip:
            rot += 180
        painter.rotate(rot)

        # defaults
        font = font or self.child_font
        fill_color = fill_color or self.child_fill_color
        outline_color = outline_color or self.child_outline_color
        t = outline_thickness if outline_thickness is not None else self.child_outline_thickness

        painter.setFont(font)
        painter.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing, True)

        fm = QtGui.QFontMetricsF(font)

        # fit to arc
        arc_rad = math.radians(max(0.0, sweep_deg - 2.0))
        max_px = label_radius * arc_rad
        s = text
        if fm.horizontalAdvance(s) > max_px:
            s = fm.elidedText(s, QtCore.Qt.ElideRight, int(max_px))

        # build path at (0,0), then center it around origin (no baseline bias)
        path = QtGui.QPainterPath()
        path.addText(0, 0, font, s)
        br = path.boundingRect()
        path.translate(-br.center().x(), -br.center().y())

        # consistent radial inset toward center
        inset = (fm.ascent() + fm.descent()) * -0.10
        painter.translate(0, -inset if not flip else inset)

        # outline
        if t and t > 0.0:
            stroker = QtGui.QPainterPathStroker()
            stroker.setWidth(t * 2.0)
            stroker.setJoinStyle(QtCore.Qt.RoundJoin)
            stroker.setCapStyle(QtCore.Qt.RoundCap)
            painter.fillPath(stroker.createStroke(path), outline_color)

        # fill
        painter.fillPath(path, fill_color)
        painter.restore()

    def get_cursor_angle(self, global_pos):
        dx = global_pos.x() - self.center_pos.x()
        dy = global_pos.y() - self.center_pos.y()
        angle = math.degrees(math.atan2(dy, dx))
        return (angle + 360) % 360

    def get_sector_from_angle(self, angle):
        if not self.inner_angles:
            return None
        step = 360 / len(self.inner_angles)
        for key, a in self.inner_angles.items():
            min_a = (a - step / 2) % 360
            max_a = (a + step / 2) % 360
            if min_a < max_a:
                if min_a <= angle < max_a:
                    return key
            else:
                if angle >= min_a or angle < max_a:
                    return key
        return None

    def get_child_angles(self):
        if not self.active_sector or not self.hovered_children:
            return {}

        labels = list(self.hovered_children.keys())
        num = len(labels)
        base_step = 25
        step = base_step * getattr(self, "child_angle_mult", 1.0)
        total_arc = step * num
        center_angle = self.inner_angles[self.active_sector]

        # FIX: Start to the left of center_angle
        start_angle = (center_angle - total_arc / 2) % 360

        return {
            label: (start_angle + i * step) % 360
            for i, label in enumerate(labels)
        }

    def get_outer_sector_from_angle(self, angle, _unused=None):
        base_step = 25
        step = base_step * getattr(self, "child_angle_mult", 1.0)  # <- use multiplier
        child_angles = self.get_child_angles()  # already respects multiplier

        for label, start_angle in child_angles.items():
            end_angle = (start_angle + step) % 360
            min_a = start_angle
            max_a = end_angle

            if min_a < max_a:
                if min_a <= angle < max_a:
                    return label
            else:  # wraps around 360
                if angle >= min_a or angle < max_a:
                    return label
        return None

    def execute_action(self, sector):
        try:
            if sector.startswith("outer_"):
                key = sector.replace("outer_", "")
                if self.hovered_children and key in self.hovered_children:
                    command_str = self.hovered_children[key]["command"]
                else:
                    print(f"[Warning] No hovered child found for {key}")
                    return
            else:
                command_str = self.inner_sections[sector]["command"]

            if not command_str:
                return

            # run multiline command strings safely
            ns = {"cmds": cmds, "__name__": "__radial__"}
            exec(compile(command_str, "<radialMenu>", "exec"), ns, ns)

        except Exception as e:
            print(f"[RadialMenu Error] Failed to run command for '{sector}': {e}")


#################################################################################
from PySide2 import QtCore, QtWidgets


class RightClickHoldDetector(QtCore.QObject):
    def __init__(self, radial_enabled, parent=None):
        super().__init__(parent)
        self._radial = None
        self.radial_enabled = radial_enabled  # store reference

    def eventFilter(self, obj, event):
        # FIX: use self.radial_enabled
        if not self.radial_enabled["state"]:
            return False

        if event.type() == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.RightButton:
            if QtWidgets.QApplication.keyboardModifiers() == QtCore.Qt.NoModifier:
                widget = QtWidgets.QApplication.widgetAt(QtGui.QCursor.pos())
                if not widget or not self._is_maya_viewport(widget):
                    return False

                # kill any prior instance
                if self._radial:
                    try:
                        self._radial.close()
                        self._radial.setParent(None)
                        self._radial.deleteLater()
                    except Exception:
                        pass
                    self._radial = None

                # HOT RELOAD the class here
                RadialMenuClass = fresh_radial_cls()

                # build a fresh menu
                self._radial = RadialMenuClass(get_main_window())
                self._radial.show()
                return True  # block Maya's marking menu
            else:
                return False

        elif event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.RightButton:
            if self._radial:
                fake_event = QtGui.QMouseEvent(
                    QtCore.QEvent.MouseButtonRelease,
                    QtGui.QCursor.pos(),
                    QtCore.Qt.RightButton,
                    QtCore.Qt.RightButton,
                    QtCore.Qt.NoModifier
                )
                QtCore.QCoreApplication.postEvent(self._radial, fake_event)
                self._radial = None
                return True

        return False

    def _is_maya_viewport(self, widget):
        while widget:
            if widget.objectName().startswith("modelPanel"):
                return True
            widget = widget.parent()
        return False


#################################################################################
def toggle_radial_menu(force_state=None):
    if force_state is not None:
        radial_enabled["state"] = bool(force_state)
    else:
        radial_enabled["state"] = not radial_enabled["state"]

    state = "ON" if radial_enabled["state"] else "OFF"
    print(f"Radial Menu is now {state}")
    cmds.inViewMessage(amg=f"Radial Menu: <hl>{state}</hl>", pos='topCenter', fade=True)


def refresh_radial_menu():
    app = QtWidgets.QApplication.instance()

    # Remove existing detector
    if _rmb_detector_ref["instance"]:
        app.removeEventFilter(_rmb_detector_ref["instance"])
        _rmb_detector_ref["instance"] = None
        print("Old radial menu detector removed.")

    # Reset toggle state (optional)
    radial_enabled["state"] = True

    # Recreate and install new detector
    detector = RightClickHoldDetector(radial_enabled, parent=app)
    app.installEventFilter(detector)
    _rmb_detector_ref["instance"] = detector
    print("Radial menu detector installed fresh.")


_rmb_detector_ref = {"instance": None}  # Module-level cache
radial_enabled = {"state": True}


def install_rmb_hold_detector():
    app = QtWidgets.QApplication.instance()
    if _rmb_detector_ref["instance"] is not None:
        app.removeEventFilter(_rmb_detector_ref["instance"])

    # Create and store new instance
    detector = RightClickHoldDetector(radial_enabled, parent=app)
    app.installEventFilter(detector)
    _rmb_detector_ref["instance"] = detector


#install_rmb_hold_detector()
# toggle_radial_menu()