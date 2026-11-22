# Automatic face capture on the headset

**Position comparison update:** [Current versus head down 40 mm](LAB_POSITION_COMPARISON.md) is installed and startup/UI verified. Select the desired position before starting capture; it is frozen for the entire run and shown as POS CURRENT/DOWN40. The new installed APK has this control; the preceding roll-only APK did not.

**Latest roll trial completed and retrieved:** [Run 672dcdaf](../artifacts/facelandmarker/registration-lab/roll-trial-2026-11-05-b8c6a3/RETRIEVAL.md) contains all four holds / twelve native-valid exports and verified intended headset roll. Both-eye references pass in a sampled pair from each hold. Keep the data for anatomical correction-transfer analysis; no repeat capture is requested. The procedure below documents this completed test.

**Current update:** [Roll-only implementation and validation](../artifacts/facelandmarker/registration-lab/roll-only-update-2026-11-05/IMPLEMENTATION.md). The app now has **Roll trial · 4 holds**, measured baseline-relative angle feedback and capture gating, and side-column references with a reserved central face region. Host/build checks pass; the APK is installed and startup/UI verified on PB311XHGKC220141G. Real-face roll capture and both-eye acceptance are the next checks. The previous [ten-hold analysis](../artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-712cf5/FINDINGS.md) remains valid. No correction has been applied.

## Roll-only test — next capture

**The wearer moves the headset; the subject stays facing forward.** Roll means bringing your ear toward the same-side shoulder while keeping your nose pointed at the subject. Yaw means turning left/right like “no.” Pitch means looking up/down like “yes.” The app uses recorded head transforms relative to the first stable hold to distinguish them.

1. Open **SpatialML Face Calibration** and wait for the live mesh to follow a well-lit real face. Keep the subject about **1 m** away, with a neutral expression, and centre the whole face. Remove glasses if practical. Start with your head upright.
2. Start the headset recorder manually in **Spatial** mode. Keep the status panel visible without covering the face or side references.
3. Press **Roll trial · 4 holds**. After the **15-second countdown**, follow the four holds below. Allow roughly **1–2 minutes**; readiness waits can extend this.
4. During each hold, remain relaxed and still while the app saves **clean → marked → clean**. Keep the face centred and wait for the next prompt. The marked interval shows eight green face points, twelve white references in side columns, and a frame code above the face.
5. At **Capture complete**, verify **12 exports**, then stop the recording manually. Keep the video and all exports. If it times out, stop recording and preserve partial evidence.

| Hold | Wearer's movement | Measured roll target |
|---|---|---|
| 1 | Upright, looking at the subject; establish the baseline | 0° relative to this baseline |
| 2 | **LEFT ear toward LEFT shoulder**; nose still toward the subject | +15° |
| 3 | **RIGHT ear toward RIGHT shoulder**; nose still toward the subject | −15° |
| 4 | Return upright to the starting position | 0° |

Read **Roll / target**, **turn**, and **nod** on the panel. Capture requires roll within **3°** of target and turn/nod each within **5°** of the original baseline. If you turn to look sideways instead of leaning ear-to-shoulder, the app waits. All three saved phases recheck measured orientation, face clearance and the existing exposure/geometry gates. The upright baseline is frozen after the first stable hold; later holds cannot redefine it. Upright is the wearer's starting posture, not an independently measured gravity reference.

If the panel asks you to centre the whole face, adjust position before holding still. Keep approximately the same distance throughout. Stay within a comfortable range; **Cancel capture** restores the starting working values and preserves saved evidence. Do not force a neck position to satisfy the target.

This test fixes C for measurement and restores the starting working values/output selection on completion, failure or cancellation. It does not save a new calibration. Reference layout clearance is checked against the reconstructed face in capture-head coordinates; actual anatomy/reference visibility in both recorded eyes still needs inspection. The roll test tests the existing correction hypotheses against new orientations. Four holds at one distance do not independently establish a universal metric-depth calibration.

Use the headset button: this ROM currently defers computer COMMAND broadcasts. `auto_roll` is available in the helper/desktop bridge for ROMs that deliver those commands. The system recorder and trial start remain manual.

## Retained geometry trial

The existing ten-hold sequence remains available. It is not the requested next capture; use the roll-only test above.

## Geometry trial — current procedure

1. Open **SpatialML Face Calibration**, put a well-lit real face in view, and wait for the live mesh to follow it. Remove glasses if practical to improve landmark measurement.
2. Start the headset recorder in **Spatial** mode. Keep the status panel and reference targets visible.
3. Press **Geometry trial** on the headset. It runs ten holds and saves thirty exports. Allow several minutes plus settling; move between prompts and keep both the subject and headset still during each hold.
4. Follow the prompts in order: frontal at about **0.7, 1.2 and 2 m**; subject turns **left, then right** at about 1.2 m; subject stays frontal while the wearer **rolls left, then right** (ear toward shoulder, rather than turning to look sideways); wearer **turns the headset left, then right** while keeping the face visible; finish with a **level frontal 1.2 m repeat**. Keep a neutral expression during capture.
5. At **DONE / Capture complete**, stop recording and retain the video and all exports. If it times out, stop recording and preserve partial evidence.

An optional flat **8×6-inner-corner, measured 20 mm-square checkerboard** beside the face during the three distance holds provides a metric control. Keep the face unobscured. Distances in prompts are approximate, not measured ground truth.

Use the headset controls because this ROM currently defers computer COMMAND broadcasts. The trial fixes C during measurement and restores the starting working values and output selection afterward; it does not save a calibration. In the latest trial, only selected still segments passed the 15 mm centre-range limit. The requested roll holds mainly produced yaw, and reference panels obscured some landmarks. The new Roll trial enforces measured roll and uses side-column references; the original Geometry trial retains its original layout and prompt sequence. See [the model, analysis and acceptance gates](BINOCULAR_GEOMETRY_INVESTIGATION.md).

## Earlier intrinsics sweep

The retained intrinsics-sweep instructions below describe the earlier [compact-pipeline correction](MESH_FLICKER_RECORDING_FINDINGS_2026-11-03.md),
installed on Swan headset `PB311XHGKC220141G` on November 3, 2026. Face tracking is verified in
537 of 542 frames; the five rejected frames repeated a camera timestamp. The controls are unlocked.
That sweep has since been completed and analyzed; see the [84-export results](../artifacts/facelandmarker/registration-lab/full-calibration-2026-11-05-8a185f/FINDINGS.md).
The steps below remain documentation for One check / Full trial. The current next capture is
**Roll trial · 4 holds** above. Earlier installation evidence is recorded in
[VALIDATION.md](VALIDATION.md#compact-pipeline-flicker-correction--2026-11-03).

One check/Full trial automatically enable all required Face pose, Face mesh and Face blendshapes
outputs and lock the switches until the run ends, then restore the selected combination.
The app waits for completed geometry and snapshots before accepting an export. Earlier packet
failures are documented in [FULL_TRIAL_MISMATCH_FINDINGS_2026-10-31.md](FULL_TRIAL_MISMATCH_FINDINGS_2026-10-31.md).

Use the headset to start and run capture. The app has **One check** and **Full trial** buttons beneath its timing badge. It saves exports and its journal on the headset. The system recorder starts and stops manually in Spatial mode. See [HEADSET_CAPTURE_UPDATE.md](HEADSET_CAPTURE_UPDATE.md) and the latest [VALIDATION.md](VALIDATION.md) entry for the timeout repair and current installation boundary.

## One check

1. Open **SpatialML Face Calibration** and put a real face in view, facing forward at about 1 m. Wait until the live mesh follows the face and the status is **Ready for One check or Full trial**.
2. Start the headset screen recorder in **Spatial** mode. Keep the timing/status panel in the recording.
3. Press **One check** in the headset. A 15-second countdown gives you time to settle into position.
4. Stay relaxed and keep the face in view. Normal small movements are allowed. The app looks for brief usable exposure windows and runs a clear face view, eight green markers, then another clear view. It saves each phase automatically.
5. Wait for **Capture complete**, then stop recording on the headset. Keep the recording and saved evidence.

One check uses the C camera values and produces three exports: clear face, green markers, clear face.
It restores the working camera values and output selection when the run ends. Keep the recording
and all three exports together for inspection before starting Full trial. The timestamp guard
excludes the camera service's wall-clock fallback without blocking later sensor frames. Three
usable exposures over at least 0.8 seconds are required; gradual drift is checked between
exposures. Head motion is checked around each camera exposure rather than requiring two seconds
of immobility. Large movements, face loss or invalid geometry may extend the wait. Each phase has
a 60-second timeout.

If the run times out, stop that recording. **One check** becomes available again for a new attempt.
Keep failed recordings and partial exports for diagnosis.

If the pose/mesh/blendshape switches and both capture buttons become disabled shortly after launch,
the runner may have stopped during GPU model initialization. Reopening the app alone can reuse the
same failing OpenMR process. Stop any recording, then use the connected PC to restart the lab and
the installed service processes:

```sh
bash FaceRegistrationLabApp/tools/registration_lab_device.sh restart
```

The helper preserves APKs, calibration and saved evidence, and refuses to interrupt an active
recording or calibration sequence. Keep the recovered app open during the calibration session.
This is a recovery for the current service lifecycle failure, not a permanent runtime fix;
see the [relaunch investigation](REGISTRATION_LAB_RELAUNCH_FAILURE_2026-11-03.md).

## Full trial

After this build's One check recording and three exports have been inspected, run **Full trial**:

1. Open **SpatialML Face Calibration** with a real face in view.
2. Start the headset recorder in **Spatial** mode. Keep the timing/status panel visible.
3. Press **Full trial** on the headset. Reserve roughly **10 minutes**; actual duration depends on waiting for usable exposures.
4. Follow the prompts: frontal about 1 m, face turned left about 1 m, face turned right about 1 m, then frontal about 2 m. Keep the face in view and stay relaxed; normal small movement is allowed.
5. At **Capture complete**, stop the recorder. Keep the recording and saved exports. If it times out, stop that recording and preserve partial evidence.

Full trial runs seven candidates at each of the four poses and produces at most 84 exports. Each pose change has an eight-second preparation interval. Distances and rotations are prompts, not measured ground truth.

Candidates retain the C image affine and test C, focal lengths −2%, focal lengths −3%, cy −40 px, cy −75 px, cy −110 px, and repeated C. Each cy candidate keeps C focal lengths; each focal candidate keeps C principal point. Odd pose groups reverse the candidate order. These are experiments; none becomes the saved profile automatically.

Both headset buttons disable while a sequence/export is active. Completion, cancellation or failure restores the working values from before the sequence, with a fresh revision. Existing saved profiles remain intact. Closing the app cancels its active run. The session is bounded to 100 exports; reopen the app to begin a new session if the Full trial button is disabled after a completed full run.

## Saved evidence

Each sample carries an automatic tag identifying run, trial, requested pose, candidate, phase and epoch. The same tag travels with the rendered FaceFrame. Export waits for a matching scene acknowledgement for that frame and checks native geometry against the readback packet. The journal contains phase changes, frame clocks, exposure motion, marker centres and exported folder names.

Markers use landmark IDs 33, 133, 362, 263, 1, 61, 291 and 152. Each is a 3 mm radius octahedron centred on its Stage-space vertex. Selected marker pairs must be more than 1 mm apart. Repeated-exposure face frames, out-of-domain timestamps and collapsed geometry cannot authorize an export.

Export freshness still requires an advancing exposure, matching K/revision, face detection, age at most 0.9 seconds, valid capture-time head history and exposure stability. Source/model images and full geometry are sampled exports. The recording is separate MV-HEVC stereo footage; retain both views. Neither badge timing nor SDK mesh-upload completion is compositor presentation time.

The capture workflow runs without a PC connection. This app collects calibration trials; it does not yet fit and apply a correction from the recorded footage on the headset. Optional desktop controls, diagnostics and retrieval remain available when requested; see [DESKTOP_CALIBRATION.md](DESKTOP_CALIBRATION.md). The [Unity comparison](UNITY_OPTIMIZATION_COMPARISON.md) and [profiling plan](PIPELINE_TIMING_PLAN.md) are separate technical follow-ups.
