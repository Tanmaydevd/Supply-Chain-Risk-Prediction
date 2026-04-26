# Model evaluation report

Best model (by F1): **rf**

| model | accuracy | precision | recall | F1 | ROC-AUC |
|---|---|---|---|---|---|
| logreg | 0.680 | 0.524 | 0.136 | 0.216 | 0.654 |
| rf | 0.672 | 0.488 | 0.253 | 0.333 | 0.614 |

## Confusion matrices

### logreg
```
[[636, 40], [280, 44]]
```

### rf
```
[[590, 86], [242, 82]]
```

## Feature importances (winner)

| feature | importance |
|---|---|
| port_congestion | 0.239 |
| warehouse_load | 0.237 |
| distance_km | 0.166 |
| hist_avg_delay_hrs | 0.165 |
| vessel_delay_hrs | 0.080 |
| flight_delay_min | 0.041 |
| weather_score | 0.036 |
| traffic_score | 0.032 |
| transport_mode | 0.006 |
