# Current versus head down 40 mm

**Evaluation update (2026-11-05):** the wearer reports that DOWN40 helps up close but places the mesh too low farther away. It is not accepted as a general correction. The [MediaPipe first-principles audit](MEDIAPIPE_TRANSFORM_AUDIT_2026-11-05.md) supersedes the next-step recommendation below; these instructions remain available for the existing experimental control. No additional comparison recording is currently requested by that audit.

The comparison APK is **installed and startup/UI verified on PB311XHGKC220141G**. The new button is visible and the scene starts **POS CURRENT**. [APK, checks and installation evidence](../artifacts/facelandmarker/registration-lab/head-down-comparison-2026-11-05/IMPLEMENTATION.md). The next step is a **30–60 second manual Spatial recording** of the live comparison below; no full calibration repeat is needed. Real-face physical acceptance remains pending.

## Live comparison

1. Open **SpatialML Face Calibration** with a well-lit real face in view. Keep the subject neutral and approximately 1–1.2 m away. Wait for the mesh to track the face.
2. The lab starts in **Current**. The timing badge says **POS CURRENT** once a frame is rendered. Start the headset recorder manually in **Spatial** mode if you want to retain the comparison.
3. Hold both heads still and inspect the eye line, nose, mouth and chin in both eye views for a few seconds.
4. Press **Use head down 40 mm**, beside **Roll trial · 4 holds**. Wait for the timing badge to show **POS DOWN40**. Inspect the same face features at the same distance and pose.
5. Press **Use current position** to switch back. Repeat once at the same position, then compare while leaning **left ear toward left shoulder** and **right ear toward right shoulder**, keeping your nose aimed toward the subject. The subject stays frontal. You can also compare nearer/farther while keeping each pair stationary.
6. Stop recording manually when finished. Keep the recording. Return to Current or close the app; reopening always starts Current.

Only the face pose and mesh position shift. Camera values and saved calibration are retained, and scale stays 1.0. The correction follows the capture head; it is not a fixed downward world shift. Do not turn left/right when intending ear-to-shoulder roll.

## Optional recorded reference check

For an export/marker recording that can be measured against the earlier baseline:

1. Select **Use head down 40 mm** and wait for **POS DOWN40**.
2. Start Spatial recording manually.
3. Press **Roll trial · 4 holds** and follow [the existing four-hold instructions](AUTOMATIC_CAPTURE_STEPS.md#roll-only-test--next-capture): upright → left ear toward left shoulder → right ear toward right shoulder → upright.
4. The correction is frozen throughout the run. White references keep their original capture-head transform; green face markers show the shifted geometry. The badge continues to identify **POS DOWN40**.
5. At **Capture complete / 12 exports**, stop recording and preserve the video and exports. Cancellation preserves partial evidence. The original ten-hold trial and full intrinsics sweep do not need repeating for this comparison.

Switching is unavailable during pending exports and automatic capture. The position selection is an experimental app-side comparison and is not saved as accepted calibration. Physical acceptance remains to be checked; the earlier correction analysis provides predictions, not an already verified headset result.

## Evidence

Exports keep the raw native packet and optical transform, corrected Stage packet, raw/corrected registration matrices, and immutable correction ID/revision. Projection uploads retain raw and rendered face markers. The offline observer verifies greens against rendered geometry and measures raw-baseline and corrected residuals separately, so the correction is not silently fitted twice.

On ROMs that deliver the existing COMMAND broadcasts, `pose_correction` toggles the same selection through the helper or desktop bridge. The tested ROM defers those broadcasts, so use the headset button.
