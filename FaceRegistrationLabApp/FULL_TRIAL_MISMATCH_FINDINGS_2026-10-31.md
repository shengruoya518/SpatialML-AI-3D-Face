# Full-trial packet mismatches and completion repair — 2026-10-31

The returned attempts contain four real snapshot/readback mismatches. All four passed the exposure-motion gate, and their producer/fit/mesh snapshots share the expected sequence. The raw result has the current packet prefix and older data in its remaining fields. The app previously accepted the leading frame number as its completion check. The lab now waits for a separate final operator, after result packing and geometry snapshotting, before reading or presenting a frame.

The repair is installed on `PB311XHGKC220141G` with SHA-256 `39861cdf012e99ddfcbb8218dfe5c08a6f28ef00add89915bb0a85753e4906fb`. Startup and sustained no-face streaming pass. A face-bearing **One check on this repaired build** remains the next acceptance step before another Full trial.

## Returned attempts

| Run | Requested sequence | Accepted exports | Final result |
| --- | --- | ---: | --- |
| `14f70d59` | Full trial, 28 candidate/pose trials | 0 | C, CLEAN_BEFORE packet mismatch |
| `764898e3` | Full trial | 2 | C, CLEAN_AFTER packet mismatch |
| `0291e0b9` | Full trial | 13 | Trial 5, Y75, MARKED packet mismatch |
| `c25d9cfa` | One check | 0 | C, CLEAN_BEFORE packet mismatch |
| `b9603afb` | One check | **3** | **DONE**, 34.6702 seconds |
| `6a6b3816` | Full trial in a later app session | 0 | Camera stopped supplying fresh frames during SETTLE |

The most recent completed One check is `b9603afb`, with CLEAN_BEFORE/MARKED/CLEAN_AFTER frames 953/967/976. Each packet matches exactly, including zero signs. Their camera ages are 248.81/255.73/284.29 ms. This successful check was on the previous build; it does not validate the new completion repair.

All **18 accepted exports** across the attempts pass independent native analysis. Their mesh/source round-trip RMS is about 0.0001–0.0002 native pixels. The marked source overlay from the successful check was visually inspected and follows the detected face coherently. The rejected packets remain separate diagnostic files and are excluded from calibration acceptance. The partial full run contains complete C/F98/F97/Y40 trials at the first frontal pose plus the first Y75 clear sample; it does not cover the four-pose experiment.

The final separate session explicitly requested 28 trials in its journal. It stopped after 23.7184 seconds because the app observed no advancing camera exposure for three seconds. This is separate from packet equality. Its service/ROM cause remains unconfirmed; the new build supplies advancing camera frames after installation, but sustained recovery from that earlier fault is not established for wearer capture.

## Exact mismatch evidence

| Rejected frame | Different float32 values | First differing index | Snapshot exposure newer than raw result | Exposure movement / rotation |
| --- | ---: | ---: | ---: | ---: |
| 137 | 199 | 2733 | 233.33 ms | 0.31590 mm / 0.08353° |
| 369 | 1886 | 1033 | 233.33 ms | 0.35147 mm / 0.15760° |
| 679 | 1166 | 1767 | 300.00 ms | 0.15121 mm / 0.03177° |
| 822 | 2672 | 261 | 233.33 ms | 0.42257 mm / 0.05113° |

All differences are real nonzero float32 differences; there are no signed-zero differences. Both result packets carry the current sequence in element zero. Before the first differing element they match exactly, while remaining landmarks, vertices, blendshapes, pose and diagnostics can differ. The snapshot's capture timestamp agrees with its nested producer frame; the raw result's diagnostic timestamp is older. Raw landmarks/ROI/fit pose match across the nested snapshot boundaries.

This is evidence of an inconsistent result readback, with a current prefix and stale tail, rather than a numerical-comparison tolerance issue or a failed wearer stillness check. The inspected app has no terminal completion signal before its result read; that ordering gap is repaired below. The installed service's internal writer/readback synchronization was not traced, so its precise internal cause is not claimed. No service or SDK modification was made.

## Repair and verification

`FaceLandmarkerGraph` allocates a lab-only `completedSequence` global. Its final mesh pipeline writes that scalar through a separate `lab_capture_marker` operator after `pack_service_result` and `lab_geometry_snapshot`. The one-frame inference coroutine waits for the matching scalar before calling `readResult`, processing motion, presenting geometry or selecting an export. It still requires the returned packet's sequence to match. Normal sample graph behavior remains as before because its completion predicate is immediately true.

The export comparison remains exact finite float32 equality with only signed-zero equivalence. Real mismatches continue to save rejected packets and stop the run. Freshness, marker separation, immutable frame tags, K/revision and exposure-motion checks remain enabled. The capture candidates and headset controls are unchanged.

- The production reader regression simulates a current header with an old tail while the completion marker is pending. It proves that no packet read occurs until the terminal signal, then accepts the coherent packet. It also verifies stale-sequence retry and bounded cancellation/timeout.
- Shipped JS/Kotlin comparator, snapshot, motion and ROM regressions pass. Production controller/profile/clock regressions pass, including all 84 exports, candidate order, stale/collapsed rejection, natural movement, cancellation and restoration.
- Both apps pass assembleDebug, lintDebug and spotlessCheck; the final build took 27 seconds. APK v2 signature verifies.
- Replacement install and explicit launch pass on `PB311XHGKC220141G`, ROM `Pico/swan/swan:16/BQ2A.260122.002-BP2A.250705.008/20261014024400:userdebug/test-keys`. Installed APK hash matches the host build.
- PID 7711 supplied advancing startup frames 2/12/22, C values/revision 0 and healthy logging. A later status reached frame 347 with healthy logging, no stopped state and IDLE capture. Startup has no face in view, so this establishes streaming and control availability, not face-bearing export success.
- All 245 existing external app files and the private optical calibration hash were preserved. The debug property is unset; no service tracing/readback bypass was enabled. The install lease was released.

## Saved evidence and reproduction

Evidence lives in `artifacts/facelandmarker/registration-lab/full-trial-failures-2026-10-31/`:

- `sessions/2026-10-31T18-10-01.419367Z-a197a4/`: five runs, 18 accepted exports, four full rejected packets and journal.
- `sessions/2026-10-31T18-15-04.644520Z-67ef4b/`: the later camera-freshness failure.
- `ScreenRecording_2026.11.01-02.09.51-AM.mp4`: 1,306,083,173-byte recording, retained on the headset. Its encoded HEVC video is 1920×1080, 10,790 frames and 359.666 seconds. Both MV-HEVC views have not been decoded/analyzed in this follow-up.
- `retrieval.json`: hash parity for all 78 retrieved session files plus the recording, 79 files total. Device clock was November 1 at UTC+08:00; session UTC names and this host's October 31 date are preserved separately.
- `attempt-summary.json`, `analyze_attempts.py`, `native-analysis/`, build/host logs and `install/`: reproducible findings, analysis and installed-build evidence.

From repository root, run `python3 artifacts/facelandmarker/registration-lab/full-trial-failures-2026-10-31/analyze_attempts.py` to reproduce the run inventory, exact packet differences and stale timestamp tails. The native analysis command uses `FaceRegistrationLabApp/tools/registration_lab.py analyze` on the first session. The completion regression is part of `tools/validate_lab_runtime.py`.

## Next wearer action

Use **One check** on the installed repair with a real face about 1 m away and Spatial recording running. Keep the panel visible, allow natural small movement, wait for Capture complete, then stop recording. Preserve its evidence and report completion so the new build's three exports can be inspected before another Full trial. If it fails, keep the partial result; another immediate repeated full attempt is not needed to obtain diagnostics.

Starting, running and storing capture require no PC connection. Fitting/applying a corrected calibration remains unimplemented on the headset. Physical binocular alignment and the winning candidate remain pending. No app-data clear, recording deletion, profile save, service/firmware change, commit or push was made.
