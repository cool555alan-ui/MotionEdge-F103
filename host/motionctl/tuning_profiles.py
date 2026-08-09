"""Central Phase 8 candidates, score weights, and immutable acceptance thresholds."""

LOW_PASS_ALPHA_CANDIDATES=(0.05,0.10,0.15,0.20,0.30,0.40,0.50)
GYRO_WEIGHT_CANDIDATES=(0.90,0.95,0.97,0.98,0.985,0.99)
SCORE_WEIGHTS={"static_mae":0.25,"noise_stddev":0.18,"peak_to_peak":0.12,
               "dynamic_lag":0.15,"overshoot":0.08,"drift":0.12,"cross_axis":0.10}
THRESHOLDS={"static_mae_pass_deg":1.5,"static_max_pass_deg":3.0,"static_r2_pass":0.995,
            "noise_stddev_pass_deg":0.5,"noise_peak_to_peak_pass_deg":3.0,
            "drift_total_pass_deg":2.0,"drift_slope_pass_deg_per_min":0.10}

if abs(sum(SCORE_WEIGHTS.values())-1.0)>1e-12:
    raise RuntimeError("Phase 8 tuning weights must sum to one")
