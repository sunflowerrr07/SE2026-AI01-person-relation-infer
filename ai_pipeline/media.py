"""Bounded local media decoding. Folder images form one ordered camera sequence."""
from math import isfinite
from pathlib import Path
import re


def iter_frames(source, fps=10.0, max_frames=300):
    import cv2
    import numpy as np

    if not isfinite(fps) or fps <= 0 or not isinstance(max_frames, int) or max_frames <= 0:
        raise ValueError('fps and max_frames must be positive')
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(path)
    image_types = {'.png', '.jpg', '.jpeg', '.bmp', '.ppm', '.webp'}
    if path.is_dir() or path.suffix.lower() in image_types:
        def natural_key(item):
            return [(0, int(part)) if part.isdigit() else (1, part.lower()) for part in re.split(r'(\d+)', item.name)]
        files = sorted((p for p in path.iterdir() if p.is_file() and p.suffix.lower() in image_types), key=natural_key) if path.is_dir() else [path]
        if not files:
            raise ValueError('no supported images found')
        for index, item in enumerate(files[:max_frames]):
            image = cv2.imdecode(np.fromfile(item, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f'cannot decode image: {item.name}')
            yield {'timestamp': index / fps, 'duration': 1 / fps, 'image': image}
        return
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError('cannot open local video')
        rate = capture.get(cv2.CAP_PROP_FPS)
        if not isfinite(rate) or rate <= 0:
            raise ValueError('video has no usable frame rate')
        for index in range(max_frames):
            ok, image = capture.read()
            if not ok:
                if index == 0:
                    raise ValueError('video contains no decodable frames')
                break
            yield {'timestamp': index / rate, 'duration': 1 / rate, 'image': image}
    finally:
        capture.release()
