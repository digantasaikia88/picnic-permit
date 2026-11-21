"""Crops and compresses the landing page photos.

Originals are kept beside this file. Output goes to frontend/public/photos/.
Run from the project folder:

    docker compose exec backend python /photos/prepare.py
"""

from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
OUT = Path("/photos-out")

# name: (source file, crop box left/top/right/bottom or None for the whole picture, output width)
PHOTOS = {
    # Hero: wide view of the stream, umbrellas and hills.
    "hero": ("original-stream-and-hills.jpg", (0, 150, 1421, 950), 1280),
    # The crop leaves out the foreground, where a number plate was readable.
    "vehicles": ("original-parking-area.jpg", (0, 235, 1155, 785), 800),
    "evening": ("original-river-boats.jpg", (0, 200, 1155, 750), 800),
    # Shown whole: the two safety messages in its corners are part of the picture.
    "driver": ("original-driver.webp", None, 800),
}

OUT.mkdir(parents=True, exist_ok=True)
for name, (source, box, width) in PHOTOS.items():
    image = Image.open(HERE / source).convert("RGB")
    if box:
        image = image.crop(box)
    height = round(image.height * width / image.width)
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    target = OUT / f"{name}.webp"
    image.save(target, "WEBP", quality=76, method=6)
    print(f"{target.name}: {width}x{height}, {target.stat().st_size // 1024} KB")
