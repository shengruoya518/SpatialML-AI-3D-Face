# Kotlin face registration: user calibration results

The returned data points to a camera-intrinsics mismatch and an intermittent geometry-output inconsistency. The checkerboard images suggest the service reports a horizontal focal length about 28% too small. This can change face rays and depth-dependent placement even when the service-to-Stage matrix math is correct.

The result is an experimental candidate, not an accepted physical calibration. The app saved 10 board views, and its full readback-motion check accepts only one. The sharp images still provide useful camera evidence; the motion gate and the image-fit result answer different questions.

## Retrieved evidence

Device: `PB311XHGKC220141G`, B3110, inspected Swan ROM `20261014024400`. The headset clock is CST (+0800); filenames are on October 29 while the experiment occurred on October 28 in Los Angeles.

| Recording | Duration | Confirmed contents |
|---|---:|---|
| `ScreenRecording_2026.10.29-05.58.52-AM.mp4` | 6 min 17 s | Live person, A/B/C face comparison, near/far and left/right poses |
| `ScreenRecording_2026.10.29-06.22.01-AM.mp4` | 6 min 15 s | Printed checkerboard mounted on the whiteboard; varied camera distances, image regions and tilts |

Both originals were pulled and SHA-256 verified against the headset. The shorter recordings at 06:05:21 and 06:06:12 were excluded from the main comparison; their separate two-sample board session was retained with the lab data. The earlier 05:20:58 recording is outside these Kotlin capture-session times. No headset files were deleted or changed.

All evidence is under `artifacts/facelandmarker/registration-lab/user-calibration-2026-10-28/`:

- `recordings/`: full MP4s, metadata, source paths and hashes in `retrieval.json`.
- `inspection/`: video contact sheets and raw-camera sample contact sheets.
- `moments/`: recording frames near each saved face sample, full-resolution details and wall-clock matching index.
- `captures/RegistrationLab/`: immutable pulled images and JSON from all four sessions, including prior smoke samples and the short board attempt.
- `face-analysis/`, `board-analysis/`: standard analyzer output.
- `board-diagnostic/`: exploratory camera fit, corner overlays, leave-one-out and distortion sensitivity results, and candidate profile.
- `scripts/`: exact one-off extraction and analysis scripts used for this report.

## Capture inventory

The main face session is `2026-10-28T21-48-11.176195Z-cb496d`, with 10 finalized samples and six passing its head-motion gate. Each cell below is saved samples, followed by stable samples in parentheses.

| Pose | A | B | C |
|---|---:|---:|---:|
| Front, about 1 m | 2 (1) | 0 | 0 |
| Looks left, about 1 m | 1 (0) | 1 (1) | 1 (1) |
| Looks right, about 1 m | 1 (1) | 1 (0) | 0 |
| Front, about 2 m | 1 (1) | 1 (1) | 1 (0) |

The video contains more live comparisons than the finalized sample inventory. Missing files are missing numerical captures; they are not evidence that a comparison was not attempted. A repeated A frontal sample means the 10 files cover nine of the twelve requested pose/mode combinations.

The main board session is `2026-10-28T22-22-06.756085Z-f9dbbe`, with 10 finalized Mode A board samples. All ten images contain the full 8×6 internal-corner pattern and were detected successfully. One passes the existing full readback-motion gate. The standard analyzer correctly reports `NEED_MORE_VIEWS`; its minimum is 12 stable views.

## Independent camera evidence

An exploratory fit used all ten sharp board images with a rectified pinhole model: radial and tangential distortion fixed to zero. Native source pixels are 3248×2464; the stored images are exactly half scale. The following values are converted back to native pixels.

| Parameter | Service metadata | Exploratory board fit | Difference |
|---|---:|---:|---:|
| Horizontal focal length, fx | 2065.590 | 2642.705 | +27.94% |
| Vertical focal length, fy | 2089.436 | 2036.955 | −2.51% |
| Principal point, cx | 1623.500 | 1672.377 | +48.877 px |
| Principal point, cy | 1231.500 | 1230.338 | −1.162 px |

The approximate centered horizontal FOV changes from 76.35° to 63.14°. The vertical FOV is similar, about 61.05° versus 62.33°. These are pinhole-model angles, not measurements of the headset display's FOV.

Validation of this exploratory fit:

- Overall calibration RMS: **0.410 saved pixels**, equivalent to 0.819 native pixels.
- Three held-out views: **0.396, 0.291 and 0.726 saved-pixel RMS** after fitting the other seven views.
- Holding service K fixed gives **1.01–4.71 saved-pixel RMS** across the same views; the fitted camera gives 0.12–0.69.
- Board-center coverage spans about 985×427 saved pixels. Inferred board tilts range from 0.6° to 48.1°.
- Leave-one-out fx ranges from approximately **2599 to 2728 native pixels**, consistently above the service's 2066. Principal point and absolute focal length have greater uncertainty than the broad horizontal/vertical mismatch.
- A free-distortion sensitivity fit gives fx≈2572, fy≈1977, RMS 0.365 saved pixels. It improves the residual only modestly and still preserves the large horizontal mismatch. It does not establish that additional distortion terms should be used on this rectified stream.

See `board-diagnostic/calibration-comparison.png` and `report.json`. Fit standard deviations exclude systematic errors such as print deformation, rolling-shutter effects and camera/pose synchronization. Ten images remain below the lab's 12-view acceptance threshold, so these values should first be tested as an explicit candidate.

The measured angular-pixel-spacing correction is fy/fx≈0.771. The existing B image affine uses horizontal scale 0.767, close to that value. However, B deliberately preserves the service's rays, so it still uses the questionable service K. C's source-equivalent focal lengths are approximately fx=2276 and fy=1746, about 14% below this board fit. The returned data supports the image-aspect hypothesis more strongly than C's absolute focal-length hypothesis.

For a measured trial that preserves the existing B model-image transform A, geometry must use:

```text
K_virtual = A × K_measured_source
```

`board-diagnostic/candidate-profile.json` contains both matrices. Putting source K directly into geometry after applying A would introduce a new ray mismatch. The principal point is also transformed by A.

## Motion and registration limits

The current motion gate measures the entire window from roughly half a second before exposure through all diagnostic readbacks. In this set that window is **2.29–4.22 seconds**. Most snapshots fail because position changes exceed 10 mm or rotation exceeds 1° during that full interval.

Within ±50 ms of the capture timestamp, the stored head history shows only approximately **0.2–2.8 mm** of position variation. The source images have readable corners. This explains why the full export-motion gate can reject a useful camera image. It does not prove exact exposure/tracking synchronization: history still uses public HMD callback-arrival timestamps.

Using the exploratory K and the existing optical extrinsics gives about **44 mm RMS stationary-board position drift**, with roughly 10–11 cm peak-to-peak along the largest axes. This number combines calibration, extrinsics, tracking and timing and is confounded by the full motion failures. It cannot be turned directly into a camera-to-head translation correction.

The numerical service-to-Stage transform reproduces the saved Stage vertices to sub-micrometre precision. That is an internal transform check, not proof that those points physically coincide with the passthrough face.

## Face geometry and recording evidence

The recording shows a live person and changing mesh shape/placement under A/B/C, including profile and near/far views. The mesh remains visible over the face, with residual mismatch under different poses. This is now actual compositor evidence; the earlier monitor-portrait smoke check was only source-camera evidence. The saved comparisons do not establish which mode is physically best for both eyes: the app does not export per-eye render matrices, and recording timestamps do not prove identical source-camera/compositor instants.

Six face samples have mesh-to-landmark source reprojection RMS below 0.00003 native pixels. Four show larger inconsistencies:

| Sample | Case | Mesh → packed landmark RMS, native px | Host replay → device vertex RMS |
|---|---|---:|---:|
| 002 | A, looks left, 1 m | 7.114 | 5.29 mm |
| 004 | A, frontal, 2 m | 1.483 | 61.26 mm |
| 006 | B, looks right, 1 m | 8.507 | 12.22 mm |
| 007 | B, frontal, 2 m | 2.424 | 6.98 mm |

The exact shipped JS, replayed from each saved raw XYZ/crop with NumPy SVD, reprojects below 0.00008 virtual pixels for all ten samples. It matches native vertices within about 0.00034 mm for the six consistent samples, while differing by millimetres to centimetres in the four listed above. Two also show disagreement between raw crop landmarks and the packet's normalized landmarks.

This separates a native execution/output-consistency issue from the mathematical camera calibration question. Possible causes include mismatched intermediate tensor generations or pose/vertex pairing; the present exports do not include the intermediate fit/metric tensors needed to identify the exact fault. It would be premature to attribute all remaining error to Stage extrinsics or apply a constant world offset.

## Next correction and validation

The next useful change is an explicit measured-intrinsics lab mode using A×K from the board candidate, together with a probe/fix for native pose/vertex consistency. That keeps the camera experiment separate from the inconsistent frames.

For the next capture pass, the lab should distinguish motion near exposure from movement during later export, show a clear accepted/repeat count, and preserve the raw fit/metric/pose intermediates with a frame marker. A short follow-up can then compare frontal near/far and one profile pose, and add varied board images to reach the image-view threshold. A full repeat of the original exercise is not the first step.

No app calibration values or world offsets were changed during this analysis. The retrieved data and exploratory results are preserved; headset files are intact, and the devmux lease was released.
