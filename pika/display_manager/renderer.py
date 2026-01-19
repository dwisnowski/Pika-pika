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
        """Draw QR code in top-right corner.
        
        Args:
            draw: ImageDraw context
            image: Image to paste QR code onto
            url: URL to encode in QR code
        """
        from ..qr_generator import QRCodeGenerator
        
        # Create small QR generator for display
        qr_gen = QRCodeGenerator(border=1, box_size=3)
        qr_img = qr_gen.create_qr_code(url)
        
        # Scale to fit display
        from PIL import ImageOps
        qr_img = ImageOps.contain(qr_img, (Layout.QR_SIZE, Layout.QR_SIZE))
        
        qx = DISPLAY_W - Layout.QR_SIZE - Layout.MARGIN
        qy = Layout.MARGIN
        image.paste(qr_img, (qx, qy))
    
    def draw_title(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        """Draw title at top of display.
        
        Args:
            draw: ImageDraw context
            font: Font to use for title
        """
        title = "PIKA-PIKA MONITOR"
        draw.text((Layout.MARGIN, Layout.TITLE_Y), title, fill=Colors.GREEN, font=font)
    
    def draw_voltage(
        self, 
        draw: ImageDraw.ImageDraw, 
        font: ImageFont.ImageFont, 
        voltage: Optional[float]
    ) -> int:
        """Draw voltage reading in center.
        
        Args:
            draw: ImageDraw context
            font: Font to use for voltage display
            voltage: Current voltage reading
            
        Returns:
            Y position for next element
        """
        vtext = format_voltage(voltage)
        vx = center_text_x(vtext, font, DISPLAY_W)
        vy = DISPLAY_H // 2 + Layout.VOLTAGE_Y_OFFSET
        draw.text((vx, vy), vtext, fill=Colors.GREEN, font=font)
        return vy
    
    def draw_anomaly_status(
        self, 
        draw: ImageDraw.ImageDraw, 
        font: ImageFont.ImageFont, 
        y_position: int,
        anomaly_count: int
    ) -> None:
        """Draw anomaly status below voltage.
        
        Args:
            draw: ImageDraw context
            font: Font to use for status text
            y_position: Y position to draw below
            anomaly_count: Number of anomalies detected
        """
        anom_text, anom_color = format_anomaly_status(anomaly_count)
        ax = center_text_x(anom_text, font, DISPLAY_W)
        ay = y_position + Layout.ANOMALY_Y_OFFSET
        draw.text((ax, ay), anom_text, fill=anom_color, font=font)
    
    def draw_time(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        """Draw current time at bottom.
        
        Args:
            draw: ImageDraw context
            font: Font to use for time display
        """
        ts = time.strftime("%H:%M:%S")
        tx = center_text_x(ts, font, DISPLAY_W)
        ty = DISPLAY_H - Layout.TIME_Y_OFFSET
        draw.text((tx, ty), ts, fill=Colors.GREEN, font=font)
    
    def draw_mascot(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        """Draw mascot tagline at very bottom.
        
        Args:
            draw: ImageDraw context
            font: Font to use for mascot text
        """
        mascot = "⚡ Electric Mascot ⚡"
        mx = center_text_x(mascot, font, DISPLAY_W)
        my = DISPLAY_H - Layout.MASCOT_Y_OFFSET
        draw.text((mx, my), mascot, fill=Colors.GREEN, font=font)
    
    def draw_analysis(
        self,
        draw: ImageDraw.ImageDraw,
        font: ImageFont.ImageFont,
        y_position: int,
        rms: float,
        freq: float
    ) -> None:
        """Draw RMS and Frequency below anomaly status."""
        text = f"RMS: {rms:.2f}V | {freq:.1f}Hz"
        x = center_text_x(text, font, DISPLAY_W)
        y = y_position + Layout.ANOMALY_Y_OFFSET  # Use same offset/spacing
        draw.text((x, y), text, fill=Colors.GREEN, font=font)

    def render_complete_frame(
        self,
        url: Optional[str],
        voltage: Optional[float],
        anomaly_count: int,
        rms: float = 0.0,
        freq: float = 0.0
    ) -> Image.Image:
        """Render complete display frame with all UI elements.
        
        Args:
            url: URL for QR code (optional)
            voltage: Current voltage reading
            anomaly_count: Number of anomalies detected
            rms: RMS voltage
            freq: Frequency in Hz
            
        Returns:
            Complete rendered image
        """
        image = self.create_blank_image()
        draw = ImageDraw.Draw(image)
        
        # Get fonts
        font = get_font_with_cache(self.font_cache, Fonts.PREFERRED_MONO, Layout.SMALL_FONT_SIZE)
        large_font = get_font_with_cache(self.font_cache, Fonts.PREFERRED_MONO, Layout.LARGE_FONT_SIZE)
        
        # Draw all elements
        if url:
            self.draw_qr_code(draw, image, url)
        
        self.draw_title(draw, font)
        voltage_y = self.draw_voltage(draw, large_font, voltage)
        
        # Draw anomaly status
        self.draw_anomaly_status(draw, font, voltage_y, anomaly_count)
        
        # Draw Analysis below anomaly status
        # Calculate Y pos: Voltage Y + Anomaly Delta + Analysis Delta
        # Or just use relative
        analysis_y = voltage_y + Layout.ANOMALY_Y_OFFSET + 25 # Add some space
        self.draw_analysis(draw, font, analysis_y, rms, freq)
        
        self.draw_time(draw, font)
        self.draw_mascot(draw, font)
        
        return image
