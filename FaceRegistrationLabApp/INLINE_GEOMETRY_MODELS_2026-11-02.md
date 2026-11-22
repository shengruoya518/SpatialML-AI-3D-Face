# One-model sparse geometry fit — 2026-11-02

`-PfaceInlineGeometry=true` selects one CPU LiteRT call for all three 33-point fitting passes. It replaces eight JavaScript operations and three native SVD calls from the original path, or four model calls plus three SVD calls from the split-model experiment. It takes precedence over `faceFusedGeometry` when both flags are set. Both flags default to false pending calibration acceptance.

The model computes the proper rotation required by the fit directly. It does not expose U, singular values or Vᵀ. All fitting intermediates remain inside the model except the scales, sparse targets, metric points and pose that downstream SpatialML consumers need. `face_pose`, `registration_diagnostics`, tracker/validity feedback, lab snapshots and final publication retain their ordering. There is no app readback/upload bridge in either fitting alternative.

## Equivalent rotation, using portable operators

For weighted cross-covariance `C = sum(w * target_centred * canonical_centredᵀ)`, the old solution is `R = U diag(1,1,det(UVᵀ)) Vᵀ`. It maximizes `trace(Rᵀ C)` over proper rotations. Singular values themselves are unused.

The inline implementation constructs Horn's symmetric 4×4 quaternion matrix from C. Its largest-eigenvalue eigenvector is a unit quaternion for the same optimum. Five fixed cyclic Jacobi sweeps diagonalize it; each sweep has three rounds, processing two disjoint plane rotations together. The quaternion is normalized and converted to a 3×3 rotation. The existing scale, translation, unprojection and invalid-frame fallbacks follow unchanged. All three passes execute inside one FlatBuffer subgraph.

The arithmetic uses FP32 builtins: matrix multiplication, gather, reshape, reductions, square root/reciprocal square root, comparisons and selection. No learned weights, JavaScript, custom SVD operator, TensorFlow Flex runtime, service change or app computation is needed. Canonical geometry and weights are fixed constants pinned by the manifest's asset hash. Covariance is normalized before squaring to protect very large/small finite values.

For zero covariance, rotation is unidentifiable and the candidate deterministically selects identity. Rank-one and tied reflected cases also have nonunique optima; OpenCV may choose a different orientation with the same fitting objective. Validation compares the objective and proper-rotation constraints for those cases rather than requiring equality of arbitrary bases. This is an explicit behavior boundary, not a guarantee of identical degenerate poses. Normal face cases and saved headset inputs use direct output parity checks.

## What crossing the model boundary costs

Local service source `TFLiteModel.cpp:235–326` copies each input into a LiteRT buffer, invokes the compiled model and copies each output into its SpatialML tensor. It uses host-memory copies or buffer lock/copy/unlock depending on availability. Native SVD in `OperatorFactory.cpp` calls `cv::SVD::compute` and writes its outputs back to service tensors. Equivalence of this checkout to the installed service revision is not independently established.

| Fitting alternative | Model calls | External native SVD calls | Model input/output copies implied by source | Model-boundary payload per fit |
| --- | ---: | ---: | ---: | ---: |
| Split models | 4 | 3 | 32 | 3,740 bytes |
| Inline model | 1 | 0 | 9 | 1,668 bytes |

The inline payload is 804 input bytes and 864 output bytes. It removes 23 model tensor-copy/access operations and 2,072 payload bytes (55.4%), plus the separate native SVD boundaries. The matrices are small, so dispatch/access/synchronization overhead may matter more than copying the bytes. These counts do not establish a measured copy duration, GPU transfer saving or total speedup. They exclude native-SVD-internal copies and final app IPC, which are separate boundaries.

## Host validation and integration

- `face_fit_inline.tflite`: 210,280 bytes, 1,492 internal operators, five Jacobi sweeps, CPU requested. These are LiteRT nodes, not 1,492 SpatialML operators.
- 126 full-fit checks pass against shipped JavaScript with **OpenCV FP32 SVD**: 120 synthetic camera/pose/deformation/invalid cases, three saved headset-input replays and reflected/zero/tiny-scale solves.
- Maximum absolute full-fit differences: pose matrix 0.0001220703125; first scale 5.96046e-8; second scale 4.76837e-7; second targets 0.000091552734375; metric points 0.0001068115234375. Coordinates use centimetres; pose matrices mix rotation/scale and translation, so the aggregate matrix number is not a physical alignment error.
- 7,001 rotation stress cases pass: reflected, rank-two, rank-one, near-rank-one, isotropic and tied-reflection matrices, with magnitude factors from 1e-25 to 1e25. Maximum orthogonality error 7.03e-7, determinant error 1.01e-6, normalized fitting-objective difference 1.23e-6. Well-separated optima agree with double-precision SVD within 5.41e-5 per rotation entry.
- Host full-model invocation averaged about 0.121 ms during the parity run. The isolated rotation probe averaged 0.0265 ms. These exclude SpatialML transport/dispatch and are not headset predictions. The inline graph does more internal arithmetic than the split models; the end-to-end comparison must include saved external calls.
- Actual Kotlin graph construction validates normal/lab apps, native/GPU/RGB-first preprocessing, legacy/split/inline fitting and both-flags precedence. All dynamic selections and calibration routes pass; 36 fit-model call bindings match serialized FlatBuffer names and shapes.
- Existing split-model assets regenerate byte-for-byte after the shared solve helper refactor; their original 126 parity checks still pass.

Native-preprocessing all-output lab execution has 25 SpatialML operators in the inline variant, versus 35 originally and 31 with split models. The standalone sparse fitting group becomes one operator. The remaining JavaScript and native preprocessing operations are still separate and must be included in the end-to-end report.

## Reproduce

```sh
python3 FaceRegistrationLabApp/tools/generate_face_inline_geometry.py \
  --output artifacts/facelandmarker/inline-geometry-20261102/models \
  --probes artifacts/facelandmarker/inline-geometry-20261102/probes
uv run --no-project --with ai-edge-litert --with opencv-python-headless python \
  FaceRegistrationLabApp/tools/validate_face_geometry_models.py \
  --inline-root artifacts/facelandmarker/inline-geometry-20261102 --opencv-svd \
  --output artifacts/facelandmarker/inline-geometry-20261102/fit-validation
uv run --no-project --with ai-edge-litert --with opencv-python-headless python \
  FaceRegistrationLabApp/tools/validate_face_inline_rotation.py \
  --root artifacts/facelandmarker/inline-geometry-20261102
./gradlew :FaceLandmarkerApp:assembleDebug :FaceRegistrationLabApp:assembleDebug \
  -PfaceInlineGeometry=true
```

For an independent validation directory, generate with both `--output <root>/models` and `--probes <root>/probes`. The asset generator defaults to the app model folder. The recorded host evidence is under `artifacts/facelandmarker/inline-geometry-20261102/`.

## Headset measurement

A controlled original/split/inline/original run completed with native preprocessing and all three outputs selected. The [measured operation inventory and comparison](INLINE_GEOMETRY_PIPELINE_BENCHMARK_2026-11-02.md) contains all 25 inline operations and app costs. Fitting means are 34.71 / 1.77 / 1.76 ms; inline does not meaningfully improve on split fitting. Untraced pipeline medians are 256.73 / 230.34 / 237.78 ms, with variation between the two inline windows. Both candidates remain opt-in.

Nine windows captured 676 completions and 182 fully matched eligible face chains. All 18 endpoint output probes pass; both experimental builds execute successfully. Both apps pass inline/default assemble, lint and format gates; existing runtime and split-model regressions pass. Original installed APK and debug/selection were restored, calibration and 271 original external files preserved, and the device lease released. No service restart or SDK/service replacement occurred. Runtime correctness does not establish optical calibration; a recorded One check remains a separate acceptance step.
