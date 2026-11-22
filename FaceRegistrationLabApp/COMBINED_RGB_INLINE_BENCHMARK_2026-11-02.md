# Combined RGB-first GPU preprocessing and inline fit — 2026-11-02

Combined **GPU/RGB-first preprocessing + inline fitting + pose/mesh/blendshape outputs**: **157.84 ms median**, **199.18 ms p95** submission through terminal readback, **5.66 completions/s**, with tracing off.

Only this configuration was timed: one 30-second untraced window and one 30-second traced window. 336 completions; 167 untraced eligible faces; 150 complete eligible traced face chains. Five initial frames per window are excluded. All four endpoint probes contain finite pose/expression values, 478 vertices and 52 blendshapes; maximum reconstruction residual 0.000147926 px is a mathematical consistency check, not optical accuracy.

## SpatialML operations in execution order

| # | Operation | Implementation | Mean ms | p95 ms |
| --- | --- | --- | --- | --- |
| 1 | Acquire 3248×2464 RGB, source K and exposure timestamp; installed internal copy phases not separately timed | Native VST operator | 18.01 | 24.68 |
| 2 | Select effective virtual camera intrinsics for the lab | JavaScript | 3.40 | 6.78 |
| 3 | Look up camera pose at the exposure timestamp | Native pose operator | 0.33 | 1.65 |
| 4 | Compose crop affine with the lab image transform | JavaScript | 2.63 | 5.57 |
| 5 | Sample/crop/scale RGB bytes, round sampled pixels and normalize to detector input | Weightless model; GPU | 10.28 | 17.71 |
| 6 | Recover byte-valued diagnostic crop: normalized input × 255 + 0.5 | Native arithmetic; lab diagnostic | 4.70 | 8.61 |
| 7 | Convert recovered crop to uint8 for calibration evidence | Native conversion; lab diagnostic | 6.89 | 10.62 |
| 8 | Infer detector boxes and confidence scores | Trained LiteRT model; NPU requested | 2.80 | 5.25 |
| 9 | Decode detector tensors, select face and construct ROI | JavaScript | 28.16 | 34.38 |
| 10 | Prepare current crop/ROI and update frame/tracking state | JavaScript | 3.43 | 5.98 |
| 11 | Copy producer state into a calibration diagnostic snapshot | JavaScript | 2.67 | 5.43 |
| 12 | Compose crop affine with the lab image transform | JavaScript | 2.47 | 5.61 |
| 13 | Affine sample/crop/scale RGB bytes, round sampled pixels and normalize to landmark input | Weightless model; GPU | 9.22 | 14.28 |
| 14 | Recover byte-valued diagnostic crop: normalized input × 255 + 0.5 | Native arithmetic; lab diagnostic | 4.26 | 7.59 |
| 15 | Convert recovered crop to uint8 for calibration evidence | Native conversion; lab diagnostic | 6.61 | 10.33 |
| 16 | Infer 478 landmark triplets and presence outputs | Trained LiteRT model; NPU requested | 2.69 | 4.47 |
| 17 | Validate landmarks, update tracking ROI, compute depth mean and prepare the 33 fit points | JavaScript | 16.77 | 21.73 |
| 18 | Three sparse fits, inline quaternion/Jacobi rotations, two unprojections, scales and pose | Weightless LiteRT model; CPU requested | 1.61 | 3.31 |
| 19 | Camera-to-world transform, pose checks/filtering and tracker validity feedback | JavaScript | 6.61 | 9.64 |
| 20 | Fit/reprojection/quality diagnostics and invalidity feedback to tracker | JavaScript | 6.28 | 9.53 |
| 21 | Copy sparse fit intermediates into a calibration diagnostic snapshot | JavaScript | 9.78 | 13.06 |
| 22 | Gather 146 XY pairs, undo ROI crop and normalize for expression model | Weightless LiteRT model; CPU requested | 0.44 | 2.13 |
| 23 | Infer 52 expression scores | Trained LiteRT model; NPU requested | 2.84 | 4.94 |
| 24 | Concatenate selected final fields into the 6,332-byte packet | Weightless LiteRT model; CPU requested | 0.31 | 1.34 |
| 25 | Publish terminal completion sequence after the output is ready | JavaScript | 2.55 | 5.54 |


Both preprocessing models execute on OpenCL: detector **48/48** and landmark **68/68** nodes, each in one partition. They sample RGB bytes before normalizing the smaller output. Native arithmetic/conversion afterward reconstructs uint8 crops for lab evidence; these are additional diagnostic copies, not preprocessing inputs for inference.

Inline fitting is CPU FP32. XNNPACK accepts 1,187 of 1,492 nodes in 209 partitions; the remaining nodes use CPU kernels. Covariance, rotations and unprojections stay inside one model call. Trained inference uses Qualcomm dispatch with NPU requested. Pose/quality consumers retain service-side tracker feedback before final publication.

## Scheduling and readback

| Boundary | Mean ms | p95 ms |
| --- | --- | --- |
| All SpatialML operators | 155.73 | 172.95 |
| Within-task overhead | 4.54 | 8.02 |
| Between-task gaps | 2.18 | 4.48 |
| Combined submission / polling / readback remainder | 10.93 | 17.97 |
| Whole traced submission-to-readback | 173.39 | 193.61 |


The first four means sum to the traced whole-frame mean; percentiles are not additive. The final packet remains 6,332 bytes plus a four-byte polling marker and IPC metadata. No intermediate is read back to the app and uploaded to continue SpatialML.

## App computation and rendering

| App-side work | Mean ms | p95 ms |
| --- | --- | --- |
| Kotlin decode / final 478-point mesh reconstruction | 0.77 | 1.82 |
| Kotlin Stage registration / frame checks | 1.29 | 2.53 |
| Readback through mesh-upload acknowledgement, inclusive | 19.12 | 26.33 |
| Camera exposure through mesh-upload acknowledgement | 212.12 | 250.90 |


The inclusive readback-to-upload interval contains decode/reconstruction and registration. Dense-mesh reconstruction is compiled Kotlin; sparse fitting stays in SpatialML.

## Evidence and limits

Device PB311XHGKC220141G; Registration Lab; APK `8d0988345a7a83bd656788bff689ad853b96bab22c9f1a6bdc06c4f3be769625`. Flags: `faceInlineGeometry=true`, `faceGpuPreprocessing=true`, `faceGpuSampleBytes=true`, split flag false. Complete successful ordered operator signatures, client/service ownership, exact task dependencies and unique clock-aligned journal matches define the traced population. Clock anchors: 9; spread 5.258 ms; unmatched complete chains: 0. Thermal snapshots: `[{"label": "before", "status": ["Thermal Status: 2"]}, {"label": "combined", "status": ["Thermal Status: 2"]}, {"label": "restored", "status": ["Thermal Status: 2"]}, {"label": "final", "status": ["Thermal Status: 2"]}]`.

- No old configuration or previous performance check was rerun; no controlled comparative speedup is claimed.
- Operator statistics use the same traced eligible chains; untraced latency is a separate population.
- GPU model timings include wrappers, buffer access/transfers and invocation, not isolated kernel time. Individual VST copy, memcpy and Binder durations remain unmeasured.
- The lab retains native diagnostic crop reconstruction and producer/fit snapshots; their cost is included.
- Mesh-upload acknowledgement is not compositor presentation. Normals, bounds, SDK replacement and scheduling are not separately measured.
- No new optical calibration, controlled device pixel replay, invalid-face recovery or mode-switch sweep was run. Existing host model and graph validation was reused.
- No scheduler/Binder/compositor/CPU-GPU-counter trace; hardware bottleneck remains unassigned.

## Final state

Original APK `7ae804e2e3606d81eb7c2ab64f649abad940731d1feab5a7578d68afd99ef023` restored/hash-verified; debug flag and output mask 1 restored. Final frame 48 has a face and the camera is running. Camera calibration hash is unchanged; all 286 pre-existing external files remain present/nonshrinking. Lease released. SpatialML was restarted once for GPU initialization; no service/SDK replacement, data clear, recording deletion, new calibration capture, commit or push.

The combined APK was assembled and its model hashes/flags verified. Prior performance and numerical suites were not repeated. Host Gradle output was restored to its default configuration. Raw logs, journals, captured graph layout, APK/build manifest, delegation evidence, CSVs and reproducible analysis are under `artifacts/facelandmarker/combined-rgb-inline-20261102/session-output-20261102-152817/`.
