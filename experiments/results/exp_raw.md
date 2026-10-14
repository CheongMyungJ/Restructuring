# Raw experiment results

## Generation

| sample/method | cost $ | wall min | sessions |
|---|---|---|---|
| s1/kitgen_v1 | 10.55 | 33.2 | 1 |
| s1/naivedoc | 2.48 | 11.3 | 1 |
| s2/kitgen_v1 | 18.53 | 47.6 | 1 |
| s2/naivedoc | 5.78 | 16.2 | 1 |
| s2/rekit_v1 | 109.68 | 328.4 | 36 |
| s2/rekit_v2_opus | 13.74 | 35.7 | 3 |
| s2/rekit_v2_sonnet | 5.01 | 23.0 | 3 |
| s2/rekit_v2_sonnet_small | 8.98 | 46.7 | 9 |
| s2/rekit_v4_balanced | 30.07 | 81.5 | 18 |
| s2/rekit_v4_max | 19.26 | 43.0 | 14 |
| s3/kitgen_v1 | 12.06 | 40.7 | 1 |
| s3/naivedoc | 3.39 | 10.5 | 1 |
| s3/rekit_v2_none | 27.56 | 84.3 | 9 |
| s3/rekit_v2_oracle | 32.06 | 115.7 | 13 |
| s4/naivedoc | 3.94 | 13.1 | 1 |
| s4/rekit_v3_none | 47.49 | 125.5 | 38 |
| s4/rekit_v3_oracle | 37.67 | 106.0 | 23 |

## Redevelopment (hidden tests)

| sample | variant | kit | rep | score | passed/total | TK-dependent | code-derivable | cost $ | wall min | audit |
|---|---|---|---|---|---|---|---|---|---|---|
| s1 | V0 | kitgen_v1 | 1 | 1.0 | 89/89 |  |  | 0.73 | 3.5 | 0 |
| s1 | V0 | kitgen_v1 | 2 | 1.0 | 89/89 |  |  | 0.9 | 4.6 | 0 |
| s1 | V1 | kitgen_v1 | 1 | 1.0 | 89/89 |  |  | 0.81 | 4.0 | 0 |
| s1 | V1 | kitgen_v1 | 2 | 1.0 | 89/89 |  |  | 1.04 | 5.4 | 0 |
| s1 | V2 | kitgen_v1 | 1 | 1.0 | 89/89 |  |  | 1.55 | 8.2 | 0 |
| s1 | V2 | kitgen_v1 | 2 | 1.0 | 89/89 |  |  | 1.55 | 6.9 | 0 |
| s1 | V3 | kitgen_v1 | 1 | 1.0 | 89/89 |  |  | 1.13 | 4.9 | 0 |
| s1 | V3 | kitgen_v1 | 2 | 1.0 | 89/89 |  |  | 0.95 | 3.6 | 0 |
| s1 | V4 | kitgen_v1 | 1 | 1.0 | 89/89 |  |  | 1.31 | 7.3 | 0 |
| s1 | V4 | kitgen_v1 | 2 | 1.0 | 89/89 |  |  | 1.13 | 6.9 | 0 |
| s3 | V0 | kitgen_v1 | 1 | 0.9241 | 134/145 | 0.732 | 1.0 | 3.91 | 30.1 | 0 |
| s3 | V0 | kitgen_v1 | 2 | 0.9241 | 134/145 | 0.732 | 1.0 | 3.19 | 23.8 | 0 |
| s3 | V1 | kitgen_v1 | 1 | 0.9241 | 134/145 | 0.732 | 1.0 | 2.09 | 17.1 | 0 |
| s3 | V1 | kitgen_v1 | 2 | 0.9241 | 134/145 | 0.732 | 1.0 | 1.85 | 11.2 | 0 |
| s3 | V3 | kitgen_v1 | 1 | 0.9034 | 131/145 | 0.732 | 0.971 | 2.63 | 19.8 | 0 |
| s3 | V3 | kitgen_v1 | 2 | 0.9241 | 134/145 | 0.732 | 1.0 | 2.26 | 17.0 | 0 |
| s3 | V3 | rekit_v2_none | 1 | 0.9241 | 134/145 | 0.732 | 1.0 | 4.17 | 25.9 | 0 |
| s3 | V3 | rekit_v2_none | 2 | 0.9241 | 134/145 | 0.732 | 1.0 | 4.32 | 27.0 | 0 |
| s3 | V3 | rekit_v2_oracle | 1 | None | None/None |  |  | 0 | 0.1 | 0 |
| s3 | V3 | rekit_v2_oracle | 2 | None | None/None |  |  | 0 | 0.1 | 0 |
| s3 | V4 | kitgen_v1 | 1 | 0.9241 | 134/145 | 0.732 | 1.0 | 3.56 | 20.1 | 0 |
| s3 | V4 | kitgen_v1 | 2 | 0.9241 | 134/145 | 0.732 | 1.0 | 4.83 | 30.5 | 0 |
| s3 | V4 | rekit_v2_oracle | 1 | None | None/None |  |  | 0 | 0.1 | 0 |
| s3 | V4 | rekit_v2_oracle | 2 | None | None/None |  |  | 0 | 0.1 | 0 |
| s3 | V5 | rekit_v2_oracle | 1 | None | None/None |  |  | 0 | 0.1 | 0 |
| s3 | V5 | rekit_v2_oracle | 2 | None | None/None |  |  | 0 | 0.1 | 0 |
| s4 | V0 | kitgen_v1 | 1 | 0.9045 | 161/178 | 0.63 | 1.0 | 5.79 | 47.8 | 0 |
| s4 | V1 | kitgen_v1 | 1 | 0.7416 | 132/178 | 0.0 | 1.0 | 2.07 | 11.3 | 0 |
| s4 | V1 | kitgen_v1 | 2 | 0.7416 | 132/178 | 0.0 | 1.0 | 1.91 | 19.1 | 0 |
| s4 | V3 | rekit_v3_none | 1 | None | None/None |  |  | 0 | 0.0 | 0 |
| s4 | V3 | rekit_v3_none | 2 | None | None/None |  |  | 0 | 0.0 | 0 |

## Mean by variant

| sample | variant | kit | n | mean score | mean cost $ | mean wall min |
|---|---|---|---|---|---|---|
| s1 | V0 | kitgen_v1 | 2 | 1.000 | 0.81 | 4.0 |
| s1 | V1 | kitgen_v1 | 2 | 1.000 | 0.93 | 4.7 |
| s1 | V2 | kitgen_v1 | 2 | 1.000 | 1.55 | 7.5 |
| s1 | V3 | kitgen_v1 | 2 | 1.000 | 1.04 | 4.2 |
| s1 | V4 | kitgen_v1 | 2 | 1.000 | 1.22 | 7.1 |
| s3 | V0 | kitgen_v1 | 2 | 0.924 | 3.55 | 27.0 |
| s3 | V1 | kitgen_v1 | 2 | 0.924 | 1.97 | 14.2 |
| s3 | V3 | kitgen_v1 | 2 | 0.914 | 2.44 | 18.4 |
| s3 | V3 | rekit_v2_none | 2 | 0.924 | 4.25 | 26.4 |
| s3 | V4 | kitgen_v1 | 2 | 0.924 | 4.20 | 25.3 |
| s4 | V0 | kitgen_v1 | 1 | 0.904 | 5.79 | 47.8 |
| s4 | V1 | kitgen_v1 | 2 | 0.742 | 1.99 | 15.2 |
