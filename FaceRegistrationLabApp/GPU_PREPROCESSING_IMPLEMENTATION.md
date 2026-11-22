# GPU preprocessing integration and detector fusion study — 2026-10-31

RGB-first follow-up: [RGB_FIRST_PREPROCESSING_2026-11-01.md](RGB_FIRST_PREPROCESSING_2026-11-01.md) implements an additional model pair that samples byte RGB directly and removes the explicit full-frame CAST. Host math/build checks pass; device pixels and performance remain pending. The benchmarked pair below remains available and unchanged.

Latest face-present measurement: [GPU_PREPROCESSING_FACE_BENCHMARK_2026-11-01.md](GPU_PREPROCESSING_FACE_BENCHMARK_2026-11-01.md). After a user-requested service reset, native/GPU/native medians were 227.33/186.14/239.06 ms (18.1–22.1% lower with GPU), with all 39 operator changes recorded. Both preprocessing models fully delegated to OpenCL. Original native APK/debug/data were restored and preserved. Pixel, coherent export and optical correctness remain unverified; the flag remains experimental.

Earlier no-face headset update: [GPU_PREPROCESSING_BENCHMARK_2026-11-01.md](GPU_PREPROCESSING_BENCHMARK_2026-11-01.md). The integrated uint8/OpenCL GPU path ran a no-face benchmark and reduced observed median latency by 24–25%; the original native build was restored. Controlled pixel probes failed during model initialization, so accuracy and face-present performance remain unverified. The disconnected/never-installed statements below describe the original host implementation boundary.

Two weightless preprocessing models are generated and integrated into the Kotlin graph. The GPU validation build is selected with `-PfaceGpuPreprocessing=true`. Default builds retain native preprocessing until headset execution, numerical accuracy and latency are verified. The headset disconnected before this implementation and is still unavailable; neither APK was installed, no calibration capture was started and no device data was changed.

## Models and pipeline integration

| Asset | Contract | Model contents |
| --- | --- | --- |
| `detector_preprocess_gpu.tflite` | uint8 RGB `[1,2464,3248,3]`, FP32 affine `[1,1,1,6]` → FP32 RGB `[1,256,256,3]` in `[0,1]` | Axis-aligned inverse sampling for full-frame/profile transform, zero border, 1/32-pixel bilinear coordinates, byte rounding and normalization; 49 operators, 17,340 bytes |
| `landmark_preprocess_gpu.tflite` | Same image/input/output sizes | General translated/scaled/rotated source-to-crop affine, inverse sampling, zero border, byte rounding and normalization; 69 operators, 12,128 bytes |

Both models have zero variable tensors and use constants, without learned weights. `tools/generate_face_preprocessing.py` constructs deterministic TFLite FlatBuffers directly and records hashes in `preprocessing_models.json`. Both require LiteRT's GPU `Resampler` custom operator, which the inspected LiteRT runtime explicitly registers for GPU execution. They are portable TFLite graphs, with no QNN context/AOT artifact.

The detector transform is fixed within the active camera/calibration profile and remains a runtime input so profile changes are coherent. Its cross-axis coefficients must be zero, as they are for the current A/B/C/D/Custom camera profiles. Landmark preprocessing uses the existing `prepare_roi` affine, including rotation. `sourceAffine` still composes the calibration transform before either model; downstream inverse mapping retains the original affine.

`SpatialMLGraphSession.preprocess` selects the separate detector or landmark model. The model backend is GPU (public backend ordinal 1), independently of the trained inference backend (currently requested ordinal 2). The model binding now accepts explicit input encodings and binds camera RGB as `UNSIGNED_FIXED_POINT8`; other inputs and outputs remain `FLOATING_POINT32`. The enum spelling was verified against the cached foundation 0.11.7 classes and the local service API. Models/pipelines are created once and retain existing dependencies and lifecycle.

Only the terminal normalized image is a model output. An early two-output probe exposed a Metal runtime issue: an intermediate crop requested as a second output was not materialized correctly. In the final integration, lab-only native arithmetic recovers `model_input*255+0.5`, then the existing truncating Assignment writes the byte crop. The model rounds before normalization, so this reconstructs the exact integer crop in the FP32 host reference. Normal sample tracking omits that diagnostic copy. Both original crop/image save formats remain intact. The detector → fit → mesh order, all snapshot inputs and final completion marker are preserved.

The lab still has 11 detector + 20 landmark/fit + 8 mesh operators because the normalized-to-byte diagnostic copy keeps the outer operator count unchanged. Each preprocessing group replaces its expensive native affine operation with one model call. Outer operator count is not an estimated speedup. The normal sample reduces its detector/landmark pipelines from 8/18 to 6/16 operations.

## Host checks and observed runtime limitations

Artifacts are under `artifacts/facelandmarker/registration-lab/gpu-fusion-2026-10-31/`.

- Serialized-model reference against OpenCV 4.11 passes 24 synthetic detector, rotated-face, off-image-border and RGB/noise cases. Every result is finite and bounded; normalized values agree exactly with the reconstructed byte crop divided by 255. Maximum observed pixel difference is 8 byte levels, with maximum RMS below 0.5 byte levels. The isolated maximum is a sampling/rounding edge, not proof of bit-identical OpenCV output or downstream face accuracy.
- Full-resolution Float32-input counterparts run through the Mac Metal GPU. With `enforce_f32=true`, both normalized outputs agree with the serialized math reference within `5.96e-8` absolute error on the current RGB-pattern case. These are host probes, not the packaged uint8 Android models.
- With the default Metal precision policy, detector/landmark outputs show maximum differences of approximately 0.937/0.529 in normalized values; RMS is 0.0083/0.0314. Lower precision therefore cannot be accepted for calibration merely because inference completes. An earlier coordinate formula also overflowed reduced-precision intermediates; the final generator separates integer/fraction parts to eliminate that overflow.
- Both final uint8 graphs compile through the Mac GPU path, but host execution fails while creating/writing the uint8 input buffer (`CompiledModel error code=5`). The existing Unity uint8 preprocessing model has the same host limitation. Android GPU/service behavior is still unverified.
- `pyspatialml model info` uses a CPU interpreter and cannot allocate the GPU-only `Resampler` model. Its reported unresolved-custom-op error is retained; FlatBuffer inspection and actual GPU Float32 execution supply the available validation evidence.
- Constant-only arithmetic was folded during generation after an early GPU probe attempted to split it onto CPU. The final Float32 Metal probes have no unsupported-operation/CPU-partition log.
- Production constructor fixtures pass separate model selection and both GPU/native layouts. Existing completion-before-read, packet equality, snapshot/motion/profile/ROM regressions pass. Both apps' GPU build and default native build pass assemble, lint and formatting. APK model bytes are hash-checked and signatures verify.

The app's public model binding exposes backend selection, but the inspected binding does not expose a per-model FP32 precision option. Do not claim the installed service can enforce FP32 based on the Mac Python option. The GPU build remains experimental until actual Android behavior is measured. No performance improvement is claimed from Mac timings.

## Detection decode and ROI: fusion feasibility

The measured 17.63 ms group comprises approximately 15.56 ms in `decode_detection` and 2.07 ms in `prepare_roi`. The former scans 896 SSD anchors, converts logits with sigmoid, decodes boxes/keypoints, ranks by score and optional identity distance, chooses the first best-ranked candidate, and computes one weighted suppression cluster against that winner. It does not need a complete sorted list to calculate its final result.

`tools/analyze_detector_fusion.py` implements the same operation as fixed-shape tensor math. It matches the actual shipped JavaScript in 40 synthetic cases, including no face, multiple candidates, equal-score stable selection, invalid sizes, NaN/Inf outputs, active/expired identity lock and letterboxed/stretched detector coordinates. Maximum absolute difference is `2.27e-13` using double precision. This proves the algebraic rewrite on those cases; it is not FP32/GPU/NPU equivalence or a benchmark.

A suitable next model boundary is:

1. Combine the 512 fine and 384 coarse outputs; use constant anchor coordinates.
2. Apply sigmoid, finite/size masks and source-coordinate identity distance.
3. Use masked rank reduction and a first-index tie rule, rather than sorting.
4. Compute IoU against that single winning box; reduce score-weighted boxes and keypoints.
5. Return weighted box/keypoints, confidence, valid flag and original detector diagnostics.

Keep timestamp interpretation, clock rebasing, ROI prediction/state update and the exact `atan2`/fallback crop logic in a small JS finishing operator initially. The inspected GPU parser supports sigmoid, gather, equal/select, min/max/sum reductions, sin and cos; it does not provide a direct ArgMax/Atan2 path in the inspected switch. Ranking can be represented by reductions and first-index masks, while angle finishing stays in JS. NaN-masked candidates must be sanitized before multiplication because `NaN*0` remains NaN. An NPU candidate requires actual compiler/partition evidence for its reductions, masks and gather; static shapes alone do not prove NPU delegation.

This has enough measured cost to justify a later model prototype. The production decode/ROI scripts are unchanged in this increment.

## Producer snapshot: safe fusion boundary

The producer snapshot concatenates 66 float32 values (264 bytes): command, exposure frame metadata, ROI, affine, virtual K, service K, calibration image transform, timestamped camera pose and mode. Its 1.46 ms measured mean includes JS/context/dispatch overhead, not just copying 264 bytes.

A weightless concat model could represent the copy, but a standalone GPU/NPU dispatch plus nine inputs and one output is unlikely to help without a measurement. FP16 would also lose exact calibration/timestamp/matrix values. It cannot be moved into detector preprocessing: current ROI/frame state is produced **after detector inference and decoding**, and snapshotting there would capture old state. It could be appended to a decode/ROI finishing model or to the existing `prepare_roi` JS after all fields are finalized, preserving the producer completion dependency. A landmark preprocessing model could also copy the finalized producer fields, but would need extra bindings, an independent terminal snapshot output and exact FP32 validation.

The first candidate is appending the 264-byte copy to the existing ROI finishing operation, rather than adding a standalone inference model. This has not been changed or benchmarked here; the current exact snapshot/barrier is retained.

## Reproduction and headset continuation

Build the GPU experiment:

```sh
./gradlew -PfaceGpuPreprocessing=true :FaceLandmarkerApp:assembleDebug :FaceRegistrationLabApp:assembleDebug
```

Archived GPU APKs and their hash/signature manifest are in `gpu-fusion-2026-10-31/apks/` and `build-manifest.json`. Ordinary Gradle output is restored to the default native variant at the end of host work. The archived experiment is separate, so a later default build cannot silently overwrite it.

When PB311XHGKC220141G is connected, recheck devmux ownership, app state, active recording/capture and installed hash. Test the GPU models on controlled tensors first and verify effective GPU coverage, byte-input transport, normalized values, reconstructed byte crop and precision. Compare full-frame/profile transforms, moving/rotated ROIs, border cases and face model outputs against the native path. Preserve the installed build and all recordings/profile/calibration data. If the installed runtime cannot provide adequate precision or transport, do not promote the experiment or change the service without a separate scoped implementation.

Once controlled tensor checks pass, measure tracing-off end-to-end latency on a face, then validate one coherent recorded One check before a Full trial. The wearer does not need to remain completely motionless. Lower latency is not proof of optical calibration accuracy.
