# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Audio playback and WAV file helpers.

Playback uses NVDA's :mod:`nvwave` when available so it honours the user's audio
output device and ducking settings. A background player thread lets us offer
stop/pause/resume without freezing the UI.
"""

import os
import io
import time
import tempfile
import threading

from . import logger

try:
	import wave
except Exception:
	wave = None

try:
	import nvwave
except Exception:
	nvwave = None


class Player:
	"""Plays a WAV byte buffer with stop and pause/resume support.

	NVDA's :class:`nvwave.WavePlayer` streams raw frames, which gives us fine
	grained control: we feed frames chunk by chunk and can pause between
	chunks. If ``nvwave`` is unavailable (non-NVDA context) playback is a no-op.
	"""

	def __init__(self):
		self._thread = None
		self._stop = threading.Event()
		self._pause = threading.Event()
		self._lock = threading.Lock()
		self._player = None

	def play(self, wav_bytes):
		self.stop()
		self._stop.clear()
		self._pause.clear()
		self._thread = threading.Thread(
			target=self._run, args=(wav_bytes,), name="SarvamAIPlayer", daemon=True)
		self._thread.start()

	def _run(self, wav_bytes):
		if nvwave is None or wave is None:
			logger.warning("nvwave/wave unavailable; cannot play audio.")
			return
		try:
			with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
				channels = wf.getnchannels()
				width = wf.getsampwidth()
				rate = wf.getframerate()
				frames = wf.readframes(wf.getnframes())
		except Exception:
			logger.exception("Could not parse WAV for playback")
			return
		player = _make_player(channels, rate, width * 8)
		if player is None:
			logger.exception("Could not create WavePlayer")
			return
		with self._lock:
			self._player = player
		# Feed the audio in ~100 ms chunks so stop/pause are responsive.
		bytes_per_sec = rate * channels * width
		chunk = max(bytes_per_sec // 10, 1024)
		try:
			pos = 0
			while pos < len(frames):
				if self._stop.is_set():
					break
				while self._pause.is_set() and not self._stop.is_set():
					time.sleep(0.05)
				block = frames[pos:pos + chunk]
				player.feed(block)
				pos += chunk
			if not self._stop.is_set():
				player.idle()
		except Exception:
			logger.exception("Playback error")
		finally:
			try:
				player.stop()
			except Exception:
				pass
			with self._lock:
				self._player = None

	def pause(self):
		self._pause.set()

	def resume(self):
		self._pause.clear()

	@property
	def paused(self):
		return self._pause.is_set()

	def is_playing(self):
		return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

	def stop(self):
		self._stop.set()
		self._pause.clear()
		with self._lock:
			player = self._player
		if player is not None:
			try:
				player.stop()
			except Exception:
				pass
		t = self._thread
		if t and t.is_alive() and t is not threading.current_thread():
			t.join(timeout=1.0)


def save_wav(wav_bytes, path):
	"""Write WAV bytes to ``path``, creating parent directories."""
	folder = os.path.dirname(path)
	if folder and not os.path.isdir(folder):
		os.makedirs(folder, exist_ok=True)
	with open(path, "wb") as f:
		f.write(wav_bytes)
	return path


def temp_wav(wav_bytes):
	"""Write WAV bytes to a temporary file and return the path."""
	fd, path = tempfile.mkstemp(suffix=".wav", prefix="sarvamAI_")
	os.close(fd)
	with open(path, "wb") as f:
		f.write(wav_bytes)
	return path


def _make_player(channels, rate, bits):
	"""Create a WavePlayer, tolerating outputDevice API differences across NVDA
	releases (integer index vs endpoint-id string vs WASAPI)."""
	kwargs = dict(channels=channels, samplesPerSec=rate, bitsPerSample=bits)
	device = _outputDevice()
	# Try with the configured device first, then fall back to the default
	# device (no outputDevice kwarg) if that signature/value is rejected.
	attempts = []
	if device is not None:
		attempts.append(dict(kwargs, outputDevice=device))
	attempts.append(kwargs)
	for kw in attempts:
		try:
			return nvwave.WavePlayer(**kw)
		except Exception:
			continue
	return None


def _outputDevice():
	try:
		import config
		return config.conf["speech"]["outputDevice"]
	except Exception:
		return None
