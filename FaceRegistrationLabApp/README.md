# Face Calibration and Registration Lab (Kotlin)

**Balanced lag response installed (2026-11-07 UTC):** Wearer confirms that v2 smoothing works really well and authorizes the tested balanced profile. [Implementation and deployment](../artifacts/facelandmarker/registration-lab/balanced-lag-2026-11-07/IMPLEMENTATION.md). Derivative cutoff 1.5 Hz, translation motion coefficient 12, angular coefficient 2.5; static damping and local-shape/outlier/capture contracts preserved. No prediction. Production tests reproduce 43.26 ms equivalent filter lag versus 69.17 ms before, 51.07% synthetic RMS jitter reduction, and zero stop overshoot. Both builds/lint/format and calibration regressions pass. APK `e430972fc9759f05ef39a782d91c5bc3d4776ec6a80a742cf374189a7ea26764` installed/hash-verified on PB311XHGKC220141G; 78 finite startup frames with no rejection and exact stereo K/D. Mesh smoothing On / POS STEREO verified. No face visible during startup. All 1127 app files, 53 recordings and private calibration state preserved; lease released and app running. This supersedes older lag-setting deployment states below.

**Pose/mesh stability v2 installed (2026-11-07 UTC):** User reports weak v1 improvement and asks to continue. [Implementation and tests](../artifacts/facelandmarker/registration-lab/pose-mesh-stabilization-2026-11-07/IMPLEMENTATION.md). Normal viewing now uses the existing landmark ROI tracking instead of detector-per-frame; capture/preview contracts still force detection. `FacePoseMeshStabilizer.kt` filters Stage translation/quaternion/scale separately from face-local shape, and uses bounded confirmation for isolated same-track jumps. It controls both displayed pose and mesh through the existing On/Off button. Camera K/D and raw diagnostic packets/exports remain unchanged. Synthetic 18 Hz RMS is 56% lower than raw and 35% lower than v1 under the same noise; translation test lag is about 69 ms. Both builds/lint/format and host filter/calibration regression pass. **The previously built APK `66adab1decfc6cc3036e20acf4f96666fe964af11013a90f7dc266afde6e347b` is installed/hash-verified on PB311XHGKC220141G.** Startup has 52 finite packets with zero rejection and unchanged K/D; the UI shows Mesh smoothing On. No face was available for live filter/tracking validation. All 1,126 existing app files, 53 recordings and private calibration are preserved; lease released. Subsequent lag-comparison settings are not applied. No new recording requested.

**Mesh stabilization (2026-11-07 UTC):** The wearer reports good colleague face overlap with the stereo calibration and asks to reduce residual jiggle. [Recording analysis, implementation and validation](../artifacts/facelandmarker/registration-lab/mesh-stabilization-2026-11-07/IMPLEMENTATION.md). The lab now defaults to **Mesh smoothing: On**, with an Off comparison button. Adaptive filtering runs on displayed Stage vertices after existing capture-head compensation; K/D, raw packets, face pose and all calibration exports stay unchanged. Shared mesh weight, motion-dependent response, 20 mm maximum correction, and tracking/configuration/time-gap resets bound lag and prevent carrying a stale face. Capture/preview paths bypass filtering. Production filter and existing calibration regressions, both app builds, lint and formatting pass. Synthetic 18 Hz jitter RMS falls 38%, with 23 ms equivalent lag for 0.2 m/s translation; this is not yet a measured wearer improvement. Installed/hash-verified on PB311XHGKC220141G as APK `d5ab8ea49d64257bedfc2987483c3e887f4118e26b0ab43495391c6778e5647d`; 76 finite startup packets, zero rejection, unchanged stereo K/D, and the On control visible. No face was available for runtime filtering validation. All 1,125 existing app files, 53 recordings and private calibration are preserved; lease released. No new calibration recording is required.

**Stereo calibration implemented and installed (2026-11-07 UTC):** [Implementation and deployment evidence](../artifacts/facelandmarker/registration-lab/stereo-calibration-app-2026-11-07/IMPLEMENTATION.md). Lab startup now selects mode 5 with the exact final measured source K and board-derived rigid D, scale 1. Working K is A×K_source; D replaces DOWN40 and transforms both vertices and pose. The headset shows **POS STEREO** and **Stereo calibration active**. **Use previous camera** restores the previous Custom camera with Current registration; the paired Stereo calibration can be restored with the same button. Saved custom/optical values and all original recordings are preserved. Kotlin/JS and fused-model regressions, both app builds, lint and formatting pass. The final APK `3dfc6be61b62a16b4f43ce90b9630c792e08e28eb006fa62943d83ae35e36b00` is verified installed. All 59 startup packets are finite with zero rejection, and all 59 scene records have exact mode-5 K/D within FP32 precision; no face was visible. The device lease is released; physical face overlap is not established by that check. The documented LiteRT GPU relaunch fault required a restart of the existing SpatialML service, with its APK unchanged. No new calibration collection is required. This entry supersedes older undeployed/startup/capture directions below.

**Final existing-data conclusion (2026-11-06):** [Full analysis and stereo predictions](../artifacts/facelandmarker/registration-lab/final-calibration-existing-2026-11-06/FINDINGS.md), [exact recommendation JSON](calibration/stereo-face-existing-data-2026-11-06.json). User explicitly requests a conclusion with no more collection. All 22 source board views, nine unambiguous stereo board exposures and 15 paired raw face snapshots are analyzed. Recommend measured source K plus board-derived D: translation [−4.311, −44.095, +42.197] mm, rotation vector [+0.328370, +1.256514, +0.068583] degrees, scale 1. Final board RMS close/middle/far 3.91/0.94/1.46 px; omitted-distance mean 2.21 px. Independent face mean 8.69 px versus old-current 55.73 px; ten turn/distance holds 9.51, four roll holds 6.65, earlier check 3.84. Different face subjects are visible across recordings; face-scale fits do not transfer consistently. Old DOWN40 scores slightly better on these face snapshots but remains rejected as general calibration by board evidence and wearer feedback. Multi-axis source/head fit now uses the existing ±30° rotations, supports vertical/yaw correction but fails the physical calibration residual gate. The frozen final JSON records the offline recommendation before deployment; the implementation entry above records its subsequent app integration. It is not accepted factory calibration. Reconstruct with K_work=A×K_source before D; do not stack DOWN40. **Analysis complete; no additional capture requested.** Application/service code and device settings were unchanged during that offline analysis. This supersedes all older next-capture requests below.

Latest two-distance result (2026-11-07 device date / November 6 UTC): [findings and offline candidate](../artifacts/facelandmarker/registration-lab/board-distance-check-2026-11-07-eeb5d2/FINDINGS.md). Six new exports, all48 corners in source/both eyes, exact same-PTS sequence/CRC/reference and native checks pass. Source depths1.169–1.210m /1.759–1.779m, tilt30.6–32.0°, all frozen K variants unique. Same-ten-point X/Y bias close18.35/41.43mm, middle32.42/34.69mm, far44.67/33.45mm; millimetres inherit recording uncertainty. A fixed rigid D fitted close+middle reduces held-out far RMS37.63→1.56px; full48 far1.57/1.69px, six additional pairs0.56–2.60px; K-family far1.499–1.731px. Translation-only far17.84px; DOWN40 leaves ~6px downward error at both new distances. Candidate D translation[-4.27,-44.49,+42.08]mm, rotation vector[0.367,1.261,0.064]degrees, scale1; frozen/offline/unaccepted, measured-source-K only. Close fit3.92px, stereo span bias/noisy point depth, physical origin and orientation transfer unresolved. No app/service/build/install/restart/calibration change. 25 session files and432,968,607-byte stereo video hash verified, APK unchanged, lease released. **Historical proposal, superseded by the final existing-data analysis above; no additional capture requested.** [Capture steps](BOARD_CAPTURE_STEPS.md). Supersedes earlier pending distance-capture instructions below.

Latest device metadata inspection (2026-11-06 device date): [root calibration findings](../artifacts/facelandmarker/registration-lab/device-calibration-root-2026-11-06/FINDINGS.md). User-enabled root confirms `config_head.txt` is absent; actual head data is `calib/imu0/sensor.yaml`, with `T_IH` labelled `IMUFromHead`. All eight configuration files and two installed capture libraries are hash verified. Camera sensor metadata describes a different size/frame and lens model from the inference source; head-basis/order and active overrides remain unverified. No source K, app/service or device calibration change. The existing two-distance capture remains next; [oblique angle explained](BOARD_CAPTURE_STEPS.md#two-recorded-board-checks-middle-then-far--already-captured).

Current result (2026-11-06 device date): **The recorded oblique board check gives unique source poses and a repeatable upward registration error.** [Findings and corrected measurement overlays](../artifacts/facelandmarker/registration-lab/board-oblique-check-2026-11-06-afea05/FINDINGS.md): three no-face exports, source RMS 0.414–0.443 saved px, exact stereo/reference matches, and ten independently visible corner measurements per eye. The lower HUD hides middle rows, so the full-48 observer remains rejected; the corrected partial protocol gives mean selected head-Y bias +41.43 mm, with +38.43–43.27 mm source-camera sensitivity range. Stereo estimates the measured 100 mm spans at about 105.55 mm, limiting absolute metric claims. [Source camera](../artifacts/facelandmarker/registration-lab/board-supplement-2026-11-06-f5e56b/analysis/diagnostic-camera-profile.json) stays frozen for offline diagnostics. Next: **two recorded oblique Board checks at greater distances**, keeping the pattern clear of the HUD; [instructions](BOARD_CAPTURE_STEPS.md). No repeat of the close check or source calibration set, and no applied correction. The eight-hold trial remains deferred.

**Current direction (2026-11-05):** [MediaPipe first-principles transform audit](MEDIAPIPE_TRANSFORM_AUDIT_2026-11-05.md). The wearer reports that 40 mm down helps near but overcorrects farther away; it is not accepted calibration. Actual MediaPipe matrix comparisons and independent replay of 42 saved exports verify the main reconstruction/Stage algebra. A rotated-crop Z normalization difference is quantified but is too small vertically to explain the offset. Next work should establish source-camera and camera-to-Stage contracts independently, with a matching-camera image preview and a measured rigid target, before further face-offset fitting. Application and device behavior are unchanged by this audit.

**Reversible comparison implemented:** [Current versus head down 40 mm](LAB_POSITION_COMPARISON.md) adds a position button beside Roll trial and records the rendered selection in the badge/exports. Build, native-packet and stereo checks pass. [APK and validation](../artifacts/facelandmarker/registration-lab/head-down-comparison-2026-11-05/IMPLEMENTATION.md); **installed and startup/UI verified on PB311XHGKC220141G**; the new button and POS CURRENT badge are visible. The wearer feedback and audit above supersede the earlier request for another comparison recording. The correction is an app-side experiment, not saved calibration. The normal sample retains Current.

**Latest correction result:** [Roll + checkerboard analysis](../artifacts/facelandmarker/registration-lab/roll-trial-2026-11-05-b8c6a3/FINDINGS.md) supports testing a **40 mm downward translation in capture-head coordinates**, scale 1.0. The earlier coefficient reduces new-recording error from 41.04 to 4.42 pixels in both-eye mean scoring; fixed-world alternatives and the earlier scale model transfer less well. Board source K is independently supported but worsens face overlap when replayed in the actual pipeline. The report includes both-eye predictions and the shared pose/vertex transform boundary. The subsequent lab comparison above implements the reversible experiment; the new APK is installed and startup/UI verified, with physical comparison acceptance pending.

**Roll-only update installed (2026-11-05 UTC):** **Roll trial · 4 holds** is implemented and built with the latest compact/fused pipeline. It runs upright → left ear toward left shoulder → right ear toward right shoulder → upright, with measured roll targets 0/+15/−15/0°, live turn/nod feedback, angle/face-clearance gates, and 12 clean/marked/clean exports. References move to side columns for this sequence. [Capture instructions](AUTOMATIC_CAPTURE_STEPS.md#roll-only-test--next-capture) and [build/device evidence](../artifacts/facelandmarker/registration-lab/roll-only-update-2026-11-05/IMPLEMENTATION.md) describe readiness. Recorded head transforms remain the source of truth; no fitted offset or scale is applied.

**Latest analysis:** [Full Geometry trial 7aeeab26](../artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-712cf5/FINDINGS.md) validates both-eye references across ten holds and yields 134 still observations. A roughly 40 mm downward registration offset reduces mean held-out error from 62.14 to 9.18 recorded pixels; adding camera-ray scale reduces it to 5.46 pixels in this trial. On the earlier recording, the downward-only correction transfers better (2.88 px versus 4.77 px with translation+scale). These are offline predictions; no correction has been applied or saved.

**Latest roll recording retrieved:** [Run 672dcdaf](../artifacts/facelandmarker/registration-lab/roll-trial-2026-11-05-b8c6a3/RETRIEVAL.md) completed all four holds / twelve native-valid exports. The 117.268 s original Spatial video and 49 session files are hash verified. Actual rolls reach +16.41/−15.43° at the two rolled holds; sampled both-eye references pass in every hold. Next is anatomical correction-transfer analysis using this data and the earlier multi-distance evidence; no additional trial is requested now.

The [original 1.79 GB stereo video and 121 session files](../artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-712cf5/RETRIEVAL.md) are retained and hash verified; native checks accept 30/30. The prior [repaired Geometry check](../artifacts/facelandmarker/registration-lab/geometry-check-2026-11-05-cc0ddf/FINDINGS.md) supplies the separate-recording transfer observations.

**Latest optimized pipeline:** [Compact adjacent-VST and fused controls](COMPACT_FUSED_CONTROL_PIPELINE_2026-11-03.md)
records the implementation, build flags and headset measurements. It uses the existing installed OpenMR
service; these app diagnostics require no service update. Build this diagnostic app with the same four flags
shown in the [face sample guide](../FaceLandmarkerApp/README.md#run), replacing
`:FaceLandmarkerApp:assembleDebug` with `:FaceRegistrationLabApp:assembleDebug`. The flags remain
opt-in, and GPU launches require fresh OpenMR processes on the tested ROM. Optical alignment
and calibration-export acceptance remain separate checks.

**Previous headset build (November 4, 2026):** The texture-repaired binocular geometry lab retains the
[square-view and detector-coordinate corrections](MESH_FLICKER_RECORDING_FINDINGS_2026-11-03.md).
APK SHA-256 `f6f57e262556a55c4e8b7ef57b3d9714ccbedc89c58c87d1086672ca00edc870` matches at the latest
retrieval on PB311XHGKC220141G. The [installation record](VALIDATION.md#texture-repair-installation--2026-11-04)
confirms preservation of calibration, service APKs, 778 prior app files and 44 recordings at that earlier install. The
subsequent check above establishes recorded binocular diagnostic readiness.

**Latest recorded baseline:** [TIMED_STEREO_CAPTURE_FINDINGS.md](TIMED_STEREO_CAPTURE_FINDINGS.md) links the new 100-second stereo video, paired face crops and badge/journal alignment. Both eyes show the upward residual; slow updates make motion unsuitable for a static calibration fit.

**Desktop controls:** open [http://127.0.0.1:47835](http://127.0.0.1:47835) on the development machine. See [DESKTOP_CALIBRATION.md](DESKTOP_CALIBRATION.md) for mouse/keyboard tuning over adb, live readback and saving values.

**Automatic calibration plan:** [AUTOCALIBRATION_PLAN.md](AUTOCALIBRATION_PLAN.md) records the earlier candidate-sweep workflow. The [binocular geometry analyzer](tools/binocular_geometry.py) now compares corrections offline with held-out poses; on-headset fitting/application remains unimplemented. Start recording through the headset's built-in Spatial recorder.

**Stereo recording verified:** [STEREO_RECORDING_FINDINGS.md](STEREO_RECORDING_FINDINGS.md) links the latest Spatial recording, decoded left/right views and an ordinary side-by-side preview. Both views contain passthrough and the face mesh.

**Headset UI:** timing badge, automatic pose/status instructions, Roll trial · 4 holds, One check / Full trial, Geometry check / Geometry trial, and capture cancellation. Start/stop Spatial recording using the headset system recorder; use Roll trial · 4 holds for the next capture. Capture and local storage run without a PC connection. The current ROM defers remote COMMAND broadcasts, so use headset controls for capture. [TIMELINE_RECORDING.md](TIMELINE_RECORDING.md) explains clock/frame/revision labels and the offline journal. Physical alignment and on-device fitting remain unresolved.

For the current agent handoff on camera FOV, landmark reconstruction and rendering, read [FOV_2D_TO_3D_FINDINGS.md](FOV_2D_TO_3D_FINDINGS.md).

The latest wearer/video result favors C, with a residual small/high mesh similarly in both eyes. D's lower checkerboard error did not produce better physical face overlap. [MODE_C_REFINEMENT_FINDINGS.md](MODE_C_REFINEMENT_FINDINGS.md) records the evidence and independent focal/vertical-ray refinement direction; the new Custom controls let you test corrections, but no values have been accepted through physical validation.

The returned A/D trial is analyzed in [TRIAL_RESULTS_2026-10-28.md](TRIAL_RESULTS_2026-10-28.md). Three independent boards strongly support the measured intrinsics; two positive-face exports pass native geometry and Stage invariants. Physical overlap in each eye remains unverified. The latest lab repair reads actual camera freshness independently of frame duration and retains queued saves until a usable frame arrives. Pending saves suppress preview refreshes. New timing fields record camera age at submission/readback and frame readback latency.

Measure the Face Landmarker offset in three stages: model/crop alignment, camera intrinsics, then camera-to-Stage registration. This is a separate installed app, `com.pico.spatial.ml.sample.facelandmarker.registrationlab`, sharing the face sample's source and models. The normal face sample still launches its existing shaded mesh.

The lab keeps Full Space Mixed passthrough, the zero-sized SpatialML rendering session, and readback-driven Stage rendering. The mesh starts as green wireframe; size/depth is fixed at 1.0. On the recorded Swan ROM, startup applies the paired Stereo camera and rigid correction described above.

For the historical short A/D comparison, see [TRIAL_CAPTURE_STEPS.md](TRIAL_CAPTURE_STEPS.md). The [original full procedure](CAPTURE_STEPS.md) remains available. Their manual headset button walkthroughs apply to earlier builds. Automatic sequences start from the headset and run disconnected with sampled exports and a timing journal.

## Install and controls

The headset has the capture buttons described above. The table below also lists remote commands; this ROM currently defers COMMAND broadcasts, so use the headset buttons to start capture.

From the project root, after building:

```sh
bash FaceRegistrationLabApp/tools/registration_lab_device.sh install
```

The helper targets `PB311XHGKC220141G` by default; set `ANDROID_SERIAL` to select another device. It uses devmux, stops the normal face sample and any earlier lab instance to release their shared camera session, then releases its lease after installation/launch. When launching from the headset menu, close the normal face sample first. Open **SpatialML Face Calibration**, allow Camera if asked, and wait for face tracking. Keep the timing badge visible while recording. The diagnostic actions below are controlled from the computer.

| Remote action | Behavior |
|---|---|
| Roll-only sequence (`auto_roll`) | Four measured holds at C, twelve exports, side-column references |
| Geometry trial (`auto_geometry`) / check (`geometry_check`) | Original ten-hold / one-hold reference sequence |
| Capture one check sample (`auto_check`) | C baseline, three clean/marked/clean exports |
| Start full trial sequence (`auto_start`) | Seven candidates at four poses, up to 84 exports; use after the check is verified |
| Cancel sequence (`auto_cancel`) | Restore starting working values and retain existing exports |
| Next mode | Stereo → A → B → C → D → Custom → Stereo; switch only between completed frames |
| Next step | Cycle four face poses and checkerboard calibration |
| Capture sample | Wait one second, then wait for a usable matching frame and save its metadata |
| Save values | Store current Custom intrinsics without requiring camera/face readiness |
| Load saved / Reset C | Restore the saved profile or C starting values |
| Wireframe / Solid / Hidden | Change mesh visibility while comparing with passthrough |

The old headset camera/model preview panel is removed. Sample exports still include source/model images. Saves wait for the requested graph/capture sequence and record producer/fit/mesh identities; the exported intermediate comparisons test native data consistency. New camera acquisition waits until capture readbacks, export, and preview processing complete. This is a diagnostic app; its forced detection and exports affect performance.

Stereo is the default on the recorded Swan ROM; **Use previous camera** switches to Custom and removes D as one paired operation.

| Mode | Source-to-virtual-image transform A | Geometry K | Purpose |
|---|---|---|---|
| Stereo: Final existing-data profile | Preserved C affine | A × frozen measured source K, paired with rigid D | Default stereo registration |
| A: Service | Identity | Actual service K from that frame | Baseline |
| B: Aspect only | Unity lab's proposed pixel-aspect affine | A × actual service K | Test model-image proportions while preserving camera rays |
| C: Renderer trial | Same affine as B | Unity lab's proposed renderer K | Test the focal-length hypothesis independently of the image transform |
| D: Measured trial | Preserved B affine | A × measured source K | Explicit exploratory checkerboard candidate |
| Custom: adjustable | Preserved C/B affine | User-entered virtual K, directly | Live independent fx/fy/cx/cy tuning with persistent profiles |

B/C use the same trial formulas as the Unity lab and are enabled only for its inspected Swan `20261014024400` ROM fingerprint and 3248×2464 capture. A and checkerboard capture work without the trial profile. Unlike Unity's guarded fixed service-K baseline, Kotlin A/B use the actual per-frame service K. Capture aspect ratio alone does not prove non-square pixels. Neither B nor C is accepted calibration.

## Historical live-face comparison: 12 samples

This protocol documents the earlier manual trial. It is not a request to repeat it with the current automatic-capture app; an agent can use the existing remote commands for diagnostic captures.

Use one person; remove other face images from the detector's view. Start a headset system recording that shows the real face, mesh and lab panel. For each row, keep the headset position fixed and save A, B and C:

| Step | Pose |
|---|---|
| Face front - 1 m | Frontal face, approximately 1 m away |
| Face looks left - 1 m | Face rotated roughly 30° toward the wearer's left |
| Face looks right - 1 m | Face rotated roughly 30° toward the wearer's right |
| Face front - 2 m | Frontal face, approximately 2 m away |

After changing mode, wait for Ready. One usable frame with matching settings is sufficient; a capture may also be queued while waiting. Keep head and subject still for two seconds before Save, and keep still until **Saved NNN**. No-face samples are rejected for face steps. Captures with excessive movement or incomplete pose history are labelled and excluded from checkerboard calibration.

For a visibly offset face, cycle Wireframe → Solid → Hidden → Wireframe while everyone stays still. Compare chin, nose, eye line and cheeks. Check each eye separately while stationary and record which mode/eye looks best. Kotlin's public capture path does not expose per-eye renderer view/projection matrices, so these eye comparisons are visual evidence rather than exported eye calibration.

## Historical checkerboard procedure: independent camera measurement

The earlier preview and Ready/Saved UI described here is no longer shown in the headset. Remote diagnostic commands/status provide capture control; the physical target requirements remain useful for future measurements.

Print [checkerboard-A4-20mm.pdf](calibration/checkerboard-A4-20mm.pdf) at **100% / Actual Size**, with Fit to Page off. Measure the 100 mm ruler. Squares must measure 20 mm, and the board must measure 180×140 mm. Mount it flat on a rigid stationary surface near head height.

Choose **Mode A**, **Checkerboard calibration**, and the full left camera preview. Board captures do not require a face. Keep the board and tracking origin unchanged for the session; move only the headset between views. Stop for two seconds before each save, and keep all corners visible:

1. Four frontal views at different distances, approximately 0.35–0.65 m.
2. Four views with the board toward left, right, upper and lower image regions.
3. Four tilted views with headset yaw about 15° and 25° from either side.
4. Four tilted views with headset pitch about 15° and 25° from above and below.

At least 12 stable usable views are required; 16 varied views are recommended. If the board moves or tracking recenters, restart the lab and collect a new complete board session.

## Pull and analyze

```sh
bash FaceRegistrationLabApp/tools/registration_lab_device.sh pull
bash FaceRegistrationLabApp/tools/registration_lab_device.sh logs
uv run --no-project --with numpy --with opencv-python-headless \
  python FaceRegistrationLabApp/tools/registration_lab.py analyze \
  artifacts/facelandmarker/registration-lab/captures/RegistrationLab/<session> \
  --output artifacts/facelandmarker/registration-lab/analysis --calibrate
```

Use a single session for checkerboard analysis. Omit `--calibrate` for face-only comparisons. Open the generated `report.md`, `report.json` and overlays. Green points are raw model landmarks restored to the source image; magenta points are final service vertices projected into that camera.

| Evidence | Interpretation |
|---|---|
| Raw crop landmarks miss the face | Inspect model input, sampling and model behavior |
| Crop landmarks fit, but source mapping misses | Inspect image/crop affine composition |
| Source landmarks fit, but projected mesh differs | Inspect pose/vertex pairing, projection, handedness and units |
| B changes shape while preserving source fit | Image proportions affect inferred geometry |
| C changes alignment relative to B | Compare candidate K with independently measured checkerboard K |
| Low, stable board residual and useful view diversity | Review fitted K, uncertainty and held-out errors |
| Good source reprojection but VST offset remains | Investigate physical face depth, camera/head/Stage registration, eye/compositor calibration and timing |

The checkerboard analysis reports a candidate pinhole K, uncertainty, held-out-view residuals, service-K comparison, coverage, and stationary-board position/rotation repeatability in Stage. It never installs fitted values. High residuals or weak view diversity require better samples or reconsidering the rectified-pinhole assumption. Stationary-board drift combines intrinsics, extrinsics, tracking and timing; it cannot uniquely identify an extrinsic correction.

## Export contract and coordinate chain

Each finalized `NNN-modeN-stepN` directory contains `source.ppm` (1624×1232 RGB, uniform half-scale of native pixels), `detector.ppm`, `landmarker.ppm` (actual 256×256 RGB model inputs before `/255`), and `sample.json`. `.pending` directories are incomplete and excluded.

Custom captures also record `calibrationRevision` and a `customCalibration` profile. The app pins the requested mode, values and revision until capture finishes; the analyzer checks profile metadata, scalar/matrix agreement and captured effective K.

Schema 3 preserves the Kotlin 2994-float service packet in `result` and the Stage packet in `stageResult`. Vertices are already in their named space, in right-handed metres, with row-major matrices acting on column vectors. They must not be multiplied by the face pose again or reflected in Z as Unity's local-vertex packet is.

```text
T_service_to_Stage = H_Stage(capture) × E_camera_to_head × inverse(C_camera_to_service)
V_Stage = T_service_to_Stage × V_service
```

The export includes raw model XYZ, virtual-image crop affine, image affine, service/effective intrinsics, camera capture metadata, camera-to-service pose, optical camera-to-head extrinsics, capture-time interpolated head-to-Stage pose, Stage transform, readback head poses and pose history. The analyzer checks the Stage chain and transformed vertices as well as source reprojection. A nested producer/fit/mesh snapshot adds the capture ROI, first/second targets and scales, sparse/full metric vertices, fitted camera pose and raw/filtered world poses. One global read preserves those snapshots with command/camera identity. The analyzer compares boundaries and replays the shipped JS with host SVD to identify native discrepancies. Metrics are camera-space centimetres; packed world/Stage vertices are metres. The mesh snapshot’s first/second targets are three-zero placeholders; the actual 33-point targets are in the fit snapshot. Matching identity alone does not prove that native intermediate values are correct.

Spatial SDK 6.1.9 does not publicly expose the tracking sensor timestamp. History uses `System.nanoTime` at direct HMD callback arrival, with existing gap/age rejection. The export states that limitation. Schema 3 accepts capture motion over ±50 ms around exposure, requiring bracketing callback samples and no gaps over 100 ms, translation below 10 mm and rotation below 1°. It retains the separate full-export motion diagnostic. Manual saves allow movement after **Image captured**; automatic sequences require holding still through all three phases. Exposure-accepted/repeat counts remain in status. History retains 2048 callback samples so exposure evidence survives diagnostic readback. This is not proof of hardware synchronization or display latency.

The shell helper also supports `step`, `mode`, `mesh`, `save`, `tools`, `set fx|fy|cx|cy value`, `save_values`, `load_values`, `reset_c` and `profiles` for repeatable collection. Its dynamic command receiver is confined to the lab and requires Android's DUMP permission, held by adb shell. It uses the same settling and validity rules as the UI.

## Validation

```sh
uv run --no-project --with numpy --with opencv-python-headless \
  python FaceRegistrationLabApp/tools/validate_registration_lab.py \
  --output artifacts/facelandmarker/registration-lab/host-validation
uv run --no-project --with numpy --with opencv-python-headless \
  python FaceRegistrationLabApp/tools/validate_rendered_boards.py
python3 FaceLandmarkerApp/tools/validate_port.py
python3 FaceLandmarkerApp/tools/check_face_geometry.py
```

The analyzer was adapted from the Unity workspace's `Tools/FaceLandmarker/registration_lab.py` and `validate_registration_lab.py`; the checkerboard and trial profile retain that lab's procedure. Host fixtures establish analyzer correctness, not headset calibration. See [VALIDATION.md](VALIDATION.md) for current build/device evidence and visual limits.

The returned physical capture set is analyzed in [CALIBRATION_RESULTS_2026-10-28.md](CALIBRATION_RESULTS_2026-10-28.md), including candidate intrinsics, video evidence, motion limits, and native output consistency findings.

## D: measured camera trial

D preserves B's exact source-to-virtual affine and uses `K_virtual = A × K_measured_source` from [the exploratory profile](calibration/measured-profile-2026-10-28.json). Source fx/fy/cx/cy are 2642.705/2036.955/1672.377/1230.338 native pixels; virtual fx is 2027.880 and virtual cx is 1661.006. B/C/D are available only for Swan ROM `20261014024400`. A remains the normal service baseline, including in the non-lab sample.

The four follow-up Mode A board views are independent checks of this fixed candidate. Schema 3 reports `board_candidate_check` with detected-corner status and service/measured saved-pixel RMS. This does not refit K or certify camera/Stage calibration. Old schema 2 files remain supported with their original full-export motion gate.

Run the real Kotlin decoder/profile/motion fixture with:

```sh
python3 FaceRegistrationLabApp/tools/validate_lab_runtime.py \
  --output artifacts/facelandmarker/registration-lab/measured-trial/runtime
```

## Camera startup and restart limit

The lab waits for active Full Space HMD callbacks before initializing the camera. Optical camera-to-head metadata is stored in app-private `left-camera-to-head-v1.json`, keyed by the ROM fingerprint and validated for finite rigid geometry. Backup is disabled. A cold query finishes and settles before SpatialML connects; subsequent launches reuse the device-local optical matrix. This cache contains factory extrinsics, not the measured Mode D intrinsics.

An immediate `am force-stop`/relaunch can still leave this ROM's service camera unavailable. Cold startup and export can succeed while that forced-restart case fails. Keep the verified app session running for the short capture pass; the UI counts may include a diagnostic save, which the capture guide excludes from the ten new user samples. No service or firmware changes were made.
