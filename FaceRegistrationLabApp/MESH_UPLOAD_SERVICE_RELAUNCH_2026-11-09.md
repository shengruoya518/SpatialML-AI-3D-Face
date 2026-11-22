# Spatial service initialization failure after app relaunch

**Later state:** the failure recurred under this recovered service process. [Repeated failure, preceding pipeline stop, and recovered performance samples](SPATIAL_SERVICE_REPEAT_FAILURE_2026-11-09.md) supersedes the current-state statements below. This report retains the earlier failure/recovery evidence.

The reported initialization failure is confirmed and the running app has been recovered. The failure occurred during GPU model construction in the existing Spatial OpenMR process, before inference and mesh uploads. Restarting only the lab and Spatial service restored initialization with the same app and service APKs. The underlying service/LiteRT lifecycle defect remains open.

## Failure evidence

Device `PB311XHGKC220141G`, Swan fingerprint `Pico/swan/swan:16/BQ2A.260122.002-BP2A.250705.008/20261014024400:userdebug/test-keys`. Device log times below are November 10; the host investigation is November 9 UTC.

The initial installation had streamed successfully. On a later app launch at 04:55:38, app PID **10680** reused Spatial service PID **14955**, which had started at 04:11:59. The app initialized its Stage mesh at 04:55:39, then failed to construct its SpatialML graph:

```text
04:55:41.439 14955 ... Replacing 4 out of 4 node(s) with delegate (LITERT_CL)
04:55:41.440 14955 ... Initializing OpenCL-based API from graph.
04:55:41.441 14955 ... LiteRt create input buffer failed
04:55:41.442 14955 ... Process 10680->createModelOperator
  [OTHER INTERNAL ERROR]: OperatorRunModelInference Unable to initialize LiteRT model and runtime
04:55:41.491 10680 ... SpatialML error: SSMR backend exception:
  SecureMR encounters internal exception
```

The saved app status has `frame=0`, `stopped=true`, `locked=true`, and no active automatic capture. The app stack points through `FaceLandmarkerGraph.buildProducer` to `compactDetectorInput`, which creates `detector_compact_preprocess_gpu` on the GPU. No inference packet or dynamic face upload was produced by this failed session.

A later `Service not registered: ...SSMRConnection` finalizer exception at 04:55:55 is a secondary cleanup failure. The native service also logged a missing-container destruction error and camera close failure after model construction failed. An empty Android crash buffer did not establish successful initialization: the app caught the backend exception and remained alive with disabled controls.

[Original service log](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-investigation/service-logcat.txt), [app log](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-investigation/app-logcat.txt), [failed status](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-investigation/failed-status.json). The complete original logcat is retained beside these extracts; no device log buffer was cleared.

## Recovery and verification

With no active recording or capture, stopped only `com.pico.spatial.ml.sample.facelandmarker.registrationlab` and `com.bytedance.pico.openmr.spatial`, then launched the same lab APK. The XR OpenMR package was not stopped. No app or service APK was reinstalled, rebuilt or replaced.

- New app PID **21158**, new Spatial service PID **21321**.
- The same first GPU model now delegates 4/4 nodes and logs `LiteRt model initialized successfully`; subsequent models initialize, followed by `pipeline_ready` and advancing camera frames.
- A hash-verified journal snapshot contains **910 pipeline frames, zero rejections**, and no crash-buffer entries. Later app status reaches **frame 1444**, `stopped=false`, `locked=false`, **Ready for One check or Full trial**.
- The UI shows **POS STEREO**, **Stereo calibration active**, and **Mesh smoothing: On**. No face was visible during verification; dynamic mesh upload timing remains pending.
- App SHA-256 remains `5b937e029ab4ea28089237af00cc747511c77bb2493035d669260975af56d4df`; service SHA-256 remains `482da7ac78ae141bce280e5e45de3b3c771dd61901900294fce893cabf5e1519`.
- All **1,131 existing app files**, **54 recordings**, and private calibration hashes were preserved. Debug logging/bypass stayed unset. The lease is released and the app is left running.

[Recovery receipt](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-investigation/recovery.json), [recovered service log](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-investigation/recovered-service-logcat.txt), [sustained snapshot](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/runtime-after-service-recovery/capture.json), [unlocked status](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-investigation/recovered-status.json), [screenshot](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/service-investigation/recovered-screen.png).

## Fix boundary and useful regression

This matches the previously documented [GPU relaunch failure](REGISTRATION_LAB_RELAUNCH_FAILURE_2026-11-03.md). Current evidence confirms failure under the reused service and successful recovery under a new process. It does not identify which internal GPU context, environment, buffer allocator or teardown state becomes invalid.

The local OpenMR implementation maps the failure to `TFLiteModel.cpp:189`, the call to `LiteRtCreateManagedTensorBufferFromRequirements`. It discards the returned LiteRT status and logs only a generic message. `OperatorFactory.cpp:517` then promotes `initialize(false)` to the generic backend exception. This is the useful instrumentation/fix boundary; local source is a code pointer, not proof that its current checkout exactly matches the installed binary.

A focused service regression should create and execute the compact GPU preprocessing model, close the client/session completely, then recreate and execute it repeatedly **within the same service PID**. Assert successful buffer allocation and deterministic output for a fixed input on every iteration; then exercise full lab close/reopen. Capture the actual LiteRT status, model/input identity, ranked tensor type, supported buffer types, required sizes and environment lifetime. Check resource destruction order and pending tasks before changing the renderer or inference graph. Separately make the SDK connection cleanup idempotent so the first initialization error does not produce a second unbind exception.

No service or app source was changed in this investigation. Process reset is an operational recovery, not a permanent fix or proof of face alignment/performance.
