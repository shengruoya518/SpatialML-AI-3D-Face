# Whole face-tracking pipeline: live benchmark — 2026-10-31

The repaired Kotlin lab completes normal tracking in **225–235 ms median from submission to completed readback**, then **about 8 ms** to acknowledge the scene upload. The camera exposure is already **275–281 ms old** at upload. Pipeline completions are **4.03–4.24 per second**. These are tracking and SDK acknowledgement boundaries; headset display refresh and motion-to-photon latency were not measured.

The trace identifies the largest measured costs: the two native affine crops average **73.4 ms combined**, final JavaScript result packing **24.6 ms**, and producer/fit/mesh diagnostic snapshots **27.8 ms combined**. All three inference operators average **6.8 ms combined**. Individual operator time includes service wrapper/logging and any wait inside that operator; it is not isolated accelerator kernel time.

## Run and identity

Physical Swan headset `PB311XHGKC220141G`; app `com.pico.spatial.ml.sample.facelandmarker.registrationlab`, debug APK SHA-256 `39861cdf012e99ddfcbb8218dfe5c08a6f28ef00add89915bb0a85753e4906fb`, client PID 10838. SpatialML service `com.bytedance.pico.openmr.spatial`, PID 30721, installed APK SHA-256 `d7a9bdaca7d82b390ba5704a85170f4eaf1ee580fdbc85604cb94388fc94b61b`. The Spatial rendering runtime is a separate package, version `6.3.0.0-master.20261011`. ROM fingerprint is `Pico/swan/swan:16/BQ2A.260122.002-BP2A.250705.008/20261014024400:userdebug/test-keys`. The Kotlin app source uses Spatial BOM 6.1.9; this does not identify the installed ML runtime delegate.

The app was closed at preflight and was launched once. It reported face-bearing, idle tracking before profiling. Three 30-second windows ran in order: tracing off, operator tracing on, tracing off. Session `2026-11-01T00-41-00.133810Z-8b7715`; the artifact timestamp is UTC, while this document uses the host's October 31 local date. Custom mode retained the C values: fx=fy=1746.4713134765625, cx=1623.5, cy=1231.5, revision 0. No One check, Full trial, export, profile edit, APK install, service restart, app-data clear, recording deletion, commit or push was performed.

`debug.pico.spatialml.debug` was temporarily enabled for the middle window; this also enables the service's readback permission bypass. Its original unset value was restored and read back. devmux released the focused lease. The capturer's manifest records successful cleanup.

## Whole-run timing

| Window | Face samples after warm-up | Submit → readback median / p95 | Readback → upload median | Exposure → upload median | Pipeline completions/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline_before | 109 | 225.0 / 239.7 ms | 8.16 ms | 274.9 ms | 4.24 |
| operators | 112 | 245.3 / 255.6 ms | 7.94 ms | 288.7 ms | 3.88 |
| baseline_after | 116 | 235.4 / 260.2 ms | 8.08 ms | 281.4 ms | 4.03 |


The windows contain 365 frame completions, 352 with faces. Five initial completions are excluded independently from each window, leaving 337 ordinary face samples. The first baseline has 13 no-face frames and one sensor-clock rejection; neither later window has a presentation rejection. There are no retained app/ML-service error or GC messages in the operator window. This is a healthy streaming benchmark, not calibration export validation.

The traced median (245.3 ms) is 10–20 ms above the two untraced medians, approximately 4–9%. The untraced medians themselves differ by 10.4 ms, so the run measures an observed tracing penalty range rather than a controlled, exact logging cost. Subjects, motion and load were not fixed. Current HAL thermal status is 0 and cooling-device values are 0 at the metadata snapshots; cached sensor temperatures differ from current HAL values. Those snapshots do not prove absence of transient thermal/scheduling changes during every frame.

## All computation components

The actual Kotlin constructor maps 11 detector/acquisition operations, 20 landmark/fit operations and 8 mesh/output operations. Native trace types confirm the layout, including the installed service's `ARITHMETIC_COMPOSE` spelling. Complete-task filters admitted 109 detector, 109 landmark/fit and 106 mesh tasks after five warm-up tasks per pipeline. Incomplete and boundary tasks remain excluded and counted in `operator-timings.json`.

The table below uses **106 matched dependency chains**, each containing all **39 operators**. The service's decimal `wait_for` explicitly links each fit to its detector task and each mesh to its fit task; task identity includes service/client ownership. Every operation appears once in the component table. Group medians and p95 values are computed from each frame's summed costs, so they are not sums of unrelated percentiles.

| Component | Mean ms | Median ms | p95 ms |
| --- | ---: | ---: | ---: |
| RGB camera, camera values and pose | 12.07 | 11.57 | 16.00 |
| Detector affine, crop, float conversion and normalization | 36.79 | 36.49 | 40.81 |
| Detector inference | 2.27 | 2.02 | 3.68 |
| Detection decode and ROI | 17.63 | 17.37 | 21.09 |
| Producer snapshot | 1.46 | 1.21 | 2.63 |
| Landmark affine, crop, float conversion and normalization | 51.69 | 51.07 | 57.03 |
| Landmark inference | 2.20 | 1.88 | 3.90 |
| Landmark decode and tracking | 9.36 | 9.28 | 11.44 |
| Three covariance / SVD / solve fits | 15.35 | 15.06 | 18.06 |
| Two sparse unprojections | 3.22 | 2.96 | 5.09 |
| Face pose and registration diagnostics | 7.25 | 7.00 | 9.13 |
| Fit snapshot | 5.66 | 5.45 | 7.27 |
| 478-point gather, projection and reconstruction | 21.22 | 21.11 | 25.53 |
| Blendshape normalization and inference | 2.43 | 2.19 | 3.94 |
| Final result packing | 24.57 | 24.15 | 27.52 |
| Mesh snapshot | 20.67 | 20.69 | 22.84 |
| Terminal completion marker | 1.16 | 0.94 | 2.16 |


The matched chains average **239.90 ms** from detector enqueue to final mesh completion (median 239.90, p95 249.02). Operators account for **235.00 ms** and all remaining service elapsed time for **4.90 ms**. That remainder is reconciled into 3.71 ms of within-pipeline gaps, 0.89 ms between dependent pipelines, and 0.30 ms initial queue time. Fit/mesh enqueue waits overlap upstream execution and are not added again.

Overlapping subsets: the affine crop pair is 73.40 ms (30.6% of service-chain elapsed), three models 6.78 ms (2.8%), all snapshots 27.79 ms, and three native SVD calls 0.36 ms. The SVD calls are already included in the fit row. Result packing plus all snapshots costs 52.36 ms.

The complete 39-row table, with means/medians/p95, is [operator-timings.csv](../artifacts/facelandmarker/registration-lab/performance/session-output-20261101-004059/performance-data/operator-timings.csv).

## Readback and host boundary

The trace records 6,939 four-byte terminal-scalar reads and 115 11,976-byte face-result reads, about 60 scalar reads per face-result read over the middle window. In complete unambiguous service handler spans, scalar-read median is 0.214 ms, face-read median 0.195 ms, and acknowledgement median 0.085 ms. Duplicate/missing starts are excluded. These are service handler spans; caller JNI/Binder transport and client scheduling are absent. Polling/handler work overlaps graph execution and cannot be added to its elapsed time.

The 8 ms paired readback/upload interval combines Stage rebase, validation, coroutine/UI scheduling and SDK upload. It does not separate those host leaves or confirm compositor presentation. No image/export/save work was run, so the historical 844 ms export envelope has not been remeasured here.

## Optimization implications and Unity comparison

Image cropping/preprocessing and JavaScript output/snapshot work now have direct Kotlin measurements. The first discriminating measurement should inspect the affine crop implementation/runtime path with CPU and call-stack evidence, retaining the same model inputs and numerical output checks. A subsequent reversible lab experiment can reduce per-frame snapshot work while preserving complete coherent snapshots for selected exports. The measured costs are ceilings on possible savings, not speedup promises. Any change to completion polling must preserve the terminal barrier and exact packet rejection.

The retained Unity XR baseline had inference operators around 2.3 ms each, close to this Kotlin trace's 2.2–2.3 ms means. Its affine preprocessing was much cheaper, but scene, graph, service, detector bytes, trace wrappers and SDK differ. This comparison prioritizes inspecting the crop path; it does not establish a Kotlin regression against an identical baseline. Unity's many-small-node native rewrite regressed overall latency, so it remains unsuitable for a wholesale port. The Kotlin trace does not prove effective NPU use: model-creation/delegate logs were not retained, and `/proc/30721/maps` access was denied. Requested backend 2 alone is insufficient.

Lower tracking latency should reduce motion-dependent registration error. A steady upward/scale alignment offset still needs optical/calibration validation; this performance run does not fit or apply calibration.

## Evidence, validation and remaining gaps

Artifacts: `artifacts/facelandmarker/registration-lab/performance/session-output-20261101-004059/`. The full logs, timeline, before/after metadata, APK/service hashes, layout, window statistics, per-operator CSV/JSON, matched chains and readback handler statistics are retained. Analysis scripts live alongside their inputs. Parser checks against this actual trace pass complete-task filtering, wrong-client isolation, wrong-native-type rejection, missing-operator rejection and duration reconciliation. Python compilation and `git diff --check` pass. The only app-repo code edit is in the host trace analyzer: canonical arithmetic type recognition and retained dependency records; app/graph/runtime code was not changed.

No Perfetto scheduler/Binder transaction/GPU trace, call stacks, compositor present timestamps or model delegate creation record was collected. Runtime resource attribution remains undetermined. Spatial runtime policy messages are retained as opaque signals; their exception integers do not establish missed frames or a rendering bottleneck. There is no configured PerformanceKB backend, and no KB-based diagnosis is made. The bounded whole-pipeline benchmark and component mapping are complete; physical display latency, export leaf costs and calibration accuracy remain outside the measured boundary.
