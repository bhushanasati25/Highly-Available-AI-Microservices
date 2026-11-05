"""
AI Training Pipeline Data Drift & Distribution Shift Detector
Implements Population Stability Index (PSI) and two-sample Kolmogorov-Smirnov (KS)
statistic to detect covariate shifts and trigger automated retraining.
"""

import math
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class DriftReport:
    feature_name: str
    psi_score: float
    ks_statistic: float
    drift_detected: bool
    drift_severity: str  # "NONE", "MODERATE", "SIGNIFICANT"
    baseline_sample_count: int
    current_sample_count: int
    details: Dict[str, Any]


class DataDriftDetector:
    def __init__(self, psi_threshold: float = 0.25, ks_threshold: float = 0.05):
        self.psi_threshold = psi_threshold
        self.ks_threshold = ks_threshold

    def calculate_psi(
        self,
        baseline: List[float],
        current: List[float],
        num_bins: int = 10,
        epsilon: float = 1e-4
    ) -> float:
        """
        Calculate Population Stability Index (PSI):
        PSI = sum((Actual% - Expected%) * ln(Actual% / Expected%))
        """
        if not baseline or not current:
            return 0.0

        sorted_baseline = sorted(baseline)
        n_base = len(sorted_baseline)
        n_curr = len(current)

        # Compute bin edges using baseline quantiles
        bin_edges = []
        for i in range(1, num_bins):
            idx = int(n_base * (i / num_bins))
            bin_edges.append(sorted_baseline[min(idx, n_base - 1)])
        bin_edges = sorted(list(set(bin_edges)))  # deduplicate

        if not bin_edges:
            return 0.0

        # Helper to compute bin counts
        def get_bin_counts(data: List[float], edges: List[float]) -> List[int]:
            counts = [0] * (len(edges) + 1)
            for val in data:
                placed = False
                for b_idx, edge in enumerate(edges):
                    if val <= edge:
                        counts[b_idx] += 1
                        placed = True
                        break
                if not placed:
                    counts[-1] += 1
            return counts

        base_counts = get_bin_counts(baseline, bin_edges)
        curr_counts = get_bin_counts(current, bin_edges)

        psi = 0.0
        for b_cnt, c_cnt in zip(base_counts, curr_counts):
            # Proportions with Laplace smoothing
            p_base = (b_cnt / n_base) if b_cnt > 0 else epsilon
            p_curr = (c_cnt / n_curr) if c_cnt > 0 else epsilon

            psi += (p_curr - p_base) * math.log(p_curr / p_base)

        return max(0.0, float(psi))

    def calculate_ks_statistic(self, baseline: List[float], current: List[float]) -> float:
        """
        Two-sample Kolmogorov-Smirnov test statistic:
        D = sup_x |F_1(x) - F_2(x)|
        """
        if not baseline or not current:
            return 0.0

        n1 = len(baseline)
        n2 = len(current)

        # Merge and tag values
        combined = [(x, 1) for x in baseline] + [(x, 2) for x in current]
        combined.sort(key=lambda item: item[0])

        cdf1 = 0.0
        cdf2 = 0.0
        d_max = 0.0

        for val, origin in combined:
            if origin == 1:
                cdf1 += 1.0 / n1
            else:
                cdf2 += 1.0 / n2
            d_max = max(d_max, abs(cdf1 - cdf2))

        return float(d_max)

    def analyze_feature_drift(
        self,
        feature_name: str,
        baseline: List[float],
        current: List[float]
    ) -> DriftReport:
        psi = self.calculate_psi(baseline, current)
        ks = self.calculate_ks_statistic(baseline, current)

        if psi >= self.psi_threshold:
            severity = "SIGNIFICANT"
            detected = True
        elif psi >= 0.10:
            severity = "MODERATE"
            detected = False
        else:
            severity = "NONE"
            detected = False

        if detected:
            logger.warn(
                "Data drift detected in feature!",
                feature=feature_name,
                psi=round(psi, 4),
                ks=round(ks, 4),
                severity=severity
            )

        return DriftReport(
            feature_name=feature_name,
            psi_score=round(psi, 4),
            ks_statistic=round(ks, 4),
            drift_detected=detected,
            drift_severity=severity,
            baseline_sample_count=len(baseline),
            current_sample_count=len(current),
            details={
                "mean_baseline": round(sum(baseline) / len(baseline), 4) if baseline else 0.0,
                "mean_current": round(sum(current) / len(current), 4) if current else 0.0,
            }
        )


drift_detector_instance = DataDriftDetector()
