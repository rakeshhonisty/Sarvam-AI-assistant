# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Dubbing dialog (Sarvam Dubbing API).

Dub a video (MP4, MOV, MKV, WebM, AVI, FLV, WMV) or an audio file (WAV, MP3,
M4A) into one or more of 12 Indian languages. By default the original
speakers' voices are cloned, so the dub sounds like them; alternatively a
preset Sarvam voice can be used. Choose what to get back - the dubbed video,
the dubbed audio and/or subtitles - and the files are saved into a folder you
choose, one per language.

Dubbing is billed per minute of source media per target language, so the
dialog shows the published price and asks before starting.
"""

import os

import wx
import gui
import addonHandler
from gui import guiHelper

addonHandler.initTranslation()

from .. import constants
from .. import config
from .. import client
from .. import fileio
from .. import tasks
from . import common


class DubbingDialog(wx.Dialog):

	def __init__(self, parent):
		# Translators: title of the dubbing dialog.
		super().__init__(parent, title=_("Sarvam AI - Dubbing"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._cli = client.SarvamClient(config)
		self._path = None
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		up = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.fileBtn = up.addButton(self, label=_("&Choose video or audio file..."))
		self.fileBtn.Bind(wx.EVT_BUTTON, self.onChooseFile)
		helper.addItem(up)
		self.sourceLabel = helper.addItem(wx.StaticText(self, label=_("Media: none selected")))

		self._srcCodes = ["auto"] + list(constants.DUB_TARGET_LANGUAGES) + list(constants.DUB_EXTRA_SOURCE_LANGUAGES)
		srcNames = dict(constants.DUB_TARGET_LANGUAGES, **constants.DUB_EXTRA_SOURCE_LANGUAGES)
		self.srcCtrl = helper.addLabeledControl(
			_("&Spoken language in the file:"), wx.Choice,
			choices=[_("Auto detect")] + ["%s (%s)" % (srcNames[c], c) for c in self._srcCodes[1:]])
		self.srcCtrl.SetSelection(0)

		self._tgtCodes = list(constants.DUB_TARGET_LANGUAGES)
		# Translators: list of languages to dub into; Space checks an item.
		self.tgtCtrl = helper.addLabeledControl(
			_("Dub &into (press Space to check one or more languages):"), wx.CheckListBox,
			choices=["%s (%s)" % (n, c) for c, n in constants.DUB_TARGET_LANGUAGES.items()])
		last = (config.conf().get("translateTargetLang") or "hi-IN")
		last = constants.to_dub_language(last)
		if last in self._tgtCodes:
			self.tgtCtrl.Check(self._tgtCodes.index(last), True)

		self._exportKeys = [k for k, _l, _e in constants.DUB_EXPORTS]
		self.exportCtrl = helper.addLabeledControl(
			_("&Files to get back for each language:"), wx.CheckListBox,
			choices=[_(lab) for _k, lab, _e in constants.DUB_EXPORTS])
		self.exportCtrl.Check(0, True)

		row = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		# Translators: keep the original speakers' voices in the dub.
		self.cloneCtrl = row.addItem(wx.CheckBox(self, label=_("C&lone the original speakers' voices")))
		self.cloneCtrl.SetValue(True)
		self.cloneCtrl.Bind(wx.EVT_CHECKBOX, self._onClone)
		self.speakersCtrl = row.addLabeledControl(
			_("Number of spea&kers (0 = detect automatically):"), wx.SpinCtrl, min=0, max=10)
		self.speakersCtrl.SetValue(1)
		helper.addItem(row.sizer)

		row2 = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		self.voiceCtrl = row2.addLabeledControl(
			_("Preset &voice name (when not cloning, for example ishita):"), wx.TextCtrl)
		self._paces = list(constants.DUB_PACE_PRESETS)
		self.paceCtrl = row2.addLabeledControl(
			_("&Pace:"), wx.Choice, choices=[_("Normal"), _("Slow"), _("Moderate"), _("Fast")])
		self.paceCtrl.SetSelection(0)
		helper.addItem(row2.sizer)

		self._registers = list(constants.DUB_REGISTERS)
		self.registerCtrl = helper.addLabeledControl(
			_("Language st&yle:"), wx.Choice,
			choices=[_("Automatic"), _("Formal"), _("Common Indic"), _("Modern colloquial"),
				_("Classic colloquial"), _("Academic")])
		self.registerCtrl.SetSelection(0)
		self.watermarkCtrl = helper.addItem(wx.CheckBox(self, label=_("Remove the &watermark from the video")))

		self.priceLabel = helper.addItem(wx.StaticText(self, label=_(
			"Cost: about {price} rupees of Sarvam credit per minute of media, for each "
			"language (Sarvam's published pay-as-you-go price).").format(
			price=constants.DUB_PRICE_PER_MINUTE)))

		go = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.dubBtn = go.addButton(self, label=_("&Dub..."))
		self.dubBtn.Bind(wx.EVT_BUTTON, self.onDub)
		closeBtn = go.addButton(self, id=wx.ID_CLOSE, label=_("Cl&ose"))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		helper.addItem(go)

		self._onClone(None)
		self.dubBtn.Enable(False)
		self.SetEscapeId(wx.ID_CLOSE)
		common.make_closeable(self)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizerAndFit(mainSizer)
		self.CentreOnScreen()
		self.fileBtn.SetFocus()

	def _onClone(self, evt):
		cloning = self.cloneCtrl.GetValue()
		self.voiceCtrl.Enable(not cloning)
		self.paceCtrl.Enable(not cloning)

	def onChooseFile(self, evt):
		exts = list(constants.DUB_EXTENSIONS)
		with wx.FileDialog(self, _("Choose a video or audio file to dub"),
				wildcard=fileio.wildcard(_("Video and audio"), exts),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			self._path = fd.GetPath()
		name = os.path.basename(self._path)
		try:
			mb = os.path.getsize(self._path) / (1024.0 * 1024.0)
			self.sourceLabel.SetLabel(_("Media: {name} ({size:.1f} MB)").format(name=name, size=mb))
		except OSError:
			self.sourceLabel.SetLabel(_("Media: {name}").format(name=name))
		is_audio = os.path.splitext(self._path)[1].lower() in constants.DUB_AUDIO_EXTENSIONS
		# For an audio file the dubbed audio is the natural result.
		self.exportCtrl.Check(0, not is_audio)
		self.exportCtrl.Check(1, is_audio or self.exportCtrl.IsChecked(1))
		self.dubBtn.Enable(True)
		common.report(_("File selected. Choose the languages, then press Dub."))
		self.srcCtrl.SetFocus()

	def onDub(self, evt):
		if not self._path:
			return
		targets = [self._tgtCodes[i] for i in range(len(self._tgtCodes)) if self.tgtCtrl.IsChecked(i)]
		exports = [self._exportKeys[i] for i in range(len(self._exportKeys)) if self.exportCtrl.IsChecked(i)]
		src = self._srcCodes[max(0, self.srcCtrl.GetSelection())]
		if not targets:
			common.report(_("Check at least one language to dub into"))
			self.tgtCtrl.SetFocus()
			return
		if not exports:
			common.report(_("Check at least one kind of file to get back"))
			self.exportCtrl.SetFocus()
			return
		cloning = self.cloneCtrl.GetValue()
		if not cloning and not self.voiceCtrl.GetValue().strip():
			common.report(_("Enter a preset voice name, or turn voice cloning back on"))
			self.voiceCtrl.SetFocus()
			return
		names = ", ".join(constants.DUB_TARGET_LANGUAGES[t] for t in targets)
		if gui.messageBox(
				_("Dub {file} into {langs}?\n\nThis uses Sarvam credits: about {price} rupees per "
					"minute of media for each of the {n} languages.").format(
					file=os.path.basename(self._path), langs=names,
					price=constants.DUB_PRICE_PER_MINUTE, n=len(targets)),
				_("Sarvam AI - Dubbing"), wx.YES | wx.NO | wx.ICON_QUESTION, self) != wx.YES:
			return
		with wx.DirDialog(self, _("Choose where to save the dubbed files"),
				defaultPath=common.default_download_folder()) as dd:
			if dd.ShowModal() != wx.ID_OK:
				return
			out_dir = dd.GetPath()
		speakers = int(self.speakersCtrl.GetValue())
		kwargs = dict(
			export_options=exports, voice_cloning=cloning,
			num_speakers=speakers if speakers > 0 else -1,
			register=self._registers[max(0, self.registerCtrl.GetSelection())],
			voice_id=self.voiceCtrl.GetValue().strip() or None,
			pace_preset=self._paces[max(0, self.paceCtrl.GetSelection())],
			disable_watermark=self.watermarkCtrl.GetValue())
		path = self._path
		self.dubBtn.Enable(False)

		def ok(paths):
			self.dubBtn.Enable(True)
			files = "\n".join(os.path.basename(p) for p in paths)
			gui.messageBox(
				_("Dubbing finished. Saved {n} files:\n{files}\n\nFolder: {folder}").format(
					n=len(paths), files=files, folder=out_dir),
				_("Sarvam AI - Dubbing"), wx.OK | wx.ICON_INFORMATION, self)

		def bad(exc):
			self.dubBtn.Enable(True)
			common.error_dialog(self, exc)

		tasks.run_task(
			lambda cancel, progress: self._cli.dub(path, src, targets, out_dir,
				cancel=cancel, progress=progress, **kwargs),
			on_success=ok, on_error=bad, title=_("Sarvam AI - Dubbing"),
			message=_("Dubbing {name}. This can take several minutes; you can keep working.").format(
				name=os.path.basename(path)),
			parent=self)
