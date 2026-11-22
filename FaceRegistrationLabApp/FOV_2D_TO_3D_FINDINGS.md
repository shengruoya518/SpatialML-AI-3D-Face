# Face registration: FOV, 2D-to-3D and rendering findings

Current adjustable-intrinsics build: [CALIBRATION_TUNING_STEPS.md](CALIBRATION_TUNING_STEPS.md). It starts from C or saved Custom values; the historical trials below remain evidence, not accepted correction constants.

Latest capture capability: [STEREO_RECORDING_FINDINGS.md](STEREO_RECORDING_FINDINGS.md) verifies Spatial screen recording with two 1920×1080 MV-HEVC eye views containing passthrough and mesh. The recording carries a 64 mm baseline and 77.899° horizontal FOV descriptor; their relationship to the actual eye/compositor projection remains to be validated. Do not substitute these values for source-camera K.

Agent handoff from the Kotlin Face Registration Lab, 2026-10-28 Los Angeles time. Capture filenames use 2026-10-29 on the headset's CST clock. Three new held-out boards strongly support a source-camera intrinsics correction. Two new positive-face exports are internally coherent through native fitting and Stage conversion. Complete physical mesh alignment remains unverified; the earlier intermittent native inconsistency has no established cause.

**Latest wearer result supersedes D as the preferred visual trial:** C is closest, with a slightly small/high mesh, similarly in both eyes; D made overlap worse. Read [MODE_C_REFINEMENT_FINDINGS.md](MODE_C_REFINEMENT_FINDINGS.md) for the inspected latest recording and same-input geometry replay. C is the leading visual candidate, while measured D remains the better independent board fit. These observations establish different validation boundaries, not one accepted physical calibration. The next refinement probes C focal length and vertical principal point independently. No refinement constants have been applied.

Start with this file for geometry conclusions, [the latest trial results](TRIAL_RESULTS_2026-10-28.md) for new measurements, [the original capture analysis](CALIBRATION_RESULTS_2026-10-28.md), and [validation](VALIDATION.md) for build/device boundaries. The latest results describe the smaller four-save A/D check after the capture repair.

## 1. Camera FOV is different from the renderer hypothesis

The native source image is 3248×2464. Saved RGB source images are uniformly half-sized, 1624×1232. The intrinsics below are in native source pixels.

| Parameter | Service metadata | Exploratory checkerboard fit |
|---|---:|---:|
| fx | 2065.589844 | 2642.704699 |
| fy | 2089.435547 | 2036.955265 |
| cx | 1623.500000 | 1672.376919 |
| cy | 1231.500000 | 1230.337555 |
| fy/fx | 1.01154 | 0.77078 |
| Horizontal source pinhole FOV | 76.350° | 63.131° |
| Vertical source pinhole FOV | 61.050° | 62.333° |

The horizontal focal-length difference is +27.94%; the vertical difference is −2.51%. The horizontal principal point differs by +48.88 pixels. The strongest evidence is the horizontal discrepancy; principal point and absolute focal length still have uncertainty.

The FOV calculation includes the fitted principal point and the full pixel footprint:

```text
horizontal = atan((cx + 0.5)/fx) + atan((W - 0.5 - cx)/fx)
vertical   = atan((cy + 0.5)/fy) + atan((H - 0.5 - cy)/fy)
```

The earlier report's centered approximation gives 63.143° horizontally for the measured fx. That agrees with the off-center calculation to about 0.013°. These are source-camera pinhole-model angles, not headset display/per-eye FOV measurements.

The Unity lab's 70.400002° renderer hypothesis, with its ±5° horizontal asymmetry, produces source-equivalent fx≈2275.977 and fy≈1746.471. Its resampled virtual K uses a common focal length ≈1746.471. This is Mode C's hypothesis, not an independently measured camera calibration. The new checkerboard evidence supports a different absolute focal length.

Evidence and acceptance boundary:

- All 48 internal corners were detected in all ten main board images.
- Zero-distortion pinhole fit RMS: 0.410 saved pixels, or 0.819 native pixels.
- Three held-out view RMS values: 0.396, 0.291 and 0.726 saved pixels. Fixed service K gives about 1.01–4.71 saved-pixel RMS on these views.
- Leave-one-out source fx stays around 2599–2728 pixels, consistently above service fx≈2066.
- Ten images are below the lab's 12-view calibration threshold; only one passes the original full-export motion gate. The candidate is experimental, not accepted physical calibration.
- On three new independent views, all 48 corners were detected. Fixed measured K gives pooled RMS 0.459648 saved pixels versus 3.797982 for service K, 8.26 times lower. This strengthens the intrinsics finding without refitting K or calibrating extrinsics. All three pass the schema 3 exposure-motion gate.

## 2. Image resampling and K must change together

Let `A_img` map native source pixels to virtual pixels, and `C_crop` map virtual pixels to the 256×256 model crop:

```text
model_xy   = C_crop × A_img × source_xy
virtual_xy = inverse(C_crop) × model_xy
source_xy  = inverse(A_img) × inverse(C_crop) × model_xy
K_virtual  = A_img × K_source
```

The preserved B affine is:

```text
A_img = [0.7673501372  0  377.70703125
         0             1    0
         0             0    1]
```

| Lab mode | Model sampling | Geometry K |
|---|---|---|
| A: Service | Identity source-to-virtual transform | Actual service K |
| B: Aspect only | A_img | A_img × service K |
| C: Renderer trial | Same affine as B | Renderer-trial virtual K |
| D: Measured trial | Exact preserved B affine | A_img × measured source K |

B preserves the service-calibrated rays because `inverse(A_img×K)×A_img = inverse(K)`. It can change the model's inferred shape through image proportions, but it does not correct questionable service K.

D's effective virtual K is:

```text
[2027.879814  0            1661.005689
 0            2036.955265  1230.337555
 0            0               1]
```

The native D smoke export measured fx=2027.879761, fy=2036.955322, cx=1661.005737, cy=1230.337524. Maximum discrepancy from the float32 `A_img×K_measured` calculation was 0.0000311 pixels.

Do not place the native measured K directly into geometry after applying A_img: both focal length and principal point must be transformed. The virtual viewport still has its original dimensions and now includes resampling margins; its nominal full-viewport FOV is not an additional physical-camera measurement.

See [the measured profile](calibration/measured-profile-2026-10-28.json), `LabCameraProfile.kt`, `lab_camera.js` and `lab_affine.js`. D is confined to the lab; the normal face sample remains on service K. B/C/D are guarded by the inspected Swan ROM fingerprint.

## 3. Monocular landmarks produce metric geometry through a canonical fit

The model returns crop-relative XYZ, not measured depth in metres. `mesh_landmarks.js` restores crop translation, scale and roll. Its normalized Z is:

```text
landmark_z = model_z / 256 × ROI_side / native_width
```

`geometry_project.js` constructs calibrated right-handed camera coordinates, with forward along negative Z:

```text
u = normalized_x × W
v = normalized_y × H
rx = (u - cx) / fx
ry = (cy - v) / fy
rz = normalized_z × W / fx
```

Horizontal and vertical projection use independent fx/fy. Using fx for both axes would change vertical rays when the source has unequal angular pixel spacing.

Three weighted similarity solves, using native SVD, estimate first scale, second scale and the final fitted pose. All 33 canonical points with positive weights are used, in ascending index order. The depth offset is the mean over all 468 non-iris landmarks; the final mesh retains 478 vertices. Adding zero-weight points supplies no fitting improvement.

The shipped unprojection is:

```text
d_cm = (rz - mean(rz over 468) + 1) / (firstScale × secondScale)
P_camera_cm = [rx × d_cm, ry × d_cm, -d_cm]
```

The canonical geometry is in centimetres. This establishes a monocular, canonical-face-based metric estimate; it does not make the model Z a direct depth measurement. Physical depth can still depend on the inferred face shape and canonical geometry assumptions.

Reprojecting with the same K yields:

```text
u = cx + fx × X / (-Z)
v = cy - fy × Y / (-Z)
```

Very low error here proves ray/geometry consistency under the selected K. A wrong K can still achieve essentially zero reprojection while generating physically wrong 3D positions or depth. It must be checked against independent known geometry, such as the printed board.

## 4. Capture-time camera geometry must be rebased into app Stage

All Kotlin matrices are row-major and act on column vectors. Camera, service Local and app Stage data in this path are right-handed. Packed vertices use metres.

```text
H = head-to-Stage at camera capture time
E = left optical camera-to-head calibration
C = captured left camera-to-service-Local transform

T_service_to_Stage = H × E × inverse(C)
V_Stage = T_service_to_Stage × V_service
```

The measured optical E is:

```text
[ 0.9999972    0.00046855063   0.0023080353  -0.026490256
 -0.00045299705 0.99997723    -0.006734796    0.04333694
 -0.0023111382  0.006733732    0.99997467    -0.047931235
  0             0             0             1]
```

The packer first removes the fitted similarity pose from camera-space metric vertices to obtain canonical-local vertices, then applies the raw world pose of that same fit. Algebraically, when the pose is a valid scaled rotation and the snapshots match, these fitted-pose operations cancel. At lab sizeScale=1 the expected result simplifies to:

```text
V_service = C × (P_camera_cm / 100)
V_Stage   = H × E × (P_camera_cm / 100)
```

This is a diagnostic invariant, not a replacement implementation. The new A and D positive-face probes match it at 1.01e−7 and 1.42e−7 m Stage RMS. A stale pose, inconsistent intermediates or a non-similarity fitted matrix can prevent the cancellation.

The readback packet's service/Stage vertices already include their relevant transforms. Do not multiply them by the face pose again. Do not import Unity's Z reflection into Kotlin. A Unity bridge must perform its right-handed-to-Unity conversion consistently once for its own local-vertex/pose contract.

HMD history is sampled at public callback arrival using System.nanoTime; it is not a hardware sensor timestamp. It rejects interpolation gaps above 100 ms and forward extrapolation above 50 ms. The service-to-Stage calculation reproduces exported Stage vertices to sub-micrometre precision, but that is an internal transform check, not proof of physical overlap.

The exploratory stationary-board position drift was about 44 mm RMS. It combines intrinsics, extrinsics, tracking and timing, so it cannot be used as a constant camera/head/world translation correction. No constant world offset or invented timing offset was applied.

## 5. Rendering and native consistency are separate problems

The initially flat appearance was a rendering-material problem: UnlitMaterial ignored the normals already supplied. The normal sample now uses cyan PhysicallyBasedMaterial, roughness 0.7, metallic 0, double-sided rendering, per-frame normals, and headset-relative key/fill directional lights. The wearer confirmed shading. The lab's green wireframe deliberately uses an unlit line material.

Full Space Mixed passthrough with Stage style 1 is retained. Style 3 previously produced the black-surround symptom. SpatialML's rendering container stays 0×0×0; the app owns the mesh through readback. Full Stage rendering does not itself calibrate the source-camera FOV.

The mesh entity has an identity transform. Before uploading geometry, `FaceMeshScene.toMeshOwner()` converts Stage positions to the entity's actual local space using the public convertPositionFrom API; this handles a nonidentity SpatialView parent. Normals are computed from those uploaded positions. The controls alone follow the headset at (0, −0.25, −1) metres.

A previous implementation combined current vertices with a filtered world pose. It now packs with `rawWorldPose` from the current fit. In the 40-frame host fixture, raw-pose reprojection was about 0.000107 pixels versus roughly 13.7 pixels with the filtered pose. This establishes the pairing requirement; it does not explain every real native inconsistency.

In ten returned real-face samples, six were internally consistent. Four disagreed:

| Sample | Mesh-to-packed-landmark RMS, native pixels | Host replay-to-device vertex RMS |
|---|---:|---:|
| 002, A left-facing 1 m | 7.114 | 5.29 mm |
| 004, A frontal 2 m | 1.483 | 61.26 mm |
| 006, B right-facing 1 m | 8.507 | 12.22 mm |
| 007, B frontal 2 m | 2.424 | 6.98 mm |

Exact shipped JS replay with host NumPy SVD reprojects all ten below 0.00008 virtual pixels. It matches six native meshes within about 0.00034 mm and differs in the four cases above. The native discrepancy's cause is still unknown. Intermediate generation mismatch, native fit output and pose/vertex pairing are hypotheses; adaptive filtering or stale ROI has not been proven as the remaining root cause.

Schema 3 now snapshots producer, fit and mesh boundaries in one global read: 66 producer, 1995 fit and 9395 final floats. It exports raw XYZ, ROI/crop, calibrated K, first/second targets and scales, sparse/full metric vertices, fitted camera pose, and raw/filtered world poses with frame identities. Actual first/second targets are the fit snapshot's 33-point arrays; the mesh snapshot has three-zero placeholders for those fields. Matching sequence tags alone do not prove correct native intermediate values.

The analyzer compares native boundaries and replays the shipped covariance/solve, unproject and pack operations. The earlier native D smoke sample contained the room with neither a measured face nor a checkerboard and validated plumbing only. The returned trial now supplies two positive-face schema 3 captures: A left-facing near and D frontal far. Both have matching producer/fit/mesh boundaries, closely matching native/host SVD and pack replay RMS below 6.75e−8 m. Their source reprojection RMS is below 0.000159 native pixels. The earlier intermittent discrepancies have not reproduced in these two packets; their cause and universal resolution remain unproven.

The Kotlin exporter has no public per-eye renderer matrices. Source-image overlays and Stage algebra cannot establish exact eye/compositor alignment. The wearer/compositor recording remains necessary, particularly for eye-dependent offset and near/far comparisons.

## 6. Next evidence and current implementation state

The user completed the requested comparison. Five finalized exports were recovered: two face samples and three independent Mode A boards. Recordings show additional face attempts; readiness/save failures limited numerical capture. D visibly narrows the mesh in near/far video moments, but these are not matched views or per-eye alignment measurements. No wearer assessment of each eye has yet been received.

The lab used frame duration as a freshness flag. It now exports actual `frame[3]` in diagnostics[30], retains queued saves on ineligible frames and suppresses preview reads while waiting. Host regression/build checks passed; see validation for the current installation/runtime boundary. This repairs capture readiness, not the unproven terminal watchdog stall or geometry calibration.

The next pass can be reduced to four accepted stationary face saves: A/D frontal near and A/D frontal far, with per-eye observations. The three returned boards already provide the independent fixed-candidate check. If D still leaves a physical offset, investigate optical camera-to-head registration, capture-pose timing and canonical-face depth before inferring an extrinsic or world translation correction.

That A/D repeat is now superseded by the latest C/D video and wearer assessment. The current panel still frequently waits for fresh frames with Saved 0, so successful capture/readiness diagnostics must be established before requesting more numerical captures. The next geometry trial should retain original C and independently perturb its focal lengths and vertical principal point, preserving its image affine and recording the parameters.

Schema 3 separates ±50 ms exposure motion from movement during later export and shows accepted/repeat counts. The old gate covered 2.29–4.22 seconds, although movement near exposure was only about 0.2–2.8 mm. Exposure acceptance still uses callback-arrival times and does not certify subject stillness or physical alignment.

Implementation and evidence locations:

- Shared implementation: `FaceLandmarkerApp/src/main/java/com/pico/spatial/ml/sample/facelandmarker/` and its `assets/SpatialML/face-landmarker/operators/`.
- Original returned evidence: `artifacts/facelandmarker/registration-lab/user-calibration-2026-10-28/`, including recordings, board diagnostics, face host replay and exact analysis scripts.
- Trial evidence: `artifacts/facelandmarker/registration-lab/measured-trial/`, including schema 3 smoke export, host/native checks, current build manifest and startup logs.
- Returned trial and capture-repair evidence: `artifacts/facelandmarker/registration-lab/trial-results-2026-10-28/`, including hash-matched captures/recordings, independent board checks, positive-face native replay, direct Stage invariants and readiness regression.
- Workspace `/Users/bytedance/Documents/Projects/SpatialML/Kotlin/spatialml-sample`, branch `dev/facelandmarker`, committed baseline `1243bfb`. All later shading/lab/trial/startup changes remain uncommitted.
- The returned trial ran APK `9d3288e129017af1f6f2f7dc89da729565fe2d3a02c005fe87ab45a3bbafdcb5`. The capture-repair build is `498f230c79a5701db80e338d44705b473d3897f4a02517a1a4d1e9792b0fc22b`; use the latest validation section for installation and runtime evidence.

The ROM is `Pico/swan/swan:16/BQ2A.260122.002-BP2A.250705.008/20261014024400:userdebug/test-keys`, serial PB311XHGKC220141G. Check live availability through devmux. Immediate forced restart can still disturb the service camera. Optical E is cached in app-private storage keyed by ROM, which avoids repeating the metadata query but did not resolve that forced-restart case. The returned board sequence also ended with stale-save rejections and a watchdog stop whose native cause is unproven. Keep camera reliability separate from the FOV/geometry findings.

Build/lint/format, shipped-operator/Kotlin-decoder fixtures, camera/profile math, Stage transforms, signature and APK asset checks passed. These checks do not establish physically correct VST registration. Preserve the Full Space/zero-container architecture and user data; do not adopt D as accepted calibration, apply a constant offset, or commit the current changes without a new request.
