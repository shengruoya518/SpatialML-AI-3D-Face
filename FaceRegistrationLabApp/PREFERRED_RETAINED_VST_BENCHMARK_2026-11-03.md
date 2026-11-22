# Preferred retained-VST face pipeline benchmark — 2026-11-03

The preferred **same-exposure retained VST + bounded landmark tile + GPU RGB-first landmark preprocessing + inline geometry** configuration measured **145.01 ms median**, **156.03 ms p95** submission-to-terminal-readback latency and **6.29 completions/s** with tracing disabled.

Against the existing combined GPU/RGB-first/inline baseline, this is:

| Tracing-off face metric | Existing combined baseline | Preferred retained GPU | Change |
| --- | ---: | ---: | ---: |
| Median submission to readback | 157.84 ms | 145.01 ms | **−12.83 ms (−8.1%)** |
| p95 submission to readback | 199.18 ms | 156.03 ms | **−43.15 ms (−21.7%)** |
| Completion cadence | 5.66 Hz | 6.29 Hz | **+0.63 Hz (+11.2%)** |

The native/CPU landmark preprocessing candidate measured **210.28 ms median**, **243.20 ms p95** and **4.37 completions/s**. Within this run, the GPU candidate is 65.27 ms (31.0%) lower at the median, 87.17 ms (35.8%) lower at p95 and 43.9% higher in cadence. The candidates were measured sequentially, CPU then GPU, with one 30-second tracing-off and one 30-second tracing-on window each; this is not a repeated randomized experiment.

## Pipeline that was measured

1. `RetainedVSTAccess` acquires one 3248×2464 left-camera exposure, retains its hardware buffer, and directly emits the 256×256 RGB detector image, full-resolution intrinsics, exposure timestamp and a retained-frame token.
2. Detector conversion, inference, decode and tracking stay inside SpatialML. No detector intermediate is read back to the app.
3. `RetainedVSTRoi` uses the detector affine and token to copy only a bounded, zero-padded 768×768 RGB tile from that same retained exposure and adjusts the affine into tile coordinates.
4. The CPU candidate uses native `ApplyAffine` plus conversion/normalization. The GPU candidate uses the separate weightless RGB-first tile model. The GPU wrapper still copies Engine tensors into delegate buffers and copies model output back; this run does not claim zero-copy GPU texture binding.
5. Landmark inference, tracking, inline geometry fitting, pose, diagnostics and blendshapes remain inside SpatialML. Only the final 6,332-byte pose + mesh + blendshape packet is read back to the app.

The full 3248×2464×3 graph image tensor (24,009,216 bytes) is absent from the retained graph. The bounded tile is 768×768×3 RGB8 (1,769,472 bytes), a 92.6% reduction in the graph image payload passed into landmark preprocessing. Host ROI/model validation preceded this run; device optical/calibration parity remains a separate acceptance boundary.

## Measurement populations

Five warm-up frames are excluded from every window.

| Candidate | Tracing-off eligible face frames | No-face / unfresh frames | Exact traced face chains | Unmatched complete chains | Clock anchors / spread |
| --- | ---: | ---: | ---: | ---: | ---: |
| Native/CPU tile preprocessing | 128 | 0 / 0 | 117 | 0 | 7 / 2.393 ms |
| GPU tile preprocessing | 186 | 0 / 0 | 132 | 0 | 7 / 1.241 ms |

Every admitted tracing-off frame had a face, a fresh camera exposure, schema 2, output mask 7, exactly 6,332 readback bytes and no calibration-evidence payload. Traced rows require one complete successful typed operator sequence, one service/client owner pair, exact wait-for dependencies through detector → landmark/fit → expressions → output, and a unique clock-aligned journal frame.

## Preprocessing result

The bounded ROI transfer is cheap. The native affine on the 768 tile is not.

| Traced block | Native/CPU mean | GPU mean | Interpretation |
| --- | ---: | ---: | --- |
| Retained VST acquire + detector sample | 45.52 ms | 50.42 ms | Includes waiting for/acquiring an exposure and the direct detector sample; internal wait, buffer copy and sample phases are not separately instrumented. |
| Detector byte-to-float + normalize | 9.57 ms | 10.62 ms | Same native conversion path in both candidates. |
| Copy/adjust retained landmark tile | 1.46 ms | 2.82 ms | Only the bounded 768×768 RGB tile is materialized. |
| Complete landmark preprocessing block | 78.55 ms | 20.07 ms | ROI plus native or GPU sampling and the lab diagnostic conversion path. GPU saves **58.48 ms (74.4%)** in the traced mean. |
| Sampling operation alone | 67.45 ms native `ApplyAffine` | 5.04 ms GPU model | The GPU model's p95 is 12.07 ms and includes wrapper copies plus invocation. |

The weightless landmark model delegated **68/68 nodes to one OpenCL partition**. There is intentionally no detector preprocessing model: the retained VST operator already produces detector-sized RGB, followed only by byte-to-float conversion and normalization.

## SpatialML operations in execution order

These are tracing-on exact-chain statistics. Means and p95 values are per operation; percentiles are not additive. The GPU trace contains one long full-chain outlier (759.79 ms), so tracing-off end-to-end distributions above are the primary user-path result.

| # | Operation and implementation | CPU mean | CPU p95 | GPU mean | GPU p95 |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Compose detector affine with lab transform — JavaScript | 4.01 | 8.24 | 5.56 | 11.30 |
| 2 | Retain exposure and directly sample 256×256 detector RGB — native retained-VST operator | 45.52 | 49.74 | 50.42 | 60.25 |
| 3 | Select effective lab intrinsics — JavaScript | 2.57 | 4.41 | 3.00 | 5.95 |
| 4 | Resolve camera pose at exposure timestamp — native pose operator | 0.14 | 0.28 | 1.04 | 0.34 |
| 5 | Convert detector RGB bytes to float — native assignment | 6.00 | 7.71 | 6.96 | 10.85 |
| 6 | Normalize detector pixels to 0…1 — native arithmetic | 3.57 | 5.52 | 3.66 | 6.23 |
| 7 | Infer detector boxes/scores — trained LiteRT, NPU requested | 2.44 | 3.98 | 2.93 | 5.40 |
| 8 | Decode detector tensors and construct ROI — JavaScript | 23.78 | 27.34 | 27.30 | 36.76 |
| 9 | Update ROI and tracking state — JavaScript | 3.07 | 4.71 | 3.59 | 6.20 |
| 10 | Copy producer calibration snapshot — JavaScript diagnostic | 2.25 | 4.23 | 2.36 | 4.82 |
| 11 | Compose landmark affine with lab transform — JavaScript | 2.28 | 4.52 | 2.83 | 6.29 |
| 12 | Copy bounded retained-frame tile and adjust affine — native retained-VST ROI | 1.46 | 3.32 | 2.82 | 4.77 |
| 13 | Sample landmark crop — native `ApplyAffine` / weightless OpenCL model | 67.45 | 72.22 | 5.04 | 12.07 |
| 14 | Native path: bytes→float / GPU path: recover diagnostic bytes — native | 6.17 | 8.42 | 5.23 | 9.89 |
| 15 | Native path: normalize / GPU path: diagnostic uint8 conversion — native | 3.47 | 5.04 | 6.98 | 11.32 |
| 16 | Infer 478 landmarks and presence — trained LiteRT, NPU requested | 2.57 | 4.54 | 3.27 | 6.63 |
| 17 | Validate landmarks, update tracking and prepare 33 fit points — JavaScript | 14.44 | 17.63 | 17.19 | 24.58 |
| 18 | Three inline fits, rotations, unprojections, scales and pose — weightless CPU model | 1.26 | 2.53 | 2.43 | 8.62 |
| 19 | Transform/filter pose and feed tracker validity — JavaScript | 5.90 | 7.91 | 6.89 | 10.44 |
| 20 | Fit/reprojection diagnostics and tracker feedback — JavaScript | 5.55 | 7.61 | 5.84 | 9.09 |
| 21 | Copy sparse fit calibration evidence — JavaScript diagnostic | 8.69 | 10.87 | 9.53 | 12.81 |
| 22 | Gather/normalize expression inputs — weightless CPU model | 0.23 | 0.60 | 0.26 | 0.76 |
| 23 | Infer 52 blendshapes — trained LiteRT, NPU requested | 2.70 | 4.79 | 3.26 | 6.28 |
| 24 | Pack pose, mesh and blendshapes into final packet — weightless CPU model | 0.20 | 0.47 | 0.29 | 0.90 |
| 25 | Publish terminal completion sequence — JavaScript | 2.03 | 4.21 | 2.61 | 5.31 |

The current GPU trace's largest remaining mean costs are retained VST acquisition/sample (50.42 ms), JavaScript detector decode/ROI construction (27.30 ms), JavaScript landmark tracking/preparation (17.19 ms), sparse diagnostic snapshot copy (9.53 ms), and the two GPU diagnostic-crop recovery operations together (12.21 ms). The detector pipeline is now the larger traced stage: 106.82 ms mean versus 68.05 ms for landmark/fit. Stage sums are descriptive means, not same-frame percentiles.

## Scheduling, app work and exposure age

| Tracing-on exact-chain boundary | CPU mean / p95 | GPU mean / p95 |
| --- | ---: | ---: |
| All SpatialML operators | 217.76 / 228.85 ms | 181.29 / 229.19 ms |
| Within-task overhead | 3.31 / 5.30 ms | 3.81 / 6.44 ms |
| Between-task gaps | 1.70 / 3.84 ms | 1.82 / 3.72 ms |
| Submission/polling/readback remainder | 8.33 / 12.71 ms | 14.20 / 29.82 ms |
| Whole traced submission to readback | 231.09 / 242.47 ms | 201.12 / 265.19 ms |

| Tracing-off app/exposure boundary | CPU mean / p95 | GPU mean / p95 |
| --- | ---: | ---: |
| Kotlin packet decode + mesh reconstruction | 0.61 / 1.12 ms | 0.56 / 1.01 ms |
| Kotlin registration/frame checks | 1.21 / 2.67 ms | 1.06 / 1.94 ms |
| Readback through mesh-upload acknowledgement | 16.60 / 23.16 ms | 14.62 / 19.77 ms |
| Camera exposure through mesh-upload acknowledgement | 265.16 / 295.69 ms | 187.92 / 205.01 ms |

Mesh upload acknowledgement is not compositor presentation. No Perfetto scheduler/Binder/GPU-counter capture was taken, so the retained VST operator's 45–50 ms cannot yet be divided into camera wait, hardware-buffer access, RGBA/RGB materialization, affine sampling and service scheduling.

## What the result supports

- Keep the bounded retained-frame architecture: it guarantees detector/landmark exposure identity and avoids the 24.0 MB full RGB graph tensor. `RetainedVSTRoi` itself is only 1.46–2.82 ms mean in these traces.
- Use the GPU tile preprocessing model, not native `ApplyAffine`, in this service implementation. The CPU candidate loses about 58.5 ms inside the comparable landmark preprocessing block.
- The next optimization target is `RetainedVSTAccess`, followed by JavaScript detector decode and landmark tracking. Splitting the native operator into camera-wait, buffer-map/copy, color-conversion and sample timers would identify whether the next change belongs in VST output, retained-buffer handling or sampling.
- Lab-only diagnostics remain material: GPU crop recovery is 12.21 ms mean and the producer/geometry snapshots are 11.89 ms mean combined. They must remain for calibration builds, but should stay absent from a production face-tracking graph.

The result does **not** prove direct DynamicTexture/LiteRT buffer sharing or optical equivalence. The LiteRT wrapper still performs input/output copies; the GPU model call includes those transfers. It also does not establish that the 8.1% median improvement over the earlier combined run is entirely architectural: the preferred run used a new service APK, a different capture session and no repeated baseline control.

## Final state and evidence

Device `PB311XHGKC220141G`, expected Swan fingerprint. Host date November 3; headset log date November 4 UTC. Thermal status was 0 at the initial/CPU/GPU snapshots and 1 after restoration; no thermal-throttling cause is inferred.

- Candidate service: `ee34ebec4927b2cb44ff96af993a7f1a4a790ee973126f0a0835514c5ef95124`.
- CPU candidate: `6c720a0b30f22e6c68f9ac5aab6ad2fd214e3283d5e23029b13a7fc3d90a2ae7`.
- GPU candidate: `f522a1480e97f1e474bb5f3cbf71e784b0712a30c0307829e8f7e3fa9886c477`.
- Original app `7ae804e2e3606d81eb7c2ab64f649abad940731d1feab5a7578d68afd99ef023` restored and hash-verified.
- Original SpatialML service `d7a9bdaca7d82b390ba5704a85170f4eaf1ee580fdbc85604cb94388fc94b61b` restored and hash-verified.
- App/service signer certificates matched before replacement. Debug and output mask 7 were restored; final face frame was healthy.
- Private calibration hash is unchanged; all 289 pre-existing external files remain present/nonshrinking. No recording, calibration trial, data clear, uninstall, file deletion, commit or push occurred. The `devmux` lease is released.

Raw manifest, APK backups, continuous/per-window logs, pulled journals, exact-chain JSON, generated analysis and ordered CSV are under `artifacts/facelandmarker/preferred-retained-vst-20261103/session-output-20261103-090003/`.
