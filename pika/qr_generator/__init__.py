"""QR code generation package.

This package provides a clean, focused module for generating QR codes
with various configuration options and output formats.
"""

from .generator import QRCodeGenerator, make_qr_image

__all__ = ['QRCodeGenerator', "make_qr_image"]
