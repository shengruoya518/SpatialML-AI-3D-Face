# Face pipeline timing and calibration

Current live analysis: [PIPELINE_PERFORMANCE_LIVE_2026-10-31.md](PIPELINE_PERFORMANCE_LIVE_2026-10-31.md). Three 30-second off/on/off windows measure normal submit/readback medians of 225–235 ms and about 8 ms paired upload. All 39 operators are timed in 106 complete dependency chains; affine crops average 73.4 ms combined, JS packing 24.6 ms, all snapshots 27.8 ms and three models 6.8 ms. Debug property restored and device lease released. Current export leaf costs, effective delegate and caller/CPU/GPU/compositor attribution remain open. Artifacts: `artifacts/facelandmarker/registration-lab/performance/session-output-20261101-004059/`. The original plan and older numbers below remain historical comparison evidence.

The live report now covers all service computation components and the aggregate host handoff. Lower latency should reduce motion-dependent mismatch and shorten capture phases. It cannot yet explain the persistent approximately 50.7 recorded-pixel upward shift measured in still, freshness-filtered frames. Keep the optical candidate tests and performance measurements as separate experiments.

The Unity counterpart does have a detailed component profile. [UNITY_OPTIMIZATION_COMPARISON.md](UNITY_OPTIMIZATION_COMPARISON.md) maps that saved XR-service profile and the current Unity optimizations to this Kotlin Spatial-service graph. Its times are comparison evidence, not measurements of Kotlin components.

## Measured baseline

Source: `artifacts/facelandmarker/registration-lab/automatic-check-2026-10-30/capture-session/*/sample.json`, and `analysis/marked-phase-timing.json`. These are measurements of the previous installed build, not the new update.

| Export | Camera age at submission | Submission to result readback | Camera age at readback |
| --- | ---: | ---: | ---: |
| CLEAN_BEFORE, frame 2808 | 24.7 ms | 451.3 ms | 476.0 ms |
| MARKED, frame 2882 | 42.1 ms | 538.0 ms | 580.0 ms |
| CLEAN_AFTER, frame 2896 | 36.6 ms | 467.9 ms | 504.4 ms |

These three successful exports are a small, selected sample. Their submission/readback interval accounts for approximately 93–95% of camera age at readback. It includes queued service work, execution and IPC/readback; it is not a model-only benchmark. VST acquisition occurs inside the submitted producer, so `camera age at submission` is a clock difference against the returned exposure, not a separately timed camera call.

Across 70 marked scene updates, camera age at readback was 410/520/980 ms (minimum/median/maximum); camera age at SDK upload completion was 429/532/998 ms. The paired upload and readback timestamps allow host/render handoff timing, but SDK upload completion does not measure compositor presentation. Missing scene rows and rejected/repeated frames need separate accounting.

## Original component measurement plan (historical)

The source submits `producer -> common -> mesh` with dependency handles and keeps one frame in flight until diagnostic reads settle. The lab currently forces the detector producer every frame; the normal sample can use predicted-ROI tracking. This is source evidence, not a measured detector cost.

| Component | Coverage at plan creation | Measurement needed then |
| --- | --- | --- |
| VST image, timestamp, camera K and camera-to-world | Included in aggregate | Service acquisition/pose operator durations and returned exposure age |
| Detector crop/normalization, face detector, ROI decoding | Included; detector forced in lab | Operator and model durations, detector versus tracking comparison |
| Landmark crop/normalization and landmark model | Included | Preprocessing and model durations separately |
| Tracking, 33-point geometry fits, three SVD calls, pose update | Included | JS, tensor dispatch and SVD durations |
| 478-point projection/unprojection and blendshape model | Included | Geometry versus blendshape durations; determine whether unused blendshapes are material |
| Packet packing and lab snapshot operators | Included | Packing/copy/snapshot durations |
| Global result polling/readback | Included | Poll count, IPC/copy and queue delay; separate from model work |
| Stage rebase and dynamic mesh upload | Paired journal endpoints available | Distribution of readback-to-upload time; visible, clean and rejected frames separately |
| Sample-only RGB/geometry readback and file export | Export timestamps available | Source capture, readbacks, encoding and file IO; exclude from steady-state inference measurements |
| Compositor presentation | Not measured | Supported compositor timestamps or recorded image association |

## Next connected check

The updated app journals `pipeline_frame` on every completed inference: frame sequence, capture/submission/readback timestamps, submission-to-readback duration, camera age, detector-path selection, face/freshness state and rejection reason. Use these rows to distinguish unseen or rejected frames from missing inference, and report warm-run median/p90/p95 plus repeated-exposure rate. This instrumentation does not provide per-component timings.

Run the updated C one-sample check first, preserving the camera/Stage/K contracts and all three exports. Capture service/operator profiling separately under the same target/ROM/backend, then associate service events with submitted run handles or frame markers. Verify the installed service actually exposes start/end or duration fields before claiming component timing. Debug logging can add overhead; compare a normal run with the profiling run.

The first optimization candidates are the unconditional detector, blendshape work unused by the lab's badge, and lab snapshot overhead. Measure them before modifying the graph. Preserve coherent detector/model/source crops at export, identical landmark/geometry outputs, advancing sensor timestamps, and exact native/Stage/sample identity. Avoid parallelizing shared mutable tensors without a proven ownership scheme. Compare end-to-end camera age and scene update rate as well as component runtime, then repeat physical marker validation. No graph optimization or latency improvement is claimed by this capture-gate update.
