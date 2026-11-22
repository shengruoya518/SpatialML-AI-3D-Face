# Headset one-check recording — 2026-10-31 headset date

The subsequent check `b2b8c9a3` completed all three exports with exact packet matches and distinct markers. Its current findings and Full trial instructions are in [PACKET_CHECK_FINDINGS_2026-10-31.md](PACKET_CHECK_FINDINGS_2026-10-31.md). The failed recording below remains historical evidence; its mismatch cause is still unconfirmed.

The headset button starts the sequence and the relaxed capture window works, but this run did not complete. Run `5474a68b` reached CLEAN_BEFORE, then rejected its first export because the native geometry snapshot did not compare equal to the displayed packet. It saved **zero accepted exports** and never reached MARKED. The recording is useful for diagnosing the flow, but it cannot validate marker placement or the full calibration sweep.

## Retrieved evidence

- Headset: PB311XHGKC220141G, app `com.pico.spatial.ml.sample.facelandmarker.registrationlab`.
- Recorded build: SHA-256 `68ac56e426c560d8a944d159139bb695e3c0b6ce93dec8c904a7dcf7c3b41a0e`.
- Session: `2026-10-30T18-48-59.259613Z-3a538e`; original journal retained on the headset.
- Video: `ScreenRecording_2026.10.31-03.04.14-AM.mp4`, 142,605,981 bytes, SHA-256 `634000ca39fede406f0a9a41720570e033d6b604be8764e495e1be624c2ad4e3`. Host and device hashes match; original remains on the headset.
- Stereo decode: 1,626 equal-PTS pairs, 1920×1080 per eye, view 0 left/view 1 right, last PTS 54.7993 seconds. A silent side-by-side preview and sampled frames preserve both views.
- Evidence directory: `artifacts/facelandmarker/registration-lab/headset-check-2026-10-31/`, including retrieval/status/journal, stereo verification, preview, contact sheets and `run-summary.json`.

## What the check establishes

| Phase | App-relative start | Duration | Completed / face frames | Stable-exposure frames |
| --- | ---: | ---: | ---: | ---: |
| COUNTDOWN | 922.897 s | 15.024 s | 35 / 35 | 35 |
| POSE | 937.921 s | 8.067 s | 19 / 19 | 19 |
| SETTLE | 945.988 s | **1.032 s** | 3 / 3 | 3 |
| CLEAN_BEFORE | 947.020 s | 3.970 s | 6 / 6 | 6 |
| FAILED | 950.991 s | — | — | — |

The previous clock poisoning is absent. In SETTLE all three fresh face frames pass, and the hold advances within about one second. Repeated-exposure face frames are rejected separately rather than poisoning later sensor captures. All six first-clear-phase frames pass the recorded ±50 ms HMD exposure-motion check. Submission-to-readback median over the pose/settle/first-clear sample is approximately 405 ms; this is not a per-component benchmark or a controlled optimization result.

The video shows the headset controls and real face in both views. The sequence starts from the headset and clears the ordinary mesh during capture. The later failure returns to the ordinary mesh. No eight-marker phase or calibration candidate sweep was recorded. There are no source/geometry exports from this automatic run, so numerical calibration and a new marker/anatomy residual cannot be accepted.

## Snapshot comparison investigation

The failed build compares all 2,994 float values with Kotlin `FloatArray.contentEquals`. This treats positive and negative zero as different even though they have the same geometric value. The failed run did not save the two rejected packets, so **signed zero is a possible false-rejection mechanism, not the confirmed cause of this failure**.

A separate manual background diagnostic capture (`diagnostic/capture-session/001-mode4-step5`) was collected without requiring another wearer recording. Its packets match numerically and bit-for-bit, with no face present. This proves the readback/packing path can be coherent in that population; it does not establish face-bearing packet consistency. Its step/configuration were restored, and it is excluded from automatic-run/calibration acceptance.

Current local JNI source duplicates the snapshot FD and sends `ackReadbackTensorContent` before returning it. The missing-ack hypothesis is therefore unsupported by this source path; no SDK/service modification was made. Source correspondence to the installed binary was not independently established.

## Bounded update and next check

`LabGeometryProbe.resultMatches` now compares finite float32 bit patterns exactly except for the sign of zero. It accepts +0/−0 equivalence and rejects every nonzero difference, including the smallest subnormal, plus NaN/infinity and length changes. There is no numerical tolerance or geometric correction.

Every automatic export records comparison details. On a real mismatch the app still rejects the export, but first saves the existing raw packet and full native geometry snapshot in `RegistrationLab/<session>/RejectedCaptures/<run>-frame<sequence>.json`, including mismatch indices, values and original float bits. A matching journal event names the rejected file. This lets the next failure be diagnosed without guessing or another instrumentation cycle. Headset status asks for One check again; no PC-connection prompt is added.

Host fixtures exercise shipped JS packing and the actual Kotlin decoder/comparator, including signed-zero equivalence and rejection of real changes, subnormals, wrong lengths and NaN. Both apps pass build/lint/format; signature verification passes. The update is a packet-comparison/diagnostic change, not a claim that the unobserved root cause is fixed.

At the time of this update, the next step was One check with a real face in view, without another video for the packet diagnostic. That follow-up has now passed; see the linked findings above. The earlier recording remains retained for physical alignment analysis, and this failed run remains excluded from calibration acceptance.


## Installed diagnostic update

APK SHA-256 `26b7b626ad0b5281b5b0cb7d3db2e1f0f3428ee6cc00c2aa52170cbcbe902e60` was verified installed on PB311XHGKC220141G and matched the host build. PID 15796 supplied advancing frames 8/16/23, effective C values and healthy logging. All 151 existing external app files and the private camera calibration were preserved; no profile was saved and no recording was deleted. The devmux lease was released. The shared headset controls and device-only prompts remain unchanged. The requested face-bearing packet follow-up has since passed; full-sweep and physical marker acceptance remain pending.
