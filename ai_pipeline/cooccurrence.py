"""Aggregate normalized image-space evidence; never infer real social identities."""
from itertools import combinations
from math import floor, hypot, isfinite, isclose


def compute_relations(frames, window_seconds=10.0, distance_scale=0.5):
    """Use half-open windows and observed intervals, without filling detection gaps.

    Strength v1 = .6 * observed_duration/window + .4 * proximity,
    proximity = max(0, 1 - mean_normalized_center_distance/distance_scale).
    """
    if not all(isfinite(x) and x > 0 for x in (window_seconds, distance_scale)):
        raise ValueError('window_seconds and distance_scale must be finite and positive')
    buckets = {}
    previous_end = 0.0
    for frame in frames:
        start, duration = frame['timestamp'], frame['duration']
        if not all(isfinite(x) for x in (start, duration)) or start < 0 or duration <= 0 or (start < previous_end and not isclose(start, previous_end, rel_tol=0, abs_tol=1e-9)):
            raise ValueError('frame intervals must be finite, positive, ordered and non-overlapping')
        end = start + duration
        if not isfinite(end):
            raise ValueError('invalid frame end')
        # Tiny decimal timestamp rounding is not a genuine overlapping frame.
        start = max(start, previous_end)
        previous_end = end
        centers = {}
        for track in frame['tracks']:
            identifier, box = track['track_id'], track['bbox']
            if not isinstance(identifier, str) or not identifier or identifier in centers:
                raise ValueError('track IDs must be distinct nonempty strings in each frame')
            if len(box) != 4 or not all(isfinite(x) and 0 <= x <= 1 for x in box) or box[0] >= box[2] or box[1] >= box[3]:
                raise ValueError('bbox must be a positive normalized xyxy rectangle')
            centers[identifier] = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        for source, target in combinations(sorted(centers), 2):
            distance = hypot(centers[source][0] - centers[target][0], centers[source][1] - centers[target][1])
            cursor = start
            while cursor < end:
                index = floor(cursor / window_seconds)
                boundary = (index + 1) * window_seconds
                overlap = min(end, boundary) - cursor
                key = (index, source, target)
                values = buckets.setdefault(key, [0, 0.0, 0.0])
                values[0] += 1
                values[1] += overlap
                values[2] += distance * overlap
                cursor = min(end, boundary)
    results = []
    for (index, source, target), (count, duration, weighted_distance) in sorted(buckets.items()):
        distance = weighted_distance / duration
        strength = 0.6 * min(1.0, duration / window_seconds) + 0.4 * max(0.0, 1 - distance / distance_scale)
        results.append({'source': source, 'target': target, 'window_start': index * window_seconds,
                        'window_end': (index + 1) * window_seconds, 'co_occurrence_count': count,
                        'total_duration_seconds': duration, 'avg_normalized_distance': distance,
                        'strength': strength, 'algorithm_version': 'cooccurrence-v1'})
    return results
