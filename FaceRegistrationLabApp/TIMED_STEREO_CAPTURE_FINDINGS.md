# Timed stereo face capture — 2026-10-30 headset date

The new recording is usable as a synchronized stereo baseline for the C configuration. The badge matches the offline journal, and the footage confirms a persistent upward mesh offset in both views. It also exposes slow mesh updates and old camera samples during motion. This capture does not establish corrected intrinsics or metric face depth.

## Retrieved evidence

Evidence directory: [`timed-spatial-recording-2026-10-30`](../artifacts/facelandmarker/registration-lab/timed-spatial-recording-2026-10-30/).

- [Original Spatial MP4](../artifacts/facelandmarker/registration-lab/timed-spatial-recording-2026-10-30/ScreenRecording_2026.10.30-08.56.13-AM.mp4): 455,844,314 bytes, 99.898 seconds, SHA-256 `08a13ffebc3d59318b9ae2a1d4cfc8039b801a6dd152e69754a8f5a57fc5dfaf`.
- [Ordinary side-by-side preview](../artifacts/facelandmarker/registration-lab/timed-spatial-recording-2026-10-30/stereo-side-by-side-preview.mp4): H.264, left then right, 1920×540 combined, silent. The original preserves full resolution and audio.
- [Paired face comparisons](../artifacts/facelandmarker/registration-lab/timed-spatial-recording-2026-10-30/face-comparison.jpg): approximately 10, 20, 60 and 70 seconds; identical 1.6× pixel enlargement for both eyes. Crops are repositioned to show faces, so use original full frames for disparity measurements.
- [Timeline](../artifacts/facelandmarker/registration-lab/timed-spatial-recording-2026-10-30/timeline.jsonl): 5,263,571 bytes, SHA-256 `4f0f0e5acd8238321f4ce538100873a021dc5f166f31755e889c160f2c3ec92e`.

Video and journal sizes were unchanged across retrieval, and local SHA-256 values match the headset copies. Target was PB311XHGKC220141G on Swan `20261014024400`; the headset date was October 30, while the host local date was October 29. Originals and app data were preserved, and the devmux lease was released. No app, profile or device setting was changed.

The video contains one MV-HEVC track plus AAC. Explicit multiview decoding produced **2,995 pairs**, each with equal left/right PTS, 1920×1080 per eye. Frame side data identifies view 0 as left and view 1 as right. `decode_preview.py`, `stereo-verification.json`, `sampled-frames.json` and five contact sheets preserve the extraction method and results. Both views visibly include VST and mesh. Audio was not analyzed.

## Badge and journal association

The visible session is `b8f55e`, matching `2026-10-30T00-44-12.461977Z-b8f55e`. The journal contains 12,985 valid JSONL rows, including 10,657 consecutive UI ticks, 2,325 scene-update events and a normal close event. The saved session continues beyond the video; it is not limited to the clip.

Fifty left-eye frames were sampled at roughly two-second intervals. OCR matched tick IDs **and** printed UI times to journal rows at 44 samples; six were rejected rather than guessed. The median mapping is:

```text
app session-relative seconds ≈ video PTS seconds + 722.380365
```

Of those matches, 43 have offset residuals between −42 and +54 ms. The 98-second sample is an outlier at −168 ms and is excluded from the reliable anchor set. This spread is compatible with the approximately 100 ms badge cadence and asynchronous presentation; it is not a claim of ±54 ms camera/display synchronization. No clock-rate correction was fitted for this short clip.

Example: video 20.032 s shows tick 9456, UI 742.420 s, camera 741.343 s and frame 2105, K0/M4. `video-timeline-matches.json` links each accepted OCR read to the exact frame/configuration record. `ocr-rejections.json` retains failed reads. `analyze_timeline.py` reproduces the association and statistics.

All scene records in the recording interval use **Custom mode 4, revision 0**, with the original C virtual intrinsics:

```text
fx = fy = 1746.4713 px
cx = 1623.5 px
cy = 1231.5 px
```

There is no candidate sweep or saved correction in this recording. The retrieved session directory contains the timeline only, with no new source-image or full-geometry sample exports. The journal carries frame identity, K and timestamps; it does not contain every frame's landmarks/vertices.

## What the footage shows

The paired comparisons around 10 and 20 seconds cover opposite face turns. The closer frontal view around 60–64 seconds and closer turned view around 70 seconds also show the mesh above the real face in both eyes. The mesh's nose/mouth/chin sit above their visible counterparts. This supports the wearer's symmetric vertical-error observation.

The mesh also leaves part of the lower face uncovered. Separating a scale/depth error from the substantial vertical shift requires landmark correspondences after alignment. The dense green wireframe obscures eyes, nose and mouth, so an automated landmark detector could follow the synthetic geometry. This review does not report an independently measured scale factor, a centimetre offset, or corrected fx/fy/cx/cy.

No-face intervals occur around 30–34 and 44–48 seconds, and during part of the close off-center/turned sequence around 80 seconds. The source continues advancing in the journal, and logs include `Waiting for a measured face` and occasional non-advancing timestamps. These are excluded from geometric fitting. The current evidence does not identify whether each loss is caused by pose, coverage, detector confidence or another pipeline limitation.

A badge reports the last completed SDK scene update. Brief video/metadata visibility disagreement at transitions remains possible because UI and mesh presentation are asynchronous. Stable intervals are required even when the tick matches exactly.

## Timing is a separate source of apparent offset

Statistics use the journal interval mapped to the video, not the entire 14-minute app session:

| Measurement | Result | Boundary |
|---|---:|---|
| Scene updates | 211 in 99.9 s, about 2.1/s | SDK update completion; not display refresh rate |
| Median interval between scene updates | 0.460 s | Includes positive and negative face results |
| Distinct camera exposure times | 165 | Some updates reuse an exposure timestamp |
| Positive visible-face updates | 165 | Not 165 independent known-pose calibration samples |
| Camera exposure to scene update completion | median 0.567 s; p95 1.055 s | Positive-face updates only |
| Camera age at UI state generation | median 0.902 s; p95 1.391 s; maximum 2.183 s | Positive visible-mesh UI ticks; includes time holding an older update |

The camera clock uses the existing monotonic-domain contract; these are application timing measurements, not compositor-present or photon latency. UI-tick statistics are sample-weighted, not a time-weighted percentage of the clip.

Turning the subject or moving the headset while a mesh is based on a substantially older image can introduce apparent positional, rotational and scale differences. Static intrinsics cannot fix that temporal error. The recurring high placement in quieter frontal and turned views is still useful evidence of a registration residual, but moving footage should not drive a camera-parameter fit.

## Next implementation step

Use this recording as the C baseline. Build the planned sparse-marker / clean-view capture sequence with automatic source/geometry exports and candidate control, preserving the badge-only headset experience. In each pose, wait for fresh advancing exposures and settled motion, then hold the candidate for several seconds; reject no-face, repeated/stale exposure, transition and logging-error intervals. Measure the slow update path separately so latency is not absorbed into calibration constants.

The first controlled search can retain the C affine and test a shared focal multiplier plus cy, as described in [AUTOCALIBRATION_PLAN.md](AUTOCALIBRATION_PLAN.md). It must measure markers against the real face independently in both eyes and compare repeated steady samples before proposing a saved profile. Do not infer a cy correction directly from a recording-pixel displacement or use the recording FOV as the SpatialML source K.

No further manual adjustment is requested from this capture review. A fresh wearer sequence should wait until one automatically tagged clean/marked sample has been verified end to end. Automatic fitting and physical alignment remain unfinished; the current APK and calibration values are unchanged.
