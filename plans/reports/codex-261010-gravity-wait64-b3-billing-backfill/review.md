# B3 single billing-backfill recheck

Wait #64 triggered the one promised read-only recheck after 60 minutes. Hourly and daily Modal reports again
agree on **$6.64800992 current app-attributed usage** for `ap-uV0nVE4wGpjtep7vRs8tot`. Delta from the terminal
snapshot is exactly zero. Resource rounding differs by at most $0.00000001 between report resolutions.

Hourly totals remain 03 UTC $0.71856024, 04 UTC $2.39520015, 05 UTC $2.39386843, 06 UTC $1.14038110; there are no
reported later hours. The short 03 UTC interval remains unexplained by the observed container interval, so this
snapshot does not establish complete or settled billing. No late backfill, separate storage/transfer charges or
all-resource invoice was verified. The prior roughly $8.30 wall-time ledger estimate remains an estimate.

The independent cleanup-inventory snapshot at 07:36–07:37 UTC confirms stopped apps, zero tasks and zero
containers. The B3 scientific result is unchanged: valid negative, 8/256 normal and 8/256 deranged, zero drop.
The $17 authorization and conditional $16.3035352 reservation were not reset or expanded.

Both report commands exited 0; raw output, command receipts, scoped arithmetic and prior-snapshot comparison are
retained. No compute, deletion, deployment, dispatch or remote write occurred. **Wait #64 is closed; no timer is
rearmed.** Settled billing remains an explicitly unresolved accounting item for a later user-requested refresh.
