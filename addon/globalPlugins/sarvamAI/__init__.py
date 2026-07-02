# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.
# See the file LICENSE for more details.

"""Sarvam AI assistant - a global plugin exposing the Sarvam AI platform
(text to speech, speech to text, translation, transliteration, language
detection, AI chat / summarisation and Windows OCR) through an accessible,
keyboard-driven NVDA interface."""

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
		add(_("&OCR..."), self.onOcr)
		add(_("&AI Assistant / Summarise..."), self.onChat)
		menu.AppendSeparator()
		add(_("Se&ttings..."), self.onSettings)
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
		from .ui.chat import ChatDialog
		from .ui.tts import _get_selection
		self._open(lambda: ChatDialog(gui.mainFrame, initial_text=_get_selection()))

	def onSettings(self, evt=None):
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
	# The main launcher is bound to NVDA+alt+s by default (mnemonic: Sarvam).
	# All other commands are unbound; assign them in Input Gestures > Sarvam AI.
	@script(
		# Translators: input help for opening the Sarvam AI menu.
		description=_("Opens the Sarvam AI menu"),
		category=SCRIPT_CATEGORY,
		gesture="kb:NVDA+alt+s")
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
		description=_("Recognises the current screen or object with Windows OCR"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_ocrScreen(self, gesture):
		from . import ocr
		if not ocr.is_available():
			nvdaUi.message(_("Windows OCR is not available"))
			return
		nvdaUi.message(_("Recognising"))

		def onText(text):
			from .ui.common import ResultDialog
			from .ui.translate import TranslateDialog
			from .ui.chat import ChatDialog
			dlg = ResultDialog(
				gui.mainFrame, _("Sarvam AI - OCR result"), text,
				on_translate=lambda t: TranslateDialog(gui.mainFrame, initial_text=t).Show(),
				on_summarize=lambda t: ChatDialog(gui.mainFrame, initial_text=t, mode="summarize").Show())
			dlg.Show()

		def onError(exc):
			from .ui.common import error_dialog
			error_dialog(gui.mainFrame, exc)

		ocr.recognize_screen(onText, onError)

	@script(
		description=_("Opens the Sarvam AI assistant (chat and summarise) window"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_chat(self, gesture):
		self.onChat()

	@script(
		description=_("Opens the Sarvam AI settings"),
		category=SCRIPT_CATEGORY, gesture=None)
	def script_settings(self, gesture):
		self.onSettings()
