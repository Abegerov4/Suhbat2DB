### Experiment 1. Baseline vs agent

| Set | Difficulty | n | Baseline EX, % | Agent EX, % | Agent relaxed EX, % |
|---|---|---|---|---|---|
| spider_subset | easy | 25 | 88.0 | 84.0 | 92.0 |
| spider_subset | extra | 25 | 56.0 | 40.0 | 60.0 |
| spider_subset | hard | 25 | 52.0 | 52.0 | 60.0 |
| spider_subset | medium | 25 | 92.0 | 76.0 | 88.0 |
| **spider_subset** | **total** | **100** | **72.0** [63.0; 81.0] | **63.0** [53.0; 72.0] | 75.0 |
| bird_subset | challenging | 20 | 45.0 | 45.0 | 60.0 |
| bird_subset | moderate | 20 | 40.0 | 35.0 | 55.0 |
| bird_subset | simple | 20 | 40.0 | 35.0 | 40.0 |
| **bird_subset** | **total** | **60** | **41.7** [30.0; 55.0] | **38.3** [26.7; 51.7] | 51.7 |

| Set | EX difference (agent − baseline), pp | 95% CI | Agent better / worse | p (McNemar) |
|---|---|---|---|---|
| spider_subset | -9.0 | [-15.0; -3.0] | 1 / 10 | 0.012 |
| bird_subset | -3.3 | [-8.3; +0.0] | 0 / 2 | 0.500 |

### Agent: self-correction, table selection, cost

| Set | First-attempt EX, % | Final EX, % | Self-correction gain, pp | Schema recall | All tables found, % | $ / question | p50, s | p95, s |
|---|---|---|---|---|---|---|---|---|
| spider_subset | 63.0 | 63.0 | +0.0 | 0.9949 | 99.0 | 0.0077 | None | None |
| bird_subset | 38.3 | 38.3 | +0.0 | 0.9569 | 90.0 | 0.0118 | None | None |
| ambiguous_ru | 77.4 | 77.4 | +0.0 | 0.9835 | 93.4 | 0.0121 | None | None |
| spider_subset (baseline) | — | 72.0 | — | — | — | 0.0030 | 1.34 | 1.86 |
| bird_subset (baseline) | — | 41.7 | — | — | — | 0.0045 | 1.56 | 2.9 |

### Experiment 2. Ambiguity clarification

| Metric | Without clarification | With clarification |
|---|---|---|
| EX on ambiguous, % | 40.3 [29.0; 53.2] | 67.7 [54.8; 79.0] |
| EX on clear, % | 93.2 | 90.9 |
| EX on the whole set, % | 62.3 | 77.4 |
| Ambiguity detection precision / recall / F1 | — | 0.89 / 0.63 / 0.74 |
| Unnecessary clarifications (over-clarification), % | — | 11.4 |
| $ / question | 0.0049 | 0.0121 |

On ambiguous questions (n = 62): EX difference +27.4 pp, 95% CI [+14.5; +38.7], clarification fixed 19 answers and broke 2, p (McNemar) = < 0.001.

### Security

| Level | Attacks | Blocked, % | False blocks, % |
|---|---|---|---|
| Agent: natural-language questions | 46 | 100.0 | 10.0 (of 30) |
| Validator: SQL attacks | 88 | 100.0 | 0.0 |

| Attack class | Blocked, % |
|---|---|
| exfiltration | 100.0 |
| injection | 100.0 |
| modify | 100.0 |

| Attack language | Blocked, % |
|---|---|
| en | 100.0 |
| kk | 100.0 |
| mixed | 100.0 |
| ru | 100.0 |

Indirect injections through data: resisted 83.3% (n = 6); heavy queries contained by limits: 100.0% (n = 4); SQL attempts violating the read-only policy: 0 (all stopped at level 2).
Missed: []; falsely blocked: ['q_benign_05', 'q_benign_07', 'q_benign_25'].
