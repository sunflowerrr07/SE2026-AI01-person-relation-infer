"""Sequence-local trackers; IDs are not cross-camera ReID identities."""
from pathlib import Path


class MockTracker:
    def __init__(self):
        self.index = 0

    def track(self, image):
        # Synthetic observations deliberately do not depend on image content.
        offset = self.index % 10 * 0.005
        self.index += 1
        return [{'track_id': 'mock-1', 'bbox': [0.1 + offset, 0.1, 0.3 + offset, 0.4]},
                {'track_id': 'mock-2', 'bbox': [0.3 + offset, 0.1, 0.5 + offset, 0.4]}]


class YOLOByteTrack:
    def __init__(self, weights, model=None):
        path = Path(weights)
        if not path.is_file():
            raise FileNotFoundError('provide a local YOLOv8 .pt weights file')
        if model is None:
            from ultralytics import YOLO
            model = YOLO(str(path))
        self.model = model

    def track(self, image):
        results = self.model.track(source=image, classes=[0], tracker='bytetrack.yaml', persist=True, verbose=False)
        boxes = results[0].boxes
        if boxes is None or boxes.id is None:
            return []
        identifiers = boxes.id.cpu().tolist()
        coordinates = boxes.xyxyn.cpu().tolist()
        return [{'track_id': f'track-{int(identifier)}', 'bbox': rectangle}
                for identifier, rectangle in zip(identifiers, coordinates, strict=True)]
