# Face pipeline: implementation and measured cost in execution order

For the new one-model fitting setup, use the [inline operation inventory and headset comparison](INLINE_GEOMETRY_PIPELINE_BENCHMARK_2026-11-02.md). This document preserves the earlier 35-operation measured baseline; the inline path has 25 operations.

Measured build: dynamic outputs, all three selected, Registration Lab, native RGB preprocessing; headset PB311XHGKC220141G. This is the build measured on 2026-11-02, before the new fused-fitting experiment. Source: `dynamic-outputs/session-output-20261102-141408`.

The service table uses the same **45 valid, fresh face frames**, with complete ordered task/operator events and dependency/clock association. Times are wall duration with service tracing on, including operator wrappers. Backend labels distinguish requested model targets from independently proven delegate placement; this trace did not capture all model initialization partitions. No isolated GPU kernel or buffer-copy duration is inferred.

| Order | Pipeline | Operation | Implementation | Work | Mean ms | p95 ms |
| ---: | --- | --- | --- | --- | ---: | ---: |
| 1 | detector | `RectifiedVSTAccess` | Native VST operator | Acquire 3248×2464 RGB, source K and exposure timestamp; installed internal copy phases not separately timed | 16.42 | 22.26 |
| 2 | detector | `lab_camera` | JavaScript | Select effective virtual camera intrinsics for the lab | 3.23 | 5.79 |
| 3 | detector | `CameraSpaceToWorld` | Native pose operator | Look up camera pose at the exposure timestamp | 0.30 | 1.13 |
| 4 | detector | `lab_affine` | JavaScript | Compose crop affine with the lab image transform | 2.25 | 4.42 |
| 5 | detector | `ApplyAffine` | Native image operator | Affine sample/crop/resize RGB bytes to 256×256 | 47.20 | 53.25 |
| 6 | detector | `Assignment` | Native conversion | Convert the cropped RGB bytes to FP32 | 6.76 | 10.16 |
| 7 | detector | `Arithmetic` | Native arithmetic | Normalize the cropped float pixels by 255 | 3.87 | 8.26 |
| 8 | detector | `face_detector` | Trained LiteRT model; NPU requested | Infer detector boxes and confidence scores | 2.28 | 3.32 |
| 9 | detector | `decode_detection` | JavaScript | Decode detector tensors, select face and construct ROI | 24.92 | 28.75 |
| 10 | detector | `prepare_roi` | JavaScript | Prepare current crop/ROI and update frame/tracking state | 3.76 | 6.13 |
| 11 | detector | `lab_frame_snapshot` | JavaScript | Copy producer state into a calibration diagnostic snapshot | 2.25 | 3.52 |
| 12 | landmark_fit | `lab_affine` | JavaScript | Compose crop affine with the lab image transform | 2.45 | 5.20 |
| 13 | landmark_fit | `ApplyAffine` | Native image operator | Affine sample/crop/resize RGB bytes to 256×256 | 70.58 | 76.68 |
| 14 | landmark_fit | `Assignment` | Native conversion | Convert the cropped RGB bytes to FP32 | 6.34 | 9.06 |
| 15 | landmark_fit | `Arithmetic` | Native arithmetic | Normalize the cropped float pixels by 255 | 3.68 | 5.83 |
| 16 | landmark_fit | `face_landmarks_detector` | Trained LiteRT model; NPU requested | Infer 478 landmark triplets and presence outputs | 2.54 | 4.17 |
| 17 | landmark_fit | `track_landmarks` | JavaScript | Validate landmarks, update tracking ROI, compute depth mean and prepare the 33 fit points | 15.71 | 19.74 |
| 18 | landmark_fit | `geometry_covariance` | JavaScript | Weighted centres and 3×3 cross-covariance | 4.21 | 6.33 |
| 19 | landmark_fit | `SVD` | Native SVD operator | Decompose the 3×3 covariance into U, singular values and Vᵀ | 0.21 | 0.32 |
| 20 | landmark_fit | `geometry_solve` | JavaScript | Correct reflections and solve rotation, uniform scale and translation | 3.93 | 5.39 |
| 21 | landmark_fit | `geometry_unproject` | JavaScript | Unproject 33 points using fitted scale/depth for the next solve | 2.53 | 4.17 |
| 22 | landmark_fit | `geometry_covariance` | JavaScript | Weighted centres and 3×3 cross-covariance | 4.41 | 7.49 |
| 23 | landmark_fit | `SVD` | Native SVD operator | Decompose the 3×3 covariance into U, singular values and Vᵀ | 0.31 | 0.73 |
| 24 | landmark_fit | `geometry_solve` | JavaScript | Correct reflections and solve rotation, uniform scale and translation | 4.54 | 9.34 |
| 25 | landmark_fit | `geometry_unproject` | JavaScript | Unproject 33 points using fitted scale/depth for the next solve | 2.36 | 3.23 |
| 26 | landmark_fit | `geometry_covariance` | JavaScript | Weighted centres and 3×3 cross-covariance | 4.57 | 6.98 |
| 27 | landmark_fit | `SVD` | Native SVD operator | Decompose the 3×3 covariance into U, singular values and Vᵀ | 0.20 | 0.68 |
| 28 | landmark_fit | `geometry_solve` | JavaScript | Correct reflections and solve rotation, uniform scale and translation | 4.35 | 7.41 |
| 29 | landmark_fit | `face_pose` | JavaScript | Camera-to-world transform, pose checks/filtering and tracker validity feedback | 6.01 | 10.01 |
| 30 | landmark_fit | `registration_diagnostics` | JavaScript | Fit/reprojection/quality diagnostics and invalidity feedback to tracker | 5.72 | 9.76 |
| 31 | landmark_fit | `lab_geometry_snapshot` | JavaScript | Copy sparse fit intermediates into a calibration diagnostic snapshot | 9.67 | 13.25 |
| 32 | expressions | `face_blend_input` | Weightless LiteRT model; CPU requested | Gather 146 XY pairs, undo ROI crop and normalize for expression model | 0.34 | 1.18 |
| 33 | expressions | `face_blendshapes` | Trained LiteRT model; NPU requested | Infer 52 expression scores | 2.55 | 4.40 |
| 34 | output_7 | `face_output_7` | Weightless LiteRT model; CPU requested | Concatenate selected final fields into the 6,332-byte packet | 0.34 | 1.30 |
| 35 | output_7 | `lab_capture_marker` | JavaScript | Publish terminal completion sequence after the output is ready | 2.51 | 5.51 |

These run as detector → landmark/fit → expressions → final publication. In the normal app, a tracking producer can replace detector acquisition on retained tracks. The lab forces detection each frame and retains producer/fit snapshots. Expressions run only when requested; mesh reconstruction below runs only when requested.

## Scheduling, readback and app work

| Boundary / operation | Implementation | Mean ms | p95 ms | Population / interpretation |
| --- | --- | ---: | ---: | --- |
| Service operators above | Sum on each linked chain | 273.28 | 286.07 | Same 45 tracing-on face frames |
| Within service task overhead | Service task wrappers / gaps / tracing | 5.96 | 9.09 | Same 45 tracing-on face frames |
| Between dependent tasks | Service dispatch between completed dependencies | 2.00 | 3.63 | Same 45 tracing-on face frames |
| Submission / terminal polling / final readback remainder | App + service transport; not individually isolated | 9.92 | 15.32 | Same 45 tracing-on face frames |
| Submission → completed readback total | Whole linked frame, including the preceding four rows | 291.16 | 304.71 | Same 45 tracing-on face frames |
| Decode / final mesh reconstruction | Compiled Kotlin: validate final packet, reconstruct 478 vertices from fitted pose/scales; includes capture-pose lookup | 0.69 | 1.59 | 99 tracing-off face frames |
| Stage registration / frame checks | Compiled Kotlin: freshness/marker checks, exposure pose lookup and coordinate conversion | 1.00 | 2.14 | 99 tracing-off face frames |
| Readback → mesh-upload acknowledgement | Includes decode/registration, StateFlow handoff, mesh-local conversion, normals/bounds, SDK mesh resource replacement and scheduling | 15.85 | 23.81 | 99 tracing-off face frames |
| Submission → decoded/registered app result | Ends before UI/display presentation | 267.29 | 305.25 | 99 tracing-off face frames |

The **15.85 ms** readback-to-mesh-upload interval includes the **0.69 ms** decode and **1.00 ms** registration rows; do not add those twice. Normals, bounds, resource replacement, UI updates and scheduling are not separately instrumented in this run. The runner also calls `delay(10)` after a frame; actual cadence includes its scheduling effects. Terminal polling overlaps service computation and is not an extra sequential block. Physical display/compositor presentation is unmeasured.

Tracing-off submission-to-readback: **260.38 ms median, 303.98 ms p95**. Tracing-on and tracing-off figures are separate populations and must not be added or subtracted to manufacture a transfer cost.

## Fused-fitting experiment

The measured fitting sequence at rows 18–28 is eight JavaScript operations (**30.89 ms total mean**) plus three native SVD calls (**0.72 ms total mean**). The candidate replaces that sequence with:

1. `face_fit_prepare` weightless CPU model: centres + covariance.
2. Native SVD 1.
3. `face_fit_bridge` weightless CPU model: solve first scale + unproject + next centres/covariance.
4. Native SVD 2.
5. Reuse `face_fit_bridge`: solve second scale + unproject + final centres/covariance.
6. Native SVD 3.
7. `face_fit_finish` weightless CPU model: final reflection-corrected pose.

This fuses across the old JS boundaries while keeping the low-cost native decomposition. Fitting stays before `face_pose` and `registration_diagnostics`, whose state feedback remains in the service. It cannot be folded into final packet publication without crossing those consumers. The optional blend-input model belongs to a separate branch; combining it would perform expression work when disabled or require more variants. Candidate model timings must be measured separately; the old 31.61 ms is an optimization target, not a promised saving.
