from pathlib import Path

from ml.preprocess import FEATURE_COLUMNS, prepare_training_frame


def test_prepare_training_frame_creates_expected_features(tmp_path: Path) -> None:
    data = prepare_training_frame(Path("data/raw"), tmp_path / "telemetry.csv")
    assert not data.empty
    assert set(FEATURE_COLUMNS).issubset(data.columns)
    assert {"voltage", "current", "frequency", "outage_event"}.issubset(data.columns)
    assert (tmp_path / "telemetry.csv").exists()

