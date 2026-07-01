# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Shared UI helpers: accessible pickers, message helpers and a reusable result
dialog with copy / save / send-to-Sarvam actions."""

import os

import wx
import gui
import addonHandler
from gui import guiHelper
import ui as nvdaUi

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import errors


def report(message):
	"""Speak a short status message via NVDA and braille."""
	try:
		nvdaUi.message(message)
	except Exception:
		pass


def error_dialog(parent, exc):
	"""Show an error to the user, tailored to the exception type."""
	if isinstance(exc, errors.SarvamError):
		msg = exc.message
		if exc.request_id:
			# Translators: appended to error dialogs; a support reference id.
			msg += "\n\n" + _("Reference: {rid}").format(rid=exc.request_id)
	else:
		msg = str(exc)
	gui.messageBox(msg, _("Sarvam AI - Error"), wx.OK | wx.ICON_ERROR, parent)


def language_choices(include_auto=False, include_unknown=False):
	"""Return parallel lists ``(labels, codes)`` for a language combo box."""
	labels = []
	codes = []
	if include_auto:
		labels.append(_("Auto detect"))
		codes.append(constants.AUTO_DETECT)
	if include_unknown:
		labels.append(_("Unknown (auto)"))
		codes.append("unknown")
	for code, name in constants.LANGUAGES.items():
		labels.append("%s (%s)" % (name, code))
		codes.append(code)
	return labels, codes


def select_in_combo(combo, codes, wanted):
	"""Select the entry in ``combo`` whose code equals ``wanted``."""
	if wanted in codes:
		combo.SetSelection(codes.index(wanted))
	elif codes:
		combo.SetSelection(0)


def default_output_folder():
	folder = (config.conf().get("outputFolder") or "").strip()
	if folder and os.path.isdir(folder):
		return folder
	return _downloads()


def default_download_folder():
	folder = (config.conf().get("downloadFolder") or "").strip()
	if folder and os.path.isdir(folder):
		return folder
	return _downloads()


def _downloads():
	path = os.path.join(os.path.expanduser("~"), "Downloads")
	return path if os.path.isdir(path) else os.path.expanduser("~")


class ResultDialog(wx.Dialog):
	"""A generic, accessible dialog to present a block of text with actions.

	Actions offered: Copy to clipboard, Save to file, and optional
	Translate / Summarise with Sarvam (wired by the caller through callbacks).
	"""

	def __init__(self, parent, title, text, on_translate=None, on_summarize=None,
			save_ext=".txt"):
		super().__init__(parent, title=title,
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._save_ext = save_ext
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# Translators: label of the multiline results text box.
		self.textCtrl = helper.addLabeledControl(
			_("&Result:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
			size=(600, 320))
		self.textCtrl.SetValue(text or "")

		btns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		copyBtn = btns.addButton(self, label=_("&Copy"))
		copyBtn.Bind(wx.EVT_BUTTON, self._onCopy)
		saveBtn = btns.addButton(self, label=_("&Save..."))
		saveBtn.Bind(wx.EVT_BUTTON, self._onSave)
		if on_translate:
			trBtn = btns.addButton(self, label=_("&Translate with Sarvam"))
			trBtn.Bind(wx.EVT_BUTTON, lambda e: on_translate(self.textCtrl.GetValue()))
		if on_summarize:
			sumBtn = btns.addButton(self, label=_("Su&mmarise with Sarvam"))
			sumBtn.Bind(wx.EVT_BUTTON, lambda e: on_summarize(self.textCtrl.GetValue()))
		closeBtn = btns.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(btns)

		self.SetEscapeId(wx.ID_CLOSE)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.textCtrl.SetFocus()

	def _onCopy(self, evt):
		if wx.TheClipboard.Open():
			try:
				wx.TheClipboard.SetData(wx.TextDataObject(self.textCtrl.GetValue()))
				wx.TheClipboard.Flush()
			finally:
				wx.TheClipboard.Close()
			report(_("Copied to clipboard"))

	def _onSave(self, evt):
		with wx.FileDialog(
				self, _("Save result"),
				defaultDir=default_output_folder(),
				wildcard=_("Text files (*.txt)|*.txt|All files (*.*)|*.*"),
				style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		try:
			with open(path, "w", encoding="utf-8") as f:
				f.write(self.textCtrl.GetValue())
			report(_("Saved"))
		except Exception as e:
			error_dialog(self, e)

	def setText(self, text):
		self.textCtrl.SetValue(text or "")
