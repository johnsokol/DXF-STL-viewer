#!/usr/bin/env python3
"""Render stl-viewer.png from Pillow primitives (mirrors stl-viewer.svg)."""
import os
from PIL import Image, ImageDraw, ImageFont

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# rounded gradient tile (warm tone, distinct from the DXF blue)
bg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
bgd = ImageDraw.Draw(bg)
top, bot = (123, 52, 30), (69, 26, 14)
for y in range(S):
    t = y / (S - 1)
    c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,)
    bgd.line([(0, y), (S, y)], fill=c)
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([16, 16, 240, 240], radius=32, fill=255)
img.paste(bg, (0, 0), mask)

# faint grid clipped to tile
grid = Image.new("RGBA", (S, S), (0, 0, 0, 0))
gd = ImageDraw.Draw(grid)
for x in range(48, 240, 32):
    gd.line([(x, 16), (x, 240)], fill=(138, 74, 48, 130), width=1)
for y in range(48, 240, 32):
    gd.line([(16, y), (240, y)], fill=(138, 74, 48, 130), width=1)
img.paste(grid, (0, 0), Image.composite(grid.split()[3], Image.new("L", (S, S), 0), mask))

# isometric cube faces
top_f = [(128, 56), (196, 96), (128, 136), (60, 96)]
left_f = [(60, 96), (128, 136), (128, 200), (60, 160)]
right_f = [(196, 96), (128, 136), (128, 200), (196, 160)]
d.polygon(top_f, fill=(90, 208, 184, 255))
d.polygon(left_f, fill=(58, 154, 137, 255))
d.polygon(right_f, fill=(44, 117, 103, 255))
for f in (top_f, left_f, right_f):
    d.line(f + [f[0]], fill=(14, 43, 37, 255), width=3, joint="curve")

try:
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
except Exception:
    font = ImageFont.load_default()
d.text((128, 212), "STL", anchor="ma", fill=(240, 226, 220, 255), font=font)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl-viewer.png")
img.save(out)
print("wrote", out)
