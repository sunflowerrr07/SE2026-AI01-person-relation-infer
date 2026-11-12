"""Bridge per-window M2 evidence and separately supplied entity features to PyG."""
import argparse
import json
from math import isfinite
from pathlib import Path
import torch
from .gnn import RelationGNN, load_checkpoint, predict_relations


def infer_m2_report(model, report, entity_features):
    if type(report.get('synthetic')) is not bool:
        raise ValueError('M2 report must declare synthetic provenance')
    identifiers = sorted(entity_features)
    positions = {identifier: index for index, identifier in enumerate(identifiers)}
    features = [entity_features[identifier] for identifier in identifiers]
    windows = {}
    seen = set()
    for edge in report['relations']:
        source, target = edge['source'], edge['target']
        start, end, strength = edge['window_start'], edge['window_end'], edge['strength']
        if source not in positions or target not in positions or source == target:
            raise ValueError('each relation requires distinct entities with supplied features')
        if not all(isfinite(v) for v in (start, end, strength)) or start < 0 or end <= start or not 0 <= strength <= 1:
            raise ValueError('invalid relation window or normalized strength')
        key = (start, end)
        pair = (key, *sorted((source, target)))
        if pair in seen:
            raise ValueError('duplicate unordered relation in a window')
        seen.add(pair)
        matrix = windows.setdefault(key, [[0.0] * len(identifiers) for _ in identifiers])
        i, j = positions[source], positions[target]
        matrix[i][j] = matrix[j][i] = strength
    return {'synthetic_input': report['synthetic'], 'probability_calibrated': False,
            'windows': [{'window_start': start, 'window_end': end,
                         'predictions': predict_relations(model, matrix, features, identifiers)}
                        for (start, end), matrix in sorted(windows.items())]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--features', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if args.output.resolve() in {p.resolve() for p in (args.input, args.features, args.checkpoint) if p is not None}:
        parser.error('output must not overwrite an input or checkpoint')
    try:
        report = json.loads(args.input.read_text(encoding='utf-8'))
        features = json.loads(args.features.read_text(encoding='utf-8'))
        if not isinstance(features, dict) or not features:
            raise ValueError('features must be a nonempty mapping from ID to feature vector')
        if args.checkpoint:
            model = load_checkpoint(args.checkpoint)
        else:
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(args.seed)
                model = RelationGNN(len(next(iter(features.values()))))
        result = infer_m2_report(model, report, features)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f'Error: {exc}\n')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(f"GNN: {len(result['windows'])} windows -> {args.output}")


if __name__ == '__main__':
    main()
