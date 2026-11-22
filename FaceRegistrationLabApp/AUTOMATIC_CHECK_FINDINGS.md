# Automatic one-sample check — 2026-10-30 headset date

**Follow-up:** the user approved all three recommended changes. They are implemented in the updated source: stale exposures preserve a valid hold, lab face frames on repeated exposures or with collapsed marker vertices are rejected before presentation/export, and the seven-candidate sweep now includes focal −3% and cy −40/−75/−110 px with repeated C. The evidence below describes the previous build. The update is now installed and startup-verified; another one-sample recording is required before the full sequence; see [AUTOMATIC_CAPTURE_STEPS.md](AUTOMATIC_CAPTURE_STEPS.md) and the latest [VALIDATION.md](VALIDATION.md) section.

The first real-face automatic check completed and is usable. Run `1cfc5957` (C, prompted frontal pose at about 1 m) produced the expected clean/marked/clean exports. The Spatial recording shows all eight markers in both eyes, and the badge matches the offline journal. Measured against MediaPipe landmarks on the recorded passthrough face, the C mesh is about **50.7 recorded pixels too high in both eyes** and about 3% too small. Its stereo disparity places it slightly nearer than the face.

Two gate problems should be fixed before the full 84-export sequence. The marked phase took 35.9 s because frequent old camera samples reset the hold. The first visible marked scene also drew five markers at a non-face point. No correction profile was fitted or applied.

## Retrieved evidence

Evidence directory: [`automatic-check-2026-10-30`](../artifacts/facelandmarker/registration-lab/automatic-check-2026-10-30/).

- Original Spatial MP4 `ScreenRecording_2026.10.30-09.50.36-AM.mp4`: 422,952,782 bytes, SHA-256 `f3aa475ad8a5a812b48d2204ddf5e2dabc4c4ae707ffa880bc1ca9fcb7642890`. The headset copy is retained.
- Session `2026-10-30T01-36-02.472865Z-6b8558`: `timeline.jsonl` plus `001`/`002`/`003-mode4-step1`. `retrieval.json` lists per-file hashes. The pulled timeline prefix matches the device.
- `stereo-verification.json`, `sampled-frames.json`, contact sheets and `stereo-side-by-side-preview.mp4` cover stereo decoding.
- `native-analysis/report.md` and overlays cover the three exports.
- `analysis/` contains the reproducible scripts listed under each section below.

Target was PB311XHGKC220141G with installed APK SHA-256 `35683f449993446dfa9da94df01f9768019cb75df35449a27063c63263128e84`. The devmux lease was released. No app data, recording, profile or device setting was changed.

## Run and exports

| Phase | App-relative start (s) | Export |
|---|---:|---|
| COUNTDOWN | 881.62 | — |
| POSE | 896.65 | — |
| SETTLE | 904.71 | — |
| CLEAN_BEFORE | 928.90 | `001-mode4-step1`, frame 2808 |
| MARKED | 933.19 | `002-mode4-step1`, frame 2882 |
| CLEAN_AFTER | 969.06 | `003-mode4-step1`, frame 2896 |
| DONE | 977.77 | Capture complete |

Each export is `exposureStable=true`, Custom mode 4, revision 2, and carries the C virtual K: fx=fy=1746.4713134765625, cx=1623.5, cy=1231.5. The marked export contains the eight Stage marker centres and `poseLabelIsPrompt=true`. Native analysis accepted 3/3 samples. Mesh round-trip RMS was 0.0001 native px, and inferred depths were 1.013, 1.021 and 1.016 m. The landmarker and source overlays are visually correct. These checks show internal consistency; they do not show physical overlap.

## Recording and clock association

Explicit multiview decoding produced **3,355 stereo pairs** with equal left/right PTS, 1920×1080 per eye. View 0 is left and view 1 is right.

`analysis/clock_association.py` matches each OCR tick and printed UI time to the journal, writing `analysis/clock-association.json`:

```text
app session-relative seconds ≈ video PTS seconds + 875.4397
```

- **Anchors:** 51 of 57 two-second samples are accepted, with residuals of −0.049 to +0.050 s. Six unreadable or mis-read samples are rejected rather than guessed.
- **Frames:** the printed frame matches the journal row's mesh frame for 41/41 readable samples.
- **Phases:** the printed phase matches the mesh tag for 36/38. Both mismatches are at phase transitions; the badge text and the last uploaded mesh update asynchronously.
- **Marker analyzer clock:** the analyzer used the earlier median 875.4338 s. The 6 ms difference is below the 100 ms badge cadence.

Neither clock is a compositor-present timestamp.

## Marker versus passthrough anatomy

`analysis/measure_markers.py` examines every second stereo pair from video 52–104 s. It uses the public MediaPipe Face Landmarker bundle; its SHA-256 matches `provenance.json`.

**Method:**
- Green markers are found by colour inside a face crop and inpainted before landmarking.
- They are ordered structurally: eye corners by x, then nose, mouth corners and chin.
- Each marker is compared with the same MediaPipe landmark ID: 33, 133, 362, 263, 1, 61, 291 or 152.

**Frame selection:**
- Analysed: 777 pairs.
- Accepted: 181 MARKED pairs.
- Rejected: 277 were not MARKED, 11 had an ambiguous marker layout and 308 were stale. A pair is stale when the passthrough anatomy moved more than 3 px between the mesh's camera exposure and its display.
- Clean phases had 0 false marker detections in 199 pairs.
- Clean-phase anatomy frame-to-frame motion has a median of 0.77 px (left) and 0.71 px (right).

Medians, in recorded pixels (marker minus anatomy; +x right, +y down):

| Measurement | Left eye | Right eye |
|---|---:|---:|
| Mean dy | **−50.64** (IQR −51.36…−49.86) | **−50.89** (IQR −51.52…−49.95) |
| Mean dx | +3.80 | +0.95 |
| Similarity scale, marker/anatomy | 0.968 | 0.974 |
| Similarity rotation | 0.19° | 0.23° |

Per-landmark dy ranges from about −49 px at the eye corners to −52/−53 px at the nose, mouth and chin in both eyes. This is consistent with a common upward shift plus the smaller pattern scale. The 489 MARKED pairs without the stale filter give the same vertical result.

| Stereo measurement | Median |
|---|---:|
| Passthrough face disparity (left x − right x) | 74.70 px |
| Marker minus face disparity | **+2.86 px** (IQR +2.63…+3.02) |
| Marker minus face vertical disparity | +0.16 px |

More crossed disparity means the markers appear **nearer** than the passthrough face, not inside it.

**Approximate metric conversion (unverified).** This uses the recording's own metadata (HFOV 77.899° over 1920 px, so f ≈ 1187.6 px, and baseline 64 mm), which is not a verified optical calibration:
- **Vertical:** 50.7 px ≈ 2.45° ≈ 4.3 cm high at 1.016 m. Under C focal length, a pure principal-point explanation would require cy lower by about 75 virtual px.
- **Depth:** the face is at about 1.02 m and the markers at about 0.98 m.

The current candidate sweep only tests cy ±20 px, about 1.1 cm per metre. The vertical source may instead be camera/head extrinsics or the render projection. A cy change would be a correction test, not proof of the cause.

A depth-only error cannot explain markers that are nearer yet 3% smaller. A fixed canonical face-size prior can place the mesh at the wrong depth. Separately, a focal length about 3% too large would reduce angular size. The existing −2% focal candidate addresses the second mechanism only partially.

## Why the marked phase took 35.9 s

`analysis/marked_phase_timing.py` writes `analysis/marked-phase-timing.json` and replays the `LabAutoCapture.frame` gates from journal values.

**Inputs during MARKED (70 scene updates):**
- **Camera age:** 21 updates had readback age above 0.9 s (min 0.41, median 0.52, max 0.98 s). The ages fall in two clusters, about 0.43–0.60 s and 0.87–0.98 s, roughly one camera interval apart.
- **Gaps:** four frames had no scene update.
- **Marker movement:** the maximum Stage marker step was 10.7 mm and nine steps exceeded 7 mm. None exceeded the 12 mm stability limit by itself.

Replaying the same MARKED inputs:

| Gate | Export frame | App time (s) | Hold resets |
|---|---:|---:|---:|
| Current, 0.9 s freshness | 2882 | 967.43 | 19 (15 stale, 3 missing update, 1 drift) |
| Freshness 1.0 s | 2816 | 936.84 | 0 |
| 0.9 s, but skip stale frames instead of resetting | 2817 | 937.32 | 0 |

The current replay reproduces the actual export frame. Earlier phases show the same pattern: SETTLE took 24.2 s, with 8 stale updates among 53. Each phase has a 60 s timeout, so the full 28-trial run could fail without any wearer error.

**Defect: misplaced markers.** The first visible marked scene, frame 2810, placed five of eight markers (133, 362, 263, 291, 152) on one point about 1.04 m from the face. The video shows only three markers on the face during that scene. The point coincides within about 2 mm with the head-to-Stage translation in the exports; since `serviceToStage` equals head-to-Stage here, that is where zero service-space vertices land. This is an inference from geometry, not a verified cause.

The frame repeated frame 2809's camera exposure while `hasFace` changed from false to true. That repeated-exposure face-flag change occurs seven times in the session. The marked export itself was not affected: frame 2882 has distinct, plausible marker positions. A later analyzer could reject frames like this, but the rendered evidence should not contain them.

## Recommended changes before the full sequence

The user approved these workflow changes on 2026-10-30; the updated source implements them:

1. **Freshness:** stop stale frames from resetting a valid hold; skip them, as already done for repeated exposures. Alternatively, raise the freshness limit to about 1.0 s. Both replays export within about 3.7 s of the markers appearing.
2. **Corrupt marker scenes:** reject or hide frames whose face flag turns true on a repeated exposure, or whose marker vertices collapse to one point, before tagging or uploading markers.
3. **Candidate range:** widen the vertical candidates so the sweep brackets the measured offset, for example cy −40, −75 and −110 px with C focal length. Consider focal −3% alongside −2%. Keep the C repeat as a drift check. The full run then still tests whether a K change, rather than an extrinsic or render offset, removes the error.

After those changes, rerun this one-sample check before the full sequence. Physical correction, compositor-present timing and the automatic video fitter remain unverified or unimplemented.
