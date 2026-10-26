"""Training-only Task 3 model selection. This module never reads December.

Selection is chronological: January-June fit, August validation. July and
November are quarantined; September-October are reserved coverage stress data.
The operational headline subset is predeclared below, not chosen on test data.
"""
import json
import platform
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from scipy.optimize import nnls
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from channel_config import ANGLE_COLUMNS, COLUMN_TO_SOURCE, MODEL_CANDIDATES, TARGET

DATA = Path("outputs/task3/data")
TABLES = Path("outputs/task3/tables")
MODELS = Path("outputs/task3/models")
TRAIN_MONTHS = list(range(1, 7))
VALIDATION_MONTHS = [8]
TRAIN_LIMIT = 120_000  # deterministic uniform temporal subset for all candidates
SEED = 4259

RESTRICTED = {"STW_kn", "SOG_kn", "HULL_HeadingTrue_deg",
              "HULL_TurnRate_degmin", "WIND_RelSpeed_kn", "WIND_RelAngle_deg"}
ENGINE = {"ME_ScavAirPressure_bar", "ME_TC_RPM_Transducer",
          "ME_FuelLoad_pct", "ME_RPM_CAMS"}
FEATURE_SETS = {
    "A_restricted_onboard": RESTRICTED,
    "B_extended_onboard": RESTRICTED | ENGINE,
    "C_exploratory_weather": set(MODEL_CANDIDATES),
}
assert len(FEATURE_SETS["A_restricted_onboard"]) == 6
assert len(FEATURE_SETS["B_extended_onboard"]) == 10
assert len(FEATURE_SETS["C_exploratory_weather"]) == 24


def columns_for(channels):
    cols = []
    for col in sorted(channels):
        if col in ANGLE_COLUMNS:
            cols += [f"sin__{col}", f"cos__{col}"]
            if COLUMN_TO_SOURCE[col] == "onboard":
                cols.append(f"resultant__{col}")
        else:
            cols.append(col)
        if COLUMN_TO_SOURCE[col] == "onboard":
            cols.append(f"n__{col}")
        else:
            cols.append(f"age_s__{col}")
    return cols


ALL_COLUMNS = sorted(set().union(*(columns_for(s) for s in FEATURE_SETS.values())))
REQUIRED = ["window_end_utc", TARGET, "target_n", "target_negative_n",
            "target_min", "STW_kn"]


def load_months(months):
    frames = []
    for m in months:
        path = DATA / f"minute_2024_{m:02d}.csv.gz"
        header = pd.read_csv(path, nrows=0).columns
        use = sorted(set(ALL_COLUMNS + REQUIRED))
        missing = set(use) - set(header)
        if missing:
            raise ValueError(f"Missing feature columns in {path}: {missing}")
        dtypes = {c: "float32" for c in use if c not in {"window_end_utc", "target_n", "target_negative_n"}}
        dtypes["target_n"] = "int16"
        dtypes["target_negative_n"] = "int16"
        frames.append(pd.read_csv(path, usecols=use, dtype=dtypes))
    return pd.concat(frames, ignore_index=True)


def label_mask(frame, broad=False):
    # Forward underway operational scope. Negative shaft readings can represent
    # reverse operation or calibration faults; neither mechanism is assumed.
    base = (frame.target_n > 0) & frame.STW_kn.ge(3) & frame[TARGET].notna()
    if broad:
        return base
    return base & frame[TARGET].gt(0) & frame.target_min.ge(0) & frame.target_negative_n.eq(0)


def metrics(y, pred):
    y = np.asarray(y, dtype=np.float64)
    pred = np.asarray(pred, dtype=np.float64)
    if len(y) != len(pred) or not np.isfinite(pred).all():
        raise ValueError("Prediction count or finiteness failure")
    # Pearson R is undefined for a constant baseline; floating-point std of a
    # repeated non-integer can be a tiny positive rounding artifact.
    pred_constant = np.ptp(pred) <= 1e-10 * max(1.0, abs(float(np.mean(pred))))
    r = float(np.corrcoef(y, pred)[0, 1]) if len(y) > 1 and not pred_constant and np.ptp(y) > 0 else np.nan
    return {"n": len(y), "mae_kw": mean_absolute_error(y, pred),
            "rmse_kw": np.sqrt(mean_squared_error(y, pred)), "pearson_r": r}


def fit_speed_cube(train):
    speed = train.STW_kn.to_numpy(dtype=np.float64)
    y = train[TARGET].to_numpy(dtype=np.float64)
    intercept, cubic = nnls(np.column_stack([np.ones(len(speed)), speed**3]), y)[0]
    # Both coefficients are fitted under nonnegative constraints on training.
    return {"intercept_kw": float(intercept), "cubic_kw_per_kn3": float(cubic)}


def speed_cube(frame, coef):
    return coef["intercept_kw"] + coef["cubic_kw_per_kn3"] * frame.STW_kn.to_numpy(dtype=np.float64)**3


def make_model(family, parameter):
    if family == "ridge":
        return make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                             StandardScaler(), Ridge(alpha=parameter))
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                         HistGradientBoostingRegressor(max_iter=120, learning_rate=0.07,
                             max_leaf_nodes=int(parameter), min_samples_leaf=80,
                             l2_regularization=1.0, random_state=SEED, early_stopping=False))


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    frozen_path = TABLES / "frozen_selection.json"
    if frozen_path.exists():
        raise FileExistsError("Frozen selection already exists; do not retune after test exposure")
    train_all = load_months(TRAIN_MONTHS)
    val_all = load_months(VALIDATION_MONTHS)
    train = train_all.loc[label_mask(train_all)].copy()
    val = val_all.loc[label_mask(val_all)].copy()
    if len(train) < 10_000 or len(val) < 1_000:
        raise ValueError("Insufficient operational-scope training or validation rows")
    if len(train) > TRAIN_LIMIT:
        train_fit = train.iloc[np.linspace(0, len(train)-1, TRAIN_LIMIT, dtype=np.int64)].copy()
    else:
        train_fit = train
    coverage = []
    for label, all_rows, selected in [("train", train_all, train), ("validation", val_all, val)]:
        broad = int(label_mask(all_rows, broad=True).sum())
        coverage.append({"split": label, "completed_minutes": len(all_rows),
                         "target_minutes": int((all_rows.target_n > 0).sum()),
                         "forward_with_target": broad, "headline_minutes": len(selected),
                         "headline_pct_of_forward": 100 * len(selected) / broad if broad else np.nan})
    pd.DataFrame(coverage).to_csv(TABLES / "label_scope_train_validation.csv", index=False)
    y_fit = train_fit[TARGET].to_numpy(dtype=np.float32)
    y_val = val[TARGET].to_numpy(dtype=np.float32)
    rows = []
    mean_kw = float(np.mean(y_fit, dtype=np.float64))
    cube = fit_speed_cube(train_fit)
    for name, pred in [("training_mean", np.full(len(val), mean_kw)),
                       ("speed_cubic", speed_cube(val, cube))]:
        rows.append({"feature_set": "baseline", "family": name, "parameter": "train_only",
                     "fit_n": len(train_fit), "fit_seconds": 0.0, **metrics(y_val, pred)})
    best = None
    for set_name, channels in FEATURE_SETS.items():
        cols = columns_for(channels)
        x_fit = train_fit[cols].to_numpy(dtype=np.float32)
        x_val = val[cols].to_numpy(dtype=np.float32)
        for family, parameters in [("ridge", [10.0, 100.0]), ("histgb", [15, 31])]:
            for parameter in parameters:
                model = make_model(family, parameter)
                started = time.perf_counter()
                model.fit(x_fit, y_fit)
                fit_seconds = round(time.perf_counter() - started, 2)
                pred = model.predict(x_val)
                score = metrics(y_val, pred)
                record = {"feature_set": set_name, "family": family,
                          "parameter": parameter, "fit_n": len(train_fit),
                          "fit_seconds": fit_seconds, **score}
                rows.append(record)
                print(record, flush=True)
                if best is None or score["mae_kw"] < best["score"]:
                    best = {"score": score["mae_kw"], "feature_set": set_name,
                            "family": family, "parameter": parameter, "columns": cols}
    comparison = pd.DataFrame(rows).sort_values(["mae_kw", "rmse_kw"])
    comparison.to_csv(TABLES / "validation_model_comparison.csv", index=False)
    # Freeze selection and all scientific rules before the December file is read.
    frozen = {"selected": best, "train_months": TRAIN_MONTHS,
              "validation_months": VALIDATION_MONTHS, "test_months": [12],
              "quarantine_months": [7, 11], "coverage_stress_months": [9, 10],
              "operational_rule": "target_n>0; STW_kn>=3; target mean>0; target_min>=0; no negative target reading in minute",
              "broader_rule": "target_n>0; STW_kn>=3 (includes zero/negative labels)",
              "max_selection_fit_rows": TRAIN_LIMIT, "selection_sampling": "uniform chronological index",
              "mean_baseline_kw": float(np.mean(train[TARGET].to_numpy(dtype=np.float64))),
              "speed_cube": fit_speed_cube(train),
              "persistence": "nondeployable: prior trustworthy power availability not established",
              "external_weather": "exploratory: raw timestamp may be validity rather than issue time",
              "software": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                           "pandas": pd.__version__, "numpy": np.__version__}}
    frozen_path.write_text(json.dumps(frozen, indent=2), encoding="utf-8")
    final = make_model(best["family"], best["parameter"])
    started = time.perf_counter()
    final.fit(train[best["columns"]].to_numpy(dtype=np.float32), train[TARGET].to_numpy(dtype=np.float32))
    frozen["final_fit_n"] = len(train)
    frozen["final_fit_seconds"] = round(time.perf_counter() - started, 2)
    frozen_path.write_text(json.dumps(frozen, indent=2), encoding="utf-8")
    joblib.dump({"pipeline": final, "columns": best["columns"], "frozen": frozen},
                MODELS / "selected_pipeline.joblib", compress=3)
    selected_pred = final.predict(val[best["columns"]].to_numpy(dtype=np.float32))
    pd.DataFrame({"window_end_utc": val.window_end_utc, "actual_kw": y_val,
                  "predicted_kw": selected_pred}).to_csv(TABLES / "validation_selected_predictions.csv", index=False)
    print("FROZEN", best, "final_fit_n", len(train), flush=True)


if __name__ == "__main__":
    main()
