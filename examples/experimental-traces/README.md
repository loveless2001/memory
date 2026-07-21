# Real Held-Out E1FULL Certification Traces

These three examples are selected deterministically from the signed clean
certification artifact. They are real held-out certification traces,
not token-level generation logs or attention dumps.

- Verdict: **NO-SHIP**, certified depth `0`
- Policy: `still-compact-v1:t1024:depth0:sha256:c00b2437fdd813cc`
- Checkpoint weights SHA-256: `c00b2437fdd813ccdf7469eff7433ccd2b02f356766d4f7a12305441b3a46099`
- Holdout SHA-256: `64043bca6642b877af7366d4980a3bd9794184ff49e1702a4ef8a3db7398882d`
- Training manifest SHA-256: `16e3ef0e7b9062218dc4f43a7ca53821c2194884b1c0580c62da2c9fba066aff`
- Overlap audit: 0 documents, 0 items
- Source: [`plans/260719-2328-e1full-unfrozen-full-recipe/summary-e1full-clean-v1-n60.json`](../../plans/260719-2328-e1full-unfrozen-full-recipe/summary-e1full-clean-v1-n60.json)

Aggregation metrics below are document-level. Question records are the
pointwise probes stored in the signed artifact.

## 1. Pointwise Recovery

Document: `financial/00009` (financial)

Depth 1 recovers 3 prior-correct item(s) lost by matched eviction.

| Arm | Aggregation KL | Accuracy delta | Lost fact | Lost given prior correct |
|---|---:|---:|---:|---:|
| `eviction-matched` | 0.3389 | 0.0000 | 1.0000 | 1.0000 |
| `compactor-d1` | 0.0860 | -0.2000 | 0.0000 | 0.0000 |
| `compactor-d4` | 11.4444 | 0.0000 | 0.3333 | 0.3333 |
| `control-0` | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

### `mcq_financial/00009_1056_4`

What was the amount of capital expenditures made by Ameritech in 1993?

- A. $188,700,000
- B. $200,400,000
- C. $196,300,000
- D. $162,900,000

| Gold | Full context | Eviction | Depth 1 | Depth 4 | Control |
|---:|---:|---:|---:|---:|---:|
| D | D | C | D | A | D |

### `mcq_financial/00009_2194_5`

What was the amount of the reduction in intraLATA toll rates in 1990?

- A. $5,272,000
- B. $15,518,000
- C. $12,832,000
- D. $762,000

| Gold | Full context | Eviction | Depth 1 | Depth 4 | Control |
|---:|---:|---:|---:|---:|---:|
| A | A | C | A | A | A |

### `mcq_financial/00009_2229_3`

What was the amount of the reduction in Touch-Tone rates in 1992?

- A. $12,832,000
- B. $5,272,000
- C. $15,518,000
- D. $762,000

| Gold | Full context | Eviction | Depth 1 | Depth 4 | Control |
|---:|---:|---:|---:|---:|---:|
| A | A | B | A | A | A |

## 2. Axis Disagreement

Document: `code/00011` (code)

Depth 1 lowers the document lost-fact rate by 1.0000 while raising aggregation KL by 0.2265.

| Arm | Aggregation KL | Accuracy delta | Lost fact | Lost given prior correct |
|---|---:|---:|---:|---:|
| `eviction-matched` | 0.0456 | -0.5000 | 1.0000 | 1.0000 |
| `compactor-d1` | 0.2721 | 0.0000 | 0.0000 | 0.0000 |
| `compactor-d4` | 16.8795 | -0.5000 | 1.0000 | 1.0000 |
| `control-0` | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

### `mcq_code/00011_4356_0`

What is the default value of the `analysis` column in the `project` table?

- A. fastq
- B. mapping
- C. variants
- D. n/a

| Gold | Full context | Eviction | Depth 1 | Depth 4 | Control |
|---:|---:|---:|---:|---:|---:|
| C | C | D | C | D | C |

## 3. Depth-4 Collapse

Document: `financial/00002` (financial)

Depth 4 loses 2 prior-correct item(s) preserved by depth 1 while adding 15.9778 aggregation KL.

| Arm | Aggregation KL | Accuracy delta | Lost fact | Lost given prior correct |
|---|---:|---:|---:|---:|
| `eviction-matched` | 0.1624 | 0.0000 | 1.0000 | 1.0000 |
| `compactor-d1` | 0.1140 | 0.0000 | 0.0000 | 0.0000 |
| `compactor-d4` | 16.0918 | -1.0000 | 1.0000 | 1.0000 |
| `control-0` | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

### `mcq_financial/00002_471_1`

In which month was the Cartoon Network Latin America launched?

- A. January
- B. April
- C. October
- D. September

| Gold | Full context | Eviction | Depth 1 | Depth 4 | Control |
|---:|---:|---:|---:|---:|---:|
| B | B | D | B | C | B |

### `mcq_financial/00002_912_2`

How many hours of programming does the Goodwill Games provide for the Company?

- A. 96 hours
- B. 120 hours
- C. 112 hours
- D. 128 hours

| Gold | Full context | Eviction | Depth 1 | Depth 4 | Control |
|---:|---:|---:|---:|---:|---:|
| D | D | C | D | C | D |
