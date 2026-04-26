# Manual demo scenarios (run before viva)

| # | Scenario | Steps | Expected |
|---|---|---|---|
| 1 | High-risk inputs | Predict page: Bangalore→Chennai, Storm + High traffic + load 0.95 | Risk level = **High**, alternate route suggested |
| 2 | Low-risk inputs | Predict page: Mumbai→Pune, Sunny + Low traffic + load 0.4 | Risk level = **Low**, no alternate suggested |
| 3 | Direct edge missing | Predict page: Kochi→Lucknow | Warning + alternate route via hub |
| 4 | Map view sanity | Map page | At least one red edge visible after refresh |
| 5 | Kill Chennai | Simulate page: pick Chennai → Simulate | ≥4 edges lost |
| 6 | Kill Bhopal | Simulate page: pick Bhopal → Simulate | small impact (low-degree node) |
| 7 | Top hubs sanity | Analytics page | Bangalore, Hyderabad, or Chennai near the top |
| 8 | Risk histogram | Analytics page | distribution should not be all green or all red |

If scenario 5 returns 0 affected routes, your `edges.csv` doesn't include Chennai connections — fix the data, not the code.
