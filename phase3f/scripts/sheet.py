"""Contact sheet of PNGs in a folder (sorted by the number in the name).   python sheet.py <dir> <out.png> [cols=5]"""
import glob, os, re, sys
from PIL import Image, ImageDraw
d, out = sys.argv[1], sys.argv[2]
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 5
fs = sorted(glob.glob(os.path.join(d, "*.png")), key=lambda s: int(re.findall(r"\d+", os.path.basename(s))[0]))
W, H = 400, 225
rows = (len(fs) + cols - 1) // cols
sh = Image.new("RGB", (cols * W, rows * (H + 18)), "white")
dr = ImageDraw.Draw(sh)
for i, f in enumerate(fs):
    im = Image.open(f).convert("RGB"); im.thumbnail((W, H))
    x, y = (i % cols) * W, (i // cols) * (H + 18)
    sh.paste(im, (x, y + 18)); dr.text((x + 4, y + 3), os.path.basename(f), fill="black")
sh.save(out)
print(len(fs), "images")
