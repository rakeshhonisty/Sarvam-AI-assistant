# -*- coding: UTF-8 -*-
"""Minimal stand-ins for NVDA and wxPython so the add-on can be imported and
exercised outside NVDA (unit tests and dialog smoke tests).

``Dummy`` is a forgiving object: any attribute, call, index or arithmetic
returns another Dummy, so dialog constructors run end to end and any
NameError / AttributeError in *our* code still surfaces.
"""

import builtins
import os
import sys
import types


class Dummy:
	def __init__(self, *a, **k):
		self._items = []
		self._sel = 0
		self._value = k.get("value", "")
		self._shown = True

	# Generic behaviour -----------------------------------------------------
	def __getattr__(self, name):
		if name.startswith("__"):
			raise AttributeError(name)
		return Dummy()

	def __call__(self, *a, **k):
		return Dummy()

	def __iter__(self):
		return iter(())

	def __bool__(self):
		return True

	def __index__(self):
		return 0

	def __int__(self):
		return 0

	def __or__(self, other):
		return self

	__ror__ = __or__

	def __enter__(self):
		return self

	def __exit__(self, *a):
		return False

	# Behaviour of the controls the add-on reads back ------------------------
	def Set(self, items):
		self._items = list(items)
		self._sel = 0 if self._items else -1

	def Append(self, item, *a):
		self._items.append(item)
		return Dummy()

	def GetCount(self):
		return len(self._items)

	def GetString(self, i):
		return self._items[i]

	def SetSelection(self, i):
		self._sel = i

	def GetSelection(self):
		return self._sel if self._items else 0

	def GetStringSelection(self):
		return self._items[self._sel] if self._items and self._sel >= 0 else ""

	def SetValue(self, v):
		self._value = v

	def ChangeValue(self, v):
		self._value = v

	def GetValue(self):
		return self._value

	def AppendText(self, t):
		self._value = (self._value or "") + t

	def SetLabel(self, t):
		self._value = t

	def Show(self, show=True):
		self._shown = show

	def ShowModal(self):
		return 0

	def GetPath(self):
		return ""

	def GetPaths(self):
		return []


class DummyModule(types.ModuleType):
	def __getattr__(self, name):
		if name.startswith("__"):
			raise AttributeError(name)
		return Dummy


class _ChoiceMixin(Dummy):
	"""Controls built via ``wx.Choice(..., choices=[...])``."""

	def __init__(self, *a, **k):
		super().__init__(*a, **k)
		self._items = list(k.get("choices") or [])


def _install_wx():
	wx = DummyModule("wx")
	for name in ("Dialog", "Frame", "Panel", "Window", "Menu", "BoxSizer", "StaticText",
			"TextCtrl", "CheckBox", "Button", "Slider", "SpinCtrl", "Gauge", "FileDialog",
			"DirDialog", "TextDataObject", "CallLater"):
		setattr(wx, name, Dummy)
	wx.Choice = _ChoiceMixin
	wx.ComboBox = _ChoiceMixin
	wx.CallAfter = lambda fn, *a, **k: None
	for const in ("ID_ANY", "ID_OK", "ID_CLOSE", "ID_CANCEL", "VERTICAL", "HORIZONTAL",
			"ALL", "EXPAND", "TE_MULTILINE", "TE_READONLY", "TE_RICH2", "TE_PASSWORD",
			"TE_PROCESS_ENTER", "TE_NO_VSCROLL", "SL_HORIZONTAL", "DEFAULT_DIALOG_STYLE",
			"RESIZE_BORDER", "FD_OPEN", "FD_SAVE", "FD_FILE_MUST_EXIST", "FD_OVERWRITE_PROMPT",
			"FD_MULTIPLE", "OK", "YES", "NO", "ICON_ERROR", "ICON_INFORMATION", "ICON_QUESTION",
			"WXK_RETURN", "WXK_NUMPAD_ENTER", "WXK_ESCAPE", "ALIGN_RIGHT"):
		setattr(wx, const, 1)
	for evt in ("EVT_BUTTON", "EVT_CHOICE", "EVT_MENU", "EVT_CLOSE", "EVT_CHAR_HOOK",
			"EVT_KEY_DOWN", "EVT_TEXT_ENTER", "EVT_SLIDER"):
		setattr(wx, evt, 1)
	wx.TheClipboard = Dummy()
	sys.modules["wx"] = wx


class _Helper(Dummy):
	"""guiHelper.BoxSizerHelper: addLabeledControl builds the real control class."""

	def addLabeledControl(self, label, cls, **kw):
		return cls(None, **kw)

	def addItem(self, item, *a, **k):
		return item


class _ButtonHelper(Dummy):
	def addButton(self, *a, **k):
		return Dummy()


class _Conf(dict):
	def get(self, k, d=None):
		return dict.get(self, k, d)


class _NVDAConf(dict):
	def __init__(self):
		super().__init__()
		self.spec = {}


def install(translation=True):
	"""Install the stubs into ``sys.modules`` and put the add-on on the path."""
	if translation:
		builtins._ = lambda s: s
	addonHandler = types.ModuleType("addonHandler")
	addonHandler.initTranslation = lambda: None
	addonHandler.getRunningAddons = lambda: []
	sys.modules["addonHandler"] = addonHandler

	cfg = types.ModuleType("config")
	cfg.conf = _NVDAConf()
	sys.modules["config"] = cfg

	_install_wx()
	gui = DummyModule("gui")
	guiHelper = types.ModuleType("gui.guiHelper")
	guiHelper.BoxSizerHelper = _Helper
	guiHelper.ButtonHelper = _ButtonHelper
	guiHelper.BORDER_FOR_DIALOGS = 10
	gui.guiHelper = guiHelper
	gui.messageBox = lambda *a, **k: 1
	settingsDialogs = types.ModuleType("gui.settingsDialogs")
	settingsDialogs.SettingsPanel = Dummy
	settingsDialogs.NVDASettingsDialog = types.SimpleNamespace(categoryClasses=[])
	gui.settingsDialogs = settingsDialogs
	gui.mainFrame = Dummy()
	sys.modules["gui"] = gui
	sys.modules["gui.guiHelper"] = guiHelper
	sys.modules["gui.settingsDialogs"] = settingsDialogs
	sys.modules["gui.nvdaControls"] = DummyModule("gui.nvdaControls")

	for name in ("globalPluginHandler", "api", "textInfos", "nvwave", "scriptHandler", "logHandler"):
		sys.modules[name] = DummyModule(name)
	import tempfile
	globalVars = types.ModuleType("globalVars")
	globalVars.appArgs = types.SimpleNamespace(configPath=tempfile.gettempdir())
	sys.modules["globalVars"] = globalVars
	sys.modules["globalPluginHandler"].GlobalPlugin = Dummy
	sys.modules["scriptHandler"].script = lambda **k: (lambda f: f)
	ui = types.ModuleType("ui")
	ui.message = lambda *a, **k: None
	sys.modules["ui"] = ui

	root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
		"addon", "globalPlugins")
	if root not in sys.path:
		sys.path.insert(0, root)


def fresh_config():
	"""Initialise the add-on config against the stub NVDA config."""
	import config as nvda_config
	nvda_config.conf.clear()
	from sarvamAI import config
	nvda_config.conf[config.SECTION] = _Conf()
	config.initialize()
	return config
