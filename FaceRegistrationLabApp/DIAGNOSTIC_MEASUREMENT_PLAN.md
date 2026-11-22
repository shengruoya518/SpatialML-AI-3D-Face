# Camera and Stage registration measurements

**Final existing-data conclusion (2026-11-06):** [Full analysis and stereo predictions](../artifacts/facelandmarker/registration-lab/final-calibration-existing-2026-11-06/FINDINGS.md), [exact recommendation JSON](calibration/stereo-face-existing-data-2026-11-06.json). User explicitly requests a conclusion with no more collection. All 22 source board views, nine unambiguous stereo board exposures and 15 paired raw face snapshots are analyzed. Recommend measured source K plus board-derived D: translation [−4.311, −44.095, +42.197] mm, rotation vector [+0.328370, +1.256514, +0.068583] degrees, scale 1. Final board RMS close/middle/far 3.91/0.94/1.46 px; omitted-distance mean 2.21 px. Independent face mean 8.69 px versus old-current 55.73 px; ten turn/distance holds 9.51, four roll holds 6.65, earlier check 3.84. Different face subjects are visible across recordings; face-scale fits do not transfer consistently. Old DOWN40 scores slightly better on these face snapshots but remains rejected as general calibration by board evidence and wearer feedback. Multi-axis source/head fit now uses the existing ±30° rotations, supports vertical/yaw correction but fails the physical calibration residual gate. The final JSON is an effective stereo registration recommendation, not deployed or accepted factory calibration. Reconstruct with K_work=A×K_source before D; do not stack DOWN40. **Analysis complete; no additional capture requested.** Application/service code and device settings unchanged. This supersedes all older next-capture requests below.

Latest two-distance result (2026-11-07 device date / November 6 UTC): [findings and offline candidate](../artifacts/facelandmarker/registration-lab/board-distance-check-2026-11-07-eeb5d2/FINDINGS.md). Six new exports, all48 corners in source/both eyes, exact same-PTS sequence/CRC/reference and native checks pass. Source depths1.169–1.210m /1.759–1.779m, tilt30.6–32.0°, all frozen K variants unique. Same-ten-point X/Y bias close18.35/41.43mm, middle32.42/34.69mm, far44.67/33.45mm; millimetres inherit recording uncertainty. A fixed rigid D fitted close+middle reduces held-out far RMS37.63→1.56px; full48 far1.57/1.69px, six additional pairs0.56–2.60px; K-family far1.499–1.731px. Translation-only far17.84px; DOWN40 leaves ~6px downward error at both new distances. Candidate D translation[-4.27,-44.49,+42.08]mm, rotation vector[0.367,1.261,0.064]degrees, scale1; frozen/offline/unaccepted, measured-source-K only. Close fit3.92px, stereo span bias/noisy point depth, physical origin and orientation transfer unresolved. No app/service/build/install/restart/calibration change. 25 session files and432,968,607-byte stereo video hash verified, APK unchanged, lease released. **Historical proposal, superseded by the final existing-data analysis above; no additional capture requested.** [Capture steps](BOARD_CAPTURE_STEPS.md). Supersedes earlier pending distance-capture instructions below.

## What is already available

| Capability | Current state |
|---|---|
| Source/crop images, raw landmarks, K, image affine, capture matrices and frame identity | Existing exported samples |
| MediaPipe reference/production reconstruction comparison | Completed on retained evidence; no wearer repeat needed |
| Raw source/model preview and 2D landmark overlay | Existing implementation, although current automatic workflow does not provide the complete diagnostic interaction below |
| 8×6-inner-corner board, 20 mm squares | [Existing printable PDF](calibration/checkerboard-A4-20mm.pdf) and generator |
| Source-board detection, camera fitting and held-out scoring | Existing `tools/registration_lab.py`; older capture instructions/UI are historical |
| Independent virtual reference panels, sequence/CRC and same-PTS stereo analysis | Verified on three no-face board pilot exposures |
| Optional board triangulation in recorded eyes | Existing `board_check` in `tools/binocular_geometry.py`; this alone does not compare source-board pose through camera-to-Stage |
| Board-only automatic capture and source-to-recorded-eye board residuals | Implemented; physical pilot readability passed; source K and registration measurements pending |

Use the headset UI for future capture. The tested ROM defers remote command broadcasts; do not build the procedure around desktop commands that have already proved unreliable. The user starts/stops the system Spatial recording manually.

## Physical setup

Use a rigid, flat checkerboard near head height, a ruler/tape measure, and good diffuse light. A real face is unnecessary for the first two experiments. Fix the board to a wall or rigid support; avoid holding it by hand during an exposure. Put a distinct orientation label outside its top-left corner so the source and both eye images can be assigned the same corner identities; checkerboard ordering can otherwise reverse by 180 degrees.

Print the existing PDF at Actual Size. Its full checker pattern is 180×140 mm with 9×7 squares and 8×6 internal intersections. Measure a five-square span horizontally and vertically; both should be 100 mm. Record the measurements, not only the printer setting. The analyzer must use measured spacing or reject/reprint a distorted sheet rather than silently assuming 20 mm. For the far test, use a larger target if the pilot cannot resolve the existing one. Any enlargement changes the recorded metric spacing and must be supported by the analyzer; current source-board code assumes 20 mm.

Mark near/mid/far positions around 0.6, 1.2 and 2.0 m, subject to board visibility. Record the tape measurement from the board plane to a clearly identified mark on the headset housing, including how it was measured. This is independent placement/coverage evidence, not an exact optical-camera depth: the housing-to-camera offset and camera viewing angle must not be silently ignored. Known board dimensions provide the metric constraint for the geometry analysis.

## Experiment 1: image and intrinsics check

First use the retained captures for the image preview. Draw the saved model landmarks on the exact saved crop, map them back to the exact source image, and show the reconstructed mesh projected through the declared camera K. The existing audit already verifies the reconstruction algebra. Visually inspect a close, middle and far source example to establish which errors, if any, exist before Stage conversion.

Then collect a fresh **16-view board set** from the current source-stream configuration. The diagnostic must accept fresh source frames without face detection and record the exact source dimensions/resizing, K, image transform and exposure identity. Mode A/identity resampling is the initial source reference; raw source images are retained so all K candidates can be evaluated later without another capture.

Keep the board fixed, move the headset between views, and remain still during each saved exposure. Cover the image centre and its left/right/top/bottom regions, several distances, and approximately 15–30-degree board viewing angles in both axes. Avoid a set containing only front-facing centred views. The prompts are targets; the actual detected coverage and saved transforms determine whether the set is adequate.

Use 12 diverse views for fitting and four separately selected views for validation. The program detects all 48 corners and fits source-camera K. Compare a zero-distortion pinhole model with a suitably constrained distortion model if the residual vectors show structure; the word "rectified" alone is not proof of zero residual distortion. If distortion is needed, later undistortion/unprojection must use it consistently.

Report per-view corner RMS, vector residuals across the image, focal/principal-point sensitivity to omitted views, board dimensions and blur/coverage failures. Existing source-camera diagnostics use approximately 1 saved pixel pooled RMS and 1.5 saved pixels per held-out view as initial warning levels. These are diagnostic gates, not a guarantee of physical calibration. Saved source pixels are half-resolution; distinguish them from native pixels.

Freeze the best supported K candidate for Experiment 2. Do not choose it by making the face overlay look better, and do not save it as accepted device calibration at this stage.

## Experiment 2: independent camera-to-Stage check

The minimum app addition is **Board check**: a short sequence that exports source frames and presents the existing independent virtual reference panels/frame code without requiring a face. No board detector needs to run on the headset for the initial measurement. The host can detect the board after retrieval.

For every exported exposure, retain:

- The exact unoverlaid source image and its frame/exposure identity; source images in app exports are distinct from passthrough pixels in system video.
- Source/working K, image and crop transforms, source dimensions and measured board spacing.
- Camera-to-head E, capture-head-to-Stage H, camera-to-service matrix, pose-history coverage and actual sample times.
- Virtual reference corners in Stage, render/upload association, full displayed sequence plus CRC, and mesh-owner conversion checks.
- A matching pair of recorded eye images with identical PTS and valid matching frame codes.

Reference panels must leave the physical board unobscured in both eyes. Hold both board and headset still from the source exposure until the matching references have been recorded. A matching code links the intended geometry; it does not by itself prove that a moving physical board was in the same pose at exposure and display. Take at least three distinct source exposures per hold so repeatability and outliers can be measured.

Start with one short **middle-distance pilot**. The wearer starts Spatial recording, selects Board check, follows the stillness prompt, and stops recording after completion. Inspect the pilot before requesting the complete set. It must contain a readable board in the source and both recorded eyes, valid reference/frame codes, and adequate head/exposure metadata.

If that pilot passes, capture these eight holds, three exposures per hold:

| Hold | Placement and orientation |
|---|---|
| 1 | Near, head level, board centred |
| 2 | Middle, head level, board centred |
| 3 | Far, head level, board centred |
| 4 | Middle, left ear toward left shoulder about 15 degrees |
| 5 | Middle, right ear toward right shoulder about 15 degrees |
| 6 | Middle, modest upward head pitch with the board still visible |
| 7 | Middle, modest downward head pitch with the board still visible |
| 8 | Repeat middle/level |

Move between holds and stop during each capture. Log measured head orientation; labels alone do not establish coverage. Do not recenter tracking during a set. Add yaw/lateral displacement only if the result leaves a specific ambiguity or the planned poses fail observability checks. Use a larger measured board or reduce the range if the far image is unreadable; an undetected far board is not a passed far-distance test.

The host computes two independent sides of the comparison:

```text
Prediction:
  source board corners + frozen source K + measured board dimensions
  -> camera-from-board pose (PnP, with planar ambiguity checks)
  -> H_capture E camera_from_board
  -> predicted board corners in Stage

Observation:
  independent virtual references + same-PTS recorded stereo pair
  -> projection matrix for each recorded eye
  -> physical board corner pixels measured in each eye
```

OpenCV PnP uses X right/Y down/Z forward; convert through `diag(1,-1,-1,1)` before composing with our X right/Y up/Z backward optical frame. Preserve multiple planar pose candidates until positive depth, orientation identity and view consistency resolve them. Reject ambiguous poses.

Project the predicted Stage board corners through each recovered eye projection and compare them with the detected physical board corners. Fit eye projection from the virtual references only; using the physical board to fit that projection would make this validation circular.

This works offline before an on-headset board-corner overlay exists. A later overlay is useful for wearer confirmation, but is not a prerequisite for the numerical comparison. The currently implemented optional `board_check` measures recorded-layer square lengths/planarity; the new analyzer must additionally implement the source-board-to-Stage prediction above.

Report per-eye RMS and signed horizontal/vertical bias, corner residual plots, results versus distance/head orientation, reconstructed square dimensions/planarity, and exposure-to-exposure spread. Reuse the current reference gates (at least nine tags covering all three depths, fit RMS ≤1.5 recorded pixels and worst held-out tag RMS ≤2 pixels) where applicable. Around 3 recorded pixels per-eye board RMS is an initial diagnostic target after accounting for corner uncertainty, not final display acceptance. Calibration must be evaluated on entire held-out distance/orientation groups, not fitted and scored on the same images.

If a correction is identifiable, fit an **effective image-camera-to-app-head rigid transform** while keeping K fixed, then test it on held-out poses. That fit does not independently establish that a particular factory extrinsic or SDK origin is faulty. Keep intrinsic, extrinsic, tracking and display-projection evidence distinct.

## Experiment 3: return to the face

Proceed when the rigid-board result is understood. Record a frontal face at the three measured placements, followed by limited subject turns and headset roll. Use the same camera/registration configuration and preserve raw inference packets. A second subject tests whether any remaining metric-scale term is tied to canonical face size.

| Result | Next boundary to investigate |
|---|---|
| Raw 2D landmarks miss the face in the source image | Image sampling, detector/crop or landmark inference |
| Source-board calibration fails held-out views | Stream geometry, K, distortion, board quality or corner detection |
| Source checks pass, but Stage board predictions miss both eyes | Camera/rectified-frame extrinsics, head origin, tracking, or passthrough/eye mapping |
| Board error changes with head orientation | Frame/origin/rotation contract; check timing if movement remains |
| Board aligns, but face depth/overlap varies by distance or subject | Monocular face depth, canonical-size/shape prior or landmark accuracy |
| Static checks pass and motion fails | Exposure, tracking and display timing |
| Recorded-eye tests pass but wearer still sees an offset | Recorded views versus physical display warp/eye calibration |

For face-depth confirmation, use synchronized stereo/depth or an independent measured physical constraint. Merely projecting a monocular reconstruction back through its own K is not that confirmation.

## Implementation and remaining physical work

1. Expose the existing exact-frame source/crop overlay as a clear diagnostic view; show its frame identity and separate it from any live mesh.
2. Add a face-independent board source-capture sequence and a board/reference pilot, including cancellation and configuration restoration. Preserve all existing captures and calibration. Log Current/scale 1 explicitly.
3. Extend the host analyzer for measured board spacing, stable corner identity, source PnP to Stage, paired-eye residuals, and held-out-group evaluation. Keep an independent reference-only projection fit.
4. Validate the new path with known synthetic cameras/board poses, deliberate unit/axis/origin/timestamp errors, and missing/ambiguous board observations. Run the relevant Kotlin/build checks and verify startup separately from physical measurement.
5. Install the diagnostic build under the normal scoped device lease, then perform only the short pilot before requesting the longer set.

Items 1–4 are now implemented with host validation. Camera fitting reports measured coverage and omitted-view sensitivity; the observer rejects unresolved planar ambiguity rather than selecting a pose by Stage overlap. Calibration corrections are not fitted automatically. Step 5 remains: install and verify startup on PB311XHGKC220141G, then run only the short pilot. The historical face Geometry/Roll buttons do not implement this workflow.
