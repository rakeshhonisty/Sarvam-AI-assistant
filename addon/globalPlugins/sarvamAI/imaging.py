# -*- coding: UTF-8 -*-
# Sarvam AI assistant NVDA add-on
# Copyright (C) 2026 Sarvam AI assistant contributors
# This file is covered by the GNU General Public License v2.

"""Dependency-free imaging helpers.

Sarvam's document OCR accepts a single PDF (or ZIP) per job. To OCR an image we
wrap it into a one-page PDF. Images are decoded and re-encoded to JPEG with
GDI+ via :mod:`ctypes` (no Pillow needed), and the JPEG is embedded into a
minimal, valid PDF using the DCTDecode filter."""

import os
import ctypes
import tempfile

import addonHandler

from . import errors
from . import logger

addonHandler.initTranslation()

# JPEG encoder CLSID used by GDI+ (Windows built-in codec).
_JPEG_ENCODER_CLSID = "{557CF401-1A04-11D3-9A73-0000F81EF32E}"


class _GUID(ctypes.Structure):
	_fields_ = [
		("Data1", ctypes.c_uint32),
		("Data2", ctypes.c_uint16),
		("Data3", ctypes.c_uint16),
		("Data4", ctypes.c_ubyte * 8),
	]


class _GdiplusStartupInput(ctypes.Structure):
	_fields_ = [
		("GdiplusVersion", ctypes.c_uint32),
		("DebugEventCallback", ctypes.c_void_p),
		("SuppressBackgroundThread", ctypes.c_int),
		("SuppressExternalCodecs", ctypes.c_int),
	]


def _clsid_from_string(s):
	guid = _GUID()
	ole32 = ctypes.WinDLL("ole32")
	if ole32.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(guid)) != 0:
		raise errors.SarvamError("Invalid encoder CLSID")
	return guid


def is_pdf(path):
	return os.path.splitext(path)[1].lower() == ".pdf"


def image_to_jpeg(src_path):
	"""Load ``src_path`` with GDI+ and save it as a temporary JPEG.

	Returns ``(jpeg_path, width, height)``.
	"""
	if not os.path.isfile(src_path):
		raise errors.InvalidRequestError(_("Image file not found: {p}").format(p=src_path))
	gdiplus = ctypes.WinDLL("gdiplus")
	token = ctypes.c_void_p()
	startup = _GdiplusStartupInput(1, None, 0, 0)
	if gdiplus.GdiplusStartup(ctypes.byref(token), ctypes.byref(startup), None) != 0:
		raise errors.SarvamError(_("Could not initialise the image loader (GDI+)."))
	bitmap = ctypes.c_void_p()
	try:
		if gdiplus.GdipCreateBitmapFromFile(ctypes.c_wchar_p(src_path), ctypes.byref(bitmap)) != 0 or not bitmap:
			raise errors.InvalidRequestError(_("Could not open the image. Unsupported or corrupt file."))
		w = ctypes.c_uint()
		h = ctypes.c_uint()
		gdiplus.GdipGetImageWidth(bitmap, ctypes.byref(w))
		gdiplus.GdipGetImageHeight(bitmap, ctypes.byref(h))
		fd, jpeg_path = tempfile.mkstemp(suffix=".jpg", prefix="sarvamAI_ocr_")
		os.close(fd)
		clsid = _clsid_from_string(_JPEG_ENCODER_CLSID)
		status = gdiplus.GdipSaveImageToFile(
			bitmap, ctypes.c_wchar_p(jpeg_path), ctypes.byref(clsid), None)
		if status != 0:
			raise errors.SarvamError(_("Could not convert the image to JPEG (GDI+ status {s}).").format(s=status))
		return jpeg_path, int(w.value), int(h.value)
	finally:
		if bitmap:
			gdiplus.GdipDisposeImage(bitmap)
		gdiplus.GdiplusShutdown(token)


def _pdf_from_jpeg(jpeg_bytes, width, height):
	"""Build a minimal one-page PDF embedding ``jpeg_bytes`` (DCTDecode)."""
	objects = []

	def add(obj_bytes):
		objects.append(obj_bytes)
		return len(objects)  # 1-based object number

	catalog = add(b"<< /Type /Catalog /Pages 2 0 R >>")
	pages = add(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
	# Page references image object 4 and content object 5 (added below).
	page = add(
		("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] "
		 "/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>"
		 % (width, height)).encode("ascii"))
	image = add(
		("<< /Type /XObject /Subtype /Image /Width %d /Height %d "
		 "/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
		 "/Length %d >>\nstream\n" % (width, height, len(jpeg_bytes))).encode("ascii")
		+ jpeg_bytes + b"\nendstream")
	content = ("q %d 0 0 %d 0 0 cm /Im0 Do Q" % (width, height)).encode("ascii")
	contentObj = add(
		("<< /Length %d >>\nstream\n" % len(content)).encode("ascii")
		+ content + b"\nendstream")

	# Assemble with a correct cross-reference table.
	out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
	offsets = [0] * (len(objects) + 1)
	for i, body in enumerate(objects, start=1):
		offsets[i] = len(out)
		out += ("%d 0 obj\n" % i).encode("ascii") + body + b"\nendobj\n"
	xref_pos = len(out)
	out += ("xref\n0 %d\n" % (len(objects) + 1)).encode("ascii")
	out += b"0000000000 65535 f \n"
	for i in range(1, len(objects) + 1):
		out += ("%010d 00000 n \n" % offsets[i]).encode("ascii")
	out += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
			% (len(objects) + 1, xref_pos)).encode("ascii")
	return bytes(out)


def image_file_to_pdf(src_path):
	"""Convert an image file to a temporary one-page PDF. Returns the PDF path."""
	jpeg_path, w, h = image_to_jpeg(src_path)
	try:
		with open(jpeg_path, "rb") as f:
			jpeg_bytes = f.read()
	finally:
		try:
			os.remove(jpeg_path)
		except OSError:
			pass
	pdf = _pdf_from_jpeg(jpeg_bytes, w, h)
	fd, pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="sarvamAI_ocr_")
	os.close(fd)
	with open(pdf_path, "wb") as f:
		f.write(pdf)
	logger.debug("Converted image to PDF: %s (%dx%d)" % (pdf_path, w, h))
	return pdf_path


class _RECT(ctypes.Structure):
	_fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
		("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _BITMAPINFOHEADER(ctypes.Structure):
	_fields_ = [
		("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
		("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
		("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
		("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
		("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
		("biClrImportant", ctypes.c_uint32)]


def _screen_rect(foreground=True):
	user32 = ctypes.WinDLL("user32")
	user32.GetForegroundWindow.restype = ctypes.c_void_p
	user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_RECT)]
	rect = _RECT()
	if foreground:
		hwnd = user32.GetForegroundWindow()
		if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
			# Clamp to the virtual screen (SM_X/Y/CX/CYVIRTUALSCREEN).
			vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
			vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
			left, top = max(rect.left, vx), max(rect.top, vy)
			right, bottom = min(rect.right, vx + vw), min(rect.bottom, vy + vh)
			if right - left > 20 and bottom - top > 20:
				return left, top, right - left, bottom - top
	# Whole primary screen.
	return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def capture_screen_bmp(foreground=True):
	"""Capture the foreground window (or the whole screen) as BMP bytes.

	Pure ctypes/GDI: BitBlt from the screen into a 24-bit DIB, then wrap the
	pixels with a BMP file header.
	"""
	import struct
	left, top, w, h = _screen_rect(foreground)
	user32 = ctypes.WinDLL("user32")
	gdi32 = ctypes.WinDLL("gdi32")
	user32.GetDC.restype = ctypes.c_void_p
	user32.GetDC.argtypes = [ctypes.c_void_p]
	user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
	gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
	gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
	gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
	gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
	gdi32.SelectObject.restype = ctypes.c_void_p
	gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
	gdi32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
		ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint32]
	gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
		ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
	gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
	gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
	screen = user32.GetDC(None)
	if not screen:
		raise errors.SarvamError(_("Could not capture the screen."))
	mem = gdi32.CreateCompatibleDC(screen)
	bmp = gdi32.CreateCompatibleBitmap(screen, w, h)
	old = gdi32.SelectObject(mem, bmp)
	try:
		SRCCOPY, CAPTUREBLT = 0x00CC0020, 0x40000000
		if not gdi32.BitBlt(mem, 0, 0, w, h, screen, left, top, SRCCOPY | CAPTUREBLT):
			raise errors.SarvamError(_("Could not capture the screen."))
		header = _BITMAPINFOHEADER()
		header.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
		header.biWidth = w
		header.biHeight = h  # bottom-up, as BMP files expect
		header.biPlanes = 1
		header.biBitCount = 24
		header.biCompression = 0
		stride = ((w * 3 + 3) // 4) * 4
		buf = ctypes.create_string_buffer(stride * h)
		lines = gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(header), 0)
		if lines != h:
			raise errors.SarvamError(_("Could not capture the screen."))
		pixels = buf.raw
		info = bytes(header)
		file_header = struct.pack("<2sIHHI", b"BM", 14 + len(info) + len(pixels), 0, 0, 14 + len(info))
		return file_header + info + pixels
	finally:
		gdi32.SelectObject(mem, old)
		gdi32.DeleteObject(bmp)
		gdi32.DeleteDC(mem)
		user32.ReleaseDC(None, screen)


def capture_screen_jpeg(foreground=True):
	"""Capture the screen and return JPEG bytes (small enough for a vision model)."""
	bmp = capture_screen_bmp(foreground)
	fd, bmp_path = tempfile.mkstemp(suffix=".bmp", prefix="sarvamAI_screen_")
	os.close(fd)
	try:
		with open(bmp_path, "wb") as f:
			f.write(bmp)
		jpeg_path, _w, _h = image_to_jpeg(bmp_path)
		try:
			with open(jpeg_path, "rb") as f:
				return f.read()
		finally:
			try:
				os.remove(jpeg_path)
			except OSError:
				pass
	finally:
		try:
			os.remove(bmp_path)
		except OSError:
			pass


def ensure_pdf(src_path):
	"""Return ``(pdf_path, is_temp)``. If ``src_path`` is already a PDF it is
	returned unchanged; otherwise an image is converted to a temporary PDF."""
	if is_pdf(src_path):
		return src_path, False
	return image_file_to_pdf(src_path), True
