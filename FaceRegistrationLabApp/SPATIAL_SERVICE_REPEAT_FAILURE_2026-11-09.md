# Repeated Spatial service failure and preceding pipeline stop

**Newer incident identified and recovered:** [Concurrent camera probe diagnosis](CAMERA_PREEMPTION_STOP_2026-11-09.md). The 14:46 PST stop was caused by external camera preemption followed by delayed client cleanup; the lab watchdog fired after three seconds of stale frames. Same-APK service reset recovered it, verified through frame 2402 with unlocked status and preserved data. The GPU failure and earlier unexplained stop described below remain separate historical incidents.

**Later user-requested recovery (2026-11-09T22:39:53.221294+00:00):** restarted only the lab and Spatial OpenMR, then relaunched the same app. New app/service PIDs 30424/30606; all models initialize and status reaches frame 635, stopped=false/locked=false, "Ready for One check or Full trial". APKs, private calibration, all 1133 existing app files and 54 recordings are preserved. Lease released. [Restart receipt](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-restart-requested-2026-11-09/recovery.json). The failed-state preservation statements below describe the preceding investigation; the lifecycle defects remain unresolved.

The current failure is another GPU model initialization failure under reused Spatial service PID **21321**. The previous app session also stopped producing inference frames almost 58 minutes before the app was closed. These are distinct observations: the relaunch failure is identified, but its error cannot be retroactively assigned to the earlier stop.

This investigation preserved the failed state. No app/service restart, APK replacement, source change, debug-property change, data clearing, or recording change was performed. The diagnostic lease is released. App PID **10804** remains at frame 0 with `stopped=true`, `locked=true`; it responds to the status broadcast. Android reports **no ANR since boot**.

## Evidence and sequence

Device **PB311XHGKC220141G**, Swan ROM `Pico/swan/swan:16/BQ2A.260122.002-BP2A.250705.008/20261014024400:userdebug/test-keys`. Capture host time: November 9, 22:28 UTC. Headset logs use November 10 CST. Journal times below are mapped from the session's monotonic origin to UTC, then Pacific Standard Time.

| Pacific time, November 9 | Observation |
|---|---|
| 12:59:30 PM | Earlier targeted recovery launches app PID 21158 and fresh Spatial PID 21321. |
| 1:25:00 PM | Last face mesh upload, frame 28413. |
| 1:28:34 PM | Last pipeline frame, 32511; finite, fresh, no face, no rejection. Its scene acknowledgement completes about 18 ms later. |
| 1:28:34–2:26:23 PM | UI ticks continue, but no further pipeline frames or uploads are journaled. |
| 2:26:23 PM | Previous app closes. Android records `USER REQUESTED / STOP APP`, not crash, ANR, or low-memory kill. |
| 2:26:36 PM | New app PID 10804 starts; Spatial PID 21321 is reused. |
| 2:26:39 PM | First compact GPU preprocessing model fails allocating an input buffer. |
| 2:28:47 PM | Status response confirms frame 0, stopped/locked, no active automatic capture. |

The previous journal contains **32,511 pipeline frames**, **11,022 face frames/uploads**, and **84,186 UI ticks**. The active readback interval spans 1,733.04 seconds; its largest inter-readback gap is 0.291 seconds. There are 3,469.22 seconds between the final pipeline frame and app close. The final face upload precedes the last pipeline frame by 213.95 seconds, so there is no evidence that the final stop happened inside an active face-mesh upload.

[Capture manifest and app status](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-repeat-2026-11-09/capture.json), [previous-session analysis](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-repeat-2026-11-09/previous-session-analysis.json), [event times](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-repeat-2026-11-09/previous-session-event-times.json), [process exit history](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-repeat-2026-11-09/app-exit-info.txt).

Both journals were copied and verified against device SHA-256. The previous journal is 142,686,174 bytes, SHA-256 `2a9c3459e127a777b2fa3c683377f13def9b1b7ff86b6e9e62b4cbbbb824830a`. The failed-session snapshot is 141,165 bytes, SHA-256 `2582ab4a9f4fc30512948730c5f92e1396268f8a281a7c8ed4f71691c0bc665d`.

## Confirmed current failure

The app and service hashes are unchanged from the earlier successful recovery:

- App: `5b937e029ab4ea28089237af00cc747511c77bb2493035d669260975af56d4df`.
- Spatial service: `482da7ac78ae141bce280e5e45de3b3c771dd61901900294fce893cabf5e1519`.

The service opens/configures the camera, starts preview, and creates a new LiteRT environment. It then logs:

```text
06:26:39.285 21321 21370 Replacing 4 out of 4 node(s) with delegate (LITERT_CL)
06:26:39.285 21321 21370 Initializing OpenCL-based API from graph.
06:26:39.286 21321 21370 LiteRt create input buffer failed
06:26:39.290 21321 21370 Process 10804->createModelOperator
  [OTHER INTERNAL ERROR]: OperatorRunModelInference Unable to initialize LiteRT model and runtime
06:26:39.349 10804 28172 SpatialML error: SSMR backend exception:
  SecureMR encounters internal exception
```

The app stack identifies `SpatialMLGraphSession.compactDetectorInput`, the `detector_compact_preprocess_gpu` construction path. Failure precedes inference and dynamic mesh preparation/upload in this new session. `FaceLandmarkerRunner` catches the exception and calls `lab.fail(..., fatal=true)`; the lab's `locked` property includes `stopped`. This explains the disabled controls while UI/status handling remains responsive.

The secondary `Service not registered: ...SSMRConnection` finalizer exception occurs at 06:26:53.529, after the primary error. Missing-container teardown messages also follow the model failure; neither is the initial failure boundary.

[Service log](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-repeat-2026-11-09/service-logcat.txt), [app log](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-repeat-2026-11-09/app-logcat.txt), [ANR state](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-repeat-2026-11-09/last-anr.txt). Full unfiltered logcat is retained beside these files; device logs were not cleared.

## Stronger lead, with limits

The successful startup in the **same service PID** logged `Created LiteRT GpuEnvironment.` at 04:59:35.151 before OpenCL model initialization. The new failed startup creates a new LiteRT environment and delegates to OpenCL, but has no corresponding GPU-environment creation log. This matches the prior local service investigation at `Service/OpenMR/docs/litert-gpu-session-teardown-investigation.md`: its leading hypothesis is process-global OpenCL state being reused without attaching compatible GPU state to the replacement LiteRT environment.

Current local service source (`dev/fix-7387367802`, HEAD `f484729b7a8a2aa8046776957e77f60da59cb7d1`) still discards the actual status from `LiteRtCreateManagedTensorBufferFromRequirements` in `Utils/src/TFLiteModel.cpp:189`. `DataPipeline/src/OperatorFactory.cpp:852` holds a weak environment reference; replacing the environment after the last model is released is possible while the process survives. Available LiteRT source has a managed GPU buffer path that returns `kLiteRtStatusErrorRuntimeFailure` when GPU environment lookup fails. These are source-backed mechanisms to test, not proof of the exact status or loaded accelerator behavior in this incident. The local checkout has not been established as byte-identical to the installed service.

Post-failure service PSS is about 285 MiB, RSS about 491 MiB, and system `MemAvailable` about 4.31 GiB. No ANR or low-memory termination is recorded for this event. These snapshots do not establish GPU allocation health at the failure instant and do not rule out a driver/allocator problem. `/proc/21321/fd` access was denied; no privileged dump was attempted.

## Why the earlier stop remains unresolved

The previous session's journal proves that pipeline output ceased at 1:28:34 PM while UI ticks continued. It does not persist the runner's fatal error, timeout, cancellation, or graph-close reason. The captured log buffers no longer contain the relevant app/service messages from that time. Therefore the first stop could not be classified as an inference timeout, service failure, camera/lifecycle interruption, or another exception from this evidence alone.

The relaunch error is a separate, reproducible recovery problem. Restarting the Spatial process recovered it earlier; repeating that reset would discard the current service state without explaining the first stop. This investigation leaves that state available.

## Fix boundary and regression

1. Persist fatal runner errors and lifecycle transitions in the app journal, with last submitted/completed sequence, outstanding operation, monotonic time, exception stack, and graph-close begin/end. That closes the evidence gap when logcat rotates.
2. Instrument the failing service allocation: actual LiteRT status, model/input name and index, ranked type/shape, required buffer types/size, environment identity and `LiteRtEnvironmentHasGpuEnvironment` before/after compilation. Record creation/run/destruction thread IDs and completion of resource teardown.
3. Reproduce create/run/close/recreate of compact GPU preprocessing within one service PID; compare replacement versus retained environment lifetime in a diagnostic build. Verify deterministic outputs, resource counts, and clean teardown. Do not add an unvalidated GPU-environment creation fallback that could mismatch contexts.
4. Exercise long no-face/face runs, headset/background transitions, explicit close, client death, failed initialization/retry, and simultaneous clients. Record the first failure durably before any recovery attempt. Keep the separate SDK double-unbind cleanup issue in scope.

No production repair is claimed. The old standalone GPU probe described in the service note is no longer present in `/tmp`, and it was not executed in this investigation.

## Performance recovered from the complete previous session

Earlier snapshots contained no faces. The complete journal now supplies **10,962 admitted tracking uploads**, plus 60 detection uploads, with all outputs, balanced filtering, green wireframe and replacement uploads. The new summaries supersede the earlier no-sample performance status.

| Tracking metric | Median | p95 |
|---|---:|---:|
| Readback → app scene acknowledgement | **15.72 ms** | **23.29 ms** |
| Readback → SDK return | 13.81 ms | 21.63 ms |
| SDK upload call | 7.34 ms | 11.37 ms |
| Numeric mesh preparation | 0.171 ms | 0.515 ms |
| Smoothing | 2.57 ms | 4.43 ms |
| SDK return → UI resumption | 0.411 ms | 6.14 ms |
| Native Stage-to-owner basis snapshot | 0.074 ms | 0.230 ms |

Historical scene-ack baseline: 18.89/33.86 ms. The new distribution is lower, but this is not a matched A/B capture: inference timing and workload also differ. Quantiles are not additive, SDK call time includes its internal scheduling/adaptation, and neither endpoint measures screen presentation. SDK upload is now a much larger measured cost than numeric preparation or owner conversion; pose/shape rendering separation is a better measured follow-up than optimizing the 0.074 ms basis snapshot.

[Frame-paired upload summary](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-repeat-2026-11-09/previous-session-upload-summary.json). The failed new session has no performance samples.
