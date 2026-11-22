# Fused weightless sparse fitting models — 2026-11-02

Follow-up: the [controlled headset comparison](INLINE_GEOMETRY_PIPELINE_BENCHMARK_2026-11-02.md) now measures this split path and the [inline alternative](INLINE_GEOMETRY_MODELS_2026-11-02.md). Fit means are 34.71 ms original, 1.77 ms split and 1.76 ms inline. Both candidates execute successfully; original installed build/data are restored and calibration acceptance remains pending. Earlier host evidence below is retained.

Implemented an opt-in service-side fitting path with **three weightless LiteRT model assets in four calls**. It replaces eight JavaScript calls around the existing three native 3×3 SVD calls. Enable both app variants with `-PfaceFusedGeometry=true`; the default is false pending headset validation. No app readback/upload intermediates are introduced.

Current performance context is the [ordered component inventory](PIPELINE_COMPONENT_INVENTORY_2026-11-02.md) and [dynamic-output benchmark](DYNAMIC_FACE_OUTPUTS_BENCHMARK_2026-11-02.md). The existing 31.61 ms fitting group consists of **30.89 ms JavaScript** and **0.72 ms native SVD**, measured on the same 45 face-bearing service chains with tracing enabled. These are optimization targets, not timings for the new models.

## Graph change

| Order | New operation | Implementation and outputs |
| ---: | --- | --- |
| 1 | `face_fit_prepare` | Weightless CPU model: 33-point weighted centres and covariance |
| 2 | SVD 1 | Existing native operator: U / singular values / Vᵀ |
| 3 | `face_fit_bridge` | Weightless CPU model: reflection correction, first scale, unprojection, next covariance/centres |
| 4 | SVD 2 | Existing native operator |
| 5 | Reuse `face_fit_bridge` | Second scale, unprojection, final covariance/centres |
| 6 | SVD 3 | Existing native operator |
| 7 | `face_fit_finish` | Weightless CPU model: final reflection-corrected rotation, scale and translation |

The old sequence was covariance → SVD → solve → unproject → covariance → SVD → solve → unproject → covariance → SVD → solve. Fusion crosses the adjacent arithmetic boundaries between SVD calls: four model invocations replace eight JS invocations and remove their marshaling/runtime overhead. Lab common-stage operator count falls from 20 to 16. CPU is requested deliberately: matrices are tiny, FP32 accuracy matters, and SVD remains native. Moving these small tensors to a GPU/NPU may add transfer overhead; requested backend is not proof of effective installed placement.

TFLite's inspected builtin catalog has no general SVD operation (`SVDF` is an unrelated neural filtering operator). The follow-up [inline rotation model](INLINE_GEOMETRY_MODELS_2026-11-02.md) implements the equivalent proper-rotation solve using an unrolled quaternion/Jacobi algorithm. Its potential saving includes model dispatch, tensor access/copies and native-operator boundaries, not just the measured 0.72 ms of SVD. Both alternatives remain available for a controlled headset comparison.

## Why a separate fitting model family

`face_pose` and `registration_diagnostics` consume the fitted result and update service validity/tracker state. They remain after the fit, before compact final publication. Folding the fit into `face_output_N` would cross these consumers or duplicate fitting. The existing blend-input model is optional and branches from raw landmarks; combining it with shared fitting would either run expression work when disabled or require extra variants.

The two bridge invocations reuse one asset with `previous_scale=1` on the first pass and `previous_scale=firstScale` on the second. No learned parameters are present. Canonical points and weights are constants from the existing geometry asset; the manifest pins its SHA-256. The fixed 33-point fit layout is checked in graph construction and all model tensor bindings are validated against the serialized signatures.

## Numerical contract

For points p_i and weights w_i, the preparation computes weighted centres and cross-covariance:

`centre(x) = sum(w_i * x_i) / sum(w_i)`

`C = sum(w_i * (target_i - centre(target)) * (canonical_i - centre(canonical))^T)`

Native SVD gives `C = U S Vᵀ`. The finishing arithmetic uses:

`R = U diag(1, 1, sign(det(U) * det(Vᵀ))) Vᵀ`

`scale = sum(w_i * dot(R * canonical_centred_i, target_centred_i)) / sum(w_i * |canonical_centred_i|²)`

Nonfinite or nonpositive/tiny scale uses the existing fallback of 1. Translation is `centre(target) - scale * R * centre(canonical)`; homogeneous pose is row-major 4×4. Unprojection uses `z = (projected.z - depthOffset + 1) / (previousScale * currentScale)` and `(projected.x*z, projected.y*z, -z)`, with canonical fallback for invalid frames.

FP32 model reductions differ slightly from JavaScript's double arithmetic followed by float32 tensor storage. Therefore, this path uses bounded numerical parity, not bit equality with the old implementation. Within the new path, original snapshot tensors, final packet publication, terminal completion and exact packet/snapshot comparisons remain intact. A new One check still needs device validation before the experimental path is accepted for calibration.

## Assets and host validation

| Asset | Size | Internal LiteRT operators |
| --- | ---: | ---: |
| `face_fit_prepare.tflite` | 4,724 bytes | 18 |
| `face_fit_bridge.tflite` | 18,460 bytes | 98 |
| `face_fit_finish.tflite` | 14,752 bytes | 75 |

Internal operations use ordinary portable arithmetic, reductions, gather/reshape, batch matrix multiplication, comparisons and selection. Multiple internal operations execute in one model call; they are not separate SpatialML/JS invocations.

- **126 numerical cases pass** with real host CPU LiteRT: 120 synthetic camera/pose/deformation cases including invalid frames, three previously accepted headset-input replays, and reflection/zero/tiny-scale cases. Both comparison paths use NumPy SVD, so this does not establish installed native SVD parity.
- Maximum absolute differences: pose matrix **0.0001525879**, first scale **3.7253e-9**, second scale **4.7684e-7**, first unprojection **0.0000610352**, metric points **0.0001831055**. Pose translations and metric coordinates are in centimetres; matrix elements mix rotation/scale and translation, so the aggregate pose number is not a physical alignment error.
- Host model invoke means are approximately 0.0091 / 0.0132 / 0.0089 ms for prepare/bridge/finish. These exclude SpatialML wrappers/transport and are **not headset performance predictions**.
- Production Kotlin constructor/submission checks pass for normal/lab × native/GPU/RGB-first preprocessing × old/fused fitting, including all seven output modes and calibration routing. All 24 new model-call bindings match the serialized input/output names, shapes and requested CPU backend.
- Existing terminal-completion, packet/snapshot equality, stale frame, exposure/export motion and profile/ROM regression checks pass.
- Both apps pass assembleDebug, lintDebug and spotlessCheck with fusion enabled and disabled. Fused APK assets match the generated model bytes. Serializer extensions reproduce all 12 existing output/preprocessing model assets bit-for-bit.
- `pico-cli spatialml model inspect` succeeds through pySpatialML on the bridge model; the full signature result is archived.

Evidence: `artifacts/facelandmarker/fused-geometry-20261102/`. Fused APKs: `apks/facelandmarker-fused-geometry.apk` and `apks/registrationlab-fused-geometry.apk`. Default Gradle output is restored after archiving the experiment.

```sh
python3 FaceRegistrationLabApp/tools/generate_face_geometry.py
uv run --no-project --with ai-edge-litert python \
  FaceRegistrationLabApp/tools/validate_face_geometry_models.py \
  --output artifacts/facelandmarker/fused-geometry-20261102/models
python3 FaceRegistrationLabApp/tools/face_pipeline_layout.py \
  --output artifacts/facelandmarker/fused-geometry-20261102/layout \
  --json-jar /private/tmp/face-calibration-tuner/json.jar
./gradlew :FaceLandmarkerApp:assembleDebug :FaceRegistrationLabApp:assembleDebug \
  -PfaceFusedGeometry=true
```

## Headset boundary

The initial readiness probes reported no face, so this first host pass made no experimental install. The later [headset comparison](INLINE_GEOMETRY_PIPELINE_BENCHMARK_2026-11-02.md) rebuilt and measured both candidates with a face, then restored the original APK/debug/selection and verified preserved data. The current driver is `tools/measure_face_geometry.py`; the earlier bounded old/fused/old driver remains archived at `artifacts/facelandmarker/fused-geometry-20261102/measure_fit.py`.

Before enabling the flag by default, complete controlled on-device parity/invalid-face recovery and a recorded One check with coherent native exports. Initialization, complete face chains, output probes and end-to-end latency are now measured in the follow-up. No optical accuracy claim, service/SDK change, commit or push was made.
