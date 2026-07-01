# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Optical Character Recognition.

Sarvam AI does not expose an OCR / document-parsing REST endpoint (verified: all
``/parse/*``, ``/ocr`` and ``/image-to-text`` paths return HTTP 404). Rather than
fake a Sarvam call, this module uses the Windows OCR engine that NVDA already
bundles (``contentRecog.uwpOcr``) and then lets the rest of the add-on feed the
recognised text into Sarvam for translation or summarisation.

Images are loaded with GDI+ through :mod:`ctypes`, so no third-party imaging
library is required.
"""

import os
import ctypes
from ctypes import wintypes

import addonHandler

from . import errors
from . import logger

addonHandler.initTranslation()

try:
	from contentRecog import uwpOcr, RecogImageInfo
except Exception:
	uwpOcr = None
	RecogImageInfo = None


class _RGBQUAD(ctypes.Structure):
	_fields_ = [
		("rgbBlue", ctypes.c_ubyte),
		("rgbGreen", ctypes.c_ubyte),
		("rgbRed", ctypes.c_ubyte),
		("rgbReserved", ctypes.c_ubyte),
	]


def is_available():
	"""True when the Windows OCR engine is usable."""
	if uwpOcr is None:
		return False
	try:
		return bool(uwpOcr.getRecognizableLanguages())
	except Exception:
		# Older engines may lack the helper; assume available.
		return True


def available_languages():
	if uwpOcr is None:
		return []
	try:
		return list(uwpOcr.getRecognizableLanguages())
	except Exception:
		return []


# --- GDI+ image loading -----------------------------------------------------
class _GdiplusStartupInput(ctypes.Structure):
	_fields_ = [
		("GdiplusVersion", ctypes.c_uint32),
		("DebugEventCallback", ctypes.c_void_p),
		("SuppressBackgroundThread", wintypes.BOOL),
		("SuppressExternalCodecs", wintypes.BOOL),
	]


class _BitmapData(ctypes.Structure):
	_fields_ = [
		("Width", ctypes.c_uint),
		("Height", ctypes.c_uint),
		("Stride", ctypes.c_int),
		("PixelFormat", ctypes.c_int),
		("Scan0", ctypes.c_void_p),
		("Reserved", ctypes.POINTER(ctypes.c_uint)),
	]


class _Rect(ctypes.Structure):
	_fields_ = [
		("X", ctypes.c_int), ("Y", ctypes.c_int),
		("Width", ctypes.c_int), ("Height", ctypes.c_int),
	]


_PIXELFORMAT_32BPP_ARGB = 0x0026200A  # PixelFormat32bppARGB
_IMAGE_LOCKMODE_READ = 0x0001


def _load_image_pixels(path):
	"""Load an image file into a ``(pixels, width, height)`` tuple where
	``pixels`` is a ctypes array of :class:`_RGBQUAD` (BGRA)."""
	if not os.path.isfile(path):
		raise errors.InvalidRequestError(_("Image file not found: {path}").format(path=path))
	gdiplus = ctypes.WinDLL("gdiplus")
	token = ctypes.c_void_p()
	startup = _GdiplusStartupInput(1, None, False, False)
	status = gdiplus.GdiplusStartup(ctypes.byref(token), ctypes.byref(startup), None)
	if status != 0:
		raise errors.SarvamError(_("Could not initialise the image loader (GDI+)."))
	bitmap = ctypes.c_void_p()
	try:
		status = gdiplus.GdipCreateBitmapFromFile(ctypes.c_wchar_p(path), ctypes.byref(bitmap))
		if status != 0 or not bitmap:
			raise errors.InvalidRequestError(
				_("Could not open the image. Unsupported or corrupt file."))
		width = ctypes.c_uint()
		height = ctypes.c_uint()
		gdiplus.GdipGetImageWidth(bitmap, ctypes.byref(width))
		gdiplus.GdipGetImageHeight(bitmap, ctypes.byref(height))
		w, h = int(width.value), int(height.value)
		if w == 0 or h == 0:
			raise errors.InvalidRequestError(_("The image has no pixels."))
		rect = _Rect(0, 0, w, h)
		data = _BitmapData()
		status = gdiplus.GdipBitmapLockBits(
			bitmap, ctypes.byref(rect), _IMAGE_LOCKMODE_READ,
			_PIXELFORMAT_32BPP_ARGB, ctypes.byref(data))
		if status != 0:
			raise errors.SarvamError(_("Could not read the image pixels."))
		try:
			pixels = (_RGBQUAD * (w * h))()
			stride = data.Stride
			src = ctypes.cast(data.Scan0, ctypes.POINTER(ctypes.c_ubyte))
			row_bytes = w * 4
			for y in range(h):
				base = y * stride
				dst_off = y * w
				# Copy one row; ARGB in memory is B,G,R,A little-endian.
				ctypes.memmove(
					ctypes.addressof(pixels) + dst_off * 4,
					ctypes.addressof(src.contents) + base,
					row_bytes)
			return pixels, w, h
		finally:
			gdiplus.GdipBitmapUnlockBits(bitmap, ctypes.byref(data))
	finally:
		if bitmap:
			gdiplus.GdipDisposeImage(bitmap)
		gdiplus.GdiplusShutdown(token)


def _make_image_info(width, height):
	recog = uwpOcr.UwpOcr()
	imgInfo = RecogImageInfo.createFromRecognizer(0, 0, width, height, recog)
	return recog, imgInfo


def _line_text(line):
	"""Extract text from one OCR line, covering every shape NVDA's UwpOcr has
	used: a dict with a "text" field, a dict with a "words" list, a list of
	word dicts / strings, or a plain string."""
	if isinstance(line, str):
		return line
	if isinstance(line, dict):
		# Prefer an explicit line text; else join the words.
		txt = line.get("text")
		if isinstance(txt, str) and txt.strip():
			return txt
		words = line.get("words")
		if isinstance(words, (list, tuple)):
			return " ".join(_word_text(w) for w in words if _word_text(w))
		return ""
	if isinstance(line, (list, tuple)):
		return " ".join(_word_text(w) for w in line if _word_text(w))
	return str(line)


def _word_text(word):
	if isinstance(word, dict):
		return word.get("text", "")
	return str(word) if word is not None else ""


def _result_to_text(result):
	"""Extract plain text from a contentRecog result, defensively covering the
	variations in ``LinesWordsResult.data`` between NVDA versions."""
	data = getattr(result, "data", None)
	if isinstance(data, dict):
		data = data.get("lines") or data.get("data") or data.get("result")
	if isinstance(data, (list, tuple)):
		lines = [_line_text(line) for line in data]
		text = "\n".join(l for l in lines if l and l.strip())
		if text.strip():
			return text
	# Fallbacks for other result shapes.
	for attr in ("text", "recognizedText"):
		val = getattr(result, attr, None)
		if isinstance(val, str) and val.strip():
			return val
	try:
		s = str(result)
		return s if s and not s.startswith("<") else ""
	except Exception:
		return ""


def recognize_pixels(pixels, imgInfo, recog, on_text, on_error):
	"""Run OCR on a pixel buffer and deliver text via ``on_text``.

	The recognizer works asynchronously and calls back on NVDA's main thread.
	"""
	def onResult(result):
		if isinstance(result, Exception):
			logger.error("OCR failed: %s" % result)
			on_error(errors.SarvamError(_("Windows OCR failed: {err}").format(err=result)))
			return
		text = _result_to_text(result)
		if not text.strip():
			on_error(errors.SarvamError(_("No text was recognised in the image.")))
			return
		on_text(text)
	try:
		recog.recognize(pixels, imgInfo, onResult)
	except Exception as e:
		logger.exception("OCR recognize() raised")
		on_error(errors.SarvamError(_("Could not start OCR: {err}").format(err=e)))


def recognize_image_file(path, on_text, on_error):
	if not is_available():
		on_error(errors.SarvamError(_("Windows OCR is not available on this system.")))
		return
	try:
		pixels, w, h = _load_image_pixels(path)
		recog, imgInfo = _make_image_info(w, h)
	except errors.SarvamError as e:
		on_error(e)
		return
	recognize_pixels(pixels, imgInfo, recog, on_text, on_error)


def recognize_screen(on_text, on_error):
	"""OCR the current navigator object / foreground window region."""
	if not is_available():
		on_error(errors.SarvamError(_("Windows OCR is not available on this system.")))
		return
	try:
		import api
		from screenBitmap import ScreenBitmap
		nav = api.getNavigatorObject()
		try:
			left, top, width, height = nav.location
		except Exception:
			left, top = 0, 0
			width = ctypes.windll.user32.GetSystemMetrics(0)
			height = ctypes.windll.user32.GetSystemMetrics(1)
		if not width or not height:
			on_error(errors.SarvamError(_("Nothing to recognise here.")))
			return
		recog, imgInfo = _make_image_info(width, height)
		sb = ScreenBitmap(imgInfo.recogWidth, imgInfo.recogHeight)
		pixels = sb.captureImage(left, top, width, height)
	except Exception as e:
		logger.exception("Screen capture for OCR failed")
		on_error(errors.SarvamError(_("Could not capture the screen for OCR: {err}").format(err=e)))
		return
	recognize_pixels(pixels, imgInfo, recog, on_text, on_error)


def capture_navigator_png():
	"""Capture the current navigator object (or whole screen) to a temporary
	PNG and return its path. Must be called on the GUI thread."""
	import wx
	import tempfile
	import api
	nav = api.getNavigatorObject()
	try:
		left, top, width, height = nav.location
	except Exception:
		left, top = 0, 0
		size = wx.GetDisplaySize()
		width, height = size.GetWidth(), size.GetHeight()
	if not width or not height:
		raise errors.SarvamError(_("Nothing to capture here."))
	screenDC = wx.ScreenDC()
	bmp = wx.Bitmap(width, height)
	memDC = wx.MemoryDC(bmp)
	memDC.Blit(0, 0, width, height, screenDC, left, top)
	memDC.SelectObject(wx.NullBitmap)
	fd, path = tempfile.mkstemp(suffix=".png", prefix="sarvamAI_screen_")
	os.close(fd)
	if not bmp.ConvertToImage().SaveFile(path, wx.BITMAP_TYPE_PNG):
		raise errors.SarvamError(_("Could not save the screen capture."))
	return path


def save_clipboard_image_to_temp():
	"""If the clipboard holds a bitmap, save it to a temp PNG and return the
	path, else return ``None``."""
	import wx
	if not wx.TheClipboard.Open():
		return None
	try:
		if not wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_BITMAP)):
			return None
		bmpData = wx.BitmapDataObject()
		if not wx.TheClipboard.GetData(bmpData):
			return None
		bmp = bmpData.GetBitmap()
	finally:
		wx.TheClipboard.Close()
	if not bmp or not bmp.IsOk():
		return None
	import tempfile
	fd, path = tempfile.mkstemp(suffix=".png", prefix="sarvamAI_clip_")
	os.close(fd)
	img = bmp.ConvertToImage()
	if not img.SaveFile(path, wx.BITMAP_TYPE_PNG):
		return None
	return path
