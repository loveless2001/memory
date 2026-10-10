# B2 authorized launch: provenance verified; training start not yet observed

User #gravity 22162 "Ok launch" authorizes the previously quoted single B2 campaign within the requested $17 scope, following CPU/package clearance 22159. The owner launched once at **05:25:07.456099Z** from the audited side worktree. This read-only audit neither launched additional work nor altered/stopped the existing app.

Independent checks verify the recorded launch HEAD and current HEAD are both `24b1432e990f878d1d8dfc9fa9183357fa9986bc`, tracked working tree clean, all eight v0.3 package file hashes matching, and memsub matching `d86639b9223d4595a53cd07f3fee4da58c413414c49ed220d7135742f444a532`. The recorded CLI, launcher PID/PGID/SID 3413654, live client/timeout process chain, app ID `ap-VsAmnu1E7eS5rXLrKD7vXd`, base image, resource request, planned B2 arm, and ledger agree with the audited package.

At the **05:26Z startup snapshot**, Modal lists this app as ephemeral, tasks 0, no containers. The existing start Dict contains the correct immutable deadline but no start-1/start-2/start-3 claim yet. This verifies an initialized campaign; it does not yet verify worker admission, GPU training, checkpoint persistence, throughput, or scientific results. The owner-reported pre-launch absence of any B2 app/Volume is not independently reconstructible after creation; it remains an owner preflight statement rather than an additional independent observation.

The recorded limits are:

| Bound | UTC | Bangkok |
| --- | --- | --- |
| Immutable campaign deadline | **11:55:12.607416** | **18:55:12** |
| Latest local client kill | 11:59:07.456099 | 18:59:07 |
| Latest cleanup-command kill | 12:04:37.456099 | 19:04:37 |

Campaign duration is 23,400 seconds from the recorded first-call/deadline origin; local client lifetime is 23,640 seconds from launch. The deadline does not reset on any of the maximum three admitted starts. Resources remain one L40S container, four CPU cores, 32 GiB. The $16.2442476 compute reservation remains conditional on CPU use and shutdown assumptions, with the requested $17 allowing for expected storage/transfer overhead. It is not a guaranteed external billing ceiling. The approximate 09:50Z finish projection is still an estimate based on unprofiled long-input fallback timing and can change with startup delay.

Both terminal exits are absent at verification, and the launcher/client are alive. A wake-up watch covers the cleanup-exit artifact **or launcher PID exit**, with a bounded timeout beyond the recorded terminal window. Normal terminal audit will inspect both exits, validate final/partial artifacts and resumed trajectories, verify the bound app stopped/unlisted with zero tasks/containers, and reconcile app-attributed billing. Unexpected launcher death requires verifying cleanup rather than assuming the app stopped. No deadline extension, separate relaunch, additional arm/seed, or branch integration is authorized.

The owner handles progress at most hourly through read-only Volume telemetry; this audit does not add a duplicate progress polling loop. Launch evidence is preserved under `launch/`; hash checks and deadline calculations are in `launch-verification.json`, and startup observations in `startup-observation.json` / `start-dict.json`. Main checkout and existing research artifacts remain untouched.
