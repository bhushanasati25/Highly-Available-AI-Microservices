import pytest
from fastapi.testclient import TestClient
import random
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../shared/python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from monitoring_app.main import app
from monitoring_app.drift_detector import DataDriftDetector

client = TestClient(app)


def test_identical_distributions_no_drift():
    detector = DataDriftDetector()
    random.seed(42)
    # Both drawn from N(10, 2)
    baseline = [random.gauss(10.0, 2.0) for _ in range(500)]
    current = [random.gauss(10.0, 2.0) for _ in range(500)]

    report = detector.analyze_feature_drift("embedding_l2", baseline, current)
    assert report.drift_detected is False
    assert report.drift_severity == "NONE"
    assert report.psi_score < 0.10
    assert report.ks_statistic < 0.15


def test_shifted_distribution_significant_drift():
    detector = DataDriftDetector(psi_threshold=0.25)
    random.seed(42)
    # Baseline N(0, 1) vs Current N(5, 1) -> massive shift
    baseline = [random.gauss(0.0, 1.0) for _ in range(500)]
    current = [random.gauss(5.0, 1.0) for _ in range(500)]

    report = detector.analyze_feature_drift("input_token_entropy", baseline, current)
    assert report.drift_detected is True
    assert report.drift_severity == "SIGNIFICANT"
    assert report.psi_score >= 0.25
    assert report.ks_statistic > 0.80


def test_drift_api_endpoint():
    payload = {
        "feature_name": "temperature_readings",
        "baseline": [20.0, 21.0, 22.0, 20.5, 21.5] * 20,
        "current": [35.0, 36.0, 37.0, 38.0, 39.0] * 20
    }
    resp = client.post("/drift", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["feature_name"] == "temperature_readings"
    assert data["drift_detected"] is True
    assert data["drift_severity"] == "SIGNIFICANT"
    assert "psi_score" in data
    assert "ks_statistic" in data
