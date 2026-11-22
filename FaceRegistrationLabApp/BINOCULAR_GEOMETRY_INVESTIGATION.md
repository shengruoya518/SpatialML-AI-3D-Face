# Binocular face registration: measure the renderer before fitting the face

**Current correction conclusion:** [Completed roll/board analysis](../artifacts/facelandmarker/registration-lab/roll-trial-2026-11-05-b8c6a3/FINDINGS.md) recovers all 69 uploads and retains 38 still exposures. The previous head-relative −40.0875 mm Y term independently transfers at 4.424 px versus 41.037 current; baseline-fixed/Stage-Y terms score 8.753/8.615. A conservative lab-only [0,−0.040,0] m head translation before H_capture is the recommended next experiment, shared by pose and vertices, scale 1.0. Physical board images revalidate source K but its actual geometry replay worsens binocular face overlap; source calibration does not independently establish current compositor/metric face scale. The subsequent [reversible lab comparison](LAB_POSITION_COMPARISON.md) is implemented and built; installation/startup/UI are verified, with real-face physical comparison acceptance pending. This analysis did not apply a correction to its source data. See the report for uncertainty, opposite-eye scale instability and the regression path.

**Roll-only follow-up implemented:** [Implementation and validation](../artifacts/facelandmarker/registration-lab/roll-only-update-2026-11-05/IMPLEMENTATION.md) adds the four-hold **Roll trial** with actual baseline-relative orientation gating, face clearance and side-column references. Follow [the current procedure](AUTOMATIC_CAPTURE_STEPS.md#roll-only-test--next-capture). The full trial does not need repeating. Prior transform audit and fits remain authoritative; no fitted correction is applied. Installation and recorded-eye acceptance are tracked separately in the implementation report.

**Full trial analyzed (2026-11-05 UTC):** [Run 7aeeab26](../artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-712cf5/FINDINGS.md) has ten holds / thirty passing native exports, 181 recovered binocular uploads and 134 selected still observations. A roughly 40 mm downward head-frame offset reduces mean held-out RMS from 62.14 to 9.18 px; head translation + camera-ray scale reduces it to 5.46 px. On the preceding recording, the downward-only model transfers better (2.88 px versus 4.77 px). Treat registration and metric-depth scale separately. These are offline predictions, not applied calibration.

The [repaired check](../artifacts/facelandmarker/registration-lab/geometry-check-2026-11-05-cc0ddf/FINDINGS.md) and full trial verify the virtual references and frame-code association on hardware. Actual roll coverage is only about −2.92° to +1.32°, some reference panels obscure anatomy, and no independent measured board was analyzed. The roll-only revision now enforces measured roll and keeps references beside the reconstructed face. Temporary offset/scale comparisons and independent metric control remain future work; see [the concrete proposal](../artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-712cf5/FINDINGS.md#next-useful-validation). Repeating the same prompts alone will not resolve the origin/depth ambiguity.

The texture-repaired APK was verified on PB311XHGKC220141G at retrieval, SHA-256 `f6f57e262556a55c4e8b7ef57b3d9714ccbedc89c58c87d1086672ca00edc870`. Original video/exports and saved calibration are preserved. This analysis made no app/service source change, install, restart or calibration save. Source changes from the diagnostic implementation remain uncommitted.

- [Previous texture-repaired APK and hash](../artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-7eebca/texture-fix/build-manifest.json)
- [Previous texture-repair installation and preservation evidence](../artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-7eebca/texture-fix/install/installation.json)
- [Full previous recording and measurements](../artifacts/facelandmarker/registration-lab/full-calibration-2026-11-05-8a185f/FINDINGS.md)
- [Additional audit of existing stereo disparity](../artifacts/facelandmarker/registration-lab/binocular-geometry-2026-11-04/existing-disparity-audit.json)
- [Capture/analysis implementation](tools/binocular_geometry.py)
- [Production-geometry synthetic regression](tools/validate_binocular_geometry.py)

## What the current evidence says

The repaired Geometry check yields 44 accepted geometry pairs from 65 sampled same-PTS stereo pairs. All accepted pairs have twelve tags; worst held-out-tag RMS is 1.951 px, and green-marker RMS median/max is 0.753/0.953 px. All 20 unique uploads supply estimated anatomy with two-view incompatibility RMS median/max 0.359/0.560 px. The mesh remains 47.22/47.87 px too high in the left/right eye, with a median triangulated anatomy-minus-mesh displacement of approximately 38 mm down and 28 mm farther away in the capture-head frame. This measures displacement through the virtual-reference projections without assuming the earlier recording pinhole parameters, but anatomy still comes from model estimates, including eye corners behind glasses. No physical board was measured. One frontal pose cannot distinguish the correction family or establish universal coefficients.

The whole hold's reconstructed anatomical centre spans 15.668 mm, above the 15 mm fitting limit. A continuous 14-exposure segment, frames 6902–6915 over 2.1667 seconds, passes at 14.516 mm. Aggregate pixel/displacement statistics describe all 20 observations; a later correction fit must use still segments and multiple poses. No full correction fit was run on this check.

The earlier intrinsics sweep provides complementary evidence:

The full run has 84 accepted exports and 1,522 eligible recorded stereo pairs. Every one of the 2,994 packet values matches the saved probe. Replaying the native geometry and Stage transforms succeeds. These checks test whether the implementation agrees with itself; they do not measure the physical face-to-eye projection.

The controls put the mesh about 45–49 recorded pixels too high near the subject and 28 pixels too high farther away. A fixed spatial displacement explains the inverse-depth pattern much better than one angular/principal-point adjustment. The previously fitted equivalent is about **39 mm downward**, conditional on inferred depth and a pinhole recording model. The cached camera-to-head Y translation is +43.34 mm. Similar magnitudes are a reason to inspect the origin contract, not evidence that the factory translation should be deleted.

The horizontal error is also binocular. In the near frontal control the median mesh disparity is 79.01 px, compared with 69.76 px for anatomy. Under shared rectified parallel eye cameras with zero disparity at infinity, their ratio would imply a **1.131 camera-ray scale**. The equivalent conditional ratios are 1.147 left turn, 1.093 right turn, and 1.111 far. These are not calibrated scale factors: convergence, recording projection, landmark bias and subject motion remain possible confounds. The ratios do establish why vertical adjustment alone is insufficient.

The previous focal reductions make both size and extra disparity worse. The old Y75 preference near and Y40 preference far are incompatible as one fixed principal-point correction. Keep C as an experimental reference while measuring the missing quantities.

## First-principles model

Let `Xc` be a reconstructed point in the left optical camera, `E` the optical-camera-to-head matrix, `H(t)` capture-head-to-Stage, and `Pe(tdisplay)` the projection from Stage into recorded eye `e`:

```text
Xstage = H(tcapture) E Xc
ue = project(Pe(tdisplay) Xstage)
```

The service emits points in its tracking space. The app currently rebases them with:

```text
TserviceToStage = H(tcapture) E inverse(Cservice)
```

This matrix multiplication is consistent with the exports. Its semantic correctness depends on E and H describing the same head origin and on the camera pose/timestamp referring to the exposure used for inference.

The face graph reconstructs metric depth from **one camera plus the canonical face prior**. Its three similarity fits do not introduce a second-view or measured-distance constraint. At fixed camera rays, `Xc` and `s Xc` give exactly the same source-image coordinates. Native reprojection can therefore pass with incorrect absolute depth and face scale. Two separated eyes can distinguish those depths through parallax.

A useful candidate family is:

```text
Xstage_corrected = H(tcapture) DeltaHead E Sray Xc
Tcorrected      = H(tcapture) DeltaHead E Sray inverse(Cservice)
```

`DeltaHead` is a rigid transform in the capture-head frame. `Sray = diag(s,s,s,1)` scales XYZ about the optical camera centre. It preserves the left source-image rays while changing metric depth. Scaling a mesh about its own centre changes its apparent size without making this same correction. A constant Stage/world translation also behaves differently from a head-frame translation as the headset rotates.

The existing normal sample size/depth parameter already scales the fitted camera-space translation and scale before the world transform. A stationary validated ray-scale correction could use that existing facility; the lab intentionally keeps its pipeline scale at 1 during measurement. A calibration must be applied consistently to both the mesh and pose, with explicit units and pivot. No service change is needed merely to test an app-side registration correction.

The analyzer compares identity, head translation, head rigid transform, camera-ray scale, and rigid-plus-ray-scale. It fits **both eyes' pixel residuals** and validates by leaving out entire pose holds. A lower training error alone is not acceptance.

## SDK and pipeline audit

- The declaring SDK version is `spatialBom = "6.1.9"` in `gradle/libs.versions.toml`.
- The local SpatialSDK HMD source documents position/rotation in global coordinates, in metres. It does not identify a physical eye midpoint, IMU origin, or prediction horizon. Its native adapter forwards `spatialpack::HMDTrackingResult.getHMDPose()` without a visible origin conversion.
- The installed 6.1.9 tracking AAR exposes `hmdPose`; its timestamp getter is Kotlin-internal. The sibling source calls that timestamp UTC milliseconds. It is not a usable, verified public exposure-clock contract. The app records callback-arrival `System.nanoTime` and preserves that distinction.
- The configured knowledge environment is Unity 6.0; there is no aligned project-local selector. That graph was not used as authority for Kotlin 6.1.9. Public signatures from the actual 6.1.9 AAR and the local SDK source support the new mesh UV/texture APIs. No private API or reflection was added.
- `CameraCalibration.cpp` multiplies optical metadata by a fixed IMU-to-head conversion copied from the OpenMR convention. The contract connecting this origin to the tracking provider remains unproven below the inspected wrapper.
- The latest graph retains the 336×336 VST workaround, logical 336×256 compact preprocessing, detector/image affine correction, fused control models, and explicit completion barrier. The new build enables `faceCompactVstPipeline`, `faceFusedControlModels`, `faceGpuPreprocessing`, and `faceGpuSampleBytes`.
- This change adds diagnostic scene geometry and metadata. It does not alter learned models, K, service binaries, camera calibration, or the accepted Stage registration equation.

## What the new capture adds

During marked phases, one mesh buffer contains the existing eight green anatomical markers, twelve ArUco reference panels, and a frame code. The panels use `DICT_4X4_50`, IDs 0–11, placed at 0.65, 1.15 and 2.05 m in the capture-HMD frame. The code carries the full 32-bit pipeline sequence plus CRC-8/ATM. It identifies the displayed mesh payload directly, independent of the old 100 ms UI badge/recording clock fit.

Reference positions depend on the chosen capture-HMD frame, but **not on the face reconstruction, camera intrinsics, optical extrinsics, or canonical face size**. Their non-coplanar layout makes a full 3×4 projection observable. App code places all geometry in Stage through the actual mesh owner conversion and records its round-trip error. The analyzer estimates each eye's projection in reference-rig coordinates; the logged rig-to-Stage matrix changes its coordinate basis afterward. An unverified physical HMD origin does not need to be assumed to fit these visible virtual references.

The `projection_reference` journal event records:

- ArUco IDs and outer-black-border corners in rig and Stage metres;
- optical-to-head, capture-head-to-Stage, service-to-Stage and capture-camera-to-service matrices;
- actual Stage face markers, face pose, sequence, protocol, trial and phase;
- head history coverage and movement at exposure, callback head pose at upload, upload/capture times;
- mesh-owner round-trip error. Upload completion is explicitly not a compositor-present timestamp.

Snapshots keep schema 3 and add `registrationEvidence`; prior native analyzers can still read them. Capture prompts are recorded as prompts, not measured physical ground truth. Existing intrinsics capture and saved profiles remain available. Completing/cancelling either geometry sequence restores the starting in-memory K configuration; neither action saves new calibration values.

## Existing recording procedure

1. The repaired build is already installed on PB311XHGKC220141G and its Geometry check passes. Put a well-lit real face in view and wait for the live mesh to follow it. Remove glasses if practical. This is the procedure used for the analyzed trial; proposed next diagnostic changes are described above. The archived APK is `artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-7eebca/texture-fix/registrationlab-geometry-texture-fix-debug.apk`.
2. Start a new **Spatial** recording manually, then choose **Geometry trial** on the headset. It has ten holds and thirty exports, normally a few minutes plus settling. The current ROM defers remote COMMAND broadcasts, so use headset controls.
3. Follow the prompts: frontal at ~0.7, ~1.2 and ~2 m; subject turns left/right at ~1.2 m; subject stays frontal while the **wearer** rolls left/right, then turns the headset left/right while retaining the face in view; finish with a level frontal ~1.2 m repeat. Holds 6–9 change headset orientation. Move between holds, then keep both people still with a neutral expression during capture.
4. Keep the real face within the reference frame and the target panels visible. **Cancel capture** is available on the headset and restores starting values. Stop recording after DONE, cancellation or timeout. Retain all recordings and session files, including partial evidence on failure.

For a later rendering/layout change, repeat the short Geometry check before requesting another full trial. It provides clean → marked → clean and three exports. Require matching valid codes in both eyes, at least nine tags including two per depth, and agreement between projected and visible green markers. The current check and full trial meet these gates on their accepted observations; panel occlusion and limited measured roll constrain the next capture.

If available, hold the existing flat **8×6-inner-corner, 20 mm-square checkerboard** beside the face during the three distance holds. Measure its printed square width rather than trusting printer scaling. It is optional, and the face must remain visible. The board provides a known metric object independent of MediaPipe anatomy. Analysis reports its stereo-reconstructed square lengths and planarity; it does not silently replace a missing board with a model estimate.

## Analysis and rejection criteria

Use Python 3.12 with NumPy 2.2.6, OpenCV headless 4.12.0.88, SciPy 1.15.3, PyAV 19.0.2, Pillow, and MediaPipe 0.10.32 when automatic anatomy inference is wanted. `UV_NATIVE_TLS=true uv run --no-project --python 3.12 --with ... python ...` can provision these locally.

Extract a pair from a marked interval, using both MV-HEVC views and identical PTS:

```sh
python FaceRegistrationLabApp/tools/binocular_geometry.py extract \
  --video /path/to/ScreenRecording.mp4 --seconds 40 --output /path/to/pair

python FaceRegistrationLabApp/tools/binocular_geometry.py observe \
  --left /path/to/pair/eye0.png --right /path/to/pair/eye1.png \
  --timeline /path/to/session/timeline.jsonl \
  --task /path/to/face_landmarker.task --output /path/to/observation.json
```

For **Roll trial** images, add `--reference-layout roll-side-columns-v1` to `observe`. The default remains `original-v1` for earlier Geometry recordings. The analyzer rejects a layout choice that disagrees with the matching journal row, and carries `rollCapture` measured angles/baseline into observations. Inspect those recorded transforms and angle acceptance fields independently of prompt labels. Combine the four new roll holds with earlier multi-distance evidence when comparing correction transfer; the general `fit` command intentionally still requires at least five near/mid/far and orientation holds.

The previously verified task is retained under `artifacts/facelandmarker/registration-lab/rom-services-one-check-2026-11-04/analysis/face_landmarker.task`; SHA-256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`. As an independent check, replace `--task` with `--anatomy points.json`: JSON fields are `landmarkIds: [33,133,362,263,1,61,291,152]` and `left`/`right`, each eight `[x,y]` pixel coordinates. Inspect eye corners, nose, mouth and chin manually; inpainted MediaPipe estimates are not ground truth. Add `--board-square-metres 0.02` only for the matching measured board.

For each still hold, measure at least three distinct displayed exposures spanning at least 0.3 seconds. Keep examples away from pose changes. Then:

```sh
python FaceRegistrationLabApp/tools/binocular_geometry.py fit \
  --observations /path/to/observations/*.json --output /path/to/correction-candidates.json
```

Observation gates include nondegenerate normalized DLT; ≥9 reference tags across three depths; ≤1.5 px fit RMS and ≤2 px worst leave-one-tag-out RMS; code CRC and identical sequence in both views; one matching journal upload; covered/stable exposure head history; ≤0.9 s camera age at upload; <0.1 mm owner-conversion error; and ≤3 px projected-to-observed green-marker distance. Initial pixel thresholds are diagnostic tolerances and must be assessed against actual recording resolution, noise and manual annotation uncertainty.

Anatomical correspondences are triangulated and then refined against both eyes. The residual remaining after free per-point 3D fitting is a **two-view incompatibility floor**. If its RMS exceeds 2 px, the observation is excluded from correction fitting. A rigid mesh pose cannot fix a correspondence that is incompatible with a single 3D point. Possible causes include mistaken anatomy, different eye times, non-pinhole recording effects, or passthrough compositing.

The fitter requires near/mid/far plus at least two orientation holds, rejects duplicate displayed frames, and checks that each hold's reconstructed anatomical centre spans no more than 15 mm. It balances holds so a long distant segment does not dominate, rejects bounded/unidentifiable solutions, and reports leave-one-pose-out errors. This stillness screen is not an exact exposure-to-display motion proof; short facial movements, timing errors and reconstruction noise still require visual review.

## How to decide the fix boundary

| New evidence | Implication and next action |
|---|---|
| Virtual references fail held-out projection | Resolve reference rendering, coordinate conversion, recording warp or timing before touching face calibration. |
| Virtual projections pass but anatomical two-view floor is high | Check landmark correspondence, stereo PTS and passthrough reprojection. One 3D transform may be insufficient. |
| One head rigid correction generalizes across distance and headset orientation | Validate the head/optical-origin contract; implement an explicit registration correction with provenance. |
| Ray scale improves both eyes while preserving source rays | Correct metric face depth/scale. Test another subject; a canonical-face prior can produce subject-specific bias. |
| Rigid plus ray scale is required | Keep the camera registration and face-depth terms separate; apply both to mesh and pose. |
| Residual varies with subject yaw or face region after those terms | Investigate landmark reconstruction/face shape. Consider synchronized right-camera landmarks or independent stereo/depth constraints. |
| Static holds pass, motion fails | Investigate timestamp/prediction and latency separately; callback arrival is not capture time. |

The final acceptance is a new held-out recording in both eyes, at multiple distances and orientations, preferably with a second subject and a metric board. A shared camera correction should not vary by subject; an anthropometric depth prior can. A recording-camera fit also needs wearer confirmation because the exported Spatial video may differ from the final physical display warp.

## Validation boundary

The repaired check and full trial empirically verify atlas orientation, reference projections, sequence/CRC association and logged-to-rendered green geometry. [Full-trial metrics, exclusions and original recording](../artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-712cf5/FINDINGS.md) document 134 still observations, held-out correction scores and earlier-recording transfer. The downward registration offset is supported; a universal scale, coordinate-origin diagnosis, broad roll/physical-distance coverage and physical-display acceptance remain unverified.

Both apps' debug builds, lint and Spotless pass with the four compact/fused flags enabled. The actual Kotlin capture harness preserves the old 84-export sequence and executes the new 30-export sequence, fixed C values, short geometry entry, immutable metadata, restoration, freshness/motion and scene-acknowledgement gates.

The synthetic renderer uses the **production Kotlin mesh/UVs and texture atlas**, not an independently drawn substitute. All twelve ArUco IDs and the sequence/CRC decode in both simulated eyes. Leave-one-tag-out projection errors are below 0.5 px. Tests recover known translation, rotation and ray-scale corrections, reject coplanar references, bad CRC, missing references, moving exposure history, duplicate observations and inconsistent stereo points, and validate all ten held-out poses. These tests do not establish headset texture orientation, visibility, SDK mesh-buffer behavior or physical calibration.

Detailed build, synthetic and host reports are retained in `artifacts/facelandmarker/registration-lab/binocular-geometry-2026-11-04/`. The original Spatial video remains in `artifacts/facelandmarker/registration-lab/full-calibration-2026-11-05-8a185f/ScreenRecording_2026.11.05-03.38.14-AM.mp4` with both eyes intact.
