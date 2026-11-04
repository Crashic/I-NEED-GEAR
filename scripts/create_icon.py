"""Знак ING с отдельной отрисовкой каждого размера значка Windows."""

from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
assets = ROOT / "assets"
assets.mkdir(exist_ok=True)
# Узкие буквы сохраняют различимость даже на значке 16×16.
GLYPHS = (
    ("111", "010", "010", "010", "010", "010", "010", "010", "111"),
    ("1001", "1101", "1101", "1101", "1011", "1011", "1011", "1001", "1001"),
    ("1111", "1000", "1000", "1000", "1011", "1001", "1001", "1001", "1111"),
)


def draw_icon(size):
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    radius = max(2, size // 9)
    draw.rounded_rectangle((0, 0, size-1, size-1), radius=radius, fill="#e6b94f")
    # Один тёмный кант вместо нескольких широких рамок.
    if size >= 24:
        draw.rounded_rectangle((0, 0, size-1, size-1), radius=radius, outline="#79501e", width=max(1,size//64))
    left, right = max(1,round(size*.06)), size-max(1,round(size*.06))
    top, bottom = round(size*.19), round(size*.81)
    # Растрируем по целым координатам каждого размера, без размытия букв уменьшением.
    offset = 0
    for glyph in GLYPHS:
        for row, pixels in enumerate(glyph):
            for col, pixel in enumerate(pixels):
                if pixel == "1":
                    x0 = left + round((offset+col)*(right-left)/13)
                    x1 = left + round((offset+col+1)*(right-left)/13)-1
                    y0 = top + round(row*(bottom-top)/9)
                    y1 = top + round((row+1)*(bottom-top)/9)-1
                    draw.rectangle((x0,y0,x1,y1),fill="#181108")
        offset += len(glyph[0])+1
    return image


sizes = [16,24,32,48,64,128,256]
icons = [draw_icon(size) for size in sizes]
icons[-1].save(assets/"icon.ico", sizes=[(size,size) for size in sizes], append_images=icons[:-1])
draw_icon(512).save(assets/"icon.png")
draw_icon(64).save(ROOT/"addon/INEEDGEAR/icon.tga")
# Векторный исходник с теми же буквами.
rectangles=[]
offset=0
for glyph in GLYPHS:
    for row,pixels in enumerate(glyph):
        for col,pixel in enumerate(pixels):
            if pixel=="1":
                rectangles.append(f'<rect x="{1.0+(offset+col)*14/13:.4f}" y="{3+row*10/9:.4f}" width="{14/13:.4f}" height="{10/9:.4f}"/>')
    offset += len(glyph[0])+1
(assets/"icon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect width="16" height="16" rx="2" fill="#e6b94f"/><g fill="#181108">'+''.join(rectangles)+'</g></svg>',encoding="utf-8")
