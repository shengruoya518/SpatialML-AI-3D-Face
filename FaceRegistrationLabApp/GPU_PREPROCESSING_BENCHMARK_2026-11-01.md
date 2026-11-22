# GPU preprocessing benchmark — 2026-11-01

Face-present follow-up: [GPU_PREPROCESSING_FACE_BENCHMARK_2026-11-01.md](GPU_PREPROCESSING_FACE_BENCHMARK_2026-11-01.md) records a fresh run after the user-requested service reset, with 18.1–22.1% lower observed GPU latency and all 39 operator changes. The numbers below retain the earlier no-face population.

The integrated GPU build reduced **observed no-face submission-to-completed-readback latency from 203–206 ms median to 153.49 ms**, a **24–25% reduction**. Pipeline throughput rose from **4.59–4.64 to 5.98 completions/s**, a **29–30% increase**. All 652 journal completions across the five windows reported no face. This is a no-face graph/runtime benchmark; it does not establish face-tracking accuracy, the performance of a rotated detected-face crop, calibration readiness, or display refresh rate.

| Window, tracing off | Eligible no-face frames | Submit → readback median | p95 | Pipeline completions/s |
| --- | ---: | ---: | ---: | ---: |
| native-baseline | 132 | 205.57 ms | 217.48 ms | 4.59 |
| gpu-baseline | 175 | 153.49 ms | 164.72 ms | 5.98 |
| native-after | 134 | 203.03 ms | 212.57 ms | 4.64 |


Thirty-second tracing-off windows ran native → GPU → restored native; twenty-second operator traces were also collected for native and GPU. Five initial completions are excluded independently per window. Readback distributions additionally exclude unfresh or rejected/out-of-domain sensor frames. Cadence counts all pipeline work in the window, including rejected frames, rather than hiding their cost. One native-baseline and two GPU-operator frames had a sensor-clock rejection; the GPU trace contains corresponding empty-camera-image messages. Native p95 is 212.57–217.49 ms versus GPU 164.72 ms. Scene upload acknowledgement is not final display presentation.

## Computation changes

| Measured preprocessing piece, tracing on | Native mean | GPU-build mean | Change |
| --- | ---: | ---: | ---: |
| Detector crop → GPU preprocessing model | 28.87 ms | 9.74 ms | -19.13 ms |
| Landmark crop → GPU preprocessing model | 43.40 ms | 9.76 ms | -33.64 ms |
| Whole detector preprocessing, including byte export copy | 36.30 ms | 17.72 ms | -18.58 ms |
| Whole landmark preprocessing, including byte export copy | 50.83 ms | 18.26 ms | -32.57 ms |


The paired sums inside each complete service task produce the whole-preprocessing means; no medians/p95 values are added across unrelated tasks. Native traces admit 74 detector, 73 landmark/fit and 73 mesh tasks after five warm-up tasks per pipeline. GPU traces admit 95/93/94 tasks. The complete current constructor and native operator types map each pipeline. The expensive native warp calls disappear from these two paths and are replaced by the two GPU model operators. The lab keeps native normalized-to-byte arithmetic/Assignment copies for export evidence, so outer graph count remains 39.

Whole preprocessing averages approximately **87.13 ms native versus 35.97 ms GPU-build**, about **51.15 ms less** across detector and landmark paths. These are sums of the task-level component means from separate complete-task populations; the direct A/B median latency reduction is reported independently. Model calls include service wrapper, GPU execution/transfer and debug logging; they are not isolated GPU kernel timings. Trained detector/landmark model means remain around 2.1–2.4 ms. The no-face pack operation is around 6 ms, unlike the prior face-bearing benchmark's 24.6 ms; do not transfer the no-face speedup into a face-bearing latency prediction.

The traced app median is 219.25 ms native versus 172.52 ms GPU on eligible no-face frames, around 21% lower. Tracing therefore remains a diagnostic mode, not the production benchmark. Untraced exposure age at upload is approximately 242–244 ms native versus 189 ms GPU, approximately 54 ms less for this population.

## Device execution evidence

Headset `PB311XHGKC220141G`, ROM `Pico/swan/swan:16/BQ2A.260122.002-BP2A.250705.008/20261014024400:userdebug/test-keys`; host date November 1, device local date November 2. Native APK SHA-256 `39861cdf012e99ddfcbb8218dfe5c08a6f28ef00add89915bb0a85753e4906fb`. GPU APK SHA-256 `ac8dea700da644fbd89848937eb479d1fbd3a465ac8492dc60a7d22d90b74bc7`. GPU app PID 24638 and SpatialML service PID 30721 are recorded in the capture. Virtual calibration remains Custom/C, fx=fy=1746.4713134765625, cx=1623.5, cy=1231.5, revision 0.

The GPU startup log records `Initializing OpenCL-based API from graph` next to creation of both preprocessing model operators with backend GPU. The trained models record Qualcomm DispatchDelegate partitions. These are executing-runtime facts from this run, not an inference from the backend integer alone. No unsupported-op/CPU-fallback message was found for the two preprocessing graphs in the startup/operator windows. Absence of such a message is not pixel-validity proof or hardware-kernel profiling.

Android service execution of the integrated uint8 model path completed the benchmark; the earlier Mac input-buffer error is therefore a host-path limitation, not evidence that this app path cannot execute on Android. Exact transfer/sampling correctness remains unresolved.

Thermal status was 0 at the three recorded metadata snapshots. Snapshot thermal/load state is not a controlled time-series experiment. The two native baseline medians differ by 2.54 ms, while the GPU delta is roughly 50–52 ms. That supports a repeatable effect within this run, without establishing a universal speedup.

## Controlled pixel validation and restoration

A test-only instrumentation probe was added to compare both GPU models with native ApplyAffine and normalization on one owned deterministic RGB source. Its inputs are synthetic; it does not save a wearer calibration or automatic capture. The first isolated-context attempt failed during model creation before any comparison case. A second attempt after initializing the Full Space app failed at the same boundary, with service `LiteRt create input buffer failed`/`Unable to initialize LiteRT model and runtime` messages. **No controlled pixel comparison completed**, and neither attempt is counted as an accuracy pass. The exact difference between the working benchmark graph and isolated validation setup is unresolved; no service-root-cause claim is made.

The diagnostic source and both attempts' logs/results are retained. The implementation adds a typed float-image allocation option for controlled output tensors and an AndroidTest-only instrumentation runner/compile-only public bindings. App UI, calibration candidates, decode, snapshots and completion logic are unchanged. Probe build/lint/format checks pass. No service APK or SDK was modified.

The original native APK and original unset debug property were restored after both tests. All 247 original external app files remain, and the private optical calibration hash is unchanged. The temporary test APK remains installed; nothing was uninstalled or deleted. One subsequent native launch stopped on camera freshness after test/session teardown. An app-only recovery is recorded in `native-recovery.json`; final recovery healthy status is **True**. Device lease release and restoration are recorded separately from the benchmark result.

## Decision and next measurement

Keep GPU preprocessing behind its validation-build flag. The measured no-face performance gain is promising, but promotion requires a working controlled pixel test and a face-present native/GPU/native comparison with coherent exports. State/clock-sensitive decode and the 264-byte producer snapshot remain unchanged. The existing tensor feasibility study for decode remains a future candidate; this run did not measure a decode-model replacement.

Artifacts: `artifacts/facelandmarker/registration-lab/gpu-benchmark-20261101-181528/`, including complete logs, journals, filtered populations, operator timings, install/hash/data-preservation records and controlled-probe failure evidence. `analyze_benchmark.py` and the staged metrics reproduce the measurements. No commit or push was made.
