# Completed headset One check — 2026-10-31

Later Full trials exposed intermittent packet mismatches; their retained packets and the installed completion repair are documented in [FULL_TRIAL_MISMATCH_FINDINGS_2026-10-31.md](FULL_TRIAL_MISMATCH_FINDINGS_2026-10-31.md). That entry supersedes the Full trial readiness below. A face-bearing One check on the repaired build is pending.

Run `b2b8c9a3` completed **CLEAN_BEFORE → MARKED → CLEAN_AFTER**, with three accepted exports and a DONE journal state. All three snapshot/readback packets match exactly, including the signs of zero. The marked phase records six visible uploads with eight distinct markers in each. This establishes the updated capture path's face-bearing packet and marker integrity for this check. The next wearer step is a recorded **Full trial**.

## Retrieved evidence

- Headset: `PB311XHGKC220141G`; package `com.pico.spatial.ml.sample.facelandmarker.registrationlab`.
- Session: `2026-10-30T21-38-42.265313Z-4e9683`; its UTC label is October 30. The wearer follow-up is documented on October 31.
- Remote directory: `/sdcard/Android/data/com.pico.spatial.ml.sample.facelandmarker.registrationlab/files/RegistrationLab/2026-10-30T21-38-42.265313Z-4e9683`.
- Local evidence: `artifacts/facelandmarker/registration-lab/packet-check-2026-10-31/`.
- All 13 retrieved session files match headset SHA-256 hashes; originals remain on the headset. `retrieval.json` records each file's size/hash. The app was already closed, so retrieval used the stored session without relaunching it.
- Last verified installed diagnostic APK: SHA-256 `26b7b626ad0b5281b5b0cb7d3db2e1f0f3428ee6cc00c2aa52170cbcbe902e60`. The installed APK was not rehashed during this retrieval. No code/build/install change was made for this follow-up.

## Export and marker acceptance

| Phase | Frame | Camera age at readback | Exposure movement | Exposure rotation | Closest marker pair |
| --- | ---: | ---: | ---: | ---: | ---: |
| CLEAN_BEFORE | 92 | 455.42 ms | 0.59848 mm | 0.06746° | 25.8268 mm |
| MARKED | 100 | 411.94 ms | 0.82609 mm | 0.11261° | 25.5021 mm |
| CLEAN_AFTER | 109 | 496.74 ms | 0.92425 mm | 0.08966° | 26.5302 mm |

Each export is `EXPOSURE_STABLE`, carries candidate C/revision 1 and compares all 2,994 float32 values with zero numerical mismatches and zero signed-zero differences. Run/trial/pose/phase/epoch tags match the saved journal events and corresponding scene-upload acknowledgements. The MARKED export's frame 100 has a visible scene acknowledgement with eight markers; all six MARKED uploads have eight distinct vertices, with no collapsed scene.

The native analyzer accepts all three exports and rejects none. Mesh-to-source round-trip RMS is 0.0000834, 0.0000843 and 0.0001194 native pixels. Stage-transform replay RMS is approximately `8e-8 m`. Inferred median face depth is 1.039, 1.062 and 1.082 m; these depths derive from the model/calibration and are not independently measured distances.

Visual inspection of `native-analysis/002-002-mode4-step1/source-overlay.png` shows the raw landmarks and projected mesh following the detected face coherently. This overlay checks the source camera's internal crop/mesh mapping. It does not measure marker overlap in either headset eye.

The preceding mismatch from run `5474a68b` did not recur. Because the new packets have **no signed-zero differences**, this success does not establish signed-zero normalization as the cause or repair of that earlier failure. The earlier rejected packets were not retained; its cause remains unconfirmed. The diagnostic path remains available if a future mismatch occurs.

## Timing

| Phase | Start, app-relative seconds | Duration |
| --- | ---: | ---: |
| COUNTDOWN | 13.5080 | 15.0679 s |
| POSE | 28.5760 | 8.0006 s |
| SETTLE | 36.5765 | **1.4301 s** |
| CLEAN_BEFORE | 38.0067 | 7.0784 s |
| MARKED | 45.0851 | **5.0701 s** |
| CLEAN_AFTER | 50.1552 | 5.6272 s |
| DONE | 55.7824 | — |

The journal interval from capture start to DONE is **42.2744 seconds**. Phase durations include automatic image/JSON export work. SETTLE and exposure checks passed with small natural movement; the wearer need not hold both heads motionless for a long interval. This single check does not establish every pose's capture success or measure individual pipeline operators.

## Next wearer step and remaining calibration work

1. Open **SpatialML Face Calibration** with a real face in view.
2. Start the headset recorder in **Spatial** mode and keep the timing/status panel visible.
3. Press **Full trial** on the headset. Allow roughly **10 minutes**, based on this check's settle/export pace across 28 candidate trials; movement or face loss can extend the wait.
4. Follow the four prompts: frontal about 1 m, left about 1 m, right about 1 m, then frontal about 2 m. Stay relaxed, keep the face in view and allow normal small movement.
5. At **Capture complete**, stop the recorder. Keep the recording and local exports. If a phase times out, stop that recording and keep its partial evidence.

The trial tests C, F98, F97, Y40, Y75, Y110 and C-repeat at each pose, for at most 84 exports. These are candidate experiments; the app restores the initial working values and does not automatically save a new profile. Capture controls, the run and evidence storage work on the headset without a PC connection.

No new stereo recording was required for this packet diagnostic. Physical marker/anatomy alignment, binocular disparity, a winning candidate and corrected calibration remain unverified. Analysis of the full stereo recording and tagged exports is still required. Fitting/applying a correction from the recording is not implemented on the headset.

## Reproduce the saved validation

From the repository root:

```sh
python3 artifacts/facelandmarker/registration-lab/packet-check-2026-10-31/analysis/validate_packet_check.py
```

This verifies local files against the recorded retrieval hashes, phase completion, export/scene tags, exact packet-comparison reports, exposure acceptance and distinct markers. It writes `check-summary.json` and consumes the independent native analyzer's `report.json`.

The native analyzer was run with:

```sh
uv run --no-project --with numpy==2.5.3 --with opencv-python-headless==5.0.0.93 python FaceRegistrationLabApp/tools/registration_lab.py analyze artifacts/facelandmarker/registration-lab/packet-check-2026-10-31/capture-session --output artifacts/facelandmarker/registration-lab/packet-check-2026-10-31/native-analysis
```

The retrieval lease was released. All original recordings, app data and profiles remain preserved. No service change, commit or push was made.
