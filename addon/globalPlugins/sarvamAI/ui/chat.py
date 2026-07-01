# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""AI chat, summarisation and document-understanding dialog built on the
Sarvam chat completions endpoint (models sarvam-105b / sarvam-30b)."""

import os

import wx
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import client
from .. import tasks
from . import common
from .tts import _get_selection, _get_clipboard_text


class ChatDialog(wx.Dialog):

	def __init__(self, parent, initial_text="", mode="chat"):
		# Translators: title of the AI assistant dialog.
		super().__init__(parent, title=_("Sarvam AI - Assistant"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		self._history = []

		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# Translators: choose the assistant task.
		self.taskCtrl = helper.addLabeledControl(
			_("&Task:"), wx.Choice,
			choices=[_("Chat / ask a question"), _("Summarise text"),
				_("Explain / understand a document")])
		self.taskCtrl.SetSelection({"chat": 0, "summarize": 1, "document": 2}.get(mode, 0))

		# Translators: the conversation / output transcript.
		self.outputCtrl = helper.addLabeledControl(
			_("&Conversation:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_READONLY, size=(600, 260))

		self.inputCtrl = helper.addLabeledControl(
			_("&Your message or text:"), wx.TextCtrl,
			style=wx.TE_MULTILINE, size=(600, 120))
		self.inputCtrl.SetValue(initial_text or "")

		srcBtns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		b1 = srcBtns.addButton(self, label=_("From se&lection"))
		b1.Bind(wx.EVT_BUTTON, lambda e: self._load(_get_selection()))
		b2 = srcBtns.addButton(self, label=_("From cli&pboard"))
		b2.Bind(wx.EVT_BUTTON, lambda e: self._load(_get_clipboard_text()))
		b3 = srcBtns.addButton(self, label=_("Open te&xt file..."))
		b3.Bind(wx.EVT_BUTTON, self._fromFile)
		helper.addItem(srcBtns)

		btns = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.sendBtn = btns.addButton(self, label=_("&Send"))
		self.sendBtn.Bind(wx.EVT_BUTTON, self.onSend)
		self.copyBtn = btns.addButton(self, label=_("&Copy conversation"))
		self.copyBtn.Bind(wx.EVT_BUTTON, self.onCopy)
		self.clearBtn = btns.addButton(self, label=_("C&lear"))
		self.clearBtn.Bind(wx.EVT_BUTTON, self.onClear)
		closeBtn = btns.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(btns)

		self.SetEscapeId(wx.ID_CLOSE)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.inputCtrl.SetFocus()

	def _load(self, text):
		if text:
			self.inputCtrl.SetValue(text)
			common.report(_("Loaded"))
		else:
			common.report(_("Nothing to load"))

	def _fromFile(self, evt):
		with wx.FileDialog(
				self, _("Open text file"),
				wildcard=_("Text files (*.txt)|*.txt|All files (*.*)|*.*"),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		try:
			with open(path, "r", encoding="utf-8", errors="replace") as f:
				self.inputCtrl.SetValue(f.read())
		except Exception as e:
			common.error_dialog(self, e)

	def onSend(self, evt):
		text = self.inputCtrl.GetValue().strip()
		if not text:
			common.report(_("Type a message first"))
			return
		task = self.taskCtrl.GetSelection()
		conf = config.conf()
		if task == 1:
			messages = [
				{"role": "system", "content": _("Summarise the following text clearly and concisely, preserving key facts.")},
				{"role": "user", "content": text}]
			self._append(_("You (summarise): ") + _shorten(text))
		elif task == 2:
			messages = [
				{"role": "system", "content": _("You are a helpful assistant. Read the document the user provides and answer questions or explain it clearly.")},
				{"role": "user", "content": text}]
			self._append(_("You (document): ") + _shorten(text))
		else:
			self._history.append({"role": "user", "content": text})
			messages = list(self._history)
			self._append(_("You: ") + text)

		self.inputCtrl.SetValue("")
		self.sendBtn.Enable(False)

		def work(cancel, progress):
			return self._cli.chat(
				messages, model=conf.get("chatModel"),
				temperature=conf.get("chatTemperature"),
				max_tokens=conf.get("chatMaxTokens"), cancel=cancel)

		def ok(reply):
			self.sendBtn.Enable(True)
			if task == 0:
				self._history.append({"role": "assistant", "content": reply})
			self._append(_("Sarvam: ") + reply)
			common.report(_("Reply received"))

		def bad(exc):
			self.sendBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - Assistant"),
			message=_("Thinking..."), parent=self)

	def _append(self, line):
		cur = self.outputCtrl.GetValue()
		self.outputCtrl.SetValue((cur + "\n\n" + line).strip() if cur else line)
		self.outputCtrl.SetInsertionPointEnd()

	def onCopy(self, evt):
		text = self.outputCtrl.GetValue()
		if text and wx.TheClipboard.Open():
			try:
				wx.TheClipboard.SetData(wx.TextDataObject(text))
				wx.TheClipboard.Flush()
			finally:
				wx.TheClipboard.Close()
			common.report(_("Copied"))

	def onClear(self, evt):
		self._history = []
		self.outputCtrl.SetValue("")
		common.report(_("Cleared"))


def _shorten(text, limit=80):
	text = text.replace("\n", " ")
	return text if len(text) <= limit else text[:limit] + "..."
