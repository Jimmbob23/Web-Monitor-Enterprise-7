from pathlib import Path
from PIL import Image, ImageChops, ImageEnhance, ImageStat

def _pad(img, size):
    if img.size == size:
        return img
    canvas = Image.new("RGB", size, "white")
    canvas.paste(img, (0, 0))
    return canvas

def compare_images(old_path: Path, new_path: Path, diff_path: Path):
    old = Image.open(old_path).convert("RGB")
    new = Image.open(new_path).convert("RGB")
    size = (max(old.width, new.width), max(old.height, new.height))
    old = _pad(old, size)
    new = _pad(new, size)
    diff = ImageChops.difference(old, new)

    if not diff.getbbox():
        return False, 0.0

    total = sum(ImageStat.Stat(diff).sum)
    maximum = size[0] * size[1] * 255 * 3
    percent = round((total / maximum) * 100, 4)

    diff_path.parent.mkdir(parents=True, exist_ok=True)
    ImageEnhance.Contrast(ImageEnhance.Brightness(diff).enhance(3)).enhance(4).save(diff_path)
    return True, percent
