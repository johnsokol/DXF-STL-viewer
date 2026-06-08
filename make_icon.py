#!/usr/bin/env python3
"""Render dxf-viewer.png from Pillow primitives (mirrors dxf-viewer.svg).

Run once to (re)generate the raster icon used for the app window:
    python3 make_icon.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# vertical gradient background inside a rounded tile
bg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
bgd = ImageDraw.Draw(bg)
top, bot = (43, 108, 176), (26, 54, 93)
for y in range(S):
    t = y / (S - 1)
    c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,)
    bgd.line([(0, y), (S, y)], fill=c)
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([16, 16, 240, 240], radius=32, fill=255)
img.paste(bg, (0, 0), mask)

# blueprint grid (clipped to tile)
grid = Image.new("RGBA", (S, S), (0, 0, 0, 0))
gd = ImageDraw.Draw(grid)
for x in range(48, 240, 32):
    gd.line([(x, 16), (x, 240)], fill=(61, 110, 165, 150), width=1)
for y in range(48, 240, 32):
    gd.line([(16, y), (240, y)], fill=(61, 110, 165, 150), width=1)
img.paste(grid, (0, 0), Image.composite(grid.split()[3], Image.new("L", (S, S), 0), mask))

# DXF drawing in mint
mint = (78, 201, 176, 255)
d.rounded_rectangle([56, 80, 200, 176], radius=4, outline=mint, width=6)
d.ellipse([78, 106, 122, 150], outline=mint, width=6)
d.line([150, 104, 186, 152], fill=mint, width=6)
d.line([150, 152, 186, 104], fill=mint, width=6)

# yellow vertex dots
for cx, cy in [(56, 80), (200, 80), (56, 176), (200, 176)]:
    d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(255, 215, 0, 255))

# DXF label
try:
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
except Exception:
    font = ImageFont.load_default()
d.text((128, 210), "DXF", anchor="ma", fill=(226, 232, 240, 255), font=font)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf-viewer.png")
img.save(out)
# also a 64px copy is fine; Tk scales the 256 down acceptably
print("wrote", out)
