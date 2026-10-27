#!/usr/bin/env python3
"""PetroMind: 3W first-N-seconds fault diagnosis sensor ablation.

Run: python ablation.py --dataset ../3W/dataset --seconds 600 --splits 10
Real WELL files only. One row per incident, first contiguous transient window.
Labels select the offline window; NEVER provided as predictive features.
"""
import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline

ORIGINAL_5 = ['P-PDG', 'P-TPT', 'T-TPT', 'P-MON-CKP', 'T-PDG']
STATS = ['median', 'std', 'change', 'missing']
# Numerical safety guardrail only (not a physical sensor calibration).
MAX_ABS_RAW = 1e12
PHYSICAL_PREFIXES = ('P-', 'T-', 'Q')  # pressure, temperature, flow; excludes valve/actuator status


def robust_std(a):
    if not len(a):
        return np.nan
    s = np.max(np.abs(a))
    return float(np.std(a / s) * s) if s else 0.0


def extract_window(df, sensors, n):
    result = {}
    for s in sensors:
        if s in df.columns:
            v = pd.to_numeric(df[s], errors='coerce').to_numpy(dtype='float64')
        else:
            v = np.full(n, np.nan, dtype='float64')
        v[~np.isfinite(v) | (np.abs(v) > MAX_ABS_RAW)] = np.nan
        valid = v[np.isfinite(v)]
        result[s + '_missing'] = float(1 - len(valid) / n)
        result[s + '_median'] = float(np.median(valid)) if len(valid) else np.nan
        result[s + '_std'] = robust_std(valid)
        a, b = v[:n//2], v[n//2:]
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        result[s + '_change'] = float(np.median(b) - np.median(a)) if len(a) and len(b) else np.nan
    return result


def dataset_rows(root, seconds):
    paths = sorted(p for p in root.rglob('WELL-*.parquet')
                   if p.parent.name.isdigit() and 1 <= int(p.parent.name) <= 9)
    if not paths:
        raise ValueError(f'No real event Parquet files found in {root}')
    sensors = set()
    for p in paths:
        schema = pd.read_parquet(p).columns
        sensors.update(c for c in schema if c not in ('class', 'state'))
    sensors = sorted(sensors)
    rows = []
    for p in paths:
        df = pd.read_parquet(p)
        label = 100 + int(p.parent.name)
        classes = df['class'].astype('Int64')
        hits = np.flatnonzero(classes.eq(label).fillna(False).to_numpy(dtype=bool))
        if not len(hits):
            continue
        start = int(hits[0])
        if start + seconds > len(df) or not classes.iloc[start:start+seconds].eq(label).fillna(False).all():
            continue
        match = re.match(r'(WELL-\d+)_', p.name)
        if not match:
            continue
        row = extract_window(df.iloc[start:start+seconds], sensors, seconds)
        row.update(well=match.group(1), event=int(p.parent.name), file=str(p))
        rows.append(row)
    if not rows:
        raise ValueError('No incidents with a sufficiently long contiguous transient stage')
    return pd.DataFrame(rows), sensors


def model(seed):
    return make_pipeline(
        SimpleImputer(strategy='constant', fill_value=-999., keep_empty_features=True),
        RandomForestClassifier(n_estimators=200, min_samples_leaf=2,
                               random_state=seed, class_weight='balanced_subsample', n_jobs=-1))


def columns_for(sensors, stats=STATS):
    return [s + '_' + stat for s in sensors for stat in stats]


def Xmat(data, cols):
    return data.reindex(columns=cols).replace([np.inf, -np.inf], np.nan).astype(float).mask(
        lambda x: x.abs() > MAX_ABS_RAW)


def top_sensors(train, sensors, seed):
    """Fit importance model on train only; aggregate engineered feature importances."""
    cols = columns_for(sensors)
    m = model(seed)
    m.fit(Xmat(train, cols), train.event)
    imp = m[-1].feature_importances_
    scores = {s: sum(float(imp[cols.index(s + '_' + stat)]) for stat in STATS) for s in sensors}
    return sorted(sensors, key=lambda s: (-scores[s], s))[:5], sorted(scores.items(), key=lambda t: -t[1])[:12]


def eval_one(train, test, sensors, stats, seed):
    cols = columns_for(sensors, stats)
    m = model(seed)
    m.fit(Xmat(train, cols), train.event)
    pred = m.predict(Xmat(test, cols))
    labels = sorted(set(train.event) | set(test.event))
    supported = sorted(set(test.event))
    return {
        'accuracy': accuracy_score(test.event, pred),
        'macro_f1_supported': f1_score(test.event, pred, labels=supported, average='macro', zero_division=0),
        'macro_f1_all': f1_score(test.event, pred, labels=labels, average='macro', zero_division=0),
        'coverage': len(set(test.event) & set(train.event)) / len(set(test.event)),
        'pred': pred, 'labels': labels,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path('../3W/dataset'))
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--splits', type=int, default=10)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if args.seconds < 2 or args.splits < 1:
        parser.error('--seconds >= 2 and --splits >= 1 required')
    data, sensors = dataset_rows(args.dataset, args.seconds)
    physical = [s for s in sensors if s.startswith(PHYSICAL_PREFIXES)]
    print(f'Eligible real transient incidents: {len(data)}; distinct wells: {data.well.nunique()}')
    print('Incident counts:', data.event.value_counts().sort_index().to_dict())
    print(f'Available: {len(sensors)} measurement/control variables, {len(physical)} physical variables')
    print('Physical variables:', physical)
    print('NOTE: selected windows begin at GROUND-TRUTH transient onset; this is offline classification, not detection.')
    print('NOTE: extreme raw measurements above 1e12 magnitude are masked, a numerical heuristic.')
    splitter = GroupShuffleSplit(n_splits=args.splits, test_size=.25, random_state=args.seed)
    results = []
    for i, (tr, te) in enumerate(splitter.split(data, data.event, groups=data.well), 1):
        train, test = data.iloc[tr], data.iloc[te]
        top5, rank = top_sensors(train, sensors, args.seed+i)
        configs = {
            'original_5': (ORIGINAL_5, STATS),
            'train_top_5': (top5, STATS),
            'physical_only': (physical, STATS),
            'all_no_missingness': (sensors, ['median','std','change']),
            'missingness_only': (sensors, ['missing']),
            'all_variables': (sensors, STATS),
        }
        if i == 1:
            print(f'\nFirst split: train={len(train)} ({train.well.nunique()} wells), test={len(test)} ({test.well.nunique()} wells)')
            print('Train classes:', sorted(train.event.unique()))
            print('Test classes:', sorted(test.event.unique()))
            print('Training-selected top 5:', top5)
            print('Training sensor importance top 12:', rank)
        for name, (sensor_subset, stat_subset) in configs.items():
            res = eval_one(train, test, sensor_subset, stat_subset, args.seed + i)
            results.append(dict(split=i, model=name, accuracy=res['accuracy'],
                                f1=res['macro_f1_supported'], coverage=res['coverage'],
                                n_test=len(test)))
            if i == 1:
                print(f'\n--- {name} ---')
                print(f'accuracy={res["accuracy"]:.3f}, supported-class macro F1={res["macro_f1_supported"]:.3f}, '
                      f'test-class coverage in train={res["coverage"]:.2f}')
                print(classification_report(test.event, res['pred'], labels=res['labels'], zero_division=0))
                print('Confusion labels:', res['labels'])
                print(confusion_matrix(test.event, res['pred'], labels=res['labels']))
    summary = pd.DataFrame(results)
    aggregate = summary.groupby('model')[['accuracy', 'f1', 'coverage']].agg(['mean', 'std'])
    print(f'\n=== {args.splits} GROUPED SPLITS: MEAN / STD ===')
    print(aggregate.round(3).to_string())
    print('\nCAVEAT: overlapping test wells across repeated splits; uncertainty is descriptive, not a confidence interval.')
    print('CAVEAT: some held-out classes may have no examples in training; consult class coverage.')
    out = Path('ablation_results.csv')
    summary.to_csv(out, index=False)
    print('Saved:', out.resolve())


if __name__ == '__main__':
    main()
