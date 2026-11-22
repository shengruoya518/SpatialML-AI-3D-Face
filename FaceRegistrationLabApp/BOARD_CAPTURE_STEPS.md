# Board diagnostic capture

**Final existing-data conclusion (2026-11-06):** [Full analysis and stereo predictions](../artifacts/facelandmarker/registration-lab/final-calibration-existing-2026-11-06/FINDINGS.md), [exact recommendation JSON](calibration/stereo-face-existing-data-2026-11-06.json). User explicitly requests a conclusion with no more collection. All 22 source board views, nine unambiguous stereo board exposures and 15 paired raw face snapshots are analyzed. Recommend measured source K plus board-derived D: translation [−4.311, −44.095, +42.197] mm, rotation vector [+0.328370, +1.256514, +0.068583] degrees, scale 1. Final board RMS close/middle/far 3.91/0.94/1.46 px; omitted-distance mean 2.21 px. Independent face mean 8.69 px versus old-current 55.73 px; ten turn/distance holds 9.51, four roll holds 6.65, earlier check 3.84. Different face subjects are visible across recordings; face-scale fits do not transfer consistently. Old DOWN40 scores slightly better on these face snapshots but remains rejected as general calibration by board evidence and wearer feedback. Multi-axis source/head fit now uses the existing ±30° rotations, supports vertical/yaw correction but fails the physical calibration residual gate. The final JSON is an effective stereo registration recommendation, not deployed or accepted factory calibration. Reconstruct with K_work=A×K_source before D; do not stack DOWN40. **Analysis complete; no additional capture requested.** Application/service code and device settings unchanged. This supersedes all older next-capture requests below.

**The two-distance checks are complete and analyzed.** [Findings and frozen offline candidate](../artifacts/facelandmarker/registration-lab/board-distance-check-2026-11-07-eeb5d2/FINDINGS.md): all six exports have complete board visibility and unique source poses. A fixed rotation-plus-translation model fitted to close/middle transfers to far at1.57/1.69 recorded pixels RMS on all48 corners. No correction is applied; source K remains frozen. No repeat distance check or source set is needed.

## Next capture: orientation transfer, three recorded Board checks

Use the existing app in **Current position, scale1**. Keep the same measured board fixed and view it from roughly1.2m at the same approximately35° sideways/oblique angle. The following holds replace the installed middle/level prompt text.

1. Check that all corners and the printed header fit above the lower status panel and below the top frame-code panel. Hide source preview and start system **Spatial recording**.
2. **Head level:** press **Board check**, remain still and let all three saves finish.
3. **Left roll about15°:** tip your left ear toward your left shoulder while keeping the board in view. Check the pattern stays clear of the HUD. Press Board check and let all three saves finish.
4. **Right roll about15°:** tip your right ear toward your right shoulder, check visibility, then complete another three-save Board check.
5. Stop recording. Keep the board fixed throughout and do not recenter tracking. No parameter changes are needed between holds.

These three holds test the frozen candidate offline; the host will not refit it to make them pass. Level is a repeat control in a new recording, and the two roll directions test transfer across head orientation. Roll changes head orientation; moving sideways relative to the board establishes obliqueness. No app install is needed. Physical scale/origin validation and consistent source-camera integration are still required before accepting a face correction.

## Two recorded Board checks, middle then far — already captured

An **oblique viewing angle** means looking at the board from off to one side, so perspective makes it look narrower. Straight-on is 0°: the viewing direction aligns with the board's perpendicular (normal). For about 35°, keep the board fixed, move sideways around its centre, and continue aiming at it. Keep your head upright; tilting an ear toward a shoulder is roll and does not create this board-view angle.

1. Keep the same flat, fixed 20 mm board and its visible physical top-left identity. Use two placements, approximately **1.2 m**, then **2.0 m**, with a visibly oblique plane angle near **35 degrees** for both. Move around the board plane to retain the oblique angle, then aim at it.
2. Before capture, use source preview to check all corners. Keep the complete physical pattern in the clear upper part of passthrough, **above the lower status panel and below the top frame-code panel**. Aim slightly below the board if needed to lift its image above the lower HUD. The smaller board image at these distances should fit in that clear gap.
3. Hide preview and manually start system **Spatial recording**. Press **Board check** at the middle-distance oblique placement, hold still through all three exports/reference display, and let it finish normally.
4. Reposition for the farther oblique hold, keep the board fixed, and press **Board check** again. Let all three exports finish, then stop recording. Use these placements in place of the installed middle/frontal prompt. Do not recenter tracking. Note tape distances from the board plane to a named headset housing mark.

The host checks full corner visibility, sequence/CRC, same-PTS eyes, pose uniqueness and independent references before interpreting signed residuals and scale across distance. Source K is not refitted to registration error. Existing close-check data remains valid for its partial-corner protocol; hidden points will not be reconstructed.

## Close oblique Board check — already captured

1. Keep the same measured 20 mm board flat and fixed. Label its physical top-left outside the checker pattern. No new span measurement is needed for this same board.
2. Use **Show source preview** to position roughly 0.6–0.8 m away, viewing from the board's left or right at about 25–35 degrees, with all corners visible. Move your viewing position around the fixed plane and aim at it. The purpose is a visibly oblique plane view.
3. Hide preview and move the control panel away from the physical pattern if needed. Manually start system **Spatial recording**, then press **Board check**. Use this oblique placement in place of the installed middle/frontal prompt.
4. Hold still through all three exports and reference display. Let the check finish normally, then stop recording.

The host uses [the frozen diagnostic camera](../artifacts/facelandmarker/registration-lab/board-supplement-2026-11-06-f5e56b/analysis/diagnostic-camera-profile.json). Matching source sequences, same-PTS recorded-eye pairs, physical corner identity, source-pose uniqueness and independent reference fitting must pass before registration residuals are interpreted. This short check is evaluated before further distance/roll/pitch capture. App settings and saved calibration need no change for it.

## Six-view supplement recipe — already captured

1. Keep the same measured board flat and fixed, preferably near head height, and mark its physical top-left outside the pattern. The confirmed five-square spans remain **100 mm horizontally and vertically**, or **20 mm spacing in both axes**; [saved board specification](calibration/measured-board-f5e56b.json).
2. Before starting, select **Show source preview** and get closer until the whole black/white pattern fills roughly one third to one half of the source-image width. Keep all 48 internal corners and the outer pattern boundary visible. Roughly 0.3–0.5 m may work with this A4 board; use image size rather than an assumed optical distance. Hide the preview before capture.
3. Select **Board views · 16**. For its first six saved views, follow the table below. These six positions replace the installed full-set prompt text for this supplement. Move your viewing position around the board plane, aim at it, and hold still at each capture. Rolling your head does not create the required perspective tilt.
4. After the sixth view is saved and the app advances to view 7, press **Cancel capture**. Saved exports remain on the headset and starting settings are restored. Any extra exports remain retained; the host selects only the first six of the named new run. No system recording or reinstall is needed. Do not recenter tracking.

| Saved view | Position | Host split fixed before capture |
|---|---|---|
| 1 | Close, from the board's left, about 25–35 degrees; pattern near image centre | Fit |
| 2 | Close, from its right, about 25–35 degrees | Fit |
| 3 | Close, from above, about 25–35 degrees | Fit |
| 4 | Close, from below, about 25–35 degrees | Fit |
| 5 | Close to middle, oblique in both axes; pattern in upper-left image region, all corners visible | Held out |
| 6 | Close to middle, opposite oblique direction; pattern in lower-right image region | Held out |

The host combines these with the existing sixteen using the [supplement analyzer](../artifacts/facelandmarker/registration-lab/board-views-2026-11-06-f5e56b/supplement_views.py), keeping the original held-out set and adding two new held-out views. Its synthetic recovery, split preservation, crop-coordinate and duplicate-exposure checks pass. Actual coverage and sensitivity are reviewed before freezing a camera candidate.

See [measurement design](DIAGNOSTIC_MEASUREMENT_PLAN.md) for the reasoning.

## First run: only Board check

1. Print [the A4 board](calibration/checkerboard-A4-20mm.pdf) at Actual Size, mount it flat and fixed, and label its physical top-left outside the pattern. Measure five squares horizontally and vertically; record both actual spans (nominally 100 mm).
2. Open the installed Face Registration Lab. **Board check**, **Board views · 16**, and **Board trial · 8 holds** appear by default. Earlier tests remain under **Show face tests**. **Show source preview** displays the captured source and model crop with the shared frame number. Model landmarks are meaningful only when a face is detected.
3. Stand about 1.2 m from the fixed board, with your head level. The source preview should show all 48 internal corners. Hide the preview and move the control panel away from the board if it obscures passthrough.
4. Manually start the system **Spatial recording**, then press **Board check**. There is a 15-second countdown and an eight-second positioning prompt. Keep the entire board visible and hold your head still. The camera switches temporarily to **Mode A / Current position / scale 1**. No face is needed.
5. The check takes three distinct source exposures, showing independently positioned reference tags and a sequence/CRC code in the recording. Keep the board fixed and remain still until completion. Cancel capture is available throughout.
6. Stop the recording after **Board capture complete**. Camera values, position selection and preview visibility return to their starting settings. Saved device calibration is never overwritten. Completion means the files were captured; the host still has to check board visibility.
7. Retrieve the new session and original stereo recording and verify their hashes. Inspect this pilot before requesting either longer sequence. Remote broadcasts are not the capture procedure: this ROM has deferred them in previous runs.

If the board or references are unreadable, change placement/lighting or use a larger measured board before repeating the short pilot. Do not fit a correction from incomplete observations.

## Later sequences

- **Board views · 16**: sixteen positioning prompts, one source exposure each, first twelve for fitting and last four held out. Move between prompts; pause to capture. The board remains fixed. No virtual reference markers are needed for this set. The host measures actual corner coverage and camera-pose diversity rather than trusting prompt labels.
- **Board trial · 8 holds**: near / middle / far level, middle left roll / right roll / upward pitch / downward pitch, middle level repeat; three exports per hold. Record Spatial video. These are coverage prompts, not on-device target-pose certification. Capture transforms and host analysis establish the actual orientations and distances.

Record tape distances relative to a named headset housing mark. These document placement; the board dimensions, not the housing distance, establish camera-relative metric scale. Do not recenter tracking during a set.

## Host analysis

Use Python with NumPy, SciPy, OpenCV contrib/ArUco and PyAV for MV-HEVC extraction. Commands below use `python`; use the prepared environment on the host. Inputs are immutable. Output directories must be separate from original captures.

The host operator runs these commands; the wearer only needs the headset controls and measurements above.

### Pilot before any camera fitting

Extract a same-PTS stereo pair from the marked portion of a saved exposure. Both eyes must decode that exported sample's full sequence and valid CRC. The extractor retains the original view IDs, PTS and image hashes. `--seconds` is a recording-time hint; a failed frame-code match means select the matching interval, not relabel the frame.

```sh
python FaceRegistrationLabApp/tools/board_registration.py extract \
  --video ORIGINAL.mp4 --seconds 30 --output analysis/pair
python FaceRegistrationLabApp/tools/board_registration.py pilot \
  --sample SESSION/001-mode0-step1/sample.json --timeline SESSION/timeline.jsonl \
  --pair analysis/pair --output analysis/pilot
```

If the full-image checkerboard search fails despite a clear board, select a region from the visible physical pattern, including its margin. Pass `--regions regions.json` to `pilot` or `observe`, for example `{"eye0":[840,320,1130,570],"eye1":[760,320,1050,570]}` for the first pilot. These are half-open `[x0,y0,x1,y1]` bounds in the original image and must be chosen for each new placement, without predicted Stage alignment. `detect` also accepts `--roi X0 Y0 X1 Y1`. Returned corners and identity anchors always use full-image pixels. Source/reference fitting and image hashes are unaffected.

`pilot.json` and three corner overlays prove board readability, reference fit, sequence matching and capture/upload head-pose checks. This does not require a calibrated K and does not claim physical registration accuracy. Check all three distinct saved exposures.

### Source camera calibration

For the same board used in the first pilot, use [measured-board-f5e56b.json](calibration/measured-board-f5e56b.json): the user measured five-square spans of 100 mm in both axes. In the commands below, `measured-board.json` denotes that file. For a different physical board, copy [measured-board.example.json](calibration/measured-board.example.json) outside the original session and enter its actual measurements. Both horizontal and vertical pitch are used explicitly, including any print anisotropy. Physical origin/row-end identity must still be confirmed before registration observations.

```sh
python FaceRegistrationLabApp/tools/board_registration.py calibrate \
  --session SESSION --board measured-board.json --model pinhole --output analysis/pinhole
python FaceRegistrationLabApp/tools/board_registration.py calibrate \
  --session SESSION --board measured-board.json --model radial-k1-k2 --output analysis/radial
```

If the session contains multiple Board views runs, add `--run RUN_ID`. Both models use the same 12/4 split; the radial model fixes tangential distortion and k3. If whole-source detection misses a visible board, `--source-regions PATH` maps selected sample directory names to full-image `[x0,y0,x1,y1]` bounds. Coordinates are restored before calibration, and the report retains crop provenance. Reports contain per-view residual vectors and overlays, source pixel dimensions, board size, actual camera poses and image-centre coverage, omitted-view sensitivity and input hashes. Initial gates are pooled fit ≤1 saved pixel and held-out RMS ≤1.5 pixels. Inspect coverage/sensitivity before freezing a candidate. `gatePassed` alone is not accepted device calibration.

For the current six-view supplement, use `supplement_views.py --session NEW_RETRIEVED_SESSION --run NEW_RUN_ID --output FRESH_ANALYSIS_DIRECTORY` from the findings folder. Optional `--regions PATH` applies only to its six new views. The normal `calibrate` command intentionally requires one complete sixteen-view run; the supplement helper records the separate predeclared 4/2 allocation without changing the original app metadata.

### Source-to-recorded-eye residuals

For each source / recorded-eye image, locate the first and last internal corners of the physical top row using the external orientation label. `detect --image IMAGE --output FOLDER` writes a numbered overlay and corner array to assist this annotation. Create identity metadata such as:

```json
{
  "group": "middle-level",
  "placement": {"housingMark": "describe measured headset mark", "tapeMetres": 1.2},
  "source": {"origin": [812, 616], "rowEnd": [947, 616]},
  "eye0": {"origin": [960, 540], "rowEnd": [1100, 540]},
  "eye1": {"origin": [940, 540], "rowEnd": [1080, 540]}
}
```

Those pixel coordinates are illustrative: annotate the actual images. The observer rejects anchors that do not match detected row endpoints. It does not pick a board orientation by minimizing the registration residual being tested.

```sh
python FaceRegistrationLabApp/tools/board_registration.py observe \
  --sample SESSION/001-mode0-step1/sample.json --timeline SESSION/timeline.jsonl \
  --pair analysis/pair --board measured-board.json \
  --camera analysis/pinhole/camera-profile.json --identity identity.json \
  --output analysis/observation-001
python FaceRegistrationLabApp/tools/board_registration.py summarize \
  --observations analysis/observation-*/observation.json \
  --held-out far-level middle-left-roll middle-up-pitch --output analysis/groups.json
```

Choose whole held-out groups before any future correction fitting. The current analyzer evaluates the frozen existing transform and reports per-group error/repeatability; it does not fit or apply a correction. At least three unique source exposures per hold are required for repeatability. Use consistent group labels that match the `--held-out` names.

Prediction uses source PnP → OpenCV-to-optical basis → camera-to-head → capture-head-to-Stage. Observation uses the virtual tags alone to recover each recorded-eye projection. The physical board is never used in that projection fit. Residuals are **predicted minus observed** pixels: positive X is rightward; positive Y is downward. Outputs include both-eye residual images, signed bias/RMS, triangulated square dimensions and planarity.

Ambiguous planar PnP is rejected when two nearly equal source fits differ materially in 3D. Use a more oblique view or independently establish multi-view continuity; do not resolve the ambiguity by choosing whichever pose makes the Stage residual smaller. Moving boards, delayed passthrough and physical display warp remain outside what sequence matching alone proves.

## Build and verification

The validated configuration retains compact VST, fused controls and GPU preprocessing:

```sh
./gradlew :FaceLandmarkerApp:assembleDebug :FaceRegistrationLabApp:assembleDebug \
  :FaceLandmarkerApp:lintDebug :FaceRegistrationLabApp:lintDebug \
  :FaceLandmarkerApp:spotlessCheck :FaceRegistrationLabApp:spotlessCheck \
  -PfaceCompactVstPipeline=true -PfaceFusedControlModels=true -PfaceGpuPreprocessing=true
```

`tools/validate_intrinsics.py` executes the production board/face controllers and restoration logic with host Android adapters. `tools/validate_board_registration.py` renders known board cameras and the production reference atlas, exercises the pilot and 16-view calibration, verifies geometry, and rejects identity/timestamp/motion/hash/axis/unit failures. `tools/validate_binocular_geometry.py` checks existing face/reference behavior. Host evidence and the installable APK are archived under `artifacts/facelandmarker/registration-lab/board-diagnostic-2026-11-05/`.

Install/startup still requires the pinned headset and a scoped devmux lease. Preserve private calibration, prior app captures and recordings. Confirm no active recording or capture before replacing/restarting the app. Do not start the pilot automatically.
