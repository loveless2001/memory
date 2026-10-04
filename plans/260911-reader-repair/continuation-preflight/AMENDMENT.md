# Execution amendment: finish the frozen capture schedule

Recorded during the first run, before completing or scoring its outputs. The
first run passes all forty cache checks, but per-check and per-answer artifact
commits dominate wall time. Its first six recorded generation times are
0.27–1.77 seconds each, while collection advances by only a few answers per
minute. At this rate the original twenty-minute run cannot finish 144 answers.

To finish the user's authorized paired experiment, permit one continuation on
one H100 after the first app stops. Preserve the first run, its time-cap failure
and every committed capture. Freeze the missing suffix after terminal retrieval;
generate each missing condition once. Do not rerun saved answers or change case
order, either prompt, references, criteria, gates, model, precision or decoding.
Only capture start index and commit cadence change. This is an execution-plan
deviation from the initial one-run budget and must be reported explicitly.

The continuation has its own 1,200-second hard cap and 1,150-second internal cap,
zero automatic retries and the same resource allocation. Thus total requested
H100 ceilings are at most forty minutes across two sequential runs. Forty
actual-prompt cache fixtures are repeated before collection in the new process.
Local artifact files are still written at each step; remote volume commits are
batched every twenty checkpoint requests and always performed at terminal exit.
This reduces checkpoint traffic without changing the model's input or decoding.
The original run and its protected artifacts are not overwritten.

The continuation is triggered by capture throughput and the terminal missing
suffix, not answer quality. Some initial answers were inspected to diagnose
timing, so this is not a wholly prospective execution schedule. Both semantic
success gates remain prospective and unchanged: repair 24/24 development and
48/48 fresh. Preserve separate manifests for both runs and a hash-bound merged
view for review. Stop after this continuation; no new prompt variant, training,
broader pipeline run or external judge is included.
