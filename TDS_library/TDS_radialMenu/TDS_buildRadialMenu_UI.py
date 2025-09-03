from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtWidgets import (QMainWindow, QDialog, QGridLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton, QPlainTextEdit,
                               QHBoxLayout)
import re
import maya.OpenMayaUI as omui
import maya.cmds as cmds
from shiboken2 import wrapInstance
import json
from collections import OrderedDict
from pathlib import Path

from TDS_library.TDS_radialMenu import radialWidget
import importlib
importlib.reload(radialWidget)

RadialMenuWidget = radialWidget.RadialMenuWidget
SCRIPT_DIR = Path(__file__).resolve().parent
menuInfo_filePath = SCRIPT_DIR / "radialMenu_info.json"

class CollapsibleFrame(QtWidgets.QFrame):
    """A simple collapsible frame similar to Maya frameLayout."""
    def __init__(self, title: str, parent=None, collapsed=False):
        super().__init__(parent)

        # Size policy: let height grow as needed when expanded
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        # Header
        self._toggle = QtWidgets.QToolButton(self)
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(not collapsed)
        self._toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(QtCore.Qt.DownArrow if not collapsed else QtCore.Qt.RightArrow)
        self._toggle.setAutoRaise(True)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(2, 2, 2, 2)
        header.addWidget(self._toggle)
        header.addStretch(1)

        # Body
        self.body = QtWidgets.QWidget(self)
        self.body.setVisible(not collapsed)
        self.body.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        self.body_layout = QGridLayout(self.body)
        self.body_layout.setContentsMargins(4, 0, 4, 4)
        self.body_layout.setHorizontalSpacing(4)
        self.body_layout.setVerticalSpacing(2)
        # Make labels get the width, buttons stay compact
        self.body_layout.setColumnStretch(0, 1)
        self.body_layout.setColumnStretch(1, 0)
        # If you end up adding a 3rd column, it will also flex
        self.body_layout.setColumnStretch(2, 1)

        # Wire up
        self._toggle.toggled.connect(self._on_toggled)

        # Main layout
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(header)
        outer.addWidget(self.body)

    # --- sizing hints so layouts recompute properly ---
    def sizeHint(self):
        sh_header = QtCore.QSize(0, 0)
        # Estimate header based on toolbutton + margins
        if self._toggle:
            sh_header = self._toggle.sizeHint() + QtCore.QSize(16, 16)
        if self.body.isVisible():
            b = self.body.sizeHint()
            return QtCore.QSize(max(sh_header.width(), b.width()), sh_header.height() + b.height())
        else:
            # Collapsed: just header height
            return sh_header

    def minimumSizeHint(self):
        mh_header = QtCore.QSize(0, 0)
        if self._toggle:
            mh_header = self._toggle.minimumSizeHint() + QtCore.QSize(16, 16)
        if self.body.isVisible():
            b = self.body.minimumSizeHint()
            return QtCore.QSize(max(mh_header.width(), b.width()), mh_header.height() + b.height())
        else:
            return mh_header

    def _on_toggled(self, checked: bool):
        self._toggle.setArrowType(QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)
        self.body.setVisible(checked)

        # Force parent layouts to recompute geometry now
        self.body.updateGeometry()
        self.updateGeometry()

        # Bubble up a bit so the dialog resizes if needed
        #p = self.parentWidget()
        #while p and not isinstance(p, (QtWidgets.QDialog, QtWidgets.QMainWindow)):
        #    p.updateGeometry()
        #    p = p.parentWidget()
        #if p:
        #    p.adjustSize()


def get_maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QMainWindow)


class buildRadialMenu_UI(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or get_maya_main_window())
        self.setWindowTitle("Radial Menu Editor")
        self.setMinimumSize(1200, 600)
        self._base_min = self.minimumSize()  # QSize(1200, 600)

        # ===== Main area with splitter =====
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(False)

        self.left = QtWidgets.QWidget()
        radialShow_layout = QVBoxLayout(self.left)
        radialShow_layout.setContentsMargins(0, 0, 0, 0)
        radialShow_layout.setSpacing(0)

        self.right = QtWidgets.QWidget()
        editRadialInfo_layout = QGridLayout(self.right)
        editRadialInfo_layout.setContentsMargins(4, 2, 4, 2)
        editRadialInfo_layout.setHorizontalSpacing(4)
        editRadialInfo_layout.setVerticalSpacing(2)

        self.splitter.addWidget(self.left)
        self.splitter.addWidget(self.right)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        #self.splitter.setSizes([800, 400])

        grid = QGridLayout(self)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(0)
        grid.addWidget(self.splitter, 0, 0)



        # Hidden context widgets (used by preview widget to tell us selection)
        self.hiddenLabel  = QLabel("")
        self.hiddenType   = QLabel("")
        self.hiddenParent = QLabel("")

        # --- Presets ---
        editRadialInfo_layout.addWidget(QLabel("Preset:"), 0, 0, 1, 1)
        from TDS_library.TDS_radialMenu import radialWidget as rw
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.addItems(rw.list_presets())
        self.preset_combo.setCurrentText(rw.get_active_preset())
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        editRadialInfo_layout.addWidget(self.preset_combo, 0, 1, 1, 2)

        row = 1
        preset_btns = QHBoxLayout()
        btn_new = QPushButton("New");      btn_new.clicked.connect(self._new_preset)
        btn_dup = QPushButton("Duplicate");btn_dup.clicked.connect(self._dup_preset)
        btn_del = QPushButton("Delete");   btn_del.clicked.connect(self._del_preset)
        for b in (btn_new, btn_dup, btn_del): preset_btns.addWidget(b)
        editRadialInfo_layout.addLayout(preset_btns, row, 0, 1, 3); row += 1

        # --- Active toggle ---
        self.active_chk = QtWidgets.QCheckBox("Active (included in scroll)")
        self.active_chk.setToolTip(
            "When off, this preset is skipped by the mouse wheel.\n"
            "Smart mode ignores this and can still select it."
        )
        self.active_chk.toggled.connect(self._on_active_toggled)
        editRadialInfo_layout.addWidget(self.active_chk, row, 0, 1, 3)
        row += 1

        self.smart_mode_combo = QtWidgets.QComboBox()
        self.smart_mode_combo.addItems(["Department", "Selection"])
        self.smart_mode_combo.currentTextChanged.connect(self._on_smart_mode_changed)
        editRadialInfo_layout.addWidget(QLabel("Smart mode: (Selection is WIP)"), row, 0, 1, 1)
        editRadialInfo_layout.addWidget(self.smart_mode_combo, row, 1, 1, 2)
        row += 1

        # --- Size controls ---
        editRadialInfo_layout.addWidget(QLabel("Menu Size (global):"), row, 0, 1, 3); row += 1

        self.radius_spin = QtWidgets.QSpinBox();       self.radius_spin.setRange(50, 2000); self.radius_spin.setSingleStep(5)
        self.ring_gap_spin = QtWidgets.QSpinBox();     self.ring_gap_spin.setRange(0, 400); self.ring_gap_spin.setSingleStep(1)
        self.outer_w_spin = QtWidgets.QSpinBox();      self.outer_w_spin.setRange(0, 800); self.outer_w_spin.setSingleStep(1)
        self.child_angle_mult_spin = QtWidgets.QDoubleSpinBox()
        self.child_angle_mult_spin.setRange(0.1, 8.0); self.child_angle_mult_spin.setSingleStep(0.1); self.child_angle_mult_spin.setDecimals(2)

        self.inner_hole_spin = QtWidgets.QSpinBox()
        self.inner_hole_spin.setRange(0, 1000)
        self.inner_hole_spin.setSingleStep(1)

        size_row1 = QHBoxLayout()
        size_row1.setContentsMargins(0, 0, 0, 0)
        size_row1.setSpacing(4)
        size_row1.addWidget(QLabel("Radius"))
        size_row1.addWidget(self.radius_spin)
        size_row1.addWidget(QLabel("Ring Gap"))
        size_row1.addWidget(self.ring_gap_spin)

        size_row2 = QHBoxLayout()
        size_row2.setContentsMargins(0, 0, 0, 0)
        size_row2.setSpacing(4)
        size_row2.addWidget(QLabel("Outer Width"))
        size_row2.addWidget(self.outer_w_spin)
        size_row2.addWidget(QLabel("Child Angle ×"))
        size_row2.addWidget(self.child_angle_mult_spin)
        size_row2.addWidget(QLabel("Inner Hole"))
        size_row2.addWidget(self.inner_hole_spin)  # ← NEW


        editRadialInfo_layout.addLayout(size_row1, row, 0, 1, 3)
        row += 1
        editRadialInfo_layout.addLayout(size_row2, row, 0, 1, 3)
        row += 1

        # Load size from JSON
        _all = radialWidget._load_data()
        _size = _all.get("ui", {}).get("size", {})
        self.radius_spin.setValue(int(_size.get("radius", 150)))
        self.ring_gap_spin.setValue(int(_size.get("ring_gap", 5)))
        self.outer_w_spin.setValue(int(_size.get("outer_ring_width", 25)))
        self.child_angle_mult_spin.setValue(float(_size.get("child_angle_multiplier", 1.0)))
        self.inner_hole_spin.setValue(int(_size.get("inner_hole_radius", max(0, int(_size.get("radius", 150) * 0.35)))))
        for w in (self.radius_spin, self.ring_gap_spin, self.outer_w_spin, self.child_angle_mult_spin, self.inner_hole_spin):
            w.valueChanged.connect(self._save_global_size)

        self.text_scale_spin = QtWidgets.QDoubleSpinBox()
        self.text_scale_spin.setRange(0.5, 10.0)
        self.text_scale_spin.setSingleStep(0.1)
        self.text_scale_spin.setDecimals(2)
        self.text_scale_spin.setValue(float(_size.get("text_scale", 1.0)))
        self.text_scale_spin.valueChanged.connect(self._save_global_size)

        size_row2.addWidget(QLabel("Text Scale"))
        size_row2.addWidget(self.text_scale_spin)

        # --- Colours section (collapsible) ---
        self.colours_frame = CollapsibleFrame("Colours (per preset)", collapsed=True)
        editRadialInfo_layout.addWidget(self.colours_frame, row, 0, 1, 3)
        row += 1

        self._colour_keys = OrderedDict([
            ("inner_colour", "Inner Fill"),
            ("innerHighlight_colour", "Inner Hover"),
            ("innerLine_colour", "Inner Line"),
            ("child_colour", "Child Fill"),
            ("childLine_colour", "Child Line"),
            ("child_text_color", "Child Text"),
            ("child_textOutline_color", "Child Text Outline"),
        ])
        self._colour_buttons = {}  # key -> QPushButton

        def add_colour_row(r_key, nice, r_idx):
            lbl = QLabel(nice + ":")
            lbl.setMinimumWidth(120)

            pick = QPushButton()
            pick.setFixedWidth(60)
            pick.clicked.connect(lambda _=None, k=r_key, b=pick: self._pick_colour(k, b))
            self._colour_buttons[r_key] = pick

            self.colours_frame.body_layout.addWidget(lbl, r_idx, 0, 1, 1)
            self.colours_frame.body_layout.addWidget(pick, r_idx, 1, 1, 2)

        row_c = 0
        for k, nice in self._colour_keys.items():
            add_colour_row(k, nice, row_c)
            row_c += 1

        # outline thickness in the same collapsible body
        self.colours_frame.body_layout.addWidget(QLabel("Child Text Outline Thickness:"), row_c, 0, 1, 1)
        self.outline_thickness = QtWidgets.QDoubleSpinBox()
        self.outline_thickness.setRange(0.0, 10.0)
        self.outline_thickness.setSingleStep(0.1)
        self.outline_thickness.setDecimals(2)
        self.outline_thickness.valueChanged.connect(self._save_colours)
        self.colours_frame.body_layout.addWidget(self.outline_thickness, row_c, 1, 1, 1)
        row_c += 1

        # --- Label/Desc/Save/Add ---
        editRadialInfo_layout.addWidget(QLabel("Label:"), row, 0, 1, 1)
        self.label_lineEdit = QLineEdit()
        editRadialInfo_layout.addWidget(self.label_lineEdit, row, 1, 1, 2); row += 1

        editRadialInfo_layout.addWidget(QLabel("Description:"), row, 0, 1, 1)
        self.desc_lineEdit = QLineEdit()
        editRadialInfo_layout.addWidget(self.desc_lineEdit, row, 1, 1, 2); row += 1

        addInner_btn = QPushButton("Add Inner"); addInner_btn.clicked.connect(self.add_inner)
        editRadialInfo_layout.addWidget(addInner_btn, row, 0, 1, 3); row += 1

        self.scriptTabs = QtWidgets.QTabWidget()
        self.scriptTabs.setDocumentMode(True)
        self.scriptEditor = QPlainTextEdit()  # Primary (legacy "command")
        self.releaseEditor = QPlainTextEdit()  # RMB release
        self.doubleEditor = QPlainTextEdit()  # LMB double-click
        self.scriptTabs.addTab(self.scriptEditor, "Primary (LMB Single-Click)")
        self.scriptTabs.addTab(self.releaseEditor, "RMB Release")
        self.scriptTabs.addTab(self.doubleEditor, "LMB Double-Click")

        self.scriptTabs.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        editRadialInfo_layout.addWidget(self.scriptTabs, row, 0, 1, 3)
        editRadialInfo_layout.setRowStretch(row, 1); row += 1

        save_btn = QPushButton("Save"); save_btn.clicked.connect(self.save_sectorInfo)
        editRadialInfo_layout.addWidget(save_btn, row, 0, 1, 3)

        # Layout stretch rules
        #grid.setColumnStretch(0, 3)
        #grid.setColumnStretch(1, 2)
        #grid.setRowStretch(0, 1)
        editRadialInfo_layout.setColumnStretch(0, 0)
        editRadialInfo_layout.setColumnStretch(1, 1)
        editRadialInfo_layout.setColumnStretch(2, 0)

        # --- Preview widget ---
        self.radial_widget = RadialMenuWidget(
            self,
            label_lineEdit=self.label_lineEdit,
            hiddenLabel=self.hiddenLabel,
            scriptEditor=self.scriptEditor,  # primary
            hiddenType=self.hiddenType,
            hiddenParent=self.hiddenParent,
            descEditor=self.desc_lineEdit,
            releaseEditor=self.releaseEditor,  # NEW
            doubleEditor=self.doubleEditor  # NEW
        )
        self.left.setMinimumWidth(self._preview_pixel_size().width() + 8)
        self.radial_widget.preset_previewed.connect(self._on_preset_previewed)
        self.radial_widget.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.radial_widget.setFixedSize(self._preview_pixel_size())
        self.radial_widget.updateGeometry()

        radialShow_layout.addWidget(self.radial_widget, 0, QtCore.Qt.AlignCenter)

        # Initial colour form fill
        self._load_colour_controls()

        try:
            from TDS_library.TDS_radialMenu import radialWidget as rw
            self._refresh_active_controls(rw.get_active_preset())
        except Exception:
            pass

        self._load_smart_mode()
        self._squash_layouts(self.right, margin=2, spacing=2)

    @QtCore.Slot(str)
    def _on_preset_previewed(self, name: str):
        # Mirror combo without triggering commit
        blocker = QtCore.QSignalBlocker(self.preset_combo)
        self.preset_combo.setCurrentText(name)
        self._refresh_active_controls(name)
        del blocker

        # Update colour controls for previewed preset
        self._load_colour_controls_for(name)
        # 🔹 Clear any previously selected inner/child in the editor UI
        self._clear_editor_selection()

    def _squash_layouts(self, root: QtWidgets.QWidget, margin=2, spacing=2):
        """Recursively compact margins/spacing for all child layouts."""

        def _walk_layout(layout: QtWidgets.QLayout):
            if layout is None:
                return
            layout.setContentsMargins(margin, margin, margin, margin)
            layout.setSpacing(spacing)
            for i in range(layout.count()):
                item = layout.itemAt(i)
                w = item.widget()
                if w and w.layout():
                    _walk_layout(w.layout())
                c = item.layout()
                if c:
                    _walk_layout(c)

        if root.layout():
            _walk_layout(root.layout())
        # also walk direct child widgets
        for w in root.findChildren(QtWidgets.QWidget):
            if w.layout():
                _walk_layout(w.layout())
    def _load_smart_mode(self):
        from TDS_library.TDS_radialMenu import radialWidget as rw
        mapping = {"department": "Department", "selection": "Selection"}
        mode = rw.get_smart_mode()
        blocker = QtCore.QSignalBlocker(self.smart_mode_combo)
        self.smart_mode_combo.setCurrentText(mapping.get(mode, "Selection"))
        del blocker

    def _on_smart_mode_changed(self, text: str):
        from TDS_library.TDS_radialMenu import radialWidget as rw
        inv = {"Department": "department", "Selection": "selection"}
        if rw.set_smart_mode(inv.get(text, "selection")):
            # optional: force an immediate smart re-eval so user sees it work
            try:
                chosen = rw.smart_autoswitch_now()
                if chosen:
                    self.preset_combo.blockSignals(True)
                    self.preset_combo.setCurrentText(chosen)
                    self.preset_combo.blockSignals(False)
                    self._on_preset_changed(chosen)
            except Exception:
                pass
            # refresh preview tint etc.
            try:
                self.radial_widget.update()
            except Exception:
                pass
    def _preview_pixel_size(self) -> QtCore.QSize:
        w = self.radial_widget
        # diameter of rings = 2 * (inner radius + gap + outer width)
        d = int(2 * (w.radius + w.ring_gap + w.outer_ring_width))
        pad = 4  # small AA/pen cushion
        extra_desc = 32  # space for the description line
        return QtCore.QSize(d + pad, d + pad + extra_desc)
    # ---------------- helpers ----------------
    def _load_active_checkbox_for(self, preset_name: str):
        data = radialWidget._load_data()
        flag = bool(data.get("presets", {}).get(preset_name, {}).get("active", True))
        blocker = QtCore.QSignalBlocker(self.active_chk)
        self.active_chk.setChecked(flag)
        del blocker

    def _refresh_active_controls(self, preset_name: str):
        """Enable/disable the Active checkbox and sync its state for the given preset."""
        is_default = (preset_name == "Default")
        # grey out when Default
        self.active_chk.setEnabled(not is_default)
        # sync the check state to JSON (uses blocker to avoid feedback)
        self._load_active_checkbox_for(preset_name)

    def _on_active_toggled(self, checked: bool):
        from TDS_library.TDS_radialMenu import radialWidget as rw

        data = self._load_all()
        name = self.preset_combo.currentText().strip()
        if not name:
            return

        # Hard guard: Default cannot be disabled
        if name == "Default" and not checked:
            cmds.warning("The 'Default' preset cannot be deactivated.")
            blocker = QtCore.QSignalBlocker(self.active_chk)
            self.active_chk.setChecked(True)
            del blocker
            return

        preset = data.setdefault("presets", OrderedDict()).setdefault(name, OrderedDict())
        preset["active"] = bool(checked)
        self._save_all(data)

        if not checked and name == rw.get_active_preset():
            # If you disable the currently-active preset (not Default), jump to Default
            rw.set_active_preset("Default")
            blocker = QtCore.QSignalBlocker(self.preset_combo)
            self.preset_combo.setCurrentText("Default")
            del blocker
            self._on_preset_changed("Default")
    def _load_all(self):
        # Use radialWidget's preset-aware loader (also migrates legacy schema)
        return radialWidget._load_data()

    def _current(self, data):
        # Use what’s selected in the Preset combo (sync’d by preview too)
        name = self.preset_combo.currentText().strip()
        return data["presets"][name]

    def _save_all(self, data):
        radialWidget._save_data(data)

    def _refresh_preview(self, data):
        preset = self._current(data)
        w = self.radial_widget
        w.inner_sections = preset.get("inner_section", OrderedDict())
        w.inner_order = list(w.inner_sections.keys())
        w.inner_angles = w.calculate_angles(w.inner_order)

        size = data.get("ui", {}).get("size", {"radius":150, "ring_gap":5, "outer_ring_width":25, "child_angle_multiplier":1.0})
        self._apply_size_to_preview(size)

    def _new_preset(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "New Preset", "Name:")
        if ok and name:
            from TDS_library.TDS_radialMenu import radialWidget as rw
            if rw.create_preset(name):
                # (optional) make it the active preset in JSON too:
                rw.set_active_preset(name)  # uses active_preset field :contentReference[oaicite:4]{index=4}
                blocker = QtCore.QSignalBlocker(self.preset_combo)
                self.preset_combo.clear()
                self.preset_combo.addItems(rw.list_presets())
                self.preset_combo.setCurrentText(name)
                del blocker
                # drive full refresh+preview sync
                self._on_preset_changed(name)

    def _dup_preset(self):
        cur = self.preset_combo.currentText()
        name, ok = QtWidgets.QInputDialog.getText(self, "Duplicate Preset", "Copy as:")
        if ok and name:
            from TDS_library.TDS_radialMenu import radialWidget as rw
            if rw.create_preset(name, clone_from=cur):
                rw.set_active_preset(name)  # optional, as above
                blocker = QtCore.QSignalBlocker(self.preset_combo)
                self.preset_combo.clear()
                self.preset_combo.addItems(rw.list_presets())
                self.preset_combo.setCurrentText(name)
                del blocker
                self._on_preset_changed(name)

    def _del_preset(self):
        cur = self.preset_combo.currentText()
        if cur == "Default":
            cmds.warning("The 'Default' preset cannot be deleted.")
            return
        from TDS_library.TDS_radialMenu import radialWidget as rw
        if rw.delete_preset(cur):
            blocker = QtCore.QSignalBlocker(self.preset_combo)
            self.preset_combo.clear()
            self.preset_combo.addItems(rw.list_presets())
            new_active = rw.get_active_preset()  # delete_preset may have changed it :contentReference[oaicite:5]{index=5}
            self.preset_combo.setCurrentText(new_active)
            del blocker
            self._on_preset_changed(new_active)
    def _save_global_size(self):
        """Auto-save global ui.size to JSON whenever a value changes."""
        data = self._load_all()
        ui = data.setdefault("ui", OrderedDict())
        size = ui.setdefault("size", OrderedDict())

        size["radius"] = int(self.radius_spin.value())
        size["ring_gap"] = int(self.ring_gap_spin.value())
        size["outer_ring_width"] = int(self.outer_w_spin.value())
        size["child_angle_multiplier"] = float(self.child_angle_mult_spin.value())
        size["inner_hole_radius"] = int(self.inner_hole_spin.value())
        size["text_scale"] = float(self.text_scale_spin.value())

        self._save_all(data)
        self._apply_size_to_preview(size)

    def _apply_size_to_preview(self, size):
        w = self.radial_widget
        w.radius = int(size.get("radius", 150))
        w.ring_gap = int(size.get("ring_gap", 5))
        w.outer_ring_width = int(size.get("outer_ring_width", 25))
        w.child_angle_mult = float(size.get("child_angle_multiplier", 1.0))
        w.inner_hole = int(size.get("inner_hole_radius", max(0, int(w.radius * 0.35))))  # ← NEW
        w.outer_radius = w.radius + w.ring_gap + w.outer_ring_width
        w.text_scale = float(size.get("text_scale", 1.0))
        w.child_font.setPixelSize(int(11 * w.text_scale))
        if hasattr(w, "inner_font"):
            w.inner_font.setPixelSize(int(12 * w.text_scale))
        if hasattr(w, "_recalc_display_metrics"):
            w._recalc_display_metrics()

        # Exact preview pixel size
        pix = self._preview_pixel_size()

        # Lock preview to that size
        w.setFixedSize(pix)
        w.updateGeometry()

        # Ensure the left pane can't be narrower than the preview
        left_min = pix.width() + 8
        self.left.setMinimumWidth(left_min)

        # If the splitter handle is currently left of the new minimum, nudge it to the minimum.
        # Otherwise leave the user's split alone.
        sizes = self.splitter.sizes()
        if sizes and sizes[0] < left_min:
            total = sum(sizes) if sum(sizes) > 0 else (self.width() or left_min)
            new_left = left_min
            new_right = max(total - new_left, 0)
            self.splitter.setSizes([new_left, new_right])

        # ---- Vertical sizing only (so the window can still shrink back later) ----
        base_h = self._base_min.height()
        chrome_h = 64  # header/margins breathing room
        min_h = max(base_h, pix.height() + chrome_h)
        self.setMinimumHeight(min_h)  # can go up or down
        if self.height() < min_h:
            self.resize(self.width(), min_h)

        w.update()

    # ---------- Colour helpers ----------
    def _load_colour_controls(self):
        data = radialWidget._load_data()
        ap = data.get("active_preset", "")
        if not ap:
            return
        self._load_colour_controls_for(ap)

    def _btn_hex(self, btn):
        """Extract color from button and return #AARRGGBB (Qt-friendly)."""
        ss = btn.styleSheet() or ""
        m = re.search(r'background-color:\s*([^;]+);?', ss, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            q = QtGui.QColor(candidate)
            if q.isValid():
                # Always ARGB
                return "#{:02X}{:02X}{:02X}{:02X}".format(q.alpha(), q.red(), q.green(), q.blue())

        # Fallback to palette; assume fully opaque
        q = btn.palette().button().color()
        return "#{:02X}{:02X}{:02X}{:02X}".format(255, q.red(), q.green(), q.blue())

    def _save_colours(self):
        """Persist colour buttons + outline thickness to JSON and live-apply."""
        data = radialWidget._load_data()
        name = self.preset_combo.currentText()
        preset = data["presets"][name]
        col = preset.setdefault("colour", OrderedDict())

        # read hex from each button
        for k, btn in self._colour_buttons.items():
            col[k] = self._btn_hex(btn)

        # thickness
        col["child_outline_thickness"] = float(self.outline_thickness.value())

        radialWidget._save_data(data)

        # live apply to preview
        try:
            self.radial_widget._apply_preset_colours(preset)
            self.radial_widget.update()
        except Exception:
            pass

    def _pick_colour(self, key, btn_widget):
        # Start from currently stored color (with alpha if any)
        data = radialWidget._load_data()
        preset_name = self.preset_combo.currentText().strip() or data.get("active_preset")
        preset = data["presets"][preset_name]
        col_block = preset.setdefault("colour", OrderedDict())
        curr = radialWidget._q(col_block.get(key, "#000000"), "#000000")

        dlg = QtWidgets.QColorDialog(self)
        dlg.setOption(QtWidgets.QColorDialog.ShowAlphaChannel, True)
        dlg.setCurrentColor(curr)

        if dlg.exec_():
            c = dlg.currentColor()

            # Store as legacy #RRGGBBAA (your JSON already uses this), our loader now handles both.
            hex_rrggbbaa = "#{:02X}{:02X}{:02X}{:02X}".format(c.alpha(), c.red(), c.green(), c.blue())
            print(hex_rrggbbaa)
            col_block[key] = hex_rrggbbaa
            radialWidget._save_data(data)

            # Swatch shows alpha via rgba(...) so there’s no QSS ambiguity
            btn_widget.setStyleSheet(
                "background-color: rgba({}, {}, {}, {});".format(c.red(), c.green(), c.blue(), c.alpha())
            )

            # Live apply to preview
            try:
                self.radial_widget._apply_preset_colours(preset)
                self.radial_widget.update()
            except Exception:
                pass

    # ---------------- adders ----------------
    def add_inner(self):
        data = self._load_all()
        preset = self._current(data)
        inner = preset.get("inner_section", OrderedDict())

        base = "new_section"
        i = 1
        label = base
        while label in inner:
            label = f"{base}_{i}"
            i += 1

        inner[label] = {
            "description": label,
            "command": f"print('{label}')",
            "on_release": "",
            "on_double": ""
        }
        preset["inner_section"] = inner
        self._save_all(data)
        self._refresh_preview(data)

        # focus in editor
        self.hiddenType.setText("inner")
        self.hiddenParent.setText("")
        self.hiddenLabel.setText(label)
        self.label_lineEdit.setText(label)
        self.scriptEditor.setPlainText(inner[label].get("command", ""))
        self.releaseEditor.setPlainText(inner[label].get("on_release", ""))
        self.doubleEditor.setPlainText(inner[label].get("on_double", ""))
        self.desc_lineEdit.setText(inner[label].get("description", ""))

    def add_child_to_active(self):
        """Add child under the currently selected inner or the parent of the selected child."""
        t = self.hiddenType.text()
        if t not in ("inner", "child"):
            cmds.warning("Select an inner slice (or a child) first.")
            return

        parent_label = self.hiddenLabel.text() if t == "inner" else self.hiddenParent.text()
        if not parent_label:
            cmds.warning("No parent inner section resolved.")
            return

        data = self._load_all()
        preset = self._current(data)
        inner = preset.get("inner_section", OrderedDict())
        parent = inner.get(parent_label)
        if parent is None:
            cmds.warning(f"Parent inner '{parent_label}' not found.")
            return

        children = parent.get("children")
        if not isinstance(children, dict):
            children = OrderedDict()
            parent["children"] = children

        base = "new_child"
        i = 1
        child_label = base
        while child_label in children:
            child_label = f"{base}_{i}"
            i += 1

        children[child_label] = {
            "description": child_label,
            "command": f"print('{child_label}')",
            "on_release": "",
            "on_double": ""
        }

        preset["inner_section"] = inner
        self._save_all(data)
        self._refresh_preview(data)

        # focus in editor
        self.hiddenType.setText("child")
        self.hiddenParent.setText(parent_label)
        self.hiddenLabel.setText(child_label)
        self.label_lineEdit.setText(child_label)
        self.scriptEditor.setPlainText(children[child_label].get("command", ""))
        self.releaseEditor.setPlainText(children[child_label].get("on_release", ""))
        self.doubleEditor.setPlainText(children[child_label].get("on_double", ""))
        self.desc_lineEdit.setText(children[child_label].get("description", ""))

    # ---------------- save/rename ----------------
    def save_sectorInfo(self):
        curLabel = self.hiddenLabel.text().strip()
        newLabel = self.label_lineEdit.text().strip()
        sel_type = self.hiddenType.text().strip()  # "inner" or "child"
        primary = self.scriptEditor.toPlainText()
        rmb_rel = self.releaseEditor.toPlainText()
        lmb_dbl = self.doubleEditor.toPlainText()

        desc = self.desc_lineEdit.text().strip()

        if not curLabel:
            cmds.warning("Nothing selected.")
            return
        if not newLabel:
            cmds.warning("Label cannot be empty.")
            return

        data = self._load_all()
        preset = self._current(data)

        # ----- INNER -----
        if sel_type == "inner":
            section_dict = preset.get("inner_section", OrderedDict())
            if curLabel not in section_dict:
                cmds.warning(f"Inner '{curLabel}' not found.")
                return

            section_dict[curLabel]["command"] = primary
            section_dict[curLabel]["on_release"] = rmb_rel
            section_dict[curLabel]["on_double"] = lmb_dbl
            section_dict[curLabel]["description"] = desc

            renamed = OrderedDict()
            for k, v in section_dict.items():
                renamed[newLabel if k == curLabel else k] = v
            preset["inner_section"] = renamed

        # ----- CHILD -----
        elif sel_type == "child":
            parent_label = self.hiddenParent.text().strip()
            if not parent_label:
                cmds.warning("No parent recorded for child.")
                return

            inner = preset.get("inner_section", OrderedDict())
            parent_data = inner.get(parent_label)
            if parent_data is None:
                cmds.warning(f"Parent '{parent_label}' not found.")
                return

            children = parent_data.get("children", OrderedDict())
            if curLabel not in children:
                cmds.warning(f"Child '{curLabel}' not found under '{parent_label}'.")
                return

            children[curLabel]["command"] = primary
            children[curLabel]["on_release"] = rmb_rel
            children[curLabel]["on_double"] = lmb_dbl
            children[curLabel]["description"] = desc

            renamed = OrderedDict()
            for k, v in children.items():
                renamed[newLabel if k == curLabel else k] = v
            parent_data["children"] = renamed
            preset["inner_section"] = inner

        else:
            cmds.warning("Unknown selection type.")
            return

        self._save_all(data)
        self._refresh_preview(data)
        self.hiddenLabel.setText(newLabel)

        w = self.radial_widget

        if sel_type == "inner":
            # highlight the renamed/edited inner slice
            w.active_sector = newLabel
            w.hovered_children = w.inner_sections.get(newLabel, {}).get("children", OrderedDict())
            w.hovered_child_angles = w.get_child_angles() if w.hovered_children else {}
            w.outer_active_sector = None

        elif sel_type == "child":
            # keep parent locked and highlight the renamed/edited child
            parent_label = self.hiddenParent.text().strip()
            w.active_sector = parent_label
            w.hovered_children = w.inner_sections.get(parent_label, {}).get("children", OrderedDict())
            w.hovered_child_angles = w.get_child_angles() if w.hovered_children else {}
            w.outer_active_sector = newLabel

        w.update()  # repaint now (no mouse move required)

    def _load_colour_controls_for(self, preset_name: str):
        data = radialWidget._load_data()
        if "presets" not in data or preset_name not in data["presets"]:
            return

        preset = data["presets"][preset_name]
        col = preset.setdefault("colour", OrderedDict())

        defaults = {
            "inner_colour": "#454545",
            "innerHighlight_colour": "#282828",
            "innerLine_colour": "#1E1E1E",
            "child_colour": "#5285a6",
            "childLine_colour": "#1E1E1E",
            "child_text_color": "#FFFFFF",
            "child_textOutline_color": "#000000",
            "child_outline_thickness": 1,
        }
        for k, v in defaults.items():
            col.setdefault(k, v)

        # Update UI buttons
        for k, btn in self._colour_buttons.items():
            qcol = radialWidget._q(col.get(k, defaults[k]), defaults[k])
            btn.setStyleSheet(
                "background-color: rgba({}, {}, {}, {});".format(
                    qcol.red(), qcol.green(), qcol.blue(), qcol.alpha()
                )
            )

        # Spinbox (block to avoid valueChanged recursion)
        self.outline_thickness.blockSignals(True)
        self.outline_thickness.setValue(float(col.get("child_outline_thickness", defaults["child_outline_thickness"])))
        self.outline_thickness.blockSignals(False)

        # Live-apply to preview widget too
        try:
            self.radial_widget._apply_preset_colours(preset)
            self.radial_widget.update()
        except Exception:
            pass

    def _clear_editor_selection(self):
        # Clear hidden context
        self.hiddenLabel.setText("")
        self.hiddenType.setText("")
        self.hiddenParent.setText("")
        # Clear visible editors
        self.label_lineEdit.clear()
        self.scriptEditor.clear()
        self.desc_lineEdit.clear()
        self.releaseEditor.clear()
        self.doubleEditor.clear()

    def _on_preset_changed(self, name):
        if not name:
            return
        if radialWidget.set_active_preset(name):
            data = self._load_all()
            self._refresh_preview(data)

            # Update colour controls to the newly active preset
            self._load_colour_controls_for(name)
            self._refresh_active_controls(name)
            self._load_active_checkbox_for(name)


            # Keep scroll-preview in sync and apply colours/sections immediately
            self.radial_widget._preview_name = name
            self.radial_widget._preview_preset(name)

            # 🔹 Clear any previously selected inner/child in the editor UI
            self._clear_editor_selection()



def show_window():
    global _simple_window_instance
    try:
        _simple_window_instance.close()
        _simple_window_instance.deleteLater()
    except:
        pass
    _simple_window_instance = buildRadialMenu_UI()
    _simple_window_instance.show()
