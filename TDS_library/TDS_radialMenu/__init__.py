from .TDS_buildRadialMenu_UI import buildRadialMenu_UI

from . import radialWidget
radialWidget.set_live_reload(False)

import importlib
importlib.reload(TDS_buildRadialMenu_UI)

def show_window():
    TDS_buildRadialMenu_UI.show_window()

def run_menu():
    import radialMenu_main

# radialMenu_main.py (or wherever your RMB-hold callback lives)
import sys, importlib
from PySide2 import QtWidgets
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance

PKGS_TO_RELOAD = [
    "TDS_library.TDS_radialMenu.radialWidget",   # your widget/paint code
    # add more module paths if your look is split across files
]

def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QMainWindow)

def _fresh_radial_cls():
    """Reload menu modules and return a fresh RadialMenuWidget class."""
    # reload children first (reverse depth), then parents
    for name in sorted([n for n in sys.modules if any(n.startswith(p) for p in PKGS_TO_RELOAD)], reverse=True):
        try:
            importlib.reload(sys.modules[name])
        except Exception:
            pass

    # ensure the main widget module is imported and return class
    mod = importlib.import_module("TDS_library.TDS_radialMenu.radialWidget")
    return mod.RadialMenuWidget

# ==== RMB HOLD CALLBACK ====
_ACTIVE_MENU = None  # kill previous ephemeral menu if detector fires again

def on_rmb_hold_show_menu(screen_pos):
    global _ACTIVE_MENU
    try:
        if _ACTIVE_MENU is not None:
            _ACTIVE_MENU.close()
            _ACTIVE_MENU.setParent(None)
            _ACTIVE_MENU.deleteLater()
    except Exception:
        pass
    _ACTIVE_MENU = None

    RadialMenuWidget = _fresh_radial_cls()   # <-- hot reload happens here
    w = RadialMenuWidget(parent=_maya_main_window())
    # position at cursor (adjust for your sizing)
    w.move(int(screen_pos.x() - w.width()/2), int(screen_pos.y() - w.height()/2))
    w.show()
    QtWidgets.QApplication.processEvents()
    _ACTIVE_MENU = w
