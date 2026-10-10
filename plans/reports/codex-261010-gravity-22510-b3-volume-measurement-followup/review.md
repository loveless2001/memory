# B3 retained-size measurement follow-up

Message 22510 / commit 479cabd: accepted as a model-free CPU payload measurement and useful retention estimate, with the qualifications below. This is not complete package/cap clearance. No numerical or model measurement was executed by this follow-up; only retained files and source were inspected and scalar arithmetic checked.

The commit adds only the measurement script and JSON. It leaves the previously audited crash-repair files unchanged. Their relevant dependencies, the B3 wrapper, checkpoint helper and proposal were captured alongside the measurement at that commit; source-manifest.json records their hashes.

The script asserts 3,744,604 parameters, builds shape-configured shift2 adapters and the taskhead, materializes both AdamW moments with a zero-gradient step and calls the real training_state/save_atomic helpers. Pretrained-model loaders are sentinel-blocked before those repository imports. The JSON reports 45,256,523 bytes for the serialized CPU checkpoint, or 1.0071 times the 44,935,248-byte parameters-plus-two-moments payload. Empty checkpoint_steps prevents fixed-endpoint parameter snapshots being embedded. The 166 B2 telemetry rows are explicitly a proxy.

This is not an exact real GPU checkpoint: CUDA RNG is omitted by the CPU runtime, B3 identity is replaced by a small placeholder, and actual B3 telemetry and all live output files are unmeasured. Preserve that qualification. The JSON also does not independently prove the reported cgroup run or final/peak Volume totals.

prepare_out confirms the identified worst-case retention path: with no resume.pt, an interrupted first-save resume.pt.tmp is moved into a whole-directory archive on the next start. Two permitted resumptions can retain two such archives. save_atomic uses one fixed live .tmp name, so a later save can additionally coexist with the live resume.pt. Normal resumption from a committed checkpoint archives telemetry only; it does not copy the checkpoint.

Using the measured CPU proxy and three telemetry files, scalar arithmetic gives 151,869,268 bytes after completion with two full archived-save temporaries, and 197,125,791 bytes at a save peak with those archives plus a live checkpoint and live temporary. Both figures exclude safetensors headers, identity/manifests/results/start records, archive metadata and differences in actual GPU RNG or telemetry. These are plausible conditional estimates, not strict maximums. The approximately 197 MB figure is the peak, not the final retained total. Decimal MB and MiB must remain distinct.

Carry an explicit superseding correction into the package handoff: replace the proposal's estimated <=155 MB Volume peak with the approximately 197 MB payload-based peak plus metadata/actual-state allowance (a rounded 200 MB planning allowance still remains an estimate). Storage/transfer remains an unpriced budget assumption; neither a small estimate nor the training deadline establishes a settled all-resource $17 cap. Preserve earlier proposals instead of silently editing their history.

The repair audit already passed in the sibling 22508 report. The next trigger is the complete package handoff with procedure, bound source/evidence, ledger, storage correction and stated risks. Package clearance and cap approval remain pending. No cloud, GPU, deployment, spawn or paid action occurred here.
