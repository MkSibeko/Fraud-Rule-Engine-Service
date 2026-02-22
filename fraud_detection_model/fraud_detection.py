import pickle
from pathlib import Path

import numpy as np
import polars as pl

from imblearn.over_sampling import SMOTE
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier


def load_data(csv_path: str) -> pl.DataFrame:
    df = pl.read_csv(csv_path)
    print("Data sample:")
    print(df.head())
    return df


def engineer_features(df: pl.DataFrame) -> tuple[pl.DataFrame, LabelEncoder]:
    df = df.with_columns(
        (pl.col("transaction_hour").is_in([0, 1, 2, 3]).cast(pl.Int64)).alias(
            "night_transaction"
        )
    )

    df = df.with_columns((pl.col("amount") > 900).cast(pl.Int64).alias("high_amount"))

    label_encoder = LabelEncoder()
    df = df.with_columns(
        pl.Series(
            "merchant_category",
            label_encoder.fit_transform(df["merchant_category"].to_list()),
        )
    )
    return df, label_encoder


def prepare_data(df: pl.DataFrame):
    X = df.drop("is_fraud")
    y = df["is_fraud"].to_numpy()

    smote = SMOTE(random_state=42)
    smote_result = smote.fit_resample(X.to_numpy(), y)
    X_resampled = np.asarray(smote_result[0])
    y_resampled = np.asarray(smote_result[1])

    print("\nBalanced target distribution:")
    print(np.unique(y_resampled, return_counts=True))

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_resampled)

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y_resampled, test_size=0.2, random_state=42
    )

    return X_train, X_test, y_train, y_test, X.columns, scaler


def train_and_evaluate(X_train, X_test, y_train, y_test) -> tuple[pl.DataFrame, dict, str]:
    models = {
        "Logistic Regression": LogisticRegression(max_iter=1000),
        "Decision Tree": DecisionTreeClassifier(random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
        "XGBoost": XGBClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric="logloss",
        ),
    }

    results = []
    fitted_models = {}

    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        fitted_models[name] = model
        results.append(
            {
                "Model": name,
                "Accuracy": accuracy_score(y_test, y_pred),
                "Precision": precision_score(y_test, y_pred),
                "Recall": recall_score(y_test, y_pred),
                "F1-Score": f1_score(y_test, y_pred),
            }
        )

    results_df = pl.DataFrame(results)
    print("\nModel comparison:")
    print(results_df)

    best_row = (
        results_df.sort(["F1-Score", "Recall", "Precision", "Accuracy"], descending=True)
        .row(0, named=True)
    )
    best_model_name = best_row["Model"]
    print(f"\nBest model selected: {best_model_name}")

    return results_df, fitted_models, best_model_name


def save_model_artifact(
    model,
    scaler: StandardScaler,
    label_encoder: LabelEncoder,
    feature_columns: list[str],
    model_name: str,
    output_path: str,
) -> None:
    artifact = {
        "model": model,
        "model_name": model_name,
        "scaler": scaler,
        "merchant_category_encoder": label_encoder,
        "feature_columns": feature_columns,
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("wb") as model_file:
        pickle.dump(artifact, model_file)

    print(f"\nSaved model artifact to: {output}")

def main() -> None:
    df = load_data("../../archive/credit_card_fraud_10k.csv")
    df, label_encoder = engineer_features(df)
    X_train, X_test, y_train, y_test, feature_names, scaler = prepare_data(df)

    _, fitted_models, best_model_name = train_and_evaluate(X_train, X_test, y_train, y_test)
    best_model = fitted_models[best_model_name]

    save_model_artifact(
        model=best_model,
        scaler=scaler,
        label_encoder=label_encoder,
        feature_columns=feature_names,
        model_name=best_model_name,
        output_path="fraud_detection_model/best_fraud_model.pkl",
    )

if __name__ == "__main__":
    main()
