# Geometry waiter correction and review (gravity 22057)

The original wrapper's GPU query pipelines discarded nvidia-smi's failure status.
An error can produce APPS=0 and MEM=""; the numeric comparison then returns an
error, the busy if-condition evaluates false, and execution proceeds to launch.
The retained offline reproducer demonstrates WOULD_LAUNCH and the numeric-test error.

Corrected the tracked wrapper to check each nvidia-smi invocation's exit status
directly, validate compute-app rows and the memory value, and refuse unknown or
malformed status with a persisted gate record and exit4. Busy status still exits3;
only known zero compute apps and memory<300MiB admit a launch. The exact cleared
timeout3600 argv, no retry/CPU fallback, exit marker and cleanup recording remain.

**Ten isolated real-shell cases pass**: app query failure, memory query failure,
empty memory, nonnumeric memory, unexpected multi-row memory, malformed app rows,
active compute app, memory exactly300MiB, idle0MiB, and idle299MiB. Every repeat
refuses at the gate record. Idle fixtures verify the exact command and retained
diagnostic exit17 followed by cleanup. Fake executables prevent any model/paid run.

Corrected wrapper SHA256:
4128e83e5d7ebf9c3670baa7ee92b8a55bfe1e35354c2f9ede7ae107e9dceddd

The old waiter PID3005546 was already absent when the guarded stop check ran;
**this reviewer sent no signal**. Its disappearance reason was not established.
No geometry output or gate existed at the subsequent check. smollm controller
2996958 remained alive and was not touched. Initial channel wording saying the
waiter was stopped by this reviewer was corrected in22061.

The corrected wrapper is cleared for owner commit and one re-arm, with the waiter's
own stdout/stderr captured for lifecycle evidence. Claude remains launch owner;
preserve smollm's GPU use until controller exit and the fresh idle gate passes.
The existing geometry index/code/input clearance in22056 remains unchanged.
No new user approval, model attempt, optimization step, paid call or retry occurs
in this correction. Existing controller and billing waits remain active.

Evidence: old-gate-reproducer-and-waiter-stop.json, check-gate.py, checks.json,
checks.log/exit and SHA256SUMS.txt.
