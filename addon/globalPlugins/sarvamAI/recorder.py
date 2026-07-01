# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Microphone recording using the Windows Multimedia (MCI) API via ctypes.

This avoids any third-party dependency (no PyAudio) and records a mono 16 kHz
16-bit PCM WAV, which is exactly what the Sarvam speech-to-text endpoint
prefers. Recording runs entirely through ``winmm.mciSendStringW`` so it works
inside NVDA's bundled Python without extra binaries.
"""

import os
import ctypes
import tempfile

from . import logger

_winmm = None


def _mci():
	global _winmm
	if _winmm is None:
		_winmm = ctypes.WinDLL("winmm")
	return _winmm


def _send(command):
	buf = ctypes.create_unicode_buffer(256)
	res = _mci().mciSendStringW(command, buf, 256, None)
	if res != 0:
		err = ctypes.create_unicode_buffer(256)
		_mci().mciGetErrorStringW(res, err, 256)
		raise RecorderError(err.value or ("MCI error %d" % res))
	return buf.value


class RecorderError(Exception):
	pass


class MicRecorder:
	"""Start/stop microphone recording to a WAV file.

	Usage::

	    rec = MicRecorder()
	    rec.start()
	    ... user speaks ...
	    path = rec.stop()  # returns the WAV path
	"""

	_ALIAS = "sarvamAIcapture"

	def __init__(self):
		self._recording = False
		self._path = None

	@property
	def recording(self):
		return self._recording

	def start(self):
		if self._recording:
			return
		fd, self._path = tempfile.mkstemp(suffix=".wav", prefix="sarvamAI_rec_")
		os.close(fd)
		try:
			_send("close %s" % self._ALIAS)
		except RecorderError:
			pass
		# Open a new waveaudio buffer, configure 16 kHz mono 16-bit PCM.
		_send('open new type waveaudio alias %s' % self._ALIAS)
		try:
			_send('set %s time format ms bitspersample 16 channels 1 samplespersec 16000 bytespersec 32000 alignment 2' % self._ALIAS)
		except RecorderError as e:
			logger.warning("Could not set recording format, using defaults: %s" % e)
		_send('record %s' % self._ALIAS)
		self._recording = True
		logger.debug("Microphone recording started -> %s" % self._path)

	def stop(self):
		if not self._recording:
			return None
		try:
			_send('stop %s' % self._ALIAS)
			_send('save %s "%s"' % (self._ALIAS, self._path))
		finally:
			try:
				_send('close %s' % self._ALIAS)
			except RecorderError:
				pass
			self._recording = False
		logger.debug("Microphone recording saved.")
		return self._path

	def cancel(self):
		if not self._recording:
			return
		try:
			_send('stop %s' % self._ALIAS)
			_send('close %s' % self._ALIAS)
		except RecorderError:
			pass
		self._recording = False
		if self._path and os.path.isfile(self._path):
			try:
				os.remove(self._path)
			except OSError:
				pass
		self._path = None
