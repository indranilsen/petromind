"""First-10-minute transient fault classification baseline for Petrobras 3W.

Example:
    python first10.py --dataset ../3W/dataset

Uses real WELL-* incidents only, keeps entire wells in either train or test,
and never uses class/state as model features. This evaluates diagnosis after
KNOWN labeled transient onset, not online onset detection.
"""
from pathlib import Path
import argparse
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline

SENSORS_3 = ["P-PDG", "P-TPT", "T-TPT"]
SENSORS_5 = SENSORS_3 + ["P-MON-CKP", "T-PDG"]
STATS = ("missing", "median", "std", "change")
# Guardrail for invalid/out-of-range engineered features, not a physical sensor bound.
MAX_ABS_FEATURE = 1e15


def stable_std(values):
    """Scale before computing standard deviation to avoid squaring huge values."""
    if not len(values):
        return np.nan
    scale = np.max(np.abs(values))
    if scale == 0:
        return 0.0
    return float(np.std(values / scale) * scale)


def get_features(frame, sensors):
    result = {}
    for sensor in sensors:
        if sensor not in frame:
            values = np.full(len(frame), np.nan)
        else:
            values = pd.to_numeric(frame[sensor], errors="coerce").to_numpy(dtype=np.float64)
        valid = values[np.isfinite(values)]
        result[f"{sensor}_missing"] = 1.0 - len(valid) / len(values)
        result[f"{sensor}_median"] = float(np.median(valid)) if len(valid) else np.nan
        result[f"{sensor}_std"] = stable_std(valid)
        midpoint = len(values) // 2
        first = values[:midpoint]
        second = values[midpoint:]
        a, b = first[np.isfinite(first)], second[np.isfinite(second)]
        result[f"{sensor}_change"] = float(np.median(b) - np.median(a)) if len(a) and len(b) else np.nan
    return result


def clean_features(df, columns, name):
    X = df.reindex(columns=columns).astype(np.float64).copy()
    array = X.to_numpy()
    invalid = (~np.isfinite(array) & ~np.isnan(array)) | (np.abs(array) > MAX_ABS_FEATURE)
    if invalid.any():
        print(f"  {name}: masked {int(invalid.sum())} infinite/extreme feature values")
        for r, c in zip(*np.where(invalid)[:2]):
            print(f"    {df.iloc[r]['file']} | {columns[c]} | {array[r, c]}")
        X = X.mask(~np.isfinite(X) | (X.abs() > MAX_ABS_FEATURE))
    return X


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="../3W/dataset")
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.seconds < 2:
        parser.error("--seconds must be at least 2")

    root = Path(args.dataset)
    paths = sorted(root.rglob("WELL-*.parquet"))
    if not paths:
        raise SystemExit(f"No real WELL-*.parquet files found under {root}")

    rows = []
    all_sensors = set()
    for path in paths:
        if not path.parent.name.isdigit() or int(path.parent.name) not in range(1, 10):
            continue
        frame = pd.read_parquet(path)
        if "class" not in frame or len(frame) == 0:
            continue
        event = int(path.parent.name)
        labels = frame["class"].astype("Int64")
        transient = 100 + event
        positions = np.flatnonzero(labels.eq(transient).fillna(False).to_numpy(dtype=bool))
        if len(positions) == 0:
            continue
        start = int(positions[0])
        if start + args.seconds > len(frame):
            continue
        if not labels.iloc[start:start + args.seconds].eq(transient).fillna(False).all():
            continue
        window = frame.iloc[start:start + args.seconds]
        sensors = [c for c in frame.columns if c not in ("class", "state")]
        all_sensors.update(sensors)
        row = get_features(window, sensors)
        row["event"] = event
        row["well"] = path.name.split("_")[0]
        row["file"] = str(path)
        rows.append(row)

    data = pd.DataFrame(rows)
    if len(data) < 10:
        raise SystemExit(f"Too few eligible real transient incidents: {len(data)}")
    print(f"Eligible real transient incidents: {len(data)}")
    print("Counts by class:", data.event.value_counts().sort_index().to_dict())
    print("Distinct wells:", data.well.nunique())

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=args.seed)
    tr, te = next(splitter.split(data, data.event, groups=data.well))
    train, test = data.iloc[tr], data.iloc[te]
    print(f"Training: {len(train)} incidents / {train.well.nunique()} wells")
    print(f"Testing:  {len(test)} incidents / {test.well.nunique()} wells")
    print("Train classes:", sorted(train.event.unique().tolist()))
    print("Test classes: ", sorted(test.event.unique().tolist()))
    unseen = sorted(set(test.event) - set(train.event))
    if unseen:
        print("WARNING: Test-only classes cannot be predicted by this classifier:", unseen)

    configurations = [("3 sensors", SENSORS_3), ("5 sensors", SENSORS_5),
                      ("all sensors", sorted(all_sensors))]
    for name, sensors in configurations:
        keys = [f"{sensor}_{stat}" for sensor in sensors for stat in STATS]
        X_train = clean_features(train, keys, f"{name} train")
        X_test = clean_features(test, keys, f"{name} test")
        # Train-only imputation and feature handling prevent test-set leakage.
        model = make_pipeline(
            SimpleImputer(strategy="constant", fill_value=-999.0),
            RandomForestClassifier(n_estimators=200, min_samples_leaf=2,
                                   random_state=args.seed, n_jobs=-1,
                                   class_weight="balanced_subsample"),
        )
        model.fit(X_train, train.event)
        predictions = model.predict(X_test)
        order = sorted(set(train.event) | set(test.event))
        print(f"\n--- {name} ---")
        print("Accuracy:", round(accuracy_score(test.event, predictions), 3))
        print("Macro F1:", round(f1_score(test.event, predictions, labels=order,
                                         average="macro", zero_division=0), 3))
        print(classification_report(test.event, predictions, labels=order, zero_division=0))
        print("Confusion matrix (rows=true, columns=predicted), labels:", order)
        print(confusion_matrix(test.event, predictions, labels=order))
        observed = sorted(set(test.event))
        print("Macro F1 (test-supported classes only):", round(
            f1_score(test.event, predictions, labels=observed,
                     average="macro", zero_division=0), 3))

        if name == "all sensors":
            rf = model.steps[-1][1]
            importance = pd.Series(rf.feature_importances_, index=keys).sort_values(ascending=False)
            print("\nTOP 20 MOST IMPORTANT FEATURES (RF impurity importance)")
            print(importance.head(20).to_string())
            sensor_importance = {}
            for feature, score in importance.items():
                sensor = feature.rsplit("_", 1)[0]
                sensor_importance[sensor] = sensor_importance.get(sensor, 0.0) + float(score)
            print("\nSENSOR IMPORTANCE (aggregated across engineered features)")
            for sensor, score in sorted(sensor_importance.items(), key=lambda item: -item[1]):
                print(f"{sensor:20s} {score:.4f}")
            print("NOTE: Impurity importance is descriptive, not causal, and can favor correlated/features with many split points.")


if __name__ == "__main__":
    main()
