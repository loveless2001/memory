# Independent occupied-fill correction review

**CPU implementation review cleared for 1b012451f7b4e02ff38dac11c3ae5c7de8dfc387**, parent a66d800c4d4d4e10b0a4015d6f904d7b1b9a2562, on `m4-sgm-occupied-fill-v1`. The numerical blocker from review 22123 is resolved. This clears preparation of a concrete bounded run proposal, not a model launch, merge, GPU/Modal activity, or 100-to-1500 continuation.

## Correction verified

The module computes missing mass directly as `u = sum(w * absent_mask)` and uses it for both the fill and detached anchor coefficient. Present mass remains available for telemetry and the fully-absent check. Integration code is unchanged: the only commit changes are this module, its test file, the spec, and its test log. Module SHA256: `2a51e55408be6c5a21d35305330236ed1373c8052a7542de036d26d744e0f496`.

Both original FP32 reproducer coordinates retain present masses on opposite sides of one (1.0000001192092896 and 0.9999999403953552), while direct missing mass, fill, anchor, and anchor gradient are now exactly zero. In both cases the read is bitwise unchanged. The new candidate test also covers the first reproducer and 200 random fractional fully-supported coordinates.

## Independent checks

- **13 fallback tests and 15 runtime tests pass, 28 unique checks total.** The initial isolated run passed 27 checks and failed only because my archive omitted the observer helper. I restored that helper from the exact candidate commit and reran only the affected test successfully. Both logs remain; this was a review-fixture error.
- Default-off four-update tiny CPU parameters, telemetry, and policy ID match the saved independently measured baseline at 95856b1 exactly: parameters `0569712afd27e91358e91cc5205ada88795694b98906ecad693438cf91e940d8`, telemetry `36ee61072abc85eccaaffec4c7c71db992a4288f5f14ab43309bbe03aa8994bd`, policy `m4-sgm:learned:sha256:51d7a1e03f11753d`.
- Independent partial-read autograd agrees with centered finite differences within **3.982e-5**. The far-empty anchor derivative still equals the exact nearest-cell pseudo-Huber derivative at the checked point.
- The shared checkout remains at 95856b153e874508726c604a8c593c6ff73684cb with no tracked changes. Checks ran in an isolated source snapshot with CPU Torch; no GPU, Modal or Qwen model forward was used.

These checks establish the corrected mechanics and default-off parity. They do not establish restored routing, useful retrieval, Qwen fit, throughput, or a paid-run cost bound. The all-occupied-cell fill remains unprofiled, and the anchor targets any occupied cell rather than necessarily the correct binding.

## Boundaries retained

Keep the variant on its side branch and preserve closed-campaign source/hash guards. The previous full-suite failure accounting remains separate; this focused correction review did not rerun the full suite. The amendment-bound terminal checkpoint deleted during cleanup remains unavailable locally, and its exact-hash recovery is unresolved. No substitution or frozen-evidence rebinding is cleared.

A later proposal must bind this corrected source and its dependencies, keep raw pre-fill absence separate from filled support, and provide an explicit resource/deadline/cost bound. The 100-update routing/mechanics gate and any longer held-out retrieval test require their own explicit authorization. The spec now correctly avoids claiming that retrieval could never emerge within 100 updates.

Evidence is in `verification.json`, `trees.json`, `correction.diff`, the retained test logs, parity JSON files, and `independent-kernel-results-1b01245.json`. `SHA256SUMS` binds this review's payload files.
