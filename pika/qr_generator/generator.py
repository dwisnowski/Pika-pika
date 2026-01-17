"""QR code generation module.

This module provides a clean interface for generating QR codes with various
configuration options and output formats. It handles QR code creation,
scaling, and positioning on background images.
"""

from typing import Tuple

from PIL import Image, ImageOps
import qrcode

from .config import QRDefaults, QRColors


class QRCodeGenerator:
    """Generator for creating QR code images with customizable options."""
    
    def __init__(
        self,
        border: int = QRDefaults.BORDER,
        box_size: int = QRDefaults.BOX_SIZE,
        margin: int = QRDefaults.MARGIN,
        text_offset_y: int = QRDefaults.TEXT_OFFSET_Y
    ):
        """Initialize QR code generator with configuration.
        
        Args:
            border: Border size around QR code
            box_size: Size of each QR code box
            margin: Margin around QR code when placing on background
            text_offset_y: Y offset for text placement below QR code
        """
        self.border = border
        self.box_size = box_size
        self.margin = margin
        self.text_offset_y = text_offset_y
    
    def create_qr_code(self, data: str) -> Image.Image:
        """Create a basic QR code image.
        
        Args:
            data: Data to encode in QR code
            
        Returns:
            QR code image with white background and black code
        """
        qr = qrcode.QRCode(border=self.border, box_size=self.box_size)
        qr.add_data(data)
        qr.make(fit=True)
        return qr.make_image(fill_color=QRColors.BLACK, back_color=QRColors.WHITE).convert("RGB")
    
    def scale_qr_to_fit(self, qr_image: Image.Image, max_width: int, max_height: int) -> Image.Image:
        """Scale QR code to fit within specified dimensions.
        
        Args:
            qr_image: QR code image to scale
            max_width: Maximum width for scaled image
            max_height: Maximum height for scaled image
            
        Returns:
            Scaled QR code image
        """
        max_size = min(max_width, max_height) - self.margin
        return ImageOps.contain(qr_image, (max_size, max_size))
    
    def create_background(self, width: int, height: int, color: Tuple[int, int, int] = QRColors.WHITE) -> Image.Image:
        """Create a background image of specified size.
        
        Args:
            width: Background width
            height: Background height
            color: Background RGB color
            
        Returns:
            Background image
        """
        return Image.new("RGB", (width, height), color=color)
    
    def center_qr_on_background(self, background: Image.Image, qr_image: Image.Image) -> Image.Image:
        """Center QR code on background image.
        
        Args:
            background: Background image to place QR on
            qr_image: QR code image to center
            
        Returns:
            Background image with QR code centered
        """
        x = (background.width - qr_image.width) // 2
        y = (background.height - qr_image.height) // 2 + self.text_offset_y
        background.paste(qr_image, (x, y))
        return background
    
    def generate_qr_image(
        self,
        data: str,
        output_width: int,
        output_height: int,
        background_color: Tuple[int, int, int] = QRColors.WHITE
    ) -> Image.Image:
        """Generate complete QR code image with background.
        
        Args:
            data: Data to encode in QR code
            output_width: Output image width
            output_height: Output image height
            background_color: Background RGB color
            
        Returns:
            Complete QR code image with background
        """
        # Create QR code
        qr_image = self.create_qr_code(data)
        
        # Scale QR to fit
        scaled_qr = self.scale_qr_to_fit(qr_image, output_width, output_height)
        
        # Create background and center QR
        background = self.create_background(output_width, output_height, background_color)
        return self.center_qr_on_background(background, scaled_qr)
    
    def generate_simple_qr(
        self,
        data: str,
        size: int = 200
    ) -> Image.Image:
        """Generate a simple QR code without background.
        
        Args:
            data: Data to encode in QR code
            size: QR code size (width and height)
            
        Returns:
            Simple QR code image
        """
        qr = qrcode.QRCode(border=self.border, box_size=self.box_size)
        qr.add_data(data)
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color=QRColors.BLACK, back_color=QRColors.WHITE)
        return qr_image.resize((size, size))


# Convenience function for backward compatibility
def make_qr_image(
    url: str,
    out_w: int = 240,
    out_h: int = 320
) -> Image.Image:
    """Generate QR code image with default settings.
    
    Args:
        url: URL to encode in QR code
        out_w: Output image width
        out_h: Output image height
        
    Returns:
        QR code image with white background
    """
    generator = QRCodeGenerator()
    return generator.generate_qr_image(url, out_w, out_h)
