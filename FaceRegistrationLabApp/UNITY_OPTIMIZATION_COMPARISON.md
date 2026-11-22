# Unity face-pipeline optimizations and Kotlin applicability

Implementation update: [GPU_PREPROCESSING_IMPLEMENTATION.md](GPU_PREPROCESSING_IMPLEMENTATION.md). Both preprocessing models and their Kotlin bindings now exist behind the explicit GPU validation-build flag. Host builds and numerical checks pass; the headset is disconnected. FP32 Metal probes work, but reduced precision and uint8 transport need Android verification before enabling the experiment for calibration. The design-only/unimplemented statements below describe the preceding investigation.

Current GPU preprocessing finding (2026-10-31): a separate Unity `face-full-space` package in the `dev-move-qnn-samples-to-tflite` worktree declares a GPU-targeted weightless `preprocess.tflite.bytes`. Its actual 1,544-byte model contains CAST → SLICE → fixed 1×1 CONV_2D, has no variable tensors, takes uint8 `[1,256,338,3]`, and outputs float32 `[1,256,256,3]`. The slice is a fixed horizontal centre crop beginning at x=41; the fixed convolution reverses channel order and divides by 255. It has no affine/ROI input and cannot replace the lab's moving affine warp unchanged. Model SHA-256 is `791f01b3791f3c34bee31d3f925c94346ba9a52db42bd59ed9a207c609a49411`. Pipeline JSON establishes the requested GPU target; effective delegation was not tested in this inspection. Camera acquisition/timestamp remain upstream SpatialML operators. Inspection evidence: `artifacts/facelandmarker/registration-lab/performance/gpu-preprocessing-study-2026-10-31/unity-model-inspection.json`.

The FaceLandmarker project and measured baseline discussed below use native ApplyAffine → Assignment → ArithmeticCompose preprocessing. The prior statement that fused weightless processing was a proposal applies to that inspected FaceLandmarker implementation; it does not cover every Unity package.

The current Kotlin GPU fusion target is the **36.79 ms detector preprocessing** and **51.69 ms landmark preprocessing** (88.48 ms combined traced means), with runtime source-to-crop affine inputs, preserved RGB `/255`, and original coherent byte crop exports. RGB acquisition and timestamped camera pose cannot execute inside a TFLite math model; the first camera/values/pose row includes about 9.6 ms acquisition, 2.3 ms lab camera-value JS, and 0.2 ms native pose access. Runtime GPU coverage, input-transfer overhead, bilinear/border/rounding parity and the terminal snapshot/export barrier require validation before replacing the installed graph. No GPU model or app-pipeline change was made during this inspection.

## Planned GPU preprocessing model split

Use two separate model artifacts and inference instances initially. Share the sampling/normalization generator and numerical reference between them. A single general affine model remains technically possible; separate artifacts permit specialization and independent GPU-coverage/performance validation.

| Model | Transform contract | Output contract |
| --- | --- | --- |
| Detector preprocessing | Full-frame detector transform fixed for the camera/profile; the lab preserves aspect ratio with letterboxing, and composes the calibration image transform. The normal sample retains its existing independent x/y scales. No face ROI input. | 256×256 float32 RGB in [0,1], plus the corresponding byte crop required by lab exports. |
| Landmark preprocessing | Per-frame translated, scaled and rotated face crop from `prepare_roi`, composed with the calibration image transform. Retain the existing affine for downstream inverse mapping and geometry. | 256×256 float32 RGB in [0,1], plus the corresponding byte crop required by lab exports. |

The detector transform is fixed within a profile, not universal across calibration modes. Configuration changes must update the detector transform coherently. Both model contracts retain interpolation, border fill and byte-rounding semantics. Camera acquisition, sensor timestamps and pose access remain upstream service operations. Preserve producer → landmark/fit → mesh dependencies and the terminal completion/export checks. Validate each model's pixels and downstream outputs separately, confirm effective GPU execution, then measure the full pipeline with tracing off. This is a design update; neither GPU model nor the app integration is implemented yet.

## Historical FaceLandmarker comparison

Compared on 2026-10-30 against the current local Unity checkout at `/Users/bytedance/Documents/Projects/SpatialML/Unity/To-Public/SecureMR-Unity-Sample-Private-worktrees/dev-pipeline_zoo`, branch `dev/medipipe-ports`. That checkout contains uncommitted changes. This comparison reads its current source and saved measurements; it does not modify, build or run Unity.

The Unity project has a complete service/operator component breakdown. The Kotlin lab currently has aggregate submission-to-readback measurements. Reuse Unity's profiling method and validated contracts, then measure this app before selecting a graph change.

## What Unity implemented

| Unity change | Current Kotlin state | Implication |
| --- | --- | --- |
| Separate acquisition and predicted-ROI tracking producers; run detector on search/recovery | Both producers exist; normal sample selects them, but lab forces detector every frame | A lab tracking trial can remove detector preprocessing/inference/decode. Export must still retain coherent detector-crop evidence, so simply dropping the force flag is insufficient. |
| Fit only 33 weighted canonical points through three passes; reconstruct 478 mesh points afterwards | Already implemented with the same fit-point count and geometry procedure | Preserve this reduction; there is no additional 478-to-33 fit optimization to port. |
| Preserve RGB and remove an unnecessary color conversion; fixed 256×256 model crops | Already uses RGB, affine crop, byte-to-float and normalization | Preserve the model input contract; no redundant color conversion remains here. |
| Native covariance/fit finishing, sparse/full unprojection, mesh transforms, blendshape gather and local vertices | Kotlin keeps covariance, solve finishing, unprojection and mesh expansion in JS with native SVD | Potential differences in JS array/context overhead and dispatch count must be profiled. The literal Unity native migration was slower end to end; do not port it wholesale. |
| Compact helmet output skips blendshapes/full mesh expansion/packing | Kotlin lab always reconstructs a mesh and runs blendshapes | Calibration needs distinct mesh markers. A pose-only output cannot replace that evidence. Blendshapes are unused by the lab's badge/marker display and are a narrower removal candidate after timing. |
| Small result-packing inputs; sampled image readback separate from steady tracking | Kotlin final packet has 2,994 floats and lab producer/fit/mesh snapshots every frame; source RGB capture is sampled | Measure snapshot and JS marshaling cost. Preserve native intermediates and exact source/geometry identity at exports if making snapshots conditional. |
| One frame in flight, explicit dependency handles, matching result sequence | Already implemented | Preserve ownership; speculative overlapping frames would mix global images/K/geometry. |
| Per-window app timing plus microsecond service/operator traces | Kotlin now adds per-completed-frame aggregate journal records; component trace pending | Adapt service/client/pipeline/task isolation and complete-successful-task filtering. Avoid using Unity's hard-coded operator-index groups for the different Kotlin layout. |

`FaceLandmarkerNativeMath.cs` constructs SpatialML tensor operators. The inspected FaceLandmarker source contains no Burst implementation; Burst/host geometry and weightless-model fusion were proposals after the native migration regression, not a demonstrated implementation in this checkout.

## Shared assets and important differences

Live SHA-256 comparison confirms byte-identical landmark and blendshape models:

- Landmark model: `1daa04f631a8592b92cca082240645b8c1cb0b0c1ff7ee9b031fa4fb8842dbc2`.
- Blendshape model: `4f36dded049db18d76048567439b2a7f58f1daabc00d78bfe8f3ad396a2d2082`.
- Detector model bytes differ: Kotlin `328ce1601afbed980a70a30e0fb8eb3982469f05e0191977cdd59917c5e109bd`; Unity `b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f`. Equivalence of those detector files has not been established; inspect metadata/operator graphs before treating detector timings as comparable.

The `track_landmarks`, `prepare_roi`, `geometry_covariance`, `geometry_solve` and `geometry_unproject` JS files are text-identical between these checkouts. Unity's current graph invokes native replacements for several of the geometry scripts. The Kotlin graph still invokes the scripts.

The saved October 26 Unity profile uses Unity 6000.3.13f1, linked SDK 6.2.0, XR service `com.bytedance.pico.openmr` and three NPU model graphs with complete single-partition delegation. The Kotlin project declares Spatial BOM 6.1.9 and compiles against SpatialML foundation 0.11.7 signatures (`com.bytedance.pico.openmr.spatial.pack`); its app selects backend integer 2. Confirm the actual executing Spatial service, binary/build provenance and model delegate in the new connected trace. Do not infer them solely from that integer or from the Unity trace. Both reports target PB311XHGKC220141G and the documented Swan fingerprint, but the service/runtime paths differ.

Unity's `docs/face-tracker-implementation.md` retains an older BGR tensor-table entry; current `PreprocessRgb` source explicitly preserves RGB and the October 26 profile describes left RGB. This comparison follows current source and the later profile.

## Saved Unity performance evidence

Latest local baseline: `docs/face-landmarker-baseline-2026-10-26.md`, with raw captures and the component parser in `Build/Baseline-20261026/`.

With tracing off, mesh mode logged **51.80 ms mean submission-to-result**, **19.22 completion Hz** and **18.40 measured-face Hz** over 700 updates. Six fully measured windows had 51.55 ms mean and 19.30 measured Hz. Helmet logged 37.61 ms mean over a different face/held/absence population, so this does not establish a controlled mesh-versus-helmet improvement. These are saved measurements, not today's device state.

Selected component means from the trace-enabled mesh profile:

| Component | Mean |
| --- | ---: |
| Camera acquisition on tracked-ROI frames | 4.678 ms |
| Detector preprocessing / model / decode, acquisition frames only | 2.147 / 2.254 / 3.889 ms |
| Landmark preprocessing / model / decode and projection | 2.289 / 2.337 / 2.963 ms |
| Three native weighted fits, including SVD | 6.420 ms |
| Two sparse unprojections | 1.965 ms |
| Full inverse crop and blendshape gather | 3.408 ms |
| Full projection / unprojection | 2.008 / 1.270 ms |
| Blendshape model | 2.336 ms |
| Packet packing | 1.967 ms |

The three SVD calls total only 0.208 ms and are included in the fit row. The 161-operator common pipeline has 8.169 ms mean traced gaps; the 111-operator mesh pipeline has 5.486 ms. Those gaps include tracing/scheduling overhead and are not isolated dispatch costs. Readback waits overlap graph execution and must not be added to model/operator time again.

Earlier matched native-migration measurements in `docs/face-landmarker-native-migration.md` show why fewer JS calls alone is insufficient: detection-plus-mesh completion increased **40.64 → 48.34 ms**, despite acquisition-plus-mesh JS time falling **22.76 → 9.14 ms**. Extra small nodes and missed polling opportunities erased the savings. This is a measured regression in the older experiment, not a controlled comparison with today's Kotlin build.

The Kotlin check's selected exports took **451–538 ms** to read back, despite capture ages of only **25–42 ms at submission**. That warrants checking executing service/build, backend/delegate, affine costs, JS/snapshot marshaling and queue/dispatch before assuming the models themselves dominate.

## Recommended connected experiment order

1. Install the already-built capture-gate update, verify native startup and record the repeated C one-sample check. These recordings validate marker integrity, phase/export identity and remaining physical offset.
2. Separately capture a normal tracing-off warm baseline and a bounded service/operator trace. Pin serial, ROM, app/service hashes, SDK, backend, source/crop sizes and thermal state. Record face-present acquisition/tracking/absence populations separately. Restore any debug property changed for tracing and release devmux when finished.
3. Reuse the generic `Tools/FaceLandmarker/parse_perf.py` isolation/filtering approach or adapt the stricter complete-chain analyzer. Derive Kotlin's actual operator layout from source plus trace; the Unity 161/111 operator ranges cannot be reused unchanged. Report each model, preprocessing, JS geometry, snapshot/packet, queue/dispatch, result-delivery and Stage-upload cost.
4. Choose the first change from this profile. Likely comparisons are tracking versus forced detection, omitting unused blendshapes, sampled diagnostic snapshots, or a fused/host geometry boundary. Preserve K, crop, capture time and native/Stage/export identity. Any host port needs Kotlin/JNI equivalents; Unity Burst code cannot be copied into Android/Kotlin.
5. Compare camera age at upload, measured scene rate and numerical/physical marker parity. Lower latency can improve motion-dependent overlap and capture efficiency; the common still-face vertical offset still needs the cy/focal experiments. No Unity optimization has been ported in this pass.
