# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.
# See the file LICENSE for more details.

"""Sarvam AI assistant - a global plugin exposing the Sarvam AI platform
(text to speech, speech to text, translation and document translation,
transliteration, language detection, Document AI, the AI Workforce and Agent,
AI vision and model switching) through an accessible, keyboard-driven NVDA
interface."""

import wx

import globalPluginHandler
import gui
import addonHandler
import ui as nvdaUi
from scriptHandler import script

addonHandler.initTranslation()

from . import config
from . import logger
from . import constants

# Translators: the input-gestures category for this add-on.
SCRIPT_CATEGORY = _("Sarvam AI")


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def __init__(self):
		super().__init__()
		config.initialize()
		logger.setDebug(bool(config.conf().get("debugLogging")))
		logger.info("Sarvam AI assistant loaded.")

		# Register the settings category.
		from .ui.settings import SarvamSettingsPanel
		self._settingsPanel = SarvamSettingsPanel
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(SarvamSettingsPanel)

		self._menu = None
		self._menuItem = None
		self._buildMenu()

	def terminate(self):
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(self._settingsPanel)
		except Exception:
			pass
		self._removeMenu()
		super().terminate()

	# -- menu ---------------------------------------------------------------
	def _populate(self, menu, target):
		"""Append all Sarvam AI items to ``menu`` and bind them to ``target``
		(the window that will receive the menu events)."""
		def add(label, handler):
			item = menu.Append(wx.ID_ANY, label)
			target.Bind(wx.EVT_MENU, handler, item)
			return item

		# Translators: items in the Sarvam AI menu.
		add(_("&Text to Speech..."), self.onTextToSpeech)
		add(_("&Speech to Text..."), self.onSpeechToText)
		add(_("&Translate..."), self.onTranslate)
		add(_("T&ransliterate..."), self.onTransliterate)
		add(_("&Detect language..."), self.onDetectLanguage)
		add(_("D&ocuments and OCR (read, extract data)..."), self.onOcr)
		# AI Assistant and AI Summarise are Task modes inside AI Workforce.
		add(_("AI &Workforce (assistant, summary, analysis)..."), self.onWorkforce)
		add(_("Sarvam &Agent (does multi-step work for you)..."), self.onAgent)
		add(_("Describe the &screen with AI vision"), self.onDescribeScreen)
		menu.AppendSeparator()
		add(_("&Model switching..."), self.onModels)
		add(_("Se&ttings (API key)..."), self.onSettings)
		add(_("Ad&vanced settings..."), self.onAdvancedSettings)
		add(_("&Logs..."), self.onLogs)
		add(_("Check for &updates..."), self.onCheckUpdates)
		add(_("&Help..."), self.onHelp)
		add(_("A&bout..."), self.onAbout)
		return menu

	def _buildMenu(self):
		"""Add a 'Sarvam AI' submenu to the NVDA menu (under Tools)."""
		try:
			toolsMenu = gui.mainFrame.sysTrayIcon.toolsMenu
		except Exception:
			logger.warning("Could not access the NVDA Tools menu.")
			return
		self._menu = self._populate(wx.Menu(), gui.mainFrame.sysTrayIcon)
		# Translators: the Sarvam AI submenu label in the NVDA menu (under Tools).
		self._menuItem = toolsMenu.AppendSubMenu(self._menu, _("Sar&vam AI"))
		logger.info("Sarvam AI menu added to the NVDA Tools menu.")

	def _removeMenu(self):
		try:
			if self._menuItem:
				gui.mainFrame.sysTrayIcon.toolsMenu.Remove(self._menuItem)
		except Exception:
			pass
		self._menuItem = None
		self._menu = None

	def _popupMenu(self):
		"""Show the Sarvam AI menu as a pop-up (used by the hotkey)."""
		menu = self._populate(wx.Menu(), gui.mainFrame)
		try:
			gui.mainFrame.prePopup()
			gui.mainFrame.PopupMenu(menu)
		finally:
			gui.mainFrame.postPopup()
			menu.Destroy()

	# -- dialog openers -----------------------------------------------------
	def _open(self, factory):
		"""Create and show a dialog on the main thread, guarding against
		duplicates and surfacing construction errors accessibly."""
		def run():
			try:
				dlg = factory()
				dlg.Show()
			except Exception as e:
				logger.exception("Could not open dialog")
				gui.messageBox(
					_("Could not open the window: {err}").format(err=e),
					_("Sarvam AI - Error"), wx.OK | wx.ICON_ERROR)
		wx.CallAfter(run)

	def onTextToSpeech(self, evt=None):
		from .ui.tts import TextToSpeechDialog, _get_selection
		self._open(lambda: TextToSpeechDialog(gui.mainFrame, initial_text=_get_selection()))

	def onSpeechToText(self, evt=None):
		from .ui.stt import SpeechToTextDialog
		self._open(lambda: SpeechToTextDialog(gui.mainFrame))

	def onTranslate(self, evt=None):
		from .ui.translate import TranslateDialog
		from .ui.tts import _get_selection
		self._open(lambda: TranslateDialog(gui.mainFrame, initial_text=_get_selection(),
			operation=TranslateDialog.OP_TRANSLATE))

	def onTransliterate(self, evt=None):
		from .ui.translate import TranslateDialog
		from .ui.tts import _get_selection
		self._open(lambda: TranslateDialog(gui.mainFrame, initial_text=_get_selection(),
			operation=TranslateDialog.OP_TRANSLITERATE))

	def onDetectLanguage(self, evt=None):
		from .ui.translate import TranslateDialog
		from .ui.tts import _get_selection
		self._open(lambda: TranslateDialog(gui.mainFrame, initial_text=_get_selection(),
			operation=TranslateDialog.OP_DETECT))

	def onOcr(self, evt=None):
		from .ui.ocr_dialog import OcrDialog
		self._open(lambda: OcrDialog(gui.mainFrame))

	def onChat(self, evt=None):
		# Kept for backward compatibility (old gestures): opens AI Workforce.
		self.onWorkforce(evt)

	def onWorkforce(self, evt=None):
		from .ui.workforce import WorkforceDialog
		from .ui.tts import _get_selection
		self._open(lambda: WorkforceDialog(gui.mainFrame, initial_text=_get_selection()))

	def onAgent(self, evt=None):
		from .ui.workforce import WorkforceDialog
		self._open(lambda: WorkforceDialog(gui.mainFrame, mode=constants.AGENT_ROLE))

	def onModels(self, evt=None):
		from .ui.models import ModelCenterDialog
		self._open(lambda: ModelCenterDialog(gui.mainFrame))

	def onDescribeScreen(self, evt=None, foreground=True):
		"""Capture the foreground window and have a vision model describe it.

		The capture happens before any Sarvam window opens, so it shows what
		the user was looking at.
		"""
		if evt is not None:
			# Chosen from a menu: let the menu close and the previous window
			# regain the foreground before capturing.
			wx.CallLater(700, self.onDescribeScreen, None, foreground)
			return
		from . import imaging
		try:
			jpeg = imaging.capture_screen_jpeg(foreground=foreground)
		except Exception as e:
			logger.exception("Screen capture failed")
			nvdaUi.message(_("Could not capture the screen: {err}").format(err=e))
			return
		nvdaUi.message(_("Screen captured. Describing..."))
		from .ui.workforce import WorkforceDialog
		self._open(lambda: WorkforceDialog(gui.mainFrame, mode=constants.VISION_ROLE,
			initial_image=(jpeg, "image/jpeg", _("screenshot"))))

	def onSettings(self, evt=None):
		from .ui.setup import SetupDialog
		self._open(lambda: SetupDialog(gui.mainFrame))

	def onAdvancedSettings(self, evt=None):
		wx.CallAfter(gui.mainFrame.popupSettingsDialog,
			gui.settingsDialogs.NVDASettingsDialog, self._settingsPanel)

	def onLogs(self, evt=None):
		from .ui.logs import LogViewerDialog
		self._open(lambda: LogViewerDialog(gui.mainFrame))

	def onCheckUpdates(self, evt=None):
		from . import updatecheck
		updatecheck.check(gui.mainFrame, interactive=True)

	def onHelp(self, evt=None):
		import addonHandler
		import os
		for addon in addonHandler.getRunningAddons():
			if addon.name == constants.ADDON_NAME:
				path = os.path.join(addon.path, "doc", "en", "readme.html")
				if os.path.isfile(path):
					os.startfile(path)
					return
		gui.messageBox(_("Help file not found."), _("Sarvam AI"), wx.OK | wx.ICON_INFORMATION)

	def onAbout(self, evt=None):
		from .ui import about
		gui.messageBox(about.about_text(), _("About Sarvam AI assistant"),
			wx.OK | wx.ICON_INFORMATION)

	# -- gestures -----------------------------------------------------------
	# No gesture is bound by default (NVDA+Alt+S is taken by NVDA's built-in
	# "sound split" command). Assign your own key to "Opens the Sarvam AI menu"
	# under Input Gestures > Sarvam AI.
	@script(
		# Translators: input help for opening the Sarvam AI menu.
		description=_("Opens the Sarvam AI menu"),
		category=SCRIPT_CATEGORY,
		gesture=None)
	def script_openSarvamMenu(self, gesture):
		wx.CallAfter(self._popupMenu)

	@script(
		# Translators: input help for opening the text to speech window.
		description=_("Opens the Sarvam AI Text to Speech window with the current selection"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_textToSpeech(self, gesture):
		self.onTextToSpeech()

	@script(
		# Translators: input help mode message.
		description=_("Speaks the current selection with Sarvam AI text to speech"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_speakSelection(self, gesture):
		from .ui.tts import TextToSpeechDialog, _get_selection
		text = _get_selection()
		if not text:
			nvdaUi.message(_("No selected text"))
			return
		def run():
			dlg = TextToSpeechDialog(gui.mainFrame, initial_text=text)
			dlg.Show()
			dlg.onSpeak(None)
		wx.CallAfter(run)

	@script(
		description=_("Opens the Sarvam AI Speech to Text window"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_speechToText(self, gesture):
		self.onSpeechToText()

	@script(
		description=_("Opens the Sarvam AI Translate window with the current selection"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_translate(self, gesture):
		self.onTranslate()

	@script(
		description=_("Opens the Sarvam AI OCR window"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_ocr(self, gesture):
		self.onOcr()

	@script(
		description=_("Opens the Sarvam AI Workforce (assistant, summary, analysis) window"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_workforce(self, gesture):
		self.onWorkforce()

	@script(
		description=_("Opens the Sarvam Agent, which carries out multi-step tasks"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_agent(self, gesture):
		self.onAgent()

	@script(
		description=_("Describes the current window with Sarvam AI vision"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_describeScreen(self, gesture):
		wx.CallAfter(self.onDescribeScreen)

	@script(
		description=_("Describes the whole screen with Sarvam AI vision"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_describeWholeScreen(self, gesture):
		wx.CallAfter(self.onDescribeScreen, None, False)

	@script(
		description=_("Opens Sarvam AI model switching"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_models(self, gesture):
		self.onModels()

	@script(
		description=_("Switches to the next Sarvam AI chat model and announces it"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_nextChatModel(self, gesture):
		from .ui.models import cycle_chat_model
		nvdaUi.message(cycle_chat_model(1))

	@script(
		description=_("Opens the Sarvam AI settings"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_settings(self, gesture):
		self.onSettings()
