# Face Landmarker in Full Space with passthrough

This independently runnable sample ports the Unity XR Face Landmarker from
`SecureMR-Unity-Sample-Private-worktrees/dev-pipeline_zoo`. It tracks one face seen by the
headset's outward-facing camera and renders a deforming **478-vertex, 906-triangle mesh** in
the app's Full Space Stage with video passthrough. The result also contains **52 MediaPipe blendshape scores**.

The Stage owns rendering. SpatialML has a **zero-sized, disabled container** and executes the
camera, detector, landmark, tracking/fit checks, and optional blendshape graph. The application
reads only selected final outputs, finishes optional mesh reconstruction, and rebases OpenXR Local
coordinates into the Stage.
Camera pixels stay in SpatialML.

## Run

Select **FaceLandmarkerApp** in Android Studio, or build it with:

```sh
./gradlew :FaceLandmarkerApp:assembleDebug
```

To build the latest compact-VST and fused-control pipeline, use:

```sh
./gradlew :FaceLandmarkerApp:assembleDebug \
  -PfaceCompactVstPipeline=true \
  -PfaceFusedControlModels=true \
  -PfaceGpuPreprocessing=true \
  -PfaceGpuSampleBytes=true
```

These flags are opt-in; the plain build command selects the native baseline described below.
The compact pipeline uses existing `RectifiedVSTAccess` operators and LiteRT inference and
requires no custom OpenMR service APK. Leave `faceRetainedVstPipeline` disabled: the earlier
retained-VST experiment requires custom service operators and cannot be combined with this path.

The optimized path uses adjacent small/full VST views, GPU image preprocessing and fused CPU
control/geometry models. The compact VST view is square 336×336 to avoid the shipped service's
non-square resize defect; its GPU model restores the logical 336×256 view before the center crop.
The lab's detector mapping includes its existing image calibration affine.
[Correction and lab verification](../FaceRegistrationLabApp/MESH_FLICKER_RECORDING_FINDINGS_2026-11-03.md)
document this shared source change; the normal app has been built but not reinstalled for that check.
Its ordinary detection path has no JavaScript. On the tested ROM,
GPU initialization required fresh OpenMR service processes before launch; stale processes
could fail with `LiteRt create input buffer failed`. The registration-lab benchmark and the
remaining tracking, optical and capture acceptance limits are documented in the
[latest pipeline report](../FaceRegistrationLabApp/COMPACT_FUSED_CONTROL_PIPELINE_2026-11-03.md).

The internal naming convention produces
`FaceLandmarkerApp/build/outputs/apk/debug/facelandmarker-1.0-debug.apk`.
The application ID is `com.pico.spatial.ml.sample.facelandmarker`. It uses the project-wide
Spatial SDK **6.1.9** BOM and requires a PICO OS 6 headset with SpatialML and LiteRT NPU support.
The emulator cannot validate these features.

Grant camera permission and point the outward-facing camera toward a face. The control panel
shows detection/presence confidence. **Face pose**, **Face mesh**, and **Face blendshapes**
switches select any combination; all-off suspends submissions. Selected pose coordinates and
strongest blendshape scores appear on the panel. Changes apply between completed frames. **Face size / depth**
scales both size and camera-relative distance about the left optical center, preserving the
projection rays. **Reset size / depth** restores `1.00`. **Pause** hides the mesh and stops new
frame submissions; **Resume** starts with detector reacquisition. The mesh hides on face loss.
**Close sample** and the system Back action close the Stage.

The launcher declares `pico.spatial.stage.style=1` (**Mixed**). Opening the Stage still places the
app in **Full Space**, while Mixed style keeps video passthrough visible at zero immersion.
Style `3` (**Full**) disables passthrough and can show a black immersive surround when no
environment is supplied. This sample does not create a separate WindowContainer or SpatialML portal;
the control panel is a transparent SpatialView attachment. Controls use SpatialUI `Button`,
`Slider`, `Switch`, and `Text`, wrapped by `PicoTheme`, with native palette roles and built-in interaction
treatment. The mesh uses a double-sided unlit green material independently of the UI palette. The menu
is centered at `(0, -0.25, -1)` meters relative to the headset, rather than the former
`(-0.45, -0.2, -0.85)` placement in the left periphery.

## Graph and SDK boundary

`FaceLandmarkerGraph.kt` constructs its pipelines once:

1. **Acquisition:** coherent left VST image, timestamp, intrinsics and calibrated capture-time
   camera-to-service-Local transform; 256-square detector; weighted suppression and face selection.
2. **Tracking:** the same capture/metadata path, with predicted ROI and no detector inference.
3. **Common:** rotated ROI crop, landmark model, quality/presence checks, persistent tracking,
   three weighted similarity fits with native SVD, depth unprojection, and raw/filtered service poses.
   The live mesh uses the raw pose matching its current vertices; filtering is reserved for rigid overlays.
4. **Optional expressions:** weightless CPU LiteRT ROI/gather/normalization and the trained blendshape head.
5. **Selected output:** one of seven compact FP32 publication variants, followed by terminal completion.

The selected producer precedes Common, optional expressions and publication through explicit native
run handles. App-only mesh reconstruction runs after this final handoff. The runner waits for the
separate terminal marker and matching packet sequence before submitting another capture.

The calibration app temporarily uses its preserved full service geometry and snapshot path for
One check/Full trial. See [dynamic output contracts, efficiency and validation](../FaceRegistrationLabApp/DYNAMIC_FACE_OUTPUTS.md). A timeout
ends that run; it never authorizes reuse of shared image tensors while work may still be pending.

The port reuses the Unity sample's preserved bulk JavaScript geometry operators with three native
SVDs. This avoids the large number of dispatches in its literal native-math expansion. It preserves
the tracker, quality gates, reflection-corrected similarity solve, canonical weights and iris
handling. This choice has host parity evidence; comparative on-device performance is not established.

Spatial SDK 6.1.9's fluent `Pipeline` API does not expose `CameraSpaceToWorld`, and its package loader
skips `cam_space_to_xr_local`. To preserve capture-time registration, `SpatialMLGraphSession.kt`
uses the **public platform native bindings** that the SDK itself uses. It does not access the SDK's
internal handles. The platform supplies these classes at runtime. Their compile-only public
signatures are included under `platform-api/`, compiled by the module build, and excluded from
the APK. This mirrors the SDK's compile-only `foundation:0.11.7` dependency without requiring
that internal artifact repository. Session, global tensors, pipeline handles, and binding maps
are owned and released explicitly by this adapter.

## Models and preprocessing

The detector is the **256-square long-range model actually assigned in the Unity scene**,
from `Assets/MLModels/face_detector.tflite.bytes`. The unused 128-square detector in the Unity
FaceLandmarker model folder is not used here. Landmarker and blendshape bytes are copied from
the FaceLandmarker folder. `provenance.json` records their source paths, source Git revision,
and SHA-256 hashes; the landmarker retains the source's fixed shape-signature adjustment.

| Model | Input | Outputs |
| --- | --- | --- |
| Detector | `image`, float32 `[1,256,256,3]`, RGB `[0,1]` | `box_coords_1` `[1,512,16]`, `box_coords_2` `[1,384,16]`, corresponding score tensors |
| Landmarker | `input_12`, float32 `[1,256,256,3]`, RGB `[0,1]` | `Identity`, 1434 values; `Identity_1` presence logit; `Identity_2` auxiliary scalar |
| Blendshapes | signature `input_points`, float32 `[1,146,2]`, image XY divided by 1024 | signature `tf.__operators__.getitem_3`, 52 scores |

The session requests **3248×2464** capture, matching the Unity source. Detector preprocessing
resizes the full image to 256 square; landmark preprocessing samples the rotated square ROI
directly from that image. Rectified VST `R8G8B8` is RGB: this port preserves that order instead
of copying the extra red/blue swap identified in the source Unity contract audit. Both image
models receive byte-to-float conversion and division by 255. The blendshape model's own scale
normalization permits the source's `/1024` numeric-range adjustment.

## Coordinate contract

The **service OpenXR Local origin and the app Stage origin are different spaces**. Both are
right-handed and use meters. A matrix from `CameraSpaceToWorld` cannot be used directly as a
Stage transform. The recording analysis in [ALIGNMENT.md](ALIGNMENT.md) documents the resulting
offset in the first version.

Canonical geometry is expressed in centimeters. Let `P = [sR,t]` be the fitted canonical-centimeter
to camera-centimeter similarity and `W` the same-capture raw canonical-meter to service-Local-meter
similarity. For a reconstructed camera-centimeter point `m`, `pack_service_result.js` computes:

```text
localMeters = 0.01 * transpose(P.basis) * (m - P.translation) / s²
serviceMeters = W.basis * localMeters + W.translation
```

The app then uses the capture-time Stage HMD pose `H_stage`, the optical-camera-to-head calibration
`E`, and the same capture's camera-to-service matrix `C_service`:

```text
serviceToStage = H_stage * E * inverse(C_service)
stageMeters = serviceToStage * serviceMeters
stageFacePose = serviceToStage * W
```

Because `C_service = H_service * E`, this removes the service origin and preserves the calibrated
left optical offset. No Unity Z reflection is applied. The app samples `HMDTrackingProvider` on
its direct callback and keeps a 512-pose monotonic history. It interpolates at the VST capture time;
SDK 6.1.9 does not expose the provider's sensor timestamp in Kotlin, so the history timestamps
callback arrival before UI dispatch. Gaps over 100 ms, captures older than the history, and forward
extrapolation over 50 ms are rejected. A missing matching pose hides the mesh instead of using
a current/render-time pose.

`CameraCalibration.cpp` only queries `PXRCaptureGetCameraExtrinsics` from the platform's public
`libpxrcapturendk.so`; it never opens a camera or starts a stream. It uses the same IMU-to-head
conversion as the deployed OpenMR VSTSession. This is a runtime/service compatibility boundary:
the source currently hardcodes that IMU conversion, so a ROM that changes it needs revalidation.
The device-specific optical matrix is queried, never replaced by a generic guessed camera offset.
The app queries and releases its metadata client **before creating the SpatialML session**, then
caches the calibration for retries. Although the query only reads metadata, `PXRCaptureRelease`
also stops the shared camera; calling it after graph creation prevents live detection. Missing or
non-advancing capture timestamps for three seconds now produce a retryable camera error instead
of leaving the status at "Looking for a face". B3110 returns a left-camera translation of
approximately `(-0.02649, 0.04334, -0.04793)` meters in head space.

`FaceMeshScene` converts final Stage positions into its actual mesh owner with public
`Entity.convertPositionFrom(..., null)` calls. Four basis samples establish the affine conversion
for all vertices. The face Entity has an identity transform: the face pose is not applied again.
Only the control-panel anchor follows the headset.

The mesh uses a double-sided cyan `PhysicallyBasedMaterial` with roughness `0.7`, metallic `0`,
and per-frame area-weighted normals. Headset-relative directional lights supply an oblique key
at `1500` lux and an opposing fill at `350` lux without shadows. The earlier unlit material ignored
normals and made the curved geometry appear flat. See [SHADING.md](SHADING.md) for the correction.

The mesh resource is created once from hidden canonical geometry. Accepted readbacks replace its
vertex positions, recompute area-weighted normals, and update bounds through
`MeshResource.replaceWithMeshModel`. Resource creation/replacement runs on an IO coroutine;
Entity changes stay on the UI thread. Mesh replacements finish sequentially; the StateFlow then
supplies the newest frame, so faster inference cannot repeatedly cancel rendering updates.
Disposal detaches SDK-owned attachment panels and releases the app-owned mesh, material, entities,
head tracking subscription, and inference graph.

## Result tensor

The global result is **2994 float32 values**. Its first 2978 slots preserve the Unity mesh-result
layout, with vertex/pose coordinates in service Local space, without Unity reflections. The app
rebases vertices and pose before publishing `FaceFrame` to the renderer. The final matrix records the
same capture's calibrated camera pose.

| Offset | Count | Value |
| --- | --- | --- |
| 0 | 4 | Sequence, valid face, detector confidence, presence confidence |
| 4 | 1434 | 478 normalized image XYZ landmarks |
| 1438 | 1434 | 478 service-Local vertex XYZ positions, meters; rebased to Stage in Kotlin |
| 2872 | 52 | Blendshape scores in geometry label order |
| 2924 | 16 | Row-major canonical-meter to service-Local-meter face pose; rebased to Stage in Kotlin |
| 2940 | 6 | Detector diagnostics and reserved slots |
| 2946 | 32 | Tracking, quality, intrinsics, fit and reprojection diagnostics |
| 2978 | 16 | Row-major capture-time left-camera-to-service-Local matrix |

`FaceFrame` exposes these arrays without Android/Unity transform assumptions. Validity is published
after geometry is packed. Invalid or non-finite geometry is rejected. The renderer clears visibility
on missing/invalid frames and does not display stale blendshape scores.

## Verification

```sh
./gradlew :FaceLandmarkerApp:assembleDebug :FaceLandmarkerApp:lintDebug :FaceLandmarkerApp:spotlessCheck
python3 FaceLandmarkerApp/tools/validate_port.py \
  --apk FaceLandmarkerApp/build/outputs/apk/debug/facelandmarker-1.0-debug.apk
```

`tools/StageRegistrationChecks.kt` also exercises the production Kotlin rebase across 40 head
poses with a known meter-scale origin/yaw offset and non-identity optical extrinsics.

`python3 FaceLandmarkerApp/tools/check_face_geometry.py` additionally verifies float32 geometry
reconstruction, sparse/full weighted-fit parity, facial depth, optical-center size scaling, and
same-capture reprojection over 40 moving-face fixtures. This check requires NumPy and Node.js.
Sampled `face_frame` logs report the maximum final-mesh reprojection error in source-camera pixels.

The standalone host check verifies asset hashes, Mixed Stage metadata for Full Space passthrough, 33 weighted fit points,
all JavaScript bindings, 24 deformed/rotated/scaled geometry fixtures against the preserved Unity
result packer, capture-pose publication, face-loss clearing, non-finite rejection, and exclusion of
platform signature stubs from APK DEX class definitions. Python 3 and Node.js are sufficient.

Build, model inspection, host math checks, and runtime evidence are recorded in
[VALIDATION.md](VALIDATION.md). Real-face mesh alignment, turning behavior, manual calibration,
and end-to-end performance require live face input and headset observation. Host reprojection
parity alone does not establish camera calibration or physical depth accuracy.

For camera/world-offset measurements, use the separately installed [Face Registration Lab](../FaceRegistrationLabApp/README.md), which shares this sample's implementation and adds coherent image/pose export and checkerboard analysis.
