# Raw experiment results

## Generation

| sample/method | cost $ | wall min | sessions |
|---|---|---|---|
| s1/kitgen_v1 | 10.55 | 33.2 | 1 |
| s1/naivedoc | 2.48 | 11.3 | 1 |
| s2/kitgen_v1 | 18.53 | 47.6 | 1 |
| s2/naivedoc | 5.78 | 16.2 | 1 |
| s2/rekit_v1 | 44.53 | 128.6 | 12 |
| s3/rekit_v2_none | 0 | 0.0 | 0 |
| s3/rekit_v2_oracle | 0.07 | 0.2 | 1 |

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

## Mean by variant

| sample | variant | kit | n | mean score | mean cost $ | mean wall min |
|---|---|---|---|---|---|---|
| s1 | V0 | kitgen_v1 | 2 | 1.000 | 0.81 | 4.0 |
| s1 | V1 | kitgen_v1 | 2 | 1.000 | 0.93 | 4.7 |
| s1 | V2 | kitgen_v1 | 2 | 1.000 | 1.55 | 7.5 |
| s1 | V3 | kitgen_v1 | 2 | 1.000 | 1.04 | 4.2 |
| s1 | V4 | kitgen_v1 | 2 | 1.000 | 1.22 | 7.1 |
