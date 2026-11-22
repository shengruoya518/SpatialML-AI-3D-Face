# Face-present GPU preprocessing benchmark after service reset — 2026-11-01

Detailed follow-up: [preprocessing and camera acquisition breakdown](PREPROCESSING_ACQUISITION_BREAKDOWN_2026-11-01.md) separates the ~10 ms GPU calls from lab export copies and breaks camera acquisition into VST, lab K and timestamped pose operators.

The GPU preprocessing build completed the face-present benchmark. Observed submission-to-completed-readback median was **186.14 ms GPU versus 227.33–239.06 ms native**, **18.1–22.1% lower**. Pipeline throughput was **4.98 completions/s**, **20.0–25.3% higher** than the native windows.

| Build/window, tracing off | Eligible face frames | Submit → completed readback median | p95 | Pipeline completions/s |
| --- | ---: | ---: | ---: | ---: |
| native-baseline | 121 | 227.33 ms | 236.56 ms | 4.15 |
| gpu-baseline | 146 | 186.14 ms | 210.81 ms | 4.98 |
| native-after | 115 | 239.06 ms | 257.24 ms | 3.97 |


Thirty-second tracing-off native/GPU/native windows and twenty-second native/GPU operator windows are bounded by app frame numbers. The two earlier face-present GPU attempts failed before processing frames with LiteRT input-buffer/model-initialization errors. The user then requested stopping both OpenMR packages, followed by this measurement. This fresh run starts after that explicit service reset; it does not include the earlier no-face timings or reuse earlier native windows.

## Population and timing boundary

| Window | All completions | Face completions | Warm-up excluded | Eligible face completions |
| --- | ---: | ---: | ---: | ---: |
| native-baseline | 126 | 126 | 5 | 121 |
| native-operators | 78 | 78 | 5 | 73 |
| gpu-baseline | 151 | 151 | 5 | 146 |
| gpu-operators | 96 | 96 | 5 | 91 |
| native-after | 121 | 120 | 5 | 115 |


Five initial completions are excluded independently per window. Face latency additionally requires a fresh, unrejected frame within the sensor-clock domain. Cadence counts all consumed work after warm-up, including rejected/no-face work, so rejection costs are retained. Every measurement here comes from the lab's terminal completion barrier; upload acknowledgement is a separate app/SDK boundary and is not compositor presentation or display refresh rate.

After-warm-up exclusions can overlap:

- native-baseline: {"noFace": 0, "unfresh": 0, "rejections": {}, "outsideSensorDomain": 0}.
- native-operators: {"noFace": 0, "unfresh": 0, "rejections": {}, "outsideSensorDomain": 0}.
- gpu-baseline: {"noFace": 0, "unfresh": 0, "rejections": {}, "outsideSensorDomain": 0}.
- gpu-operators: {"noFace": 0, "unfresh": 0, "rejections": {}, "outsideSensorDomain": 0}.
- native-after: {"noFace": 1, "unfresh": 1, "rejections": {"Waiting for a sensor camera timestamp\u2026": 1}, "outsideSensorDomain": 1}.

The subject moves naturally; images and face orientation are not identical across sequential windows. Face presence alone does not prove equivalent sampling, geometry accuracy or marker alignment. The operator trace may include occasional no-face frames; the population table makes those counts explicit.

## Computation across the pipeline

| Component, tracing on | Native mean | GPU-build mean | Change |
| --- | ---: | ---: | ---: |
| RGB camera, camera values and pose | 12.48 ms | 12.72 ms | +0.24 ms |
| Detector affine, crop, conversion and normalization | 36.42 ms | 18.44 ms | -17.98 ms |
| Detector inference | 2.53 ms | 2.38 ms | -0.15 ms |
| Detection decode and ROI | 17.90 ms | 18.22 ms | +0.31 ms |
| Producer snapshot | 1.43 ms | 1.53 ms | +0.10 ms |
| Landmark affine, crop, conversion and normalization | 52.21 ms | 17.87 ms | -34.34 ms |
| Landmark inference | 2.19 ms | 2.17 ms | -0.02 ms |
| Tracking and geometry fits | 31.88 ms | 32.74 ms | +0.86 ms |
| Registration diagnostics | 3.33 ms | 3.63 ms | +0.30 ms |
| Fit snapshot | 5.63 ms | 5.86 ms | +0.24 ms |
| Mesh projection, unprojection and conversion | 21.76 ms | 22.53 ms | +0.77 ms |
| Blendshape inference | 2.22 ms | 2.29 ms | +0.06 ms |
| Result packing | 24.67 ms | 25.43 ms | +0.76 ms |
| Mesh snapshot | 21.15 ms | 21.04 ms | -0.11 ms |
| Terminal completion marker | 1.09 ms | 1.07 ms | -0.01 ms |


The two complete-task preprocessing groups total **88.63 ms native versus 36.31 ms GPU**, **52.32 ms less** in the traced population. This sum of group means is separate from the directly observed end-to-end median; task medians and p95 values are never added.

| Crop/model operator, tracing on | Native mean | GPU model mean |
| --- | ---: | ---: |
| Detector | 28.71 ms | 9.78 ms |
| Landmark | 44.44 ms | 9.98 ms |


native: complete task counts {'mesh': 65, 'detector': 66, 'landmark_fit': 65}; explicitly linked detector → fit → mesh chains 64, elapsed mean 241.73 ms. gpu: complete task counts {'mesh': 81, 'landmark_fit': 80, 'detector': 82}; explicitly linked detector → fit → mesh chains 79, elapsed mean 192.75 ms. Complete successful service tasks require all expected operator starts/completions, matching native types and correct task bounds. Five complete tasks are excluded per pipeline. Groups sum operators within each complete task. Downstream `wait_for` values use decimal IDs while task identifiers are hexadecimal; the analysis normalizes the IDs before joining dependencies. Enqueue wait includes upstream work and is not added again to execution totals.

The lab still exports reconstructed byte crops through native arithmetic/Assignment and keeps 39 outer operators. GPU model operator timings include service wrapper, execution/transfer and trace overhead. These are not isolated GPU kernel timings. Decode/ROI, the 264-byte producer snapshot and the geometry/snapshot/packet paths retain their existing implementation; their measurements describe current costs rather than a deployed GPU/NPU fusion.

## Change for every service operator

| Pipeline / element | Native index | GPU index | Native mean | GPU mean | Change | Change % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| detector / RectifiedVSTAccess | 0 | 0 | 9.906 ms | 10.25 ms | +0.342 ms | +3.4% |
| detector / lab_camera | 1 | 1 | 2.332 ms | 2.31 ms | -0.026 ms | -1.1% |
| detector / CameraSpaceToWorld | 2 | 2 | 0.243 ms | 0.17 ms | -0.075 ms | -30.8% |
| detector / lab_affine | 3 | 3 | 1.540 ms | 1.63 ms | +0.085 ms | +5.5% |
| detector / ApplyAffine → detector_preprocess_gpu | 4 | 4 | 28.708 ms | 9.78 ms | -18.930 ms | -65.9% |
| detector / Assignment | 5 | 6 | 3.913 ms | 4.57 ms | +0.657 ms | +16.8% |
| detector / Arithmetic | 6 | 5 | 2.256 ms | 2.46 ms | +0.208 ms | +9.2% |
| detector / face_detector | 7 | 7 | 2.533 ms | 2.38 ms | -0.149 ms | -5.9% |
| detector / decode_detection | 8 | 8 | 15.723 ms | 16.21 ms | +0.485 ms | +3.1% |
| detector / prepare_roi | 9 | 9 | 2.181 ms | 2.01 ms | -0.171 ms | -7.8% |
| detector / lab_frame_snapshot | 10 | 10 | 1.434 ms | 1.53 ms | +0.100 ms | +7.0% |
| landmark_fit / lab_affine | 0 | 0 | 1.575 ms | 1.33 ms | -0.243 ms | -15.4% |
| landmark_fit / ApplyAffine → landmark_preprocess_gpu | 1 | 1 | 44.437 ms | 9.98 ms | -34.458 ms | -77.5% |
| landmark_fit / Assignment | 2 | 3 | 3.999 ms | 4.07 ms | +0.073 ms | +1.8% |
| landmark_fit / Arithmetic | 3 | 2 | 2.199 ms | 2.49 ms | +0.289 ms | +13.2% |
| landmark_fit / face_landmarks_detector | 4 | 4 | 2.191 ms | 2.17 ms | -0.019 ms | -0.9% |
| landmark_fit / track_landmarks | 5 | 5 | 9.715 ms | 9.97 ms | +0.256 ms | +2.6% |
| landmark_fit / geometry_covariance | 6 | 6 | 2.626 ms | 2.93 ms | +0.307 ms | +11.7% |
| landmark_fit / SVD | 7 | 7 | 0.160 ms | 0.15 ms | -0.013 ms | -7.9% |
| landmark_fit / geometry_solve | 8 | 8 | 2.432 ms | 2.26 ms | -0.167 ms | -6.9% |
| landmark_fit / geometry_unproject | 9 | 9 | 1.522 ms | 1.56 ms | +0.040 ms | +2.6% |
| landmark_fit / geometry_covariance | 10 | 10 | 2.641 ms | 2.71 ms | +0.067 ms | +2.5% |
| landmark_fit / SVD | 11 | 11 | 0.088 ms | 0.13 ms | +0.038 ms | +42.9% |
| landmark_fit / geometry_solve | 12 | 12 | 2.403 ms | 2.56 ms | +0.152 ms | +6.3% |
| landmark_fit / geometry_unproject | 13 | 13 | 1.431 ms | 1.59 ms | +0.155 ms | +10.8% |
| landmark_fit / geometry_covariance | 14 | 14 | 2.323 ms | 2.41 ms | +0.084 ms | +3.6% |
| landmark_fit / SVD | 15 | 15 | 0.106 ms | 0.12 ms | +0.009 ms | +8.4% |
| landmark_fit / geometry_solve | 16 | 16 | 2.515 ms | 2.45 ms | -0.062 ms | -2.5% |
| landmark_fit / face_pose | 17 | 17 | 3.918 ms | 3.91 ms | -0.008 ms | -0.2% |
| landmark_fit / registration_diagnostics | 18 | 18 | 3.333 ms | 3.63 ms | +0.301 ms | +9.0% |
| landmark_fit / lab_geometry_snapshot | 19 | 19 | 5.625 ms | 5.86 ms | +0.236 ms | +4.2% |
| mesh / mesh_landmarks | 0 | 0 | 6.687 ms | 6.90 ms | +0.215 ms | +3.2% |
| mesh / geometry_project | 1 | 1 | 9.339 ms | 9.64 ms | +0.305 ms | +3.3% |
| mesh / geometry_unproject | 2 | 2 | 5.627 ms | 5.86 ms | +0.235 ms | +4.2% |
| mesh / Arithmetic | 3 | 3 | 0.111 ms | 0.13 ms | +0.015 ms | +13.9% |
| mesh / face_blendshapes | 4 | 4 | 2.224 ms | 2.29 ms | +0.061 ms | +2.7% |
| mesh / pack_service_result | 5 | 5 | 24.669 ms | 25.43 ms | +0.758 ms | +3.1% |
| mesh / lab_geometry_snapshot | 6 | 6 | 21.150 ms | 21.04 ms | -0.109 ms | -0.5% |
| mesh / lab_capture_marker | 7 | 7 | 1.085 ms | 1.07 ms | -0.013 ms | -1.2% |


The CSV also retains native/GPU median, p95 and task counts. Semantic matching preserves the two byte-copy operator identities even though their indices swap between builds. Repeated geometry operators are matched by occurrence in their pipeline. Values below one millisecond are retained; percentage changes on these small durations should be interpreted with trace/logging variation in mind.

## End-to-end boundaries beyond the graph

| Measured boundary, eligible face population | Native before median | GPU median | Native after median | GPU change vs native before |
| --- | ---: | ---: | ---: | ---: |
| Exposure → submission | 37.06 ms | 31.45 ms | 36.92 ms | -5.61 ms |
| Submission → terminal readback | 227.33 ms | 186.14 ms | 239.06 ms | -41.18 ms |
| Exposure → terminal readback | 266.00 ms | 220.01 ms | 278.96 ms | -45.99 ms |
| Terminal readback → scene upload acknowledgement | 8.32 ms | 8.70 ms | 9.07 ms | +0.38 ms |
| Exposure → scene upload acknowledgement | 275.44 ms | 227.51 ms | 289.38 ms | -47.94 ms |


Each boundary has its own paired face population; differences are computed directly and boundary medians are not added. Graph upload/transport leaf costs, GPU kernel/transfer decomposition and actual compositor/display presentation remain unmeasured.

## Runtime and accuracy boundaries

Headset: `PB311XHGKC220141G`; ROM: `Pico/swan/swan:16/BQ2A.260122.002-BP2A.250705.008/20261014024400:userdebug/test-keys`. Native APK SHA-256: `39861cdf012e99ddfcbb8218dfe5c08a6f28ef00add89915bb0a85753e4906fb`. Tested GPU APK SHA-256: `ac8dea700da644fbd89848937eb479d1fbd3a465ac8492dc60a7d22d90b74bc7`. Native ready metadata, GPU startup metadata, final metadata and all process inventories are retained. Calibration values and revision are recorded in every window's status; no profile or calibration candidate was changed.

The full runtime ring and filtered `runtime-delegate-evidence.txt` retain actual GPU creation evidence: the detector's 49/49 nodes and landmark preprocessing's 69/69 nodes each become a single LITERT_CL partition and initialize OpenCL. Both occur in the new service process after the reset; backend integer 1 alone is not execution proof. The shorter startup dump begins after these creation messages. Trained-model Qualcomm delegate messages are reported separately. The retained error-evidence file contains any buffer/model errors found in this run's startup capture.

The earlier controlled synthetic pixel probe failed before comparison and remains unresolved. This timing run does not repeat that probe or validate pixels, immutable export packets, the physical optical fit or Full trial readiness. Keep `faceGpuPreprocessing` behind its experimental flag until those checks pass. Subject, camera and thermal/load state are not a controlled time-series experiment. No caller Binder transaction, CPU scheduling, GPU kernel, or compositor trace was collected, so binding-resource/root-cause attribution remains undetermined.

## Restoration and retained evidence

Original APK restored=True; native startup healthy=True; original debug property restored=True; original external files preserved=True; private calibration hashes preserved=True; device lease released=True.

All existing recordings and app/private calibration data are retained. Only the app builds and temporary debug property were changed during this measurement; the prior service stop was explicitly user requested. No service APK/SDK change, clear, uninstall, commit or push occurred.

Artifacts: `artifacts/facelandmarker/registration-lab/gpu-face-reset-benchmark-20261101-184143/`. `compare_pipeline.py`, `analyze_benchmark.py` and `write_report.py` reproduce capture/analysis/report construction. Raw logs/journals, filtered windows, complete task chains, all-operator CSV, component distributions and restoration provenance are retained.
