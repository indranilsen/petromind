#!/usr/bin/env python3
"""PetroMind active-sensor benchmark (offline first-10-minute transient diagnosis).

Uses real Petrobras 3W WELL files, grouped by well. Labels ONLY locate the
transient evaluation window and supervise model training. Test labels are not
available to selection or prediction policies.

All limited-budget policies share exactly one train-fitted diagonal Gaussian
sensor-evidence model. Each requested sensor costs 1 regardless of missingness.
No test-set statistics are used to fit the model or sensor rankings.

Run: python active_sensors.py --dataset ../3W/dataset --seconds 600 --splits 10
"""
import argparse
from collections import Counter
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import accuracy_score, f1_score

# Reuse feature extraction with numerical cleaning and real-incident filter.
from ablation import dataset_rows, MAX_ABS_RAW

FEATURES = ('median', 'std', 'change')


def logsumexp(a):
    m = np.max(a)
    return m + np.log(np.exp(a - m).sum())


def posterior(logp):
    z = logp - logsumexp(logp)
    return np.exp(z)


class SensorEvidence:
    """Train-only fitted Gaussian evidence for each sensor and event class.

    For each sensor, a 3-feature vector (median, std, change) is transformed
    using train-only robust scaling, then class-conditional Gaussian densities
    are estimated with variance floors. Missing readings are ignored at
    inference, never interpreted as negative evidence.
    """
    def __init__(self, var_floor=.25):
        self.var_floor = var_floor

    def fit(self, train, sensors):
        self.sensors = list(sensors)
        self.classes = np.array(sorted(train.event.unique()), dtype=int)
        self.columns = {s: [f'{s}_{f}' for f in FEATURES] for s in self.sensors}
        y = train.event.to_numpy()
        counts = np.array([(y == c).sum() for c in self.classes], dtype=float)
        self.prior = np.log((counts + 1) / (counts.sum() + len(counts)))
        self.params = {}
        self.separation = {}
        for s in self.sensors:
            x = train[self.columns[s]].to_numpy(dtype=float)
            x[~np.isfinite(x) | (np.abs(x) > MAX_ABS_RAW)] = np.nan
            # Train-only robust standardization: differences in raw sensor units
            # must not dominate the evidence scoring.
            center = np.nanmedian(x, axis=0)
            center = np.where(np.isfinite(center), center, 0.0)
            q25 = np.nanpercentile(x, 25, axis=0)
            q75 = np.nanpercentile(x, 75, axis=0)
            scale = (q75 - q25) / 1.349
            scale = np.where(np.isfinite(scale) & (scale > 1e-8), scale, 1.0)
            x = np.clip((x - center) / scale, -10, 10)
            # Global fallback for rare / absent classes; no test data used.
            gmean = np.nanmean(x, axis=0)
            gmean = np.where(np.isfinite(gmean), gmean, 0.0)
            means, variances = [], []
            for c in self.classes:
                part = x[y == c]
                finite_count = np.isfinite(part).sum(axis=0)
                sums = np.nansum(part, axis=0)
                mean = np.divide(sums, finite_count, out=gmean.copy(), where=finite_count > 0)
                centered = np.where(np.isfinite(part), part - mean, 0.0)
                var = np.divide((centered ** 2).sum(axis=0), finite_count,
                                out=np.ones(3, dtype=float), where=finite_count > 1)
                means.append(mean)
                variances.append(np.maximum(var, self.var_floor))
            means = np.array(means)
            variances = np.array(variances)
            self.params[s] = (center, scale, means, variances)
            self.separation[s] = self.discriminativeness(s, np.exp(self.prior))
        return self

    def evidence(self, row, s):
        center, scale, means, variances = self.params[s]
        vals = np.asarray([row[f'{s}_{f}'] for f in FEATURES], dtype=float)
        vals[~np.isfinite(vals) | (np.abs(vals) > MAX_ABS_RAW)] = np.nan
        z = np.clip((vals - center) / scale, -10, 10)
        valid = np.isfinite(z)
        if not valid.any():
            return np.zeros(len(self.classes))
        z, mu, var = z[valid], means[:, valid], variances[:, valid]
        return -0.5 * (np.log(2 * np.pi * var) + ((z - mu) ** 2) / var).sum(axis=1)

    def discriminativeness(self, s, probs):
        """Posterior-weighted separation of class signatures, train-only."""
        _, _, mu, var = self.params[s]
        weighted = (mu * probs[:, None]).sum(axis=0)
        between = (probs[:, None] * (mu - weighted) ** 2).sum(axis=0)
        within = (probs[:, None] * var).sum(axis=0)
        return float(np.mean(between / (within + .25)))


def run_policy(model, row, policy, budget, rank, rng):
    score = model.prior.copy()
    remaining = set(model.sensors)
    chosen = []
    preds = []
    for _ in range(budget):
        if policy == 'fixed':
            sensor = next(s for s in rank if s in remaining)
        elif policy == 'random':
            sensor = rng.choice(sorted(remaining))
        elif policy == 'adaptive':
            probs = posterior(score)
            sensor = max(sorted(remaining),
                         key=lambda s: model.discriminativeness(s, probs))
        else:
            raise ValueError(policy)
        chosen.append(sensor)
        remaining.remove(sensor)
        score += model.evidence(row, sensor)
        preds.append(int(model.classes[np.argmax(score)]))
    return chosen, preds


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dataset', type=Path, default=Path('../3W/dataset'))
    ap.add_argument('--seconds', type=int, default=600)
    ap.add_argument('--splits', type=int, default=10)
    ap.add_argument('--budget', type=int, default=5)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--out', type=Path, default=Path('active_results.csv'))
    args = ap.parse_args()
    data, sensors = dataset_rows(args.dataset, args.seconds)
    if args.budget < 1 or args.budget > len(sensors):
        ap.error(f'--budget must be between 1 and {len(sensors)}')
    print(f'Incidents: {len(data)}, distinct wells: {data.well.nunique()}')
    print('Class distribution:', dict(sorted(Counter(data.event).items())))
    print('NOTE: labels locate transient onset; this is NOT real-time onset detection.')
    print('NOTE: no missingness features used; missing readings provide zero evidence.')
    print('NOTE: Gaussian evidence model is a diagnostic benchmark, not calibrated production inference.')
    # Reject splits with test classes unseen in train. Different well-level test
    # samples may still overlap across splits; not a confidence interval.
    candidates = GroupShuffleSplit(n_splits=max(args.splits * 100, 200),
                                   test_size=.25, random_state=args.seed)
    accepted = []
    seen = set()
    for tr, te in candidates.split(data, data.event, groups=data.well):
        train, test = data.iloc[tr], data.iloc[te]
        if not set(test.event).issubset(set(train.event)):
            continue
        key = tuple(sorted(test.well.unique()))
        if key in seen:
            continue
        seen.add(key)
        accepted.append((tr, te))
        if len(accepted) >= args.splits:
            break
    if not accepted:
        raise RuntimeError('No split with full test-class coverage; consider restricting rare classes.')
    if len(accepted) < args.splits:
        print(f'WARNING: only {len(accepted)} valid splits found.')
    rows, examples = [], []
    for split_idx, (tr, te) in enumerate(accepted, 1):
        train, test = data.iloc[tr], data.iloc[te]
        m = SensorEvidence().fit(train, sensors)
        ranking = sorted(sensors, key=lambda s: (-m.separation[s], s))
        if split_idx == 1:
            print(f'First split train/test: {len(train)}/{len(test)} incidents, '
                  f'{train.well.nunique()}/{test.well.nunique()} wells')
            print('Classes train/test:', sorted(train.event.unique()), sorted(test.event.unique()))
            print('Top-ranked training sensors:', ranking[:10])
        for incident_idx, (_, incident) in enumerate(test.iterrows()):
            y = int(incident.event)
            for policy in ('random', 'fixed', 'adaptive'):
                rng = np.random.RandomState(args.seed + split_idx * 100000 + incident_idx)
                chosen, preds = run_policy(m, incident, policy, args.budget, ranking, rng)
                for k, (sensor, pred) in enumerate(zip(chosen, preds), 1):
                    rows.append(dict(split=split_idx, well=incident.well,
                                     file=incident.file, true=y, policy=policy,
                                     queries=k, chosen_sensor=sensor,
                                     prediction=pred, correct=int(y == pred)))
                if split_idx == 1 and incident_idx < 3:
                    examples.append((policy, incident.file, y, chosen, preds))
    result = pd.DataFrame(rows)
    result.to_csv(args.out, index=False)
    summary = result.groupby(['policy', 'queries']).agg(
        accuracy=('correct', 'mean'), n_predictions=('correct', 'size')).reset_index()
    print('\nQUERY BUDGET CURVES (incident-weighted pooled; overlapping splits)')
    print(summary.pivot(index='queries', columns='policy', values='accuracy').round(3).to_string())
    print('\nPER-SPLIT RESULTS AT FINAL BUDGET')
    final = result[result.queries == args.budget]
    per_split = []
    for (policy, split), block in final.groupby(['policy', 'split']):
        per_split.append(dict(policy=policy, split=split,
                              accuracy=accuracy_score(block.true, block.prediction),
                              macro_f1=f1_score(block.true, block.prediction,
                                               labels=sorted(block.true.unique()),
                                               average='macro', zero_division=0),
                              n_test=len(block)))
    by_split = pd.DataFrame(per_split)
    print(by_split.groupby('policy')[['accuracy', 'macro_f1']].agg(['mean', 'std']).round(3).to_string())
    print('\nEXAMPLE QUERY TRACES (split 1, first 3 test incidents)')
    for policy, file, label, chosen, preds in examples:
        print(f'{policy:8} label={label} {Path(file).name}:')
        print(f'  sensors={chosen}; predictions={preds}')
    print('\nLIMITATIONS: Gaussian conditional independence; 3-feature sensor summarization;')
    print('no causal inference; restricted access is simulated, not physically measured cost;')
    print('splits can overlap; small class counts; window starts at known transient label.')
    print('Saved:', args.out.resolve())


if __name__ == '__main__':
    main()
