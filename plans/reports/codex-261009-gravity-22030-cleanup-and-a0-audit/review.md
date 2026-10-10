# Independent cleanup receipt and returned A0 review (gravity 22030)

Cleanup receipt accepted within the user-approved A/B/C/D scope (22029).
No deletion, paid API call, model forward, launch, retry, or stop was performed by
this independent review.

## Cleanup

- Receipt's three payload hashes verify, using its own directory as the checksum base.
  The earlier B/C inventory bundle and all eleven Stage A package hashes also verify.
- All **12,591** receipt paths are absent and untracked; paths are unique and confined
  to the approved groups. B and C match every path, size and hash of the independent
  predeletion manifests exactly. A is confined to gen-*.pt under the closed P2.5
  plan; D is confined to the stated July/September plan tensor types.
- All **30 protected files** exist and match their predeletion hashes. No receipt
  path overlaps them or the active Stage A plan. The only tracked changes between
  the approved launch commit fe43fc9 and cleanup commit c3651b1 are the four receipt files.
- Group counts/bytes independently sum to the recorded totals:
  A 581 / 13,300,144,773; B 51 / 1,276,221,807;
  C 11,700 / 1,664,290,626; D 259 / 293,263,511.
- **16,533,920,717 bytes (16.534 GB decimal) of file content removed.**
  Receipt's filesystem-free readings differ by **16,503,693,312 bytes
  (16.504 GB decimal)**. Both round to 16.5 GB, but file-content totals and
  filesystem free-space change are distinct measures.
- A/D predeletion hashes and the filesystem-before measurement are retained receipt
  evidence; this reviewer did not independently observe those files before deletion.
  The live remaining trained_parameters inventory is recorded separately; files
  without a sibling manifest are explicitly marked rather than assumed valid.

Tests, source/tool code, B's first/step100/final states and corrupt/supplement pairs,
diagnosis dependencies, and Stage A package remain. The intentionally removed
intermediate tensors cannot be reconstructed from hashes. Do not rerun historical
full-artifact checksum checks expecting deliberately deleted fixture/checkpoint
bytes to exist; retain the removal receipt with the original inventories.

## Returned Stage A A0

The baseline result was recomputed from the returned telemetry, without evaluating
the model. It exactly matches stage_a_result.json. Manifest matches the bound probe
recipe with only the cleared Stage A changes; seed0, batch16, 100 updates, devseed4242,
25-step evaluation, pinned stack and TF32=false are verified. Saved parameter hash
matches the returned manifest. Return code 0, worker wall 642.076 s (10.70 min).

| step | pooled absent-read weight |
|---|---:|
| 0 | 0.046701282903086394 |
| 25 | 0.9960536565631628 |
| 50 | 0.9993223361670971 |
| 75 | 0.999745893292129 |
| 100 | 0.9927543895319104 |

A0 is **valid / escaped**, kept_through_100=false. Its frozen continuation gate
passes. This is the baseline routing-failure reproduction, not a remedy/learning
result. Only A0 had returned at this snapshot. Whole-run terminal exits, shutdown,
A1/A2 endpoints and final billing remain pending. Deadline remains unchanged at
20:25:00Z (03:25 Bangkok). Existing wait25 remains; no new launch is authorized by
this review. Geometry still needs its new bound index and exact argv reviewed first.

Evidence: verify.py, verify.log/exit, verification.json, remaining-p2p5-finals.json,
and this bundle's SHA256SUMS.txt.
