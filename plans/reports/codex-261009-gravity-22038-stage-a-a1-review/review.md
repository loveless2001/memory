# Independent A1 artifact review (gravity 22038)

The returned A1 artifacts verify. Classification recomputed from routing_telemetry
exactly equals stage_a_result.json: valid, band_at_100=partial,
kept_through_100=false. The manifest matches the approved bound probe configuration,
devseed4242, pinned versions and TF32=false; final parameter hash matches. Against
A0, the only PilotConfig difference is the global learning rate (.003 -> .0003),
with matching SGM config/policy and exactly matching initial absent weight.
Worker wall time 727.121 s. No model forward, paid compute call, or intervention
was performed in this review.

| step | A1 pooled absent weight |
|---|---:|
| 0 | 0.046701282903086394 |
| 25 | 0.4886660152114928 |
| 50 | 0.5301995989866555 |
| 75 | 0.6111422991380095 |
| 100 | 0.6523364614695311 |

The lower-rate arm has less absent weight than A0 on these sampled dev points,
but misses the <=.2 retention condition. This one-seed global-rate intervention
does not isolate address learning rate, establish H2, or demonstrate learning or
useful discrimination. A1 supplies no kept-arm Stage B condition. A2 remains
unevaluable while no result is returned.

At the single read-only snapshot 20:12:16Z, the bound app remains ephemeral with
zero tasks and no listed containers. This does not establish why the pending call
has not started. No terminal/cleanup markers exist. The unchanged 20:25:00Z
deadline has 763.9 s remaining; the 600 s post-setup admission check implies a
cutoff around 20:15:00Z, after which A2 cannot begin training. A refusal/timeout
must remain a not-run/incomplete arm, not a negative A2 scientific endpoint.
No extension, retry, automatic Stage B or new geometry pass is cleared here.
Existing wait25 remains for terminal artifacts and strict shutdown review.

Evidence: verify.py, verify.log/exit, verification.json, and SHA256SUMS.txt.
