# Camera preemption and delayed cleanup stopped the lab

The November 9 run that stopped around **2:46:42 PM PST** lost its camera because a separate TRAE task opened a PXRCapture client and later released it. OpenMR recovered from the initial preemption, but the other client's delayed cleanup then stopped the recovered preview. The lab's three-second camera-freshness watchdog terminated processing. This incident has direct camera-error evidence and is distinct from the earlier GPU model initialization failures on app relaunch.

## Exact sequence

Headset PB311XHGKC220141G; lab PID 30424; Spatial OpenMR PID 30606; PXRCapture service PID 2757; external probe PID 32444. Device log times below are November 10 CST (UTC+8), equivalent to November 9 PST minus 16 hours.

| Device time | Evidence |
|---|---|
| 06:46:31.017 | Probe PID 32444 registers a capture client; capture service releases its existing resources. |
| 06:46:31.018 | OpenMR receives `errorCode:-95, msg:priority is preempted`. |
| 06:46:31.064 | OpenMR schedules recovery and forces reset, close, release and recreation. |
| 06:46:31.118 | Probe calls `openCameraAsync`. Its source installs callbacks and waits up to eight seconds for characteristics. |
| 06:46:31.497 | OpenMR logs recovery complete: previewing with advancing VST frames. |
| 06:46:39.118–119 | Probe calls reset, close and release. Reset/close return -1 (`wrong state 6`); release returns 0. |
| 06:46:39.119 | Capture service handles that release by invoking `onStopPreview`. |
| 06:46:39.135–206 | Capture service resets and closes the camera. Sensor-provider/kernel logs corroborate both RGB streams stopping. |
| 06:46:39.203 onward | OpenMR repeatedly reports `CAMERA ERROR: Camera Session: camera is not ready or is finished`. |
| 06:46:42.228 | App reports `IllegalStateException: Camera stream stopped supplying fresh frames. Retry camera capture.` at `FaceLandmarkerRunner.kt:170`. |
| 07:06:03.562 | Android later stops the app with `USER REQUESTED / STOP APP`. No ANR is recorded. |

The last journaled pipeline frame is **8324**, capture time **11342.013637721539 s**, readback time **11345.094867598 s**, camera age **3.0812298764612933 s**, `freshCameraFrame=false`. Readbacks briefly continued from the same exposure before the watchdog fired. UI ticks continued after pipeline frames stopped. By the diagnostic capture, the app process was already absent; this was not a live ANR inspection.

## Probe provenance and evidence

The independent task `01a1a465-b7b2-7790-b091-43f8528f7ebf` held a devmux lease from 2:46:28 to 2:46:39 PM PST with the note “Read PXRCapture camera characteristics; no preview or recording”. Although described as a metadata query, its actual native probe calls `PXRCaptureGetInstance`, registers callbacks and calls `PXRCaptureOpenCameraAsync`. Client registration/opening therefore affected the running camera owner. Probe output records `metadata_received=0`, cleanup reset=-1/close=-1/release=0, and exit code 3.

The diagnostic capture's current main log buffer had rotated past the failure. The other task's saved `post-probe-logcat.txt` retains the complete preemption, recovery, delayed release and app exception. Relevant files were copied into this incident's evidence directory without rerunning the probe or changing the other task's artifacts.

- [Line-numbered causal events](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/runtime-stall-20261109-230856/concurrent-probe/incident-key-lines.txt), with line numbers into the preserved full post-probe log.
- [Probe source](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/runtime-stall-20261109-230856/concurrent-probe/capture_characteristics_probe.c), [probe results](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/runtime-stall-20261109-230856/concurrent-probe/probe-results.txt), and [lease events](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/runtime-stall-20261109-230856/concurrent-probe/devmux-events.json).
- [Device capture](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/runtime-stall-20261109-230856/capture.json), [journal analysis](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/runtime-stall-20261109-230856/journal-analysis.json), and [Android exit history](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/runtime-stall-20261109-230856/app-exit-info.txt).

Session `2026-11-09T22-39-04.093614Z-56e752` contains 8,324 pipeline frames, 130 uploads and 24,355 UI ticks. Its copied journal is 30,255,322 bytes, SHA-256 `44511e2fff538ca05f3f0ea1627b8bc7a8b753777fb9d4d4dabe39d30770aaed`.

## Why recovery did not cover the second interruption

The installed logs prove that error-triggered camera recovery is present. Current local `Service/OpenMR/app/src/main/cpp/InferenceEngine/src/VSTSession.cpp:142` enters recovery when `m_hasError` is set by the capture error callback. At line 178, an unexpected non-preview state instead throws a camera error without itself scheduling recovery. This is consistent with the second shutdown remaining unrecovered. Local source has not been proven byte-identical to the installed service, and PXRCapture's internal ownership implementation has not been audited here.

`FaceLandmarkerRunner.kt:170` deliberately fails after three seconds without fresh camera data. Its error handler calls `lab.fail(..., fatal=true)`, which sets `stopped`; the lab's `locked` property includes `stopped`. This explains disabled controls after processing stops. The durable journal currently omits that fatal error, so recovering the saved logcat was necessary.

Devmux serialized host operations, but our earlier verification lease had been released while the app continued to use the camera. A free command lease does not imply an idle camera. Future camera-open probes must account for the active app's camera ownership; a metadata label alone does not make a probe non-disruptive.

## Repair boundaries and useful regressions

1. **Capture ownership:** audit PXRCapture release/reset/close against client identity or generation. A displaced client's delayed release must not stop the new owner's preview. In a controlled test, start client A, preempt it with B, allow A to recover, then release B eight seconds later and verify A's frame timestamps continue.
2. **OpenMR recovery:** handle unexpected terminal/non-preview state and a stalled image sequence even when no error callback arrives. Preserve intentional stop/teardown semantics, run capture API calls outside callbacks, and bound/back off retries. Simulate preview-to-closed without an error callback; require fresh timestamps after recovery and no reopening after intentional close.
3. **App diagnostics/recovery:** journal fatal runner errors and graph lifecycle transitions durably, and provide a usable stopped/retry state. Exercise watchdog stop and recovery while preserving calibration. A full graph reconnect must also address the separate existing GPU environment reuse failure; blindly retrying it is not a demonstrated repair.

No production repair or camera-preemption regression was executed. No source, APK, calibration or debug-property change was needed to identify this incident. The interfering probe was not rerun.

## Recovery verification

Completed at **2026-11-09T23:16:39.731937+00:00**. Restarted only the lab and Spatial OpenMR, then launched the existing lab APK. New app/service PIDs **14963/5798**; session `2026-11-09T23-14-19.150623Z-c7eebc`. The recovered service creates its GPU environment and has no captured camera or GPU-input-allocation errors.

Six checks over 90 seconds show advancing frame numbers and capture timestamps through frame 1744. The captured journal contains **1,777 finite packets over 94.48 seconds**, **1,777 unique camera timestamps**, **1,776 fresh packets** and zero rejected packets. The first startup packet is the single nonfresh packet. No faces were present, so this verifies camera/pipeline recovery rather than face-mesh tracking or alignment. Final status reaches **frame 2402**, `stopped=false`, `locked=false`, and “Ready for One check or Full trial”.

The app and service APK hashes remain unchanged. All **1134** existing app files and **54** recordings remain present with no size loss; private calibration hashes match. Live mode/applied mode, intrinsics/applied intrinsics and correction/applied correction match the prior recovered session exactly. Debug property remains unset. Lease released; app left running.

[Recovery script and receipt](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/camera-interference-recovery-2026-11-09/recovery.json), [captured journal summary](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/camera-interference-recovery-2026-11-09/recovered-journal-summary.json), and [final app status](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/camera-interference-recovery-2026-11-09/recovered-status.json). This is a verified process-reset recovery, not a permanent repair or a sustained face-tracking acceptance run.
