"""Воспроизводимый знак ING: геометрическая бронзовая рамка и золотые буквы."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
assets = ROOT / "assets"
assets.mkdir(exist_ok=True)
image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((10, 10, 502, 502), radius=64, fill="#17110b", outline="#392612", width=10)
draw.rounded_rectangle((24, 24, 488, 488), radius=48, fill="#a87732", outline="#e6c577", width=5)
draw.rounded_rectangle((43, 43, 469, 469), radius=32, fill="#191613", outline="#4b3018", width=9)
draw.rounded_rectangle((55, 55, 457, 457), radius=23, outline="#bc8a42", width=3)
for y in range(65, 448):
    t = (y - 65) / 383
    color = (int(39 - 17*t), int(32 - 15*t), int(24 - 11*t))
    draw.line((66, y, 446, y), fill=color)
for x,y in ((36,36),(476,36),(36,476),(476,476)):
    draw.ellipse((x-8,y-8,x+8,y+8), fill="#ebca78", outline="#6f471c", width=3)
font = ImageFont.truetype('C:/Windows/Fonts/georgiab.ttf', 142)
draw.text((256,270), "ING", font=font, anchor="mm", fill="#090807", stroke_width=5, stroke_fill="#090807")
draw.text((256,260), "ING", font=font, anchor="mm", fill="#efd185", stroke_width=1, stroke_fill="#b48638")
draw.line((117,353,395,353),fill="#a97832",width=3)
draw.polygon(((246,353),(256,343),(266,353),(256,363)), fill="#e0b65e")
image.save(assets/'icon.png')
image.save(assets/'icon.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
image.resize((64,64),Image.Resampling.LANCZOS).save(ROOT/'addon/INEEDGEAR/icon.tga')
(assets/'icon.svg').write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<rect x="16" y="16" width="480" height="480" rx="56" fill="#a87732" stroke="#e6c577" stroke-width="8"/>
<rect x="48" y="48" width="416" height="416" rx="28" fill="#191613" stroke="#bc8a42" stroke-width="4"/>
<text x="256" y="300" text-anchor="middle" fill="#efd185" font-family="Georgia,serif" font-weight="bold" font-size="142">ING</text>
<path d="M117 353H395 M246 353L256 343L266 353L256 363Z" fill="#e0b65e" stroke="#a97832" stroke-width="3"/>
</svg>''',encoding='utf-8')
