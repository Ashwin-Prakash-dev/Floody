"""
analysis/severity_model.py
---------------------------
K-Means severity clustering that combines SAR flood detection results
with OSM vulnerability factors to produce a 3-tier severity label
(LOW / MEDIUM / HIGH) per subdivision.

Feature vector per subdivision
--------------------------------
  flood_pct           – % of subdivision area flooded (from SAR)
  building_density    – OSM buildings / km²  (population proxy)
  schools_count       – OSM schools
  hospitals_count     – OSM hospitals / clinics
  road_density        – OSM road km / km²

All features are scaled to [0, 1] before clustering so no single
feature dominates due to scale differences.

The cluster with the highest combined weighted score is labelled HIGH,
the lowest is labelled LOW, and the middle is MEDIUM.

Public API
----------
    from analysis.severity_model import SeverityModel
    model = SeverityModel(n_clusters=3)
    results = model.fit_predict(flood_stats, vulnerability_df)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger(__name__)

# Feature weights used only for LABELLING clusters (not for clustering itself).
# Clustering is unsupervised — weights only determine which cluster gets
# called HIGH vs MEDIUM vs LOW after the fact.
FEATURE_WEIGHTS = {
    "flood_pct":          0.40,   # primary signal
    "building_density":   0.25,   # how many people are exposed
    "schools_count":      0.10,   # critical infrastructure
    "hospitals_count":    0.15,   # critical infrastructure
    "road_density":       0.10,   # accessibility / isolation risk
}

SEVERITY_LABELS = {2: "HIGH", 1: "MEDIUM", 0: "LOW"}
SEVERITY_COLORS = {"HIGH": "#ff6b35", "MEDIUM": "#ffaa00", "LOW": "#00c8ff"}


@dataclass
class SeverityResult:
    subdivision:       str
    district:          str
    flood_pct:         float
    flooded_ha:        float
    total_ha:          float
    building_density:  float
    schools_count:     int
    hospitals_count:   int
    road_density:      float
    severity_score:    float        # 0-1 composite score
    severity_label:    str          # LOW / MEDIUM / HIGH
    severity_color:    str          # hex color for frontend
    cluster_id:        int
    geometry:          dict


class SeverityModel:
    """
    Unsupervised K-Means severity model.

    fit_predict() takes flood stats + vulnerability factors,
    clusters subdivisions, ranks clusters by weighted score,
    and returns labelled SeverityResult objects.
    """

    def __init__(self, n_clusters: int = 3, random_state: int = 42):
        self.n_clusters   = n_clusters
        self.random_state = random_state
        self.scaler       = MinMaxScaler()
        self.kmeans       = KMeans(
            n_clusters=n_clusters,
            random_state=random_state,
            n_init=20,
            max_iter=500,
        )
        self.feature_cols = list(FEATURE_WEIGHTS.keys())
        self._fitted      = False

    def fit_predict(
        self,
        flood_stats: list[dict],
        vulnerability_df: pd.DataFrame,
    ) -> list[SeverityResult]:
        """
        Parameters
        ----------
        flood_stats      : list of subdivision dicts from flood_detector.zonal_flood_stats()
                           Must have keys: subdivision, district, flood_pct,
                           flooded_ha, total_ha, geometry
        vulnerability_df : DataFrame from vulnerability.fetch_vulnerability_factors()
                           Must have columns: subdivision, building_density,
                           schools_count, hospitals_count, road_density

        Returns
        -------
        List of SeverityResult, one per subdivision, sorted HIGH → LOW.
        """
        # ── Merge flood stats with vulnerability factors ───────────────────
        flood_df = pd.DataFrame(flood_stats)[
            ["subdivision", "district", "flood_pct", "flooded_ha", "total_ha", "geometry"]
        ]
        merged = flood_df.merge(
            vulnerability_df[["subdivision", "building_density",
                               "schools_count", "hospitals_count", "road_density"]],
            on="subdivision",
            how="left",
        )

        # Fill missing vulnerability data with zeros (subdivisions not found in OSM)
        for col in ["building_density", "schools_count", "hospitals_count", "road_density"]:
            merged[col] = merged[col].fillna(0)

        logger.info(
            "Severity model: %d subdivisions, %d with OSM data",
            len(merged),
            merged["building_density"].gt(0).sum(),
        )

        # ── Build feature matrix ───────────────────────────────────────────
        X_raw = merged[self.feature_cols].values.astype(float)

        # Handle edge case: all zeros in a column
        if X_raw.shape[0] < self.n_clusters:
            logger.warning(
                "Fewer subdivisions (%d) than clusters (%d) — reducing k",
                X_raw.shape[0], self.n_clusters,
            )
            self.n_clusters = X_raw.shape[0]
            self.kmeans = KMeans(n_clusters=self.n_clusters, random_state=self.random_state, n_init=10)

        X_scaled = self.scaler.fit_transform(X_raw)

        # ── Cluster ────────────────────────────────────────────────────────
        cluster_ids = self.kmeans.fit_predict(X_scaled)
        merged["cluster_id"] = cluster_ids
        self._fitted = True

        # ── Rank clusters by weighted score ───────────────────────────────
        # For each cluster, compute the mean weighted score across its members
        weights = np.array([FEATURE_WEIGHTS[c] for c in self.feature_cols])
        scores  = (X_scaled * weights).sum(axis=1)   # per-subdivision score
        merged["severity_score"] = scores

        cluster_means = (
            merged.groupby("cluster_id")["severity_score"].mean().sort_values()
        )
        # Map: lowest mean score → rank 0 (LOW), highest → rank 2 (HIGH)
        rank_map = {cid: rank for rank, cid in enumerate(cluster_means.index)}
        merged["severity_rank"]  = merged["cluster_id"].map(rank_map)
        merged["severity_label"] = merged["severity_rank"].map(SEVERITY_LABELS)
        merged["severity_color"] = merged["severity_label"].map(SEVERITY_COLORS)

        # Normalise severity_score to [0, 1]
        s_min, s_max = scores.min(), scores.max()
        if s_max > s_min:
            merged["severity_score"] = (scores - s_min) / (s_max - s_min)
        else:
            merged["severity_score"] = 0.5

        # ── Log summary ───────────────────────────────────────────────────
        for label in ["HIGH", "MEDIUM", "LOW"]:
            subset = merged[merged["severity_label"] == label]
            logger.info(
                "  %s: %d subdivisions  avg flood=%.1f%%  avg score=%.3f",
                label,
                len(subset),
                subset["flood_pct"].mean() if len(subset) else 0,
                subset["severity_score"].mean() if len(subset) else 0,
            )

        # ── Build results ──────────────────────────────────────────────────
        results = []
        for _, row in merged.iterrows():
            results.append(SeverityResult(
                subdivision=      row["subdivision"],
                district=         row["district"],
                flood_pct=        round(float(row["flood_pct"]),    2),
                flooded_ha=       round(float(row["flooded_ha"]),   2),
                total_ha=         round(float(row["total_ha"]),     2),
                building_density= round(float(row["building_density"]), 2),
                schools_count=    int(row["schools_count"]),
                hospitals_count=  int(row["hospitals_count"]),
                road_density=     round(float(row["road_density"]),  3),
                severity_score=   round(float(row["severity_score"]), 4),
                severity_label=   row["severity_label"],
                severity_color=   row["severity_color"],
                cluster_id=       int(row["cluster_id"]),
                geometry=         row["geometry"],
            ))

        results.sort(key=lambda r: r.severity_score, reverse=True)
        return results

    def feature_importance(self) -> dict:
        """Return the weight assigned to each feature."""
        return dict(FEATURE_WEIGHTS)

    def cluster_summary(self, results: list[SeverityResult]) -> dict:
        """Return per-cluster summary statistics."""
        from collections import defaultdict
        groups = defaultdict(list)
        for r in results:
            groups[r.severity_label].append(r)
        summary = {}
        for label, items in groups.items():
            summary[label] = {
                "count":            len(items),
                "avg_flood_pct":    round(np.mean([i.flood_pct    for i in items]), 2),
                "avg_bld_density":  round(np.mean([i.building_density for i in items]), 2),
                "avg_schools":      round(np.mean([i.schools_count for i in items]), 2),
                "avg_hospitals":    round(np.mean([i.hospitals_count for i in items]), 2),
                "avg_road_density": round(np.mean([i.road_density  for i in items]), 3),
            }
        return summary
