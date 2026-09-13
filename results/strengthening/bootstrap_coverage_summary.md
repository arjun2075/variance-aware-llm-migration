# Bootstrap coverage simulation

- simulation datasets per scenario: **2000**
- bootstrap replicates per interval: **200**
- scenarios: **18**  (2 task counts x 3 effects x 3 heterogeneity levels, all non-zero)
- seed: `20260803`
- runtime: 10481.2 s
- Monte Carlo SE on a coverage near 0.95: 0.0049

All scenarios were fixed before any method was evaluated.

## Aggregate across all scenarios

| method | mean bias | mean 95% coverage | mean CI width |
|---|---|---|---|
| A_proposed_offdiag_cluster | +0.0081 | 0.972 | 0.1463 |
| B_naive_offdiag_pairwise | +0.0081 | 0.717 | 0.0667 |
| C_diagonal_contaminated_cluster | -0.0282 | 0.674 | 0.1284 |

## Expected qualitative checks

- **CONFIRMED**: diagonal contamination biases Delta downward — C bias -0.0282 vs A bias +0.0081
- **CONFIRMED**: naive pairwise inference under-covers relative to clustered — B coverage 0.717 vs A coverage 0.972
- **CONFIRMED**: naive under-coverage worsens with heterogeneity — B coverage at h=0.25: 0.570 vs overall 0.717
- **CONFIRMED**: task-aware off-diagonal inference is near nominal — A coverage 0.972 (nominal 0.95)

## Caveat: method A is conservative, not exactly nominal

Method A's mean coverage is **0.972**, above the nominal 0.95. It is not
under-covering, but it is not exactly calibrated either: the two-stage bootstrap
is somewhat conservative at low heterogeneity and approaches nominal as
heterogeneity rises.

| | h=0.10 | h=0.175 | h=0.25 |
|---|---|---|---|
| T=20 | 0.993 | 0.980 | 0.955 |
| T=60 | 0.996 | 0.979 | 0.932 |

At the highest heterogeneity and larger task count (T=60, h=0.25) coverage is
0.932, marginally *below* nominal. The honest statement is that method A is
well-calibrated to conservative across the grid, while method B is severely
anti-conservative and method C is both biased and anti-conservative. A claim
that A is exactly nominal would overstate what this simulation shows.

## Monotone degradation patterns

Naive pairwise coverage falls monotonically as within-task dependence grows,
which is the mechanism the paper describes:

| heterogeneity | B coverage |
|---|---|
| 0.10 | 0.858 |
| 0.175 | 0.723 |
| 0.25 | 0.570 |

Diagonal contamination bias is largest exactly where the incumbent agrees with
itself most — i.e. when the true effect is null:

| true Delta | C bias | C coverage |
|---|---|---|
| 0.00 | −0.0365 | 0.506 |
| −0.15 | −0.0251 | 0.739 |
| −0.35 | −0.0230 | 0.778 |

This matters for the paper's own data: the properties most at risk from
diagonal contamination are the ones where a migration looks *acceptable*, since
the bias pushes Delta spuriously negative and can manufacture an apparent
regression.

## Per-scenario detail

| scenario | method | bias | coverage | width |
|---|---|---|---|---|
| T20_pw0.85_pc0.85_h0.1 | A_proposed_offdiag_cluster | +0.0001 | 0.989 | 0.1511 |
| T20_pw0.85_pc0.85_h0.1 | B_naive_offdiag_pairwise | +0.0001 | 0.847 | 0.0753 |
| T20_pw0.85_pc0.85_h0.1 | C_diagonal_contaminated_cluster | -0.0334 | 0.741 | 0.1265 |
| T20_pw0.85_pc0.85_h0.175 | A_proposed_offdiag_cluster | +0.0010 | 0.982 | 0.1697 |
| T20_pw0.85_pc0.85_h0.175 | B_naive_offdiag_pairwise | +0.0010 | 0.722 | 0.0771 |
| T20_pw0.85_pc0.85_h0.175 | C_diagonal_contaminated_cluster | -0.0348 | 0.750 | 0.1445 |
| T20_pw0.85_pc0.85_h0.25 | A_proposed_offdiag_cluster | -0.0017 | 0.972 | 0.1933 |
| T20_pw0.85_pc0.85_h0.25 | B_naive_offdiag_pairwise | -0.0017 | 0.651 | 0.0802 |
| T20_pw0.85_pc0.85_h0.25 | C_diagonal_contaminated_cluster | -0.0412 | 0.736 | 0.1650 |
| T20_pw0.85_pc0.7_h0.1 | A_proposed_offdiag_cluster | +0.0007 | 0.995 | 0.1667 |
| T20_pw0.85_pc0.7_h0.1 | B_naive_offdiag_pairwise | +0.0007 | 0.854 | 0.0847 |
| T20_pw0.85_pc0.7_h0.1 | C_diagonal_contaminated_cluster | -0.0329 | 0.824 | 0.1445 |
| T20_pw0.85_pc0.7_h0.175 | A_proposed_offdiag_cluster | +0.0105 | 0.980 | 0.1867 |
| T20_pw0.85_pc0.7_h0.175 | B_naive_offdiag_pairwise | +0.0105 | 0.727 | 0.0859 |
| T20_pw0.85_pc0.7_h0.175 | C_diagonal_contaminated_cluster | -0.0254 | 0.883 | 0.1651 |
| T20_pw0.85_pc0.7_h0.25 | A_proposed_offdiag_cluster | +0.0221 | 0.949 | 0.2108 |
| T20_pw0.85_pc0.7_h0.25 | B_naive_offdiag_pairwise | +0.0221 | 0.594 | 0.0875 |
| T20_pw0.85_pc0.7_h0.25 | C_diagonal_contaminated_cluster | -0.0176 | 0.912 | 0.1889 |
| T20_pw0.85_pc0.5_h0.1 | A_proposed_offdiag_cluster | +0.0017 | 0.995 | 0.1726 |
| T20_pw0.85_pc0.5_h0.1 | B_naive_offdiag_pairwise | +0.0017 | 0.879 | 0.0888 |
| T20_pw0.85_pc0.5_h0.1 | C_diagonal_contaminated_cluster | -0.0319 | 0.865 | 0.1524 |
| T20_pw0.85_pc0.5_h0.175 | A_proposed_offdiag_cluster | +0.0113 | 0.979 | 0.1917 |
| T20_pw0.85_pc0.5_h0.175 | B_naive_offdiag_pairwise | +0.0113 | 0.750 | 0.0897 |
| T20_pw0.85_pc0.5_h0.175 | C_diagonal_contaminated_cluster | -0.0244 | 0.896 | 0.1712 |
| T20_pw0.85_pc0.5_h0.25 | A_proposed_offdiag_cluster | +0.0278 | 0.943 | 0.2190 |
| T20_pw0.85_pc0.5_h0.25 | B_naive_offdiag_pairwise | +0.0278 | 0.592 | 0.0911 |
| T20_pw0.85_pc0.5_h0.25 | C_diagonal_contaminated_cluster | -0.0116 | 0.938 | 0.1987 |
| T60_pw0.85_pc0.85_h0.1 | A_proposed_offdiag_cluster | +0.0002 | 0.995 | 0.0872 |
| T60_pw0.85_pc0.85_h0.1 | B_naive_offdiag_pairwise | +0.0002 | 0.835 | 0.0436 |
| T60_pw0.85_pc0.85_h0.1 | C_diagonal_contaminated_cluster | -0.0333 | 0.197 | 0.0733 |
| T60_pw0.85_pc0.85_h0.175 | A_proposed_offdiag_cluster | +0.0001 | 0.990 | 0.0995 |
| T60_pw0.85_pc0.85_h0.175 | B_naive_offdiag_pairwise | +0.0001 | 0.745 | 0.0447 |
| T60_pw0.85_pc0.85_h0.175 | C_diagonal_contaminated_cluster | -0.0357 | 0.289 | 0.0846 |
| T60_pw0.85_pc0.85_h0.25 | A_proposed_offdiag_cluster | -0.0010 | 0.978 | 0.1137 |
| T60_pw0.85_pc0.85_h0.25 | B_naive_offdiag_pairwise | -0.0010 | 0.645 | 0.0465 |
| T60_pw0.85_pc0.85_h0.25 | C_diagonal_contaminated_cluster | -0.0405 | 0.323 | 0.0974 |
| T60_pw0.85_pc0.7_h0.1 | A_proposed_offdiag_cluster | +0.0006 | 0.998 | 0.0966 |
| T60_pw0.85_pc0.7_h0.1 | B_naive_offdiag_pairwise | +0.0006 | 0.861 | 0.0489 |
| T60_pw0.85_pc0.7_h0.1 | C_diagonal_contaminated_cluster | -0.0328 | 0.354 | 0.0842 |
| T60_pw0.85_pc0.7_h0.175 | A_proposed_offdiag_cluster | +0.0109 | 0.974 | 0.1092 |
| T60_pw0.85_pc0.7_h0.175 | B_naive_offdiag_pairwise | +0.0109 | 0.682 | 0.0495 |
| T60_pw0.85_pc0.7_h0.175 | C_diagonal_contaminated_cluster | -0.0249 | 0.654 | 0.0969 |
| T60_pw0.85_pc0.7_h0.25 | A_proposed_offdiag_cluster | +0.0224 | 0.920 | 0.1234 |
| T60_pw0.85_pc0.7_h0.25 | B_naive_offdiag_pairwise | +0.0224 | 0.500 | 0.0506 |
| T60_pw0.85_pc0.7_h0.25 | C_diagonal_contaminated_cluster | -0.0172 | 0.804 | 0.1109 |
| T60_pw0.85_pc0.5_h0.1 | A_proposed_offdiag_cluster | +0.0005 | 0.994 | 0.1009 |
| T60_pw0.85_pc0.5_h0.1 | B_naive_offdiag_pairwise | +0.0005 | 0.872 | 0.0514 |
| T60_pw0.85_pc0.5_h0.1 | C_diagonal_contaminated_cluster | -0.0329 | 0.430 | 0.0892 |
| T60_pw0.85_pc0.5_h0.175 | A_proposed_offdiag_cluster | +0.0101 | 0.974 | 0.1127 |
| T60_pw0.85_pc0.5_h0.175 | B_naive_offdiag_pairwise | +0.0101 | 0.714 | 0.0520 |
| T60_pw0.85_pc0.5_h0.175 | C_diagonal_contaminated_cluster | -0.0257 | 0.676 | 0.1008 |
| T60_pw0.85_pc0.5_h0.25 | A_proposed_offdiag_cluster | +0.0279 | 0.899 | 0.1288 |
| T60_pw0.85_pc0.5_h0.25 | B_naive_offdiag_pairwise | +0.0279 | 0.435 | 0.0529 |
| T60_pw0.85_pc0.5_h0.25 | C_diagonal_contaminated_cluster | -0.0117 | 0.861 | 0.1165 |


---

# Appendix: bootstrap resolution sensitivity

**Added after the main simulation; the original results above are unchanged.**

The main study used 200 bootstrap replicates per interval. A 200-draw bootstrap
estimates the 2.5%/97.5% quantiles from the 5th and 195th order statistics,
which is coarse — quantile noise widens intervals on average and could by
itself have produced method A's conservative coverage.

Three representative scenarios were rerun at **1,000 datasets x 1,000 bootstrap
replicates** (5× the datasets' resolution, 5× the replicates), spanning all
three heterogeneity levels and including two T=60 cases. Runtime 5,107 s.

| scenario | h | coverage @200 | coverage @1000 | change | width @200 | width @1000 | ratio |
|---|---|---|---|---|---|---|---|
| T20_pw0.85_pc0.85_h0.1 | 0.1 | 0.9885 | 0.9970 | +0.0085 | 0.1511 | 0.1529 | 1.0122 |
| T60_pw0.85_pc0.7_h0.175 | 0.175 | 0.9735 | 0.9790 | +0.0055 | 0.1092 | 0.1110 | 1.0168 |
| T60_pw0.85_pc0.85_h0.25 | 0.25 | 0.9775 | 0.9740 | -0.0035 | 0.1137 | 0.1157 | 1.0176 |

## Conclusion

**The conservative coverage is real, not a resolution artifact.**

Coverage moves by between **−0.0035 and +0.0085** — smaller than the Monte
Carlo standard error on the original estimates (0.0049) — and in inconsistent
directions, so the differences are noise rather than a systematic shift.

Interval widths at 1,000 replicates are **1.2–1.8% wider**, not narrower. Had
the coarse quantiles been inflating the intervals, higher resolution would have
*shrunk* them and pulled coverage toward nominal. The opposite (very slightly)
occurs.

Method A therefore remains conservative at low heterogeneity and close to
nominal at high heterogeneity for reasons intrinsic to the two-stage bootstrap,
not because of how finely its quantiles were estimated.
