# Independent readings launch verification

PASS as of **2026-10-07 15:40:16 UTC**. All ten launch checks passed (`launch-verification.json`). This verifies the approved launch and its bindings; scientific readings remain pending.

The bound call is `fc-01M4BG37XCKFD3A9WRJ91D44MB`, on app `ap-MvPw7JVom3vnRTxVVyzldN`. Independent polling returns pending. Function stats show one running input, one runner and zero backlog. The admission Dict contains exactly `start-1`; the live app/container are bound to the expected app.

Provenance matches frozen commit `a17cd401c9046b1aa92826c0ecb47914d06270c7`, memsub `2eee4228…`, and manifest `882dd4a4…`. The submitted tracked tree is clean and the launch manifest validates. The readings guard exactly matches provenance; the control registry adds only that exact readings entry. The original controller is unchanged and its horizon fits. All nine training apps remain stopped/unlisted without tasks or containers. A fresh remote-volume read verifies the original learned-n32-s1 FAILED state and done.json hashes and output-hash map against the frozen exception spec.

The candidate was set at **15:35:38.243969 UTC**, before the existing latest candidate. The immutable readings deadline is **19:26:04.843969 UTC** (**Oct 8, 02:26:04.843969 Bangkok**). The controller deadline remains **21:26:57.252974 UTC**. No deadline extension or additional start was introduced.

Continue the existing collector, stop by bound app ID when terminal, verify shutdown, and fetch the retained evidence. Terminal review must verify remote parity, reserved-population/gate order, start/end dependency binding, whole-campaign and both-N post-hoc labels, and the preserved original unavailable outcome. These are not established by a pending launch. Billing reconciliation also remains pending.

Reviewer actions were local reads and read-only Modal queries, with no workload invocation, remote mutation, or shared campaign artifact edit.
