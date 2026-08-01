# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""AI Workforce - the unified AI module.

This single dialog replaces the previous separate "AI Assistant" and
"AI Summarise" dialogs; those capabilities are now Task modes here rather than
duplicated windows. It is powered by Sarvam's 105B reasoning model.

Focus and tab order are deliberate:

    Ask a question   <- focus starts here
    Shift+Tab        -> Upload file
    Tab              -> Response
    Tab              -> Task mode, reasoning effort, Run, save options

Uploaded files of any supported kind are read automatically: text, Word and
EPUB are extracted directly, PDFs and images are read with Sarvam OCR, and
audio files are transcribed - then used as context for the task.
"""

import os

import wx
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import client
from .. import tasks
from .. import textextract
from .. import imaging
from . import common


class WorkforceDialog(wx.Dialog):

	def __init__(self, parent, initial_text="", initial_context="", mode=None):
		# Translators: title of the unified AI Workforce dialog.
		super().__init__(parent, title=_("Sarvam AI - AI Workforce"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		self._context = initial_context or ""
		self._contextName = _("pasted text") if initial_context else None
		conf = config.conf()
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# 1) Upload file (Shift+Tab from the question box reaches this).
		up = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.uploadBtn = up.addButton(self, label=_("&Upload file for analysis..."))
		self.uploadBtn.Bind(wx.EVT_BUTTON, self.onUpload)
		helper.addItem(up)
		# Translators: shows which file is loaded as context for the AI.
		self.fileLabel = helper.addItem(wx.StaticText(self, label=self._contextLabel()))

		# 2) Ask a question (initial focus).
		self.askCtrl = helper.addLabeledControl(
			_("&Ask a question or describe the task:"), wx.TextCtrl,
			style=wx.TE_MULTILINE, size=(620, 130))
		self.askCtrl.SetValue(initial_text or "")
		self.askCtrl.Bind(wx.EVT_KEY_DOWN, self._onAskKey)

		# 3) Response.
		self.responseCtrl = helper.addLabeledControl(
			_("&Response:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(620, 240))

		# 4) Task mode and reasoning.
		row = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self._roleKeys = [r[0] for r in constants.WORKFORCE_ROLES]
		self.modeCtrl = row.addLabeledControl(
			_("&Task mode:"), wx.Choice,
			choices=[_(r[1]) for r in constants.WORKFORCE_ROLES])
		common.select_in_combo(self.modeCtrl, self._roleKeys,
			mode or conf.get("workforceRole") or constants.DEFAULT_WORKFORCE_ROLE)
		self._effortKeys = list(constants.REASONING_EFFORTS)
		self.effortCtrl = row.addLabeledControl(
			_("&Reasoning effort:"), wx.Choice, choices=self._effortKeys)
		common.select_in_combo(self.effortCtrl, self._effortKeys, conf.get("reasoningEffort"))
		# Translators: checkbox to ground answers in reference data.
		self.wikiCtrl = row.addItem(wx.CheckBox(self, label=_("Wiki &grounding")))
		self.wikiCtrl.SetValue(bool(conf.get("wikiGrounding")))
		helper.addItem(row.sizer)

		# 5) Run.
		go = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.runBtn = go.addButton(self, label=_("&Run"))
		self.runBtn.Bind(wx.EVT_BUTTON, self.onRun)
		helper.addItem(go)

		# 6) Save bar - hidden until a response is produced. Markdown is offered
		# because generated reports and summaries are often structured.
		self.saveBar = common.SaveBar(self, helper,
			lambda: self.responseCtrl.GetValue(), "sarvam-ai-result",
			markdown=True, include_md=True)

		closeRow = guiHelper.ButtonHelper(wx.HORIZONTAL)
		closeBtn = closeRow.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(closeRow)

		self.SetEscapeId(wx.ID_CLOSE)
		common.make_closeable(self)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.askCtrl.SetFocus()

	# -- helpers ------------------------------------------------------------
	def _contextLabel(self):
		if self._contextName:
			return _("Loaded context: {name} ({n} characters)").format(
				name=self._contextName, n=len(self._context))
		return _("No file loaded (optional)")

	def _onAskKey(self, evt):
		# Ctrl+Enter runs the task; plain Enter still inserts a new line.
		if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and evt.ControlDown():
			self.onRun(None)
		else:
			evt.Skip()

	# -- upload -------------------------------------------------------------
	def onUpload(self, evt):
		doc = list(textextract.SUPPORTED_EXTENSIONS)
		ocr = list(constants.OCR_INPUT_EXTENSIONS)
		audio = list(constants.AUDIO_EXTENSIONS)
		allexts = ";".join("*" + e for e in (doc + ocr + audio))
		with wx.FileDialog(self, _("Upload a file for analysis"),
				wildcard=_("Supported files (%s)|%s|All files (*.*)|*.*") % (allexts, allexts),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		ext = os.path.splitext(path)[1].lower()
		conf = config.conf()

		def work(cancel, progress):
			if ext in constants.AUDIO_EXTENSIONS:
				res = self._cli.transcribe(
					path, model=conf.get("sttModel"), cancel=cancel, progress=progress)
				return res.get("transcript", "")
			if ext in constants.OCR_INPUT_EXTENSIONS:
				pdf_path, is_temp = imaging.ensure_pdf(path)
				try:
					res = self._cli.document_ocr(
						pdf_path, language=conf.get("ocrLanguage"),
						output_format=conf.get("ocrOutputFormat"),
						cancel=cancel, progress=progress)
					return res.get("text", "")
				finally:
					if is_temp:
						try:
							os.remove(pdf_path)
						except OSError:
							pass
			return textextract.extract_text(path)

		def ok(text):
			self._context = text or ""
			self._contextName = os.path.basename(path)
			self.fileLabel.SetLabel(self._contextLabel())
			common.report(_("File loaded: {n} characters. Now ask your question.").format(n=len(self._context)))
			self.askCtrl.SetFocus()

		tasks.run_task(work, on_success=ok,
			on_error=lambda e: common.error_dialog(self, e),
			title=_("Sarvam AI - AI Workforce"),
			message=_("Reading file..."), parent=self)

	# -- run ----------------------------------------------------------------
	def onRun(self, evt):
		question = self.askCtrl.GetValue().strip()
		if not question and not self._context:
			common.report(_("Ask a question or upload a file first"))
			return
		role_key = self._roleKeys[self.modeCtrl.GetSelection()]
		system_prompt = next(
			(r[2] for r in constants.WORKFORCE_ROLES if r[0] == role_key),
			constants.WORKFORCE_ROLES[0][2])
		effort = self._effortKeys[self.effortCtrl.GetSelection()]
		wiki = self.wikiCtrl.GetValue()
		max_tokens = config.conf().get("workforceMaxTokens")

		user_parts = []
		if self._context:
			user_parts.append(_("Here is the document to work with:") + "\n\n" + self._context)
		if question:
			user_parts.append(question)
		else:
			user_parts.append(_("Perform the selected task on the document above."))
		messages = [
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": "\n\n".join(user_parts)},
		]
		self.runBtn.Enable(False)
		self.saveBar.show(False)

		def work(cancel, progress):
			return self._cli.chat(
				messages, model=constants.WORKFORCE_MODEL,
				reasoning_effort=effort, wiki_grounding=wiki,
				max_tokens=max_tokens, cancel=cancel)

		def ok(reply):
			self.runBtn.Enable(True)
			self.responseCtrl.ChangeValue(reply)
			self.saveBar.show(True)
			common.report(_("Response ready ({n} characters). Save options are now available.").format(n=len(reply)))
			self.responseCtrl.SetFocus()

		def bad(exc):
			self.runBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - AI Workforce"),
			message=_("The 105B model is reasoning through your task..."), parent=self)
