# DTD Cross-Family Transfer Matrix (TODO-35)

Families: 15 · pairs: 105

## Lane decision

- Near-duplicate pairs (Jaccard ≥ 0.5): **7**
- Moderate-overlap pairs (0.15 ≤ Jaccard < 0.5): **6**
- Low-overlap pairs (Jaccard < 0.15): **92**

unified lanes for near-duplicate pairs (Jaccard >= 0.5); per-family or family-tagged lanes for moderate-overlap pairs (0.15 <= Jaccard < 0.5), where cross-family discrimination (T10) is the binding constraint; independent lanes for low-overlap pairs (Jaccard < 0.15).

## Top 25 pairs by combined Jaccard

| A | B | Jaccard | A-in-B | B-in-A | elements | attributes | entities | notations |
|---|---|---|---|---|---|---|---|---|
| mathml | xhtml11 | 0.861 | 0.906 | 0.946 | 0.717 | 0.359 | 0.931 | 1.000 |
| JATS-DTDs | mathml | 0.743 | 0.792 | 0.922 | 0.327 | 0.204 | 0.971 | 0.000 |
| org.oasis-open.dita.v1_3 | xhtml11 | 0.716 | 0.750 | 0.939 | 0.261 | 0.307 | 0.969 | 0.000 |
| mathml | org.oasis-open.dita.v1_3 | 0.677 | 0.888 | 0.740 | 0.192 | 0.358 | 0.921 | 0.000 |
| JATS-DTDs | xhtml11 | 0.665 | 0.728 | 0.885 | 0.276 | 0.066 | 0.930 | 0.000 |
| JATS-DTDs | org.oasis-open.dita.v1_3 | 0.595 | 0.757 | 0.735 | 0.184 | 0.143 | 0.912 | 0.000 |
| daisy | xhtml | 0.508 | 0.581 | 0.801 | 0.231 | 0.086 | 1.000 | 0.000 |
| org.dita.specialization.dita11 | org.oasis-open.dita.v1_2 | 0.482 | 0.809 | 0.543 | 0.544 | 0.259 | 0.294 | 0.000 |
| docbook | mathml | 0.295 | 0.596 | 0.368 | 0.001 | 0.049 | 0.431 | 0.000 |
| JATS-DTDs | docbook | 0.280 | 0.335 | 0.631 | 0.048 | 0.074 | 0.429 | 0.026 |
| docbook | xhtml11 | 0.253 | 0.514 | 0.332 | 0.000 | 0.051 | 0.373 | 0.000 |
| docbook | org.oasis-open.dita.v1_3 | 0.232 | 0.554 | 0.285 | 0.043 | 0.053 | 0.365 | 0.000 |
| org.oasis-open.dita.v1_2 | org.oasis-open.dita.v1_3 | 0.183 | 0.953 | 0.185 | 0.582 | 0.156 | 0.016 | 0.000 |
| docbook | xhtml | 0.143 | 0.155 | 0.662 | 0.038 | 0.042 | 0.216 | 0.000 |
| daisy | docbook | 0.143 | 0.513 | 0.165 | 0.045 | 0.065 | 0.216 | 0.000 |
| org.dita.specialization.dita11 | org.oasis-open.xdita.v0_2_2 | 0.115 | 0.120 | 0.729 | 0.126 | 0.081 | 0.077 | 0.000 |
| xhtml | xhtml11 | 0.105 | 0.725 | 0.109 | 0.000 | 0.165 | 0.120 | 0.000 |
| mathml | xhtml | 0.103 | 0.107 | 0.741 | 0.000 | 0.165 | 0.112 | 0.000 |
| org.dita.specialization.dita11 | org.oasis-open.dita.v1_3 | 0.101 | 0.793 | 0.103 | 0.316 | 0.107 | 0.005 | 0.000 |
| daisy | xhtml11 | 0.098 | 0.517 | 0.107 | 0.000 | 0.064 | 0.120 | 0.000 |
| daisy | mathml | 0.096 | 0.526 | 0.105 | 0.000 | 0.074 | 0.112 | 0.000 |
| org.oasis-open.dita.v1_3 | xhtml | 0.088 | 0.091 | 0.756 | 0.030 | 0.038 | 0.116 | 0.000 |
| daisy | org.oasis-open.dita.v1_3 | 0.082 | 0.533 | 0.088 | 0.022 | 0.029 | 0.116 | 0.000 |
| JATS-DTDs | daisy | 0.080 | 0.086 | 0.505 | 0.018 | 0.048 | 0.100 | 0.000 |
| JATS-DTDs | xhtml | 0.077 | 0.080 | 0.649 | 0.019 | 0.025 | 0.100 | 0.000 |

## Findings

1. **Transfer is kind-specific.** DITA v1.2 → v1.3 elements transfer at 0.998 containment (534/535), but entities do not (34 vs 2174): version pairs share structure, not entity vocabulary.
2. **High overlap is mostly module inclusion.** xhtml11 embeds MathML (mathml|xhtml11 Jaccard 0.861). The near-duplicate band is inclusion, not coincidence.
3. **The moderate band is where T10 binds.** JATS↔DocBook (0.280), DocBook↔DITA v1.3 (0.232), DITA v1.2↔DITA v1.3 (0.183): shared vocabulary exists, but each side has substantial unique structure — exactly the cross-family discrimination failure T10 measures.
4. **Most pairs are independent** (92/105 below 0.15): no transfer, no discrimination risk.


## Full pair table

| A | B | Jaccard | A-in-B | B-in-A |
|---|---|---|---|---|
| mathml | xhtml11 | 0.861 | 0.906 | 0.946 |
| JATS-DTDs | mathml | 0.743 | 0.792 | 0.922 |
| org.oasis-open.dita.v1_3 | xhtml11 | 0.716 | 0.750 | 0.939 |
| mathml | org.oasis-open.dita.v1_3 | 0.677 | 0.888 | 0.740 |
| JATS-DTDs | xhtml11 | 0.665 | 0.728 | 0.885 |
| JATS-DTDs | org.oasis-open.dita.v1_3 | 0.595 | 0.757 | 0.735 |
| daisy | xhtml | 0.508 | 0.581 | 0.801 |
| org.dita.specialization.dita11 | org.oasis-open.dita.v1_2 | 0.482 | 0.809 | 0.543 |
| docbook | mathml | 0.295 | 0.596 | 0.368 |
| JATS-DTDs | docbook | 0.280 | 0.335 | 0.631 |
| docbook | xhtml11 | 0.253 | 0.514 | 0.332 |
| docbook | org.oasis-open.dita.v1_3 | 0.232 | 0.554 | 0.285 |
| org.oasis-open.dita.v1_2 | org.oasis-open.dita.v1_3 | 0.183 | 0.953 | 0.185 |
| docbook | xhtml | 0.143 | 0.155 | 0.662 |
| daisy | docbook | 0.143 | 0.513 | 0.165 |
| org.dita.specialization.dita11 | org.oasis-open.xdita.v0_2_2 | 0.115 | 0.120 | 0.729 |
| xhtml | xhtml11 | 0.105 | 0.725 | 0.109 |
| mathml | xhtml | 0.103 | 0.107 | 0.741 |
| org.dita.specialization.dita11 | org.oasis-open.dita.v1_3 | 0.101 | 0.793 | 0.103 |
| daisy | xhtml11 | 0.098 | 0.517 | 0.107 |
| daisy | mathml | 0.096 | 0.526 | 0.105 |
| org.oasis-open.dita.v1_3 | xhtml | 0.088 | 0.091 | 0.756 |
| daisy | org.oasis-open.dita.v1_3 | 0.082 | 0.533 | 0.088 |
| JATS-DTDs | daisy | 0.080 | 0.086 | 0.505 |
| JATS-DTDs | xhtml | 0.077 | 0.080 | 0.649 |
| org.oasis-open.dita.v1_2 | org.oasis-open.xdita.v0_2_2 | 0.065 | 0.068 | 0.614 |
| org.dita.specialization.dita11 | xhtml | 0.061 | 0.111 | 0.120 |
| svg | xhtml11 | 0.058 | 0.653 | 0.060 |
| daisy | dtds | 0.055 | 0.077 | 0.161 |
| docbook | org.dita.specialization.dita11 | 0.055 | 0.065 | 0.259 |
| org.oasis-open.xdita.v0_2_2 | xhtml | 0.055 | 0.343 | 0.061 |
| (root) | dtds | 0.051 | 0.116 | 0.084 |
| org.oasis-open.dita.v1_3 | svg | 0.048 | 0.049 | 0.665 |
| dtds | org.dita.specialization.dita11 | 0.043 | 0.107 | 0.066 |
| daisy | org.dita.specialization.dita11 | 0.041 | 0.070 | 0.089 |
| (root) | org.oasis-open.xdita.v0_2_2 | 0.040 | 0.053 | 0.143 |
| docbook | org.oasis-open.dita.v1_2 | 0.040 | 0.053 | 0.141 |
| dtds | org.oasis-open.xdita.v0_2_2 | 0.038 | 0.046 | 0.171 |
| org.oasis-open.dita.v1_2 | xhtml | 0.035 | 0.055 | 0.089 |
| daisy | org.oasis-open.xdita.v0_2_2 | 0.034 | 0.037 | 0.286 |
| docbook | tei | 0.033 | 0.056 | 0.076 |
| dtds | xhtml | 0.033 | 0.081 | 0.053 |
| dtds | svg | 0.033 | 0.061 | 0.067 |
| dtds | tei | 0.033 | 0.184 | 0.039 |
| daisy | tei | 0.032 | 0.102 | 0.044 |
| org.dita.specialization.dita11 | tei | 0.030 | 0.115 | 0.039 |
| tei | xhtml | 0.029 | 0.037 | 0.117 |
| (root) | org.dita.specialization.dita11 | 0.029 | 0.090 | 0.040 |
| daisy | org.oasis-open.dita.v1_2 | 0.027 | 0.057 | 0.049 |
| (root) | daisy | 0.027 | 0.101 | 0.035 |
| dtds | org.oasis-open.dita.v1_2 | 0.024 | 0.081 | 0.033 |
| docbook | dtds | 0.024 | 0.027 | 0.172 |
| org.oasis-open.xdita.v0_2_2 | svg | 0.023 | 0.100 | 0.029 |
| (root) | xhtml | 0.023 | 0.069 | 0.033 |
| JATS-DTDs | org.dita.specialization.dita11 | 0.022 | 0.024 | 0.181 |
| org.oasis-open.dita.v1_2 | tei | 0.021 | 0.062 | 0.031 |
| svg | xhtml | 0.019 | 0.050 | 0.030 |
| (root) | svg | 0.019 | 0.042 | 0.034 |
| (root) | tei | 0.018 | 0.132 | 0.020 |
| JATS-DTDs | tei | 0.017 | 0.024 | 0.060 |
| JATS-DTDs | org.oasis-open.dita.v1_2 | 0.017 | 0.020 | 0.101 |
| (root) | docbook | 0.017 | 0.164 | 0.018 |
| org.oasis-open.dita.v1_3 | tei | 0.017 | 0.022 | 0.059 |
| org.dita.specialization.dita11 | svg | 0.015 | 0.024 | 0.042 |
| org.oasis-open.dita.v1_3 | org.oasis-open.xdita.v0_2_2 | 0.015 | 0.015 | 0.686 |
| daisy | svg | 0.014 | 0.020 | 0.046 |
| svg | tei | 0.014 | 0.084 | 0.016 |
| org.oasis-open.xdita.v0_2_2 | tei | 0.013 | 0.243 | 0.014 |
| (root) | org.oasis-open.dita.v1_2 | 0.012 | 0.053 | 0.016 |
| docbook | svg | 0.011 | 0.013 | 0.088 |
| JATS-DTDs | dtds | 0.011 | 0.011 | 0.138 |
| mathml | org.dita.specialization.dita11 | 0.011 | 0.012 | 0.078 |
| docbook | org.oasis-open.xdita.v0_2_2 | 0.010 | 0.011 | 0.257 |
| dtds | org.oasis-open.dita.v1_3 | 0.010 | 0.138 | 0.011 |
| mathml | tei | 0.009 | 0.013 | 0.027 |
| tei | xhtml11 | 0.009 | 0.026 | 0.013 |
| dtds | xhtml11 | 0.008 | 0.092 | 0.009 |
| dtds | mathml | 0.008 | 0.088 | 0.008 |
| org.dita.specialization.dita11 | xhtml11 | 0.008 | 0.054 | 0.009 |
| (root) | JATS-DTDs | 0.007 | 0.127 | 0.008 |
| org.oasis-open.dita.v1_2 | svg | 0.007 | 0.009 | 0.025 |
| mathml | org.oasis-open.dita.v1_2 | 0.007 | 0.008 | 0.035 |
| mathml | org.oasis-open.xdita.v0_2_2 | 0.006 | 0.006 | 0.243 |
| JATS-DTDs | org.oasis-open.xdita.v0_2_2 | 0.006 | 0.006 | 0.271 |
| (root) | org.oasis-open.dita.v1_3 | 0.006 | 0.106 | 0.006 |
| mathml | svg | 0.005 | 0.006 | 0.067 |
| (root) | mathml | 0.005 | 0.079 | 0.005 |
| org.oasis-open.xdita.v0_2_2 | xhtml11 | 0.005 | 0.186 | 0.005 |
| (root) | xhtml11 | 0.005 | 0.069 | 0.005 |
| org.oasis-open.dita.v1_2 | xhtml11 | 0.005 | 0.024 | 0.006 |
| JATS-DTDs | svg | 0.004 | 0.004 | 0.050 |
| office | svg | 0.003 | 0.004 | 0.017 |
| (root) | office | 0.002 | 0.011 | 0.002 |
| office | org.dita.specialization.dita11 | 0.002 | 0.002 | 0.005 |
| office | org.oasis-open.dita.v1_2 | 0.001 | 0.002 | 0.003 |
| office | org.oasis-open.xdita.v0_2_2 | 0.001 | 0.001 | 0.014 |
| dtds | office | 0.001 | 0.004 | 0.001 |
| office | xhtml11 | 0.001 | 0.002 | 0.001 |
| JATS-DTDs | office | 0.001 | 0.001 | 0.002 |
| mathml | office | 0.001 | 0.001 | 0.002 |
| office | org.oasis-open.dita.v1_3 | 0.001 | 0.002 | 0.001 |
| daisy | office | 0.000 | 0.000 | 0.000 |
| docbook | office | 0.000 | 0.000 | 0.000 |
| office | tei | 0.000 | 0.000 | 0.000 |
| office | xhtml | 0.000 | 0.000 | 0.000 |
