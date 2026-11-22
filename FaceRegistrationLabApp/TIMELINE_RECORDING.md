# Match Spatial recordings to the app timeline

The calibration app shows a timing/status badge plus **One check** and **Full trial** start buttons in the headset. Recording starts/stops with the headset system recorder, and capture runs without USB. [AUTOMATIC_CAPTURE_STEPS.md](AUTOMATIC_CAPTURE_STEPS.md) is the current wearer flow. The previous manual tuning/preview/menu controls remain removed; desktop/adb diagnostics are optional. The normal face sample keeps its own controls.

The badge looks like this:

```text
SYNC 722814 #000080
UI 7.157 s | CAM 6.884 s
F9 K0 M4 | MESH
```

- `SYNC` identifies the session; the six-character suffix matches the end of its saved directory name.
- `#` is a unique tick ID within that session. It is the key to the corresponding `ui_tick` journal row.
- `UI` is the time when the app generated this badge state, in seconds since session start.
- `CAM` is the camera exposure timestamp associated with the last completed scene update, in the same session-relative seconds.
- `F` is that scene update's camera/inference sequence; `K` is its calibration revision; `M` is its mode (`4` is Custom).
- `MESH`, `HIDDEN`, `NO FACE` or `NO MESH` describes the associated scene state. `LOG ERROR` means the journal could not accept or write data; do not use that interval as a complete saved timeline.

The clock refreshes approximately every 100 ms and immediately after scene/visibility updates. Frame and calibration metadata travel with the immutable frame through Stage conversion, so a newer requested desktop value cannot relabel an older uploaded mesh. A repeating camera time is expected while the same mesh remains displayed.

## Record and retrieve

Open **SpatialML Face Calibration** and use the headset recorder's **Spatial** mode, which has been verified to capture both eye views with passthrough and mesh. Keep the badge visible in the recording. No manual tuning on the headset is needed. Use the system back/home action to leave the app.

The timeline is written automatically to:

```text
/sdcard/Android/data/com.pico.spatial.ml.sample.facelandmarker.registrationlab/files/
  RegistrationLab/<session>/timeline.jsonl
```

It works with USB disconnected. Each row is flushed by an IO worker; queued rows drain on normal app disposal. An abrupt process/device shutdown can leave the final row missing or incomplete. Existing profile and diagnostic-capture files remain separate and are preserved.

The existing `tools/registration_lab_device.sh pull` retrieves the session directory, including the journal. The ordered `status` command also exposes a `timeline` object with the full session name, monotonic origin, latest tick, scene metadata and logging health. Diagnostic `sample.json` files include this reference alongside their own capture sequence/timestamp; the reference is a snapshot at export time, not an assertion that the exported sample was displayed at that exact tick.

## Align on the computer

1. Decode both views of the MV-HEVC recording, preserving video presentation timestamps. The working extraction method is documented in [STEREO_RECORDING_FINDINGS.md](STEREO_RECORDING_FINDINGS.md).
2. Read several clear `SYNC`/tick labels distributed through the clip. Locate their `ui_tick` rows in the matching session journal.
3. Pair each video timestamp with that row's `relativeSeconds`. Estimate the offset, and check drift over longer clips before fitting a clock scale. Keep residuals and uncertainty.
4. Use the row's `mesh` fields to identify the sequence, effective intrinsics, calibration revision, camera time and scene upload-completion time. Inspect stable intervals and reject transitions, tracking loss and logging errors.

The journal header's `originNanos` comes from `System.nanoTime()`. Reconstruct an absolute monotonic time with `originNanos × 1e-9 + relativeSeconds`. Camera exposure/readback times use the same monotonic timeline assumed and checked by the existing capture-age logic. `utcAtStart` is a human-readable reference; do not use wall-clock time to infer camera/display latency.

## Precision and remaining work

The printed milliseconds are formatting precision. They do not establish millisecond display synchronization. The UI stamp records state generation, and the mesh stamp records completion of the SDK resource update; neither is a compositor-present or photon timestamp. Compose and mesh presentation are separate asynchronous paths. A badge first appearing in a video frame includes those presentation delays.

The ordinary 100 ms update cadence gives a useful timeline anchor; stable repeated samples and recorded tick transitions let the analyzer estimate uncertainty. Exact display latency still requires platform timing support. HMD poses retain the existing callback-arrival timing limitation.

Sparse facial markers, clean/marked capture phases and automatic parameter sweeps are implemented. The video fitter remains unimplemented. The new badge and journal provide the timing association needed for that work; they do not automatically save source images or full geometry for every tick.

Implementation: `LabTimeline.kt`, `LabTimelineBadge.kt`, frame metadata in `FaceLandmarkerRunner.kt`, scene-completion publication in `FaceLandmarkerSample.kt`, and session/status/export references in `FaceRegistrationLab.kt`.
