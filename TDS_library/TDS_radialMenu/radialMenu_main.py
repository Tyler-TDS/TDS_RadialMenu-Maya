import maya.cmds as cmds
from PySide2 import QtWidgets
from TDS_library.TDS_radialMenu import radialWidget
from TDS_library.TDS_radialMenu.radialWidget import RightClickHoldDetector, fresh_radial_cls, get_main_window


try:
    _rmb_detector_ref
except NameError:
    _rmb_detector_ref = {"instance": None}

try:
    radial_enabled
except NameError:
    radial_enabled = {"state": True}

# in radialMenu_main.py (your small wrapper/entry helpers)
from TDS_library.TDS_radialMenu import radialWidget as rw

def toggle_smart_preset(force_state=None):
    """Toggle smart preset on/off.
    If force_state is True/False, explicitly set it.
    If None, just flip current state."""
    cur = rw.is_smart_preset_enabled()
    if force_state is None:
        new_state = not cur
    else:
        new_state = bool(force_state)

    rw.set_smart_preset_enabled(new_state)
    msg = "ON" if new_state else "OFF"
    cmds.inViewMessage(amg=f"Smart Preset: <hl>{msg}</hl>", pos='topCenter', fade=True)


def toggle_radial_menu(force_state=None):
    if force_state is not None:
        radial_enabled["state"] = bool(force_state)
    else:
        radial_enabled["state"] = not radial_enabled["state"]

    state = "ON" if radial_enabled["state"] else "OFF"
    print(f"Radial Menu is now {state}")
    cmds.inViewMessage(amg=f"Radial Menu: <hl>{state}</hl>", pos='topCenter', fade=True)

def install_rmb_hold_detector():
    app = QtWidgets.QApplication.instance()
    if _rmb_detector_ref["instance"]:
        app.removeEventFilter(_rmb_detector_ref["instance"])

    detector = RightClickHoldDetector(radial_enabled, parent=app)  # pass toggle dict
    app.installEventFilter(detector)
    _rmb_detector_ref["instance"] = detector
    print("Radial RMB detector installed.")

def select_preset(name: str):
    from TDS_library.TDS_radialMenu import radialWidget as rw
    if rw.set_active_preset(name):
        cmds.inViewMessage(amg=f"Radial Preset: <hl>{name}</hl>", pos='topCenter', fade=True)

def launch_or_toggle_radial(force_state=None):
    """If RMB detector installed, toggle or set active state.
       If not installed, install & enable (or disable if force_state=False)."""

    app = QtWidgets.QApplication.instance()

    # Helper to apply state change without reinstall
    def _set_state(new_state):
        radial_enabled["state"] = new_state
        state_txt = "ON" if new_state else "OFF"
        print(f"Radial Menu is now {state_txt}")
        cmds.inViewMessage(amg=f"Radial Menu: <hl>{state_txt}</hl>", pos='topCenter', fade=True)

    if _rmb_detector_ref["instance"] is None:
        # Not installed
        detector = RightClickHoldDetector(radial_enabled, parent=app)
        app.installEventFilter(detector)
        _rmb_detector_ref["instance"] = detector

        if force_state is None:
            radial_enabled["state"] = True
        else:
            radial_enabled["state"] = bool(force_state)

        state_txt = "ON" if radial_enabled["state"] else "OFF"
        print(f"Radial RMB detector installed and active: {state_txt}")
        cmds.inViewMessage(amg=f"Radial Menu: <hl>{state_txt}</hl>", pos='topCenter', fade=True)

    else:
        # Already installed
        if force_state is None:
            # Toggle
            _set_state(not radial_enabled["state"])
        else:
            # Force to specific value
            _set_state(bool(force_state))

def uninstall_radial_menu():
    """Completely remove the RMB hold detector and disable the radial menu."""
    app = QtWidgets.QApplication.instance()

    if _rmb_detector_ref["instance"] is not None:
        try:
            app.removeEventFilter(_rmb_detector_ref["instance"])
            _rmb_detector_ref["instance"].deleteLater()
        except Exception:
            pass
        _rmb_detector_ref["instance"] = None

    radial_enabled["state"] = False
    print("Radial RMB detector uninstalled.")
    cmds.inViewMessage(amg="Radial Menu: <hl>UNINSTALLED</hl>", pos='topCenter', fade=True)