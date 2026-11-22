# Compact adjacent-VST and fused-control face pipeline — 2026-11-03

## Result

The opt-in candidate is implemented, host-validated and measured on `PB311XHGKC220141G`. The
ordinary path contains no JavaScript. Bulk per-frame image work uses weightless GPU models;
fixed-shape detector, tracking, fitting, pose, diagnostic and publication work uses weightless CPU
models.

The valid tracing-off window contains 297 fresh face frames after warmup. Submission to terminal
readback is 35.61 ms median / 47.03 ms p95, and whole-pipeline completion cadence is 20.14 Hz across
all consumed frames. The operator-traced window provides 259 exact eligible face chains with zero
unmatched complete chains. Their 13 operator calls total 33.83 ms mean; the service dependency chain
is 37.45 ms mean and traced submission-to-readback is 43.94 ms mean.

Every measured frame selected detection, so the 13-operation detection path is measured and the
10-operation tracking path is not. The first two corrected candidate launches failed while reusing
Spatial OpenMR PID 19385. After force-stopping the app and both OpenMR packages, new Spatial OpenMR
PIDs 27641 and 29701 initialized the same candidate successfully. This is strong lifecycle-state
evidence, but it does not identify the service's internal allocation defect.

Enable the exact candidate with:

```sh
./gradlew :FaceLandmarkerApp:assembleDebug :FaceRegistrationLabApp:assembleDebug \
  -PfaceCompactVstPipeline=true \
  -PfaceFusedControlModels=true \
  -PfaceGpuPreprocessing=true \
  -PfaceGpuSampleBytes=true
```

All four flags remain off by default. Fused controls require the compact adjacent-VST contract;
the retained-VST and compact-VST paths are mutually exclusive.

## Dataflow and ownership

```text
336x256 VST RGB8 ── GPU center-crop/normalize ── detector inference ── CPU detector control ─┐
3248x2464 VST RGB8 ──────────────────────────────────────────────────────────────────────────┼─ ROI/affine/state
full-view timestamp ── camera pose ──────────────────────────────────────────────────────────┘
                                                                                             │
full VST RGB8 ── GPU affine/sample/normalize ── landmark inference ── CPU landmark control ──┤
                                                                                             ├─ optional blendshapes
                                                                                             └─ selected final packet
```

The two VST operators are adjacent on detection frames. Their timestamps remain available to
native tracing, but the graph deliberately accepts the very small risk that adjacent accesses use
different exposures. Camera pose and the fused control contract use the full-view timestamp and
calibration.

No intermediate is read back to the app and uploaded again. Detector boxes/scores, ROI, affine,
tracking state, raw landmarks, fitting state and expression input remain inside SpatialML. The app
reads only the selected final face result. Calibration additionally reads frozen evidence after a
selected capture has completed.

This is not a zero-copy design. The current LiteRT SpatialML wrapper still copies Engine tensors
into delegate buffers and copies outputs back. In particular, the full 24,009,216-byte RGB8 image
is still an input to the landmark GPU-model wrapper. The candidate eliminates redundant outer
operators and app-process movement, but it does not prove direct VST texture-to-LiteRT binding.

## Ordinary detection-frame operations

The production constructor records this exact order for both the normal and lab apps. Backend 0 is
the requested CPU model backend, backend 1 the requested GPU preprocessing backend and backend 2
the existing trained-model backend.

| # | Operation | Implementation | What it does | Mean / p95 (ms) |
| ---: | --- | --- | --- | ---: |
| 1 | Compact camera access | Native `RectifiedVSTAccess`, 336×256 RGB8 | Obtains an aspect-preserving small detector view. | 1.98 / 4.64 |
| 2 | Full camera access | Native `RectifiedVSTAccess`, 3248×2464 RGB8 | Supplies the full landmark source and authoritative timestamp/K. | 10.34 / 14.53 |
| 3 | Camera pose | Native `CameraSpaceToWorld` | Resolves left optical-camera pose at the full-view timestamp. It moves only timestamp/matrix data. | 0.22 / 0.84 |
| 4 | Detector preprocessing | `detector_compact_preprocess_gpu`, backend 1 | One three-op model: slice columns 40…295, cast only the 256×256 crop and divide by 255. | 2.07 / 4.92 |
| 5 | Face detector | Existing trained `face_detector`, backend 2 | Produces 896 boxes and scores. | 2.70 / 4.82 |
| 6 | Detector control | `face_detector_control`, backend 0 | Fuses decode, identity ranking/suppression, ROI, lab camera selection, affine composition, clock/state update and producer snapshot. | 1.30 / 3.07 |
| 7 | Landmark preprocessing | `landmark_preprocess_rgb_gpu`, backend 1 | Applies the composed affine in RGB8 and emits one normalized 256×256 FP32 crop. | 7.68 / 11.61 |
| 8 | Face landmarks | Existing trained `face_landmarks_detector`, backend 2 | Produces 478 XYZ landmarks and presence. | 2.37 / 4.14 |
| 9 | Landmark control | `face_landmark_control_lab`, backend 0 | Fuses landmark validation/tracking, three inline Horn/Jacobi fits, pose filtering, validity feedback, diagnostics and the lab snapshot. | 2.39 / 4.89 |
| 10 | Expression input | `face_blend_input`, backend 0 | Gathers and normalizes the 146 expression points without JavaScript. | 0.16 / 0.49 |
| 11 | Blendshape inference | Existing `face_blendshapes`, backend 2 | Produces 52 expression scores. | 2.33 / 4.49 |
| 12 | Selected all-output packet | `face_output_7`, backend 0 | Packs pose, mesh and blendshapes into the 6,332-byte final result. | 0.17 / 0.69 |
| 13 | Completion fence | `face_completion_marker`, backend 0 | Publishes the sequence after the selected packet is complete. | 0.10 / 0.31 |

An all-output detection frame therefore uses 13 outer operations, down from the 25 operations in
the previous combined RGB-first/inline path. Pose-only or mesh-only skips the two expression calls
and uses 11 operations.

## Ordinary tracking-frame operations

Tracking frames skip the compact VST access, detector preprocessing, detector inference and the
896-anchor decoder:

| # | Operation | Implementation | What it does | Headset time |
| ---: | --- | --- | --- | ---: |
| 1 | Full camera access | Native `RectifiedVSTAccess` | Obtains the landmark image/timestamp/K. | Unmeasured |
| 2 | Camera pose | Native `CameraSpaceToWorld` | Resolves the optical-camera pose. | Unmeasured |
| 3 | Predicted ROI control | `face_roi_control`, backend 0 | Advances the ROI/clock/state and composes the landmark affine without paying detector decode cost. | Unmeasured |
| 4–6 | Landmark preprocess, inference and control | GPU model, trained model, CPU model | Same three-stage landmark path as a detection frame. | Unmeasured |
| 7–10 | Optional expressions, output and completion | Weightless/trained models | Publishes the requested final result. | Unmeasured |

The all-output tracking path uses 10 outer operations; a path without blendshapes uses eight. The
lab configuration selected detection for all 606 post-warmup normal frames and all 535 post-warmup
traced frames. No tracking-pipeline task appears in the trace, so detection-stage values must not be
presented as tracking measurements.

## Why models are used, and where native operators remain

- The two VST source accesses and `CameraSpaceToWorld` remain native because they are hardware and
  timestamp/pose sources, not replaceable tensor math.
- Detector image manipulation is one weightless GPU call. The fixed center crop happens before
  conversion, so only 196,608 RGB values are converted to float instead of the full image.
- Landmark affine sampling and normalization stay in one weightless GPU call. The full-image
  wrapper copy remains the largest unresolved data-movement risk.
- Detector decode/state and landmark tracking/fitting/pose use separate fused CPU models. They
  operate on compact fixed-shape tensors and avoid JavaScript dispatch/marshalling.
- Publication and completion are small CPU models so there is no JavaScript on the ordinary path.
- Lab diagnostic detector and landmark crops retain the normalized model outputs. Byte recovery is
  now performed app-side only when a selected final capture is read; two per-frame native bulk
  conversion operators have been removed.

One native bulk operation remains outside ordinary tracking: a selected calibration capture uses
`ApplyAffine` once to produce the final 1624×1232 RGB8 source image consumed by the app. Replacing
it with a model would require proving UINT8 GPU output support and pixel parity while moving a very
large final buffer; it is not paid per frame and is not included in the ordinary benchmark path.

## Calibration-evidence-only path

The full legacy calibration evidence path intentionally remains separate. After the fused landmark
stage it currently adds:

1. `mesh_landmarks` JavaScript.
2. `geometry_project` JavaScript.
3. `geometry_unproject` JavaScript.
4. One native arithmetic normalization.
5. Trained blendshape inference.
6. `pack_service_result` JavaScript.
7. `lab_geometry_snapshot` JavaScript.
8. The weightless completion marker.

These operations run only when a selected calibration evidence frame requests the old 2,994-float
packet and nested snapshot. They do not run during ordinary dynamic-output tracking. If evidence
capture latency becomes important, the correct follow-up is two weightless CPU models around the
trained blendshape inference, preserving the exact packet/snapshot contract and terminal fence.

## Generated weightless models

| Model | Backend | Bytes | Internal ops | Purpose |
| --- | --- | ---: | ---: | --- |
| `face_detector_control.tflite` | CPU | 99,380 | 467 | Detection decode, ROI, state, affine and producer snapshot. |
| `face_roi_control.tflite` | CPU | 38,084 | 218 | Predicted-ROI/state path when detection is skipped. |
| `face_landmark_control.tflite` | CPU | 383,436 | 2,522 | Production landmark tracking, inline fits, pose and diagnostics. |
| `face_landmark_control_lab.tflite` | CPU | 385,672 | 2,533 | Same computation plus the 1,995-float sparse lab snapshot. |
| `detector_compact_preprocess_gpu.tflite` | GPU | 1,132 | 3 | 336×256 RGB8 center crop, cast and normalization. |
| `face_completion_marker.tflite` | CPU | 676 | 1 | Copies the command sequence as the terminal fence. |

All mutable state remains explicit tensor input/output. The models do not hide persistent state.
`face_control_models.json` records the hashes, operators and full tensor contracts.

## Host correctness and call-cost evidence

Real host CPU LiteRT parity passes 30 detector/ROI/utility cases and 18 landmark cases against the
shipped JavaScript at FP32 operator boundaries. Maximum absolute differences are:

| Boundary | Maximum absolute difference |
| --- | ---: |
| Detector ROI | 0.0002746582 |
| Detector affine/sample affine | 0.0018310547 |
| Landmark pose | 0.0000228882 |
| Landmark diagnostics | 0.0001525879 |
| Lab fit snapshot | 0.0000305176 |

Informational host means are:

| Model | Host CPU mean |
| --- | ---: |
| Detector control | 0.422 ms |
| Predicted ROI control | 0.083 ms |
| Production landmark control | 0.700 ms |
| Lab landmark control | 0.410 ms |
| Compact preprocessing, CPU fallback | 0.557 ms |
| Completion marker | 0.016 ms |

The production graph-layout fixture passes every legacy variant plus the new candidate, all seven
output masks, detection/tracking selection and calibration routing. It validates 96 serialized
weightless-model call bindings against the actual FlatBuffers. For the fused candidate it asserts:

- exactly two adjacent VST accesses on detection frames;
- six detector, three tracking and three landmark-stage operators;
- no JavaScript in detector, tracking, landmark, expression or output pipelines;
- backend 1 for compact preprocessing and backend 0 for all control/completion models.

Existing terminal completion, stale-packet retry, bounded timeout, snapshot decode, exposure/export
motion, automatic 84-export ordering, clock recovery, collapsed-geometry rejection and intrinsics
regressions pass. Both apps pass `assembleDebug`, `lintDebug` and `spotlessCheck` with the candidate
flags. After correcting the timestamp ABI to bind the native four-word timestamp as INT32, the built
APK hashes are:

- Face Landmarker: `a2a5b85582993274bdb57784fb28040fb1f0aef0bf71eeaf03a4ea071a8ee3ad`
- Registration Lab: `3deef9c8b581be5d157bd48b66e00dec5fc1e9a4436546069475455f5e18c4ff`

The detector and ROI control models now accept INT32 timestamps and cast their four scalar
components to FP32 internally. This preserves the SpatialML timestamp ABI; binding those bytes as
FP32 previously produced zero timestamps even though the payload itself was valid.

## Headset measurement result

### Tracing-off whole-pipeline window

The valid normal window ran for 30.507 seconds from frame 384 through 995. Five initial frames are
excluded, leaving 606 analyzed completions: 297 eligible face frames and 309 no-face frames. All 606
used the detector path. Ten frames were stale and carried the expected “Waiting for a sensor camera
timestamp…” rejection. Every frame retained schema 2, output mask 7, the 6,332-byte packet and the
ordinary non-calibration route.

| Boundary | Population | Mean (ms) | Median (ms) | P95 (ms) |
| --- | ---: | ---: | ---: | ---: |
| Submit → terminal readback | 297 eligible face frames | 36.96 | 35.61 | 47.03 |
| Exposure → submit | 297 | 28.86 | 26.78 | 45.13 |
| Exposure → readback | 297 | 65.82 | 65.28 | 83.11 |
| App packet decode | 297 | 0.48 | 0.35 | 1.06 |
| App registration/reconstruction | 297 | 0.57 | 0.41 | 1.26 |
| Submit → app result ready | 297 | 38.02 | 36.68 | 48.84 |
| Readback → mesh upload acknowledgement | 297 | 10.51 | 10.56 | 15.19 |
| Exposure → mesh upload acknowledgement | 297 | 76.32 | 72.51 | 94.28 |
| Submit interval, all completions | 605 intervals | 49.65 | 48.51 | 61.75 |

The all-completion cadence is 20.14 Hz. Mesh upload is an app/SDK acknowledgement, not compositor
presentation, so the exposure-to-upload row is not motion-to-photon latency. Quantiles from
separate rows are not additive.

### Operator-traced dependency chains

The trace-only window ran for 30.483 seconds from frame 544 through 1084. The service submitted 530
instances of each of the four pipelines. After rejecting incomplete boundary events, the analyzer
formed 526 exact `detector → landmark_fit → expressions → output_7` chains. All 526 associate
uniquely with journal frames; zero complete chains are unmatched. The five `face_frame` clock anchors
span 2.44 ms. After window warmup and face/freshness/contract admission, 259 chains supply the
13-operation table above. Five other eligible journal frames lack a complete accepted four-task
event set and are excluded rather than filled from all-task statistics.

The two two-model pipelines cannot be named by native type signature alone. Their stable handle
contracts disambiguate them:

| Pipeline | Handle | Operators | Mapped placeholders | Accepted complete tasks |
| --- | --- | ---: | ---: | ---: |
| Detector | `0xb400007d2282a308` | 6 | 17 | 528 |
| Landmark + fit | `0xb400007d2282dcc8` | 3 | 23 | 527 |
| Expressions | `0xb400007d228bc1c8` | 2 | 3 | 527 |
| All-output publication | `0xb400007d229fa988` | 2 | 14 | 528 |

| Same-chain budget | Mean (ms) | Median (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| Sum of 13 operator calls | 33.83 | 33.31 | 40.57 |
| Within-task traced overhead | 2.01 | 1.76 | 3.90 |
| Inter-task dependency gap | 1.61 | 1.30 | 3.78 |
| Complete service chain span | 37.45 | 37.39 | 44.37 |
| Outside service chain: submit/readback/polling | 6.49 | 6.25 | 10.24 |
| Traced submit → terminal readback | 43.94 | 43.70 | 53.01 |

Enqueue wait is not added to these totals because downstream pipelines are enqueued before their
upstream dependency completes. Adding it would double-count upstream execution. Trace logging raises
latency, so the tracing-off 35.61/47.03 ms values are the end-to-end result; the traced window exists
to attribute the service budget.

Startup logs show both preprocessing models using the intended GPU path: the compact detector model
delegates 3/3 nodes to one `LITERT_CL` partition and the landmark model delegates 68/68 nodes to one
partition. The fixed-shape control models are created with the CPU backend; the trained detector,
landmark and blendshape models use the existing Qualcomm dispatch path. Model-call timings still
include Engine-to-delegate and delegate-to-Engine wrapper copies.

### Fresh-service requirement and restoration

The corrected build first failed twice while Spatial OpenMR PID 19385 remained alive. Both launches
stopped during creation of the first GPU compact-preprocessing model with `LiteRt create input buffer
failed`, followed by `OperatorRunModelInference Unable to initialize LiteRT model and runtime`. The
second failure under the same service PID rules out a one-off launch race.

The measurement helper was then changed to force-stop the lab and normal face apps plus
`com.bytedance.pico.openmr.spatial` and `com.bytedance.pico.openmr` before candidate and restored-app
launches. The unchanged candidate initialized under fresh Spatial OpenMR PID 27641 for the normal
window and PID 29701 for the trace window. Treat fresh OpenMR processes as a required precondition
for GPU candidate launches until the service teardown/allocation lifecycle is fixed; the evidence
does not identify the exact internal retained resource.

After both valid runs the original APK hash
`7ae804e2e3606d81eb7c2ab64f649abad940731d1feab5a7578d68afd99ef023`, unset debug property and
output mask 7 were restored. The final trace run preserved the private optical calibration and all
301 pre-existing external files, reported no restoration errors, recovered healthy face frame 57
and released the devmux lease. No app data was cleared, no app was uninstalled, and no service APK,
recording, profile or calibration was changed.

Performance does not validate optical alignment or selected calibration exports. A future capture
acceptance run remains separate from this benchmark.

## Reproduction

```sh
python3 FaceRegistrationLabApp/tools/generate_face_control_models.py

uv run --no-project --with ai-edge-litert python \
  FaceRegistrationLabApp/tools/validate_face_control_models.py \
  --models FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker/model \
  --output <model-validation-output>

python3 FaceRegistrationLabApp/tools/face_pipeline_layout.py \
  --output <layout-output> \
  --json-jar /private/tmp/face-calibration-tuner/json.jar

python3 FaceRegistrationLabApp/tools/validate_lab_runtime.py --output <runtime-output>
python3 FaceRegistrationLabApp/tools/validate_intrinsics.py \
  --output <intrinsics-output> \
  --json-jar /private/tmp/face-calibration-tuner/json.jar

# Device capture. A fresh service process is required for this GPU candidate.
python3 FaceRegistrationLabApp/tools/measure_compact_fused_controls.py \
  --output <unique-session-output> \
  --candidate-apk FaceRegistrationLabApp/build/outputs/apk/debug/registrationlab-1.0-debug.apk \
  --seconds 30 \
  --reset-openmr-services \
  --window both

# Offline combination of the valid tracing-off and traced sessions.
python3 FaceRegistrationLabApp/tools/analyze_compact_fused_controls.py \
  --normal-session artifacts/facelandmarker/compact-fused-controls-20261103/session-output-20261103-int32-fresh-services \
  --trace-session artifacts/facelandmarker/compact-fused-controls-20261103/session-output-20261103-int32-fresh-services-trace \
  --layout artifacts/facelandmarker/compact-fused-controls-20261103/preflight-int32/layout/operator-layout-compact-fused-controls.json \
  --output artifacts/facelandmarker/compact-fused-controls-20261103/session-output-20261103-int32-fresh-services-trace/analysis/compact-fused
```

The final machine-readable results are `compact-fused-analysis.json`, `face-chains.json`,
`mapped-operator-timings.json` and `ordered-face-operations.csv` under that analysis directory.

No commit or push was made.
