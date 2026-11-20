# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""AI Workforce - chat, agent and vision in one accessible window.

New in 2.0:

* **Model switch** right in the dialog: Sarvam 105B or any of Sarvam's open
  models (GLM 5.3 / Flash, Gemma 4, DeepSeek V4.1 Flash, ...). The reasoning
  effort list adapts to the chosen model.
* **Agent** task mode: the model calls tools to translate, transliterate,
  detect languages, read your attached files, make speech files with the right
  voice and save documents in any format - and tells you each step.
* **Describe images**: attach photos or screenshots; a vision model describes
  them. If the chosen model cannot see images the vision model from Model
  switching is used for that turn automatically.
* **Conversations**: follow-up questions keep the context; New conversation
  starts afresh.
* **Attach several files** of any type (documents, PDFs, scans, images,
  audio).

Tab order: Ask (focus starts here) -> Response -> Agent steps -> Task mode ->
Model -> Reasoning -> Run -> New conversation -> Download ... Shift+Tab from
Ask reaches the attachment buttons. Ctrl+Enter in Ask runs the task.
"""

import os

import wx
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import agent
from .. import constants
from .. import config
from .. import client
from .. import fileio
from .. import models
from .. import tasks
from . import common


class WorkforceDialog(wx.Dialog):

	def __init__(self, parent, initial_text="", initial_context="", mode=None,
			context_name=None, initial_image=None):
		# Translators: title of the unified AI Workforce dialog.
		super().__init__(parent, title=_("Sarvam AI - AI Workforce and Agent"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		self._attachments = []  # dicts: name, text, image (bytes), mime, sent
		self._messages = []
		if initial_context:
			self._attachments.append(dict(name=context_name or _("pasted text"),
				text=initial_context, image=None, mime=None, sent=False))
		if initial_image:
			data, mime, name = initial_image
			self._attachments.append(dict(name=name, text="", image=data, mime=mime, sent=False))
		conf = config.conf()
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# 1) Attachments (Shift+Tab from the question box reaches these).
		up = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.uploadBtn = up.addButton(self, label=_("&Attach files (documents, PDF, images, audio)..."))
		self.uploadBtn.Bind(wx.EVT_BUTTON, self.onUpload)
		self.clearBtn = up.addButton(self, label=_("Remove attac&hments"))
		self.clearBtn.Bind(wx.EVT_BUTTON, self.onClearAttachments)
		helper.addItem(up)
		self.fileLabel = helper.addItem(wx.StaticText(self, label=self._attachLabel()))

		# 2) Ask (initial focus).
		self.askCtrl = helper.addLabeledControl(
			_("Ask a &question or describe the task (Ctrl+Enter runs it):"), wx.TextCtrl,
			style=wx.TE_MULTILINE, size=(640, 110))
		self.askCtrl.SetValue(initial_text or "")
		self.askCtrl.Bind(wx.EVT_KEY_DOWN, self._onAskKey)

		# 3) Response.
		self.responseCtrl = helper.addLabeledControl(
			_("&Response:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(640, 220))

		# 4) Agent steps (what the agent did, step by step).
		self.stepsCtrl = helper.addLabeledControl(
			_("Agent ste&ps:"), wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_READONLY, size=(640, 90))

		# 5) Task mode, model and reasoning.
		row = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self._roleKeys = [r[0] for r in constants.WORKFORCE_ROLES]
		self.modeCtrl = row.addLabeledControl(
			_("&Task mode:"), wx.Choice,
			choices=[_(r[1]) for r in constants.WORKFORCE_ROLES])
		wanted = mode or (constants.VISION_ROLE if initial_image else None) or conf.get("workforceRole") \
			or constants.DEFAULT_WORKFORCE_ROLE
		common.select_in_combo(self.modeCtrl, self._roleKeys, wanted)
		self.modeCtrl.Bind(wx.EVT_CHOICE, self._onMode)
		self._modelIds = list(models.chat_ids())
		self.modelCtrl = row.addLabeledControl(
			_("&Model:"), wx.Choice, choices=[models.chat_label(m) for m in self._modelIds])
		startModel = conf.get("chatModel") or models.DEFAULT_CHAT_MODEL
		if initial_image and not models.supports_vision(startModel):
			startModel = conf.get("visionModel") or models.DEFAULT_VISION_MODEL
		common.select_in_combo(self.modelCtrl, self._modelIds, startModel)
		self.modelCtrl.Bind(wx.EVT_CHOICE, self._onModel)
		self.effortCtrl = row.addLabeledControl(_("Reasonin&g:"), wx.Choice, choices=[])
		self._effortKeys = []
		helper.addItem(row.sizer)
		self._fillEfforts(conf.get("reasoningEffort"))

		# 6) Run / new conversation.
		go = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.runBtn = go.addButton(self, label=_("&Run"))
		self.runBtn.Bind(wx.EVT_BUTTON, self.onRun)
		self.newBtn = go.addButton(self, label=_("&New conversation"))
		self.newBtn.Bind(wx.EVT_BUTTON, self.onNewConversation)
		helper.addItem(go)

		# 7) Download bar - hidden until a response is produced.
		self.saveBar = common.SaveBar(self, helper,
			lambda: self.responseCtrl.GetValue(), "sarvam-ai-result",
			markdown=True, include_md=True, title=_("Sarvam AI result"))

		closeRow = guiHelper.ButtonHelper(wx.HORIZONTAL)
		closeBtn = closeRow.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(closeRow)

		self.SetEscapeId(wx.ID_CLOSE)
		common.make_closeable(self, cleanup=self._remember)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self._onMode(None, speak=False)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.askCtrl.SetFocus()
		if initial_image and not initial_text:
			wx.CallAfter(self.onRun, None)

	# -- helpers ------------------------------------------------------------
	def _role(self):
		return self._roleKeys[max(0, self.modeCtrl.GetSelection())]

	def _model(self):
		return self._modelIds[max(0, self.modelCtrl.GetSelection())]

	def _effort(self):
		return self._effortKeys[max(0, self.effortCtrl.GetSelection())] if self._effortKeys else None

	def _fillEfforts(self, wanted=None):
		model = self._model()
		self._effortKeys = list(models.efforts_for(model))
		self.effortCtrl.Set([_(models.EFFORT_LABELS.get(e, e)) for e in self._effortKeys])
		common.select_in_combo(self.effortCtrl, self._effortKeys,
			models.normalise_effort(model, wanted))

	def _onModel(self, evt):
		self._fillEfforts(self._effort())
		common.report(models.describe_chat(self._model()))

	def _onMode(self, evt, speak=True):
		agentMode = self._role() == constants.AGENT_ROLE
		self.stepsCtrl.Show(agentMode)
		try:
			self.stepsCtrl.GetPrevSibling().Show(agentMode)
		except Exception:
			pass
		if self._role() == constants.VISION_ROLE and not models.supports_vision(self._model()):
			common.select_in_combo(self.modelCtrl, self._modelIds,
				config.conf().get("visionModel") or models.DEFAULT_VISION_MODEL)
			self._fillEfforts(self._effort())
			if speak:
				common.report(_("Switched to {model}, which can see images.").format(
					model=models.chat_label(self._model())))
		self.Layout()
		try:
			self.Fit()
		except Exception:
			pass

	def _attachLabel(self):
		if not self._attachments:
			return _("No files attached (optional)")
		names = ", ".join(a["name"] for a in self._attachments)
		return _("Attached: {names}").format(names=names)

	def _remember(self):
		conf = config.conf()
		try:
			conf["workforceRole"] = self._role()
			conf["chatModel"] = self._model()
			if self._effort():
				conf["reasoningEffort"] = self._effort()
		except Exception:
			pass

	def _onAskKey(self, evt):
		if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and evt.ControlDown():
			self.onRun(None)
		else:
			evt.Skip()

	# -- attachments ----------------------------------------------------------
	def onUpload(self, evt):
		exts = fileio.all_extensions()
		with wx.FileDialog(self, _("Attach files"),
				wildcard=fileio.wildcard(_("Supported files"), exts),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			paths = fd.GetPaths()
		conf = config.conf()

		def work(cancel, progress):
			out = []
			for i, path in enumerate(paths):
				if cancel:
					cancel.check()
				name = os.path.basename(path)
				if fileio.kind_of(path) == fileio.KIND_IMAGE:
					data, mime = fileio.read_image_bytes(path)
					out.append(dict(name=name, text="", image=data, mime=mime, sent=False))
				else:
					text = fileio.read_any(path, self._cli, conf, cancel, None)
					out.append(dict(name=name, text=text or "", image=None, mime=None, sent=False))
				progress(i + 1, len(paths))
			return out

		def ok(items):
			self._attachments.extend(items)
			self.fileLabel.SetLabel(self._attachLabel())
			images = sum(1 for a in items if a["image"])
			msg = _("{n} files attached.").format(n=len(items))
			if images and not models.supports_vision(self._model()):
				msg += " " + _("Images will be sent to the vision model {model}.").format(
					model=models.chat_label(config.conf().get("visionModel") or models.DEFAULT_VISION_MODEL))
			common.report(msg + " " + _("Now ask your question."))
			self.Layout()
			self.askCtrl.SetFocus()

		tasks.run_task(work, on_success=ok,
			on_error=lambda e: common.error_dialog(self, e),
			title=_("Sarvam AI"), message=_("Reading attached files..."), parent=self)

	def onClearAttachments(self, evt):
		self._attachments = []
		self.fileLabel.SetLabel(self._attachLabel())
		common.report(_("Attachments removed"))

	def onNewConversation(self, evt):
		self._messages = []
		for a in self._attachments:
			a["sent"] = False
		self.responseCtrl.ChangeValue("")
		self.stepsCtrl.ChangeValue("")
		self.saveBar.show(False)
		common.report(_("New conversation started"))
		self.askCtrl.SetFocus()

	# -- run ----------------------------------------------------------------
	def _build_user_message(self, question, agentMode, use_images):
		parts = []
		texts = [a for a in self._attachments if not a["sent"] and a["text"]]
		if texts:
			if agentMode:
				parts.append(_("Attached files (read them with the read_attached_file tool): {names}").format(
					names=", ".join("%d. %s" % (i, a["name"]) for i, a in enumerate(
						[x for x in self._attachments if x["text"]], 1))))
			else:
				for a in texts:
					parts.append(_("Document '{name}':").format(name=a["name"]) + "\n\n" + a["text"])
		parts.append(question or _("Perform the selected task on the material above."))
		text = "\n\n".join(parts)
		images = [a for a in self._attachments if not a["sent"] and a["image"]] if use_images else []
		if not images:
			return {"role": "user", "content": text}
		content = [{"type": "text", "text": text}]
		for a in images:
			content.append(client.image_part(a["image"], a["mime"] or "image/jpeg"))
		return {"role": "user", "content": content}

	def onRun(self, evt):
		question = self.askCtrl.GetValue().strip()
		if not question and not any(not a["sent"] for a in self._attachments):
			common.report(_("Ask a question or attach a file first"))
			return
		role = self._role()
		agentMode = role == constants.AGENT_ROLE
		model = self._model()
		effort = self._effort()
		has_images = any(a["image"] and not a["sent"] for a in self._attachments)
		note = None
		if has_images and not models.supports_vision(model):
			model = config.conf().get("visionModel") or models.DEFAULT_VISION_MODEL
			effort = models.default_effort(model)
			note = _("Using {model} for the images.").format(model=models.chat_label(model))
		system_prompt = next(r[2] for r in constants.WORKFORCE_ROLES if r[0] == role)
		if self._messages and self._messages[0].get("role") == "system":
			self._messages[0]["content"] = system_prompt
		else:
			self._messages.insert(0, {"role": "system", "content": system_prompt})
		self._messages.append(self._build_user_message(question, agentMode, use_images=True))
		sent = [a for a in self._attachments if not a["sent"]]
		conf = config.conf()
		max_tokens = conf.get("workforceMaxTokens")
		self.runBtn.Enable(False)
		self.saveBar.show(False)
		if agentMode:
			self.stepsCtrl.ChangeValue("")

		def on_step(text):
			def add():
				self.stepsCtrl.AppendText(text + "\n")
				common.report(text)
			wx.CallAfter(add)

		def work(cancel, progress):
			if agentMode:
				tools = agent.AgentTools(self._cli, conf,
					[(a["name"], a["text"]) for a in self._attachments if a["text"]],
					common.default_output_folder(), cancel=cancel)
				reply = agent.run_agent(self._cli, self._messages, model, tools,
					effort=effort, max_steps=conf.get("agentMaxSteps") or constants.AGENT_MAX_STEPS,
					max_tokens=max_tokens, on_step=on_step, cancel=cancel)
				return reply, tools.saved_files
			msg = self._cli.chat_message(self._messages, model=model,
				reasoning_effort=effort, max_tokens=max_tokens, cancel=cancel)
			content = msg.get("content") or ""
			if isinstance(content, list):
				content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
			if not content and msg.get("finish_reason") == "length":
				content = _("The model ran out of output space before answering. Lower the "
					"reasoning level or raise the maximum response length in Advanced settings.")
			self._messages.append({"role": "assistant", "content": content})
			return content, []

		def ok(result):
			reply, saved = result
			for a in sent:
				a["sent"] = True
			self.runBtn.Enable(True)
			self.responseCtrl.ChangeValue(reply or "")
			self.askCtrl.ChangeValue("")
			self.saveBar.show(True)
			msg = _("Response ready ({n} characters).").format(n=len(reply or ""))
			if saved:
				msg += " " + _("Saved {n} files in {folder}.").format(
					n=len(saved), folder=common.default_output_folder())
			if note:
				msg = note + " " + msg
			common.report(msg + " " + _("Ask a follow-up or download the answer."))
			self.responseCtrl.SetFocus()

		def bad(exc):
			# Drop the unanswered user turn so the conversation stays valid.
			if self._messages and self._messages[-1].get("role") == "user":
				self._messages.pop()
			self.runBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(work, on_success=ok, on_error=bad,
			title=_("Sarvam AI - AI Workforce"),
			message=(_("The agent is working through your task...") if agentMode
				else _("{model} is thinking...").format(model=models.chat_label(model))),
			parent=self)
