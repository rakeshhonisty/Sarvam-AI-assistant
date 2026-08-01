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


def make_closeable(dialog, cleanup=None):
	"""Guarantee a dialog can always be exited.

	- Pressing Escape anywhere in the dialog (including inside text boxes)
	  closes it.
	- Closing the dialog runs an optional ``cleanup`` callback and then
	  destroys the window, so focus returns to NVDA and the dialog does not
	  linger (which is what made earlier dialogs feel "stuck").
	"""
	def onCharHook(evt):
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			dialog.Close()
		else:
			evt.Skip()

	def onClose(evt):
		if cleanup:
			try:
				cleanup()
			except Exception:
				pass
		dialog.Destroy()

	dialog.Bind(wx.EVT_CHAR_HOOK, onCharHook)
	dialog.Bind(wx.EVT_CLOSE, onClose)


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


def batch_concurrency():
	"""How many work items to process at once, from Advanced settings (1x-10x)."""
	from .. import constants
	return constants.batch_multiplier_value(config.conf().get("batchConcurrency"))


def save_result(parent, text, default_name, as_docx=False, markdown=False):
	"""Show the standard Windows Save As dialog and write ``text``.

	``as_docx`` writes a Word document; when ``markdown`` is also true the text
	is treated as Markdown so headings, lists and tables become real Word
	structure (used for OCR / AI output). Unicode is always preserved and the
	dialog prompts before overwriting.
	"""
	from .. import docwriter
	if not (text or "").strip():
		report(_("Nothing to save"))
		return None
	if as_docx:
		wildcard = _("Word documents (*.docx)|*.docx")
	elif default_name.lower().endswith(".md"):
		wildcard = _("Markdown files (*.md)|*.md")
	else:
		wildcard = _("Text files (*.txt)|*.txt")
	with wx.FileDialog(
			parent, _("Save as"), defaultDir=default_output_folder(),
			defaultFile=default_name, wildcard=wildcard,
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
		if fd.ShowModal() != wx.ID_OK:
			return None
		path = fd.GetPath()
	try:
		if as_docx:
			if markdown:
				docwriter.write_docx_from_markdown(text, path)
			else:
				docwriter.write_docx(text, path)
		else:
			docwriter.write_txt(text, path)
		report(_("Saved"))
		return path
	except Exception as e:  # noqa: BLE001
		error_dialog(parent, e)
		return None


class SaveBar:
	"""A row of Save buttons that stays hidden until a task succeeds.

	Every Sarvam feature follows the same rule: perform task -> show result ->
	only then reveal Save as TXT / Save as DOCX. This small helper keeps that
	behaviour identical everywhere.
	"""

	def __init__(self, dialog, helper, get_text, base_name, markdown=False,
			include_md=False):
		self._dialog = dialog
		self._get_text = get_text
		self._base = base_name
		self._markdown = markdown
		bar = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self._buttons = []
		self.txtBtn = bar.addButton(dialog, label=_("Save as &text (.txt)"))
		self.txtBtn.Bind(wx.EVT_BUTTON, self._onTxt)
		self._buttons.append(self.txtBtn)
		self.docBtn = bar.addButton(dialog, label=_("Save as &Word (.docx)"))
		self.docBtn.Bind(wx.EVT_BUTTON, self._onDocx)
		self._buttons.append(self.docBtn)
		self.mdBtn = None
		if include_md:
			# Markdown keeps Sarvam's original converted structure (headings,
			# tables, lists) so the user can convert it to any format later.
			self.mdBtn = bar.addButton(dialog, label=_("Save as &Markdown (.md)"))
			self.mdBtn.Bind(wx.EVT_BUTTON, self._onMd)
			self._buttons.append(self.mdBtn)
		self.copyBtn = bar.addButton(dialog, label=_("&Copy"))
		self.copyBtn.Bind(wx.EVT_BUTTON, self._onCopy)
		self._buttons.append(self.copyBtn)
		helper.addItem(bar)
		self.show(False)

	def show(self, visible):
		for b in self._buttons:
			b.Show(visible)
		self._dialog.Layout()
		try:
			self._dialog.Fit()
		except Exception:
			pass

	def focus(self):
		try:
			self.txtBtn.SetFocus()
		except Exception:
			pass

	def _onTxt(self, evt):
		save_result(self._dialog, self._get_text(), self._base + ".txt", as_docx=False)

	def _onDocx(self, evt):
		save_result(self._dialog, self._get_text(), self._base + ".docx",
			as_docx=True, markdown=self._markdown)

	def _onMd(self, evt):
		save_result(self._dialog, self._get_text(), self._base + ".md", as_docx=False)

	def _onCopy(self, evt):
		text = self._get_text()
		if text and wx.TheClipboard.Open():
			try:
				wx.TheClipboard.SetData(wx.TextDataObject(text))
				wx.TheClipboard.Flush()
			finally:
				wx.TheClipboard.Close()
			report(_("Copied"))
		else:
			report(_("Nothing to copy"))


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
		make_closeable(self)
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
