"""Contact sheet of captures: python contact.py <out.png> <cols> <width> <img> [<img> ...] (labels = file names)."""
import os
import sys

from PIL import Image, ImageDraw


def main(out, cols, width, *imgs):
    cols, width = int(cols), int(width)
    ims = [Image.open(p).convert("RGB") for p in imgs]
    h = int(width * ims[0].height / ims[0].width)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * width, rows * (h + 16)), "black")
    dr = ImageDraw.Draw(sheet)
    for i, (p, im) in enumerate(zip(imgs, ims)):
        x, y = (i % cols) * width, (i // cols) * (h + 16)
        sheet.paste(im.resize((width, h)), (x, y + 16))
        dr.text((x + 4, y + 2), os.path.basename(p), fill="yellow")
    sheet.save(out)


if __name__ == "__main__":
    main(*sys.argv[1:])
