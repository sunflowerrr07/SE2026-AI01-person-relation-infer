"""Run local media through mock or YOLOv8/ByteTrack observations and aggregation."""
import argparse
import json
from pathlib import Path

from .cooccurrence import compute_relations
from .media import iter_frames
from .tracking import MockTracker, YOLOByteTrack


def run_pipeline(source, mode='mock', fps=10.0, window_seconds=10.0, max_frames=300, weights=None):
    if mode not in ('mock', 'yolo'):
        raise ValueError('mode must be mock or yolo')
    if mode == 'yolo' and weights is None:
        raise ValueError('yolo mode requires local weights')
    tracker = MockTracker() if mode == 'mock' else YOLOByteTrack(weights)
    count = 0

    def observations():
        nonlocal count
        for frame in iter_frames(source, fps=fps, max_frames=max_frames):
            tracks = tracker.track(frame['image'])
            count += 1
            yield {'timestamp': frame['timestamp'], 'duration': frame['duration'], 'tracks': tracks}

    relations = compute_relations(observations(), window_seconds=window_seconds)
    return {'mode': mode, 'synthetic': mode == 'mock', 'frames_processed': count,
            'source_name': Path(source).name, 'window_seconds': window_seconds,
            'coordinate_system': 'normalized_image_xyxy', 'identity_scope': 'single_sequence_track',
            'tracking': 'synthetic' if mode == 'mock' else 'YOLOv8+ByteTrack',
            'relations': relations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--mode', choices=['mock', 'yolo'], default='mock')
    parser.add_argument('--fps', type=float, default=10.0, help='image sequence fps; videos use embedded fps')
    parser.add_argument('--window-seconds', type=float, default=10.0)
    parser.add_argument('--max-frames', type=int, default=300)
    parser.add_argument('--weights', type=Path)
    args = parser.parse_args()
    if args.output.resolve() == args.source.resolve():
        parser.error('output must not overwrite source')
    try:
        report = run_pipeline(args.source, args.mode, args.fps, args.window_seconds, args.max_frames, args.weights)
    except (ValueError, FileNotFoundError, ImportError) as exc:
        parser.exit(2, f'Error: {exc}\n')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    print(f"{report['mode']}: {report['frames_processed']} frames, {len(report['relations'])} windowed relations -> {args.output}")


if __name__ == '__main__':
    main()
