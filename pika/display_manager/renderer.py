"""Display rendering component for drawing UI elements.

This module handles all drawing operations for display, including QR codes,
voltage readings, status information, and layout management.
"""

import time
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from ..mini_display import DISPLAY_W, DISPLAY_H
from .config import Colors, Layout, Fonts
from .utils import get_font_with_cache, center_text_x, format_voltage, format_anomaly_status


class DisplayRenderer:
    """Handles all display rendering operations."""
    
    def __init__(self, font_cache: dict):
        """Initialize renderer with font cache.
        
        Args:
            font_cache: Dictionary for caching loaded fonts
        """
        self.font_cache = font_cache
    
    def create_blank_image(self) -> Image.Image:
        """Create a blank black image for the display.
        
        Returns:
            New RGB image with black background
        """
        return Image.new("RGB", (DISPLAY_W, DISPLAY_H), color=Colors.BLACK)
    
    def draw_qr_code(self, draw: ImageDraw.ImageDraw, image: Image.Image, url: str) -> None:
        """Draw QR code centered in the middle."""
        from ..qr_generator import QRCodeGenerator
        
        qr_gen = QRCodeGenerator(border=2, box_size=4)
        qr_img = qr_gen.create_qr_code(url)
        
        from PIL import ImageOps
        qr_img = ImageOps.contain(qr_img, (Layout.QR_SIZE, Layout.QR_SIZE))
        
        # Center QR code
        qx = (DISPLAY_W - qr_img.width) // 2
        qy = (DISPLAY_H - qr_img.height) // 2 - 5 # Shift slightly up
        
        # Draw white background for QR if needed, or just paste it
        # The web component has border-radius and white padding
        bg_pad = 6
        draw.rectangle(
            [qx - bg_pad, qy - bg_pad, qx + qr_img.width + bg_pad, qy + qr_img.height + bg_pad],
            fill=Colors.WHITE
        )
        image.paste(qr_img, (qx, qy))
    
    def draw_header(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        """Draw 'Pika-pika LCD' centered at top."""
        text = "Pika-pika LCD"
        x = center_text_x(text, font, DISPLAY_W)
        draw.text((x, Layout.TITLE_Y), text, fill=Colors.GREEN, font=font)
    
    def draw_data_row(
        self, 
        draw: ImageDraw.ImageDraw, 
        volt_font: ImageFont.ImageFont,
        freq_font: ImageFont.ImageFont,
        voltage: Optional[float],
        freq: float
    ) -> None:
        """Draw Voltage (left) and Frequency (right) in a data row."""
        v_text = format_voltage(voltage)
        f_text = f"{freq:.1f} Hz"
        
        # Calculate positions to keep them apart like the Web UI rows
        # Web UI uses space-around. Let's place them at 1/4 and 3/4 widths roughly
        vx = (DISPLAY_W // 4) - (draw.textlength(v_text, font=volt_font) // 2)
        fx = (3 * DISPLAY_W // 4) - (draw.textlength(f_text, font=freq_font) // 2)
        
        draw.text((vx, Layout.DATA_ROW_Y), v_text, fill=Colors.WHITE, font=volt_font)
        draw.text((fx, Layout.DATA_ROW_Y + 4), f_text, fill=Colors.GREEN, font=freq_font)

    def draw_footer(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        """Draw footer text at bottom."""
        text = "320x240 HORIZONTAL MODE"
        x = center_text_x(text, font, DISPLAY_W)
        y = DISPLAY_H - Layout.MARGIN - 10
        draw.text((x, y), text, fill=(85, 85, 85), font=font) # Faded color

    def render_complete_frame(
        self,
        url: Optional[str],
        voltage: Optional[float],
        anomaly_count: int,
        rms: float = 0.0,
        freq: float = 0.0
    ) -> Image.Image:
        """Render complete display frame matching the Web UI design."""
        image = self.create_blank_image()
        draw = ImageDraw.Draw(image)
        
        # Get fonts
        header_font = get_font_with_cache(self.font_cache, Fonts.PREFERRED_MONO, Layout.MEDIUM_FONT_SIZE)
        volt_font = get_font_with_cache(self.font_cache, Fonts.PREFERRED_MONO, Layout.LARGE_FONT_SIZE)
        freq_font = get_font_with_cache(self.font_cache, Fonts.PREFERRED_MONO, Layout.MEDIUM_FONT_SIZE)
        footer_font = get_font_with_cache(self.font_cache, Fonts.PREFERRED_MONO, Layout.EXTRA_SMALL_FONT_SIZE)
        
        # 1. Header
        self.draw_header(draw, header_font)
        
        # 2. QR Code (Centered)
        if url:
            self.draw_qr_code(draw, image, url)
        
        # 3. Data Row (Voltage & Frequency)
        # Note: We use freq instead of rms for the sidebar match if requested, 
        # but User asked for Peak to Peak freq @config.toml:L41 which is freq param.
        self.draw_data_row(draw, volt_font, freq_font, voltage, freq)
        
        # 4. Footer
        self.draw_footer(draw, footer_font)
        
        return image
