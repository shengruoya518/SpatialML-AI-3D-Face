# Face calibration: recording and optional desktop tuning

## Current control surface

**The headset now shows only a timing badge.** All manual headset calibration, capture and preview controls have been removed. No manual adjustment is required for recording. Use [TIMELINE_RECORDING.md](TIMELINE_RECORDING.md) for the current recording and time-matching procedure.

Open **SpatialML Face Calibration**, start the headset recorder in **Spatial** mode, and keep the badge visible. Timing journals save automatically, including with USB disconnected. Existing saved calibration values load on launch. Automatic parameter sweeps and video fitting are still to be implemented; this update does not ask you to repeat the earlier manual calibration procedure.

The badge-only build is installed on PB311XHGKC220141G. Startup, positive face detection, visible-mesh journal entries and the badge-to-journal match are verified. [VALIDATION.md](VALIDATION.md) records the artifact and verification limits.

## Optional desktop tuning reference

The browser at **http://127.0.0.1:47835** remains available for computer-driven adjustments over adb. See [DESKTOP_CALIBRATION.md](DESKTOP_CALIBRATION.md) for startup, controls and connection behavior. Desktop commands require the headset connection; disconnected operation uses the current values and records the timeline.

Starting values, rounded for display:

| Value | Mode C starting point | What it controls |
|---|---:|---|
| fx | 1746.47 px | Horizontal focal length |
| fy | 1746.47 px | Vertical focal length |
| cx | 1623.50 px | Horizontal principal point |
| cy | 1231.50 px | Vertical principal point |

These are pixels in the 3248×2464 virtual image used for reconstruction. The image transform stays fixed to Mode C. The app applies these values directly as the geometry camera matrix.

## Refine the small/high residual

Change one aspect at a time and compare nose, eye line, chin and both cheeks. Avoid trying to correct a brief tracking error by changing the calibration.

1. **Size and depth:** try reducing fx and fy by the same small amount, for example 25 px each. Reducing both focal lengths moved the reconstructed face closer in the earlier host sensitivity check. Compare the result with the starting values and undo it if it is worse. Focal changes also affect inferred geometry; they are not a pure mesh scale control. Adjust fx or fy separately only when horizontal and vertical fit need different changes.
2. **Vertical placement:** try decreasing cy in 5 px steps. A smaller cy moved the reconstructed face down in the earlier sensitivity check. Refine with 0.5 px steps if helpful.
3. **Horizontal placement:** if needed, change cx in small steps. At a fixed positive depth, increasing cx moves the reconstructed camera-space points left; decreasing it moves them right. Check the actual overlay after each edit.
4. Recheck the best settings at approximately 2 m, with the face turned a little left and right, and with each eye separately while stationary. Prefer values that work across these views. The earlier C residual was similar in both eyes; a new difference between eyes is useful evidence to record.

These directions are controlled experiments, not measured correction constants. If one set of values cannot fit near/far or both eyes, record that result. Camera intrinsics alone may not account for the remaining registration error.

## Save and restore from the desktop

Use **Save on headset** in the browser to preserve working values and wait for **Calibration saved on this headset.** Saving is independent of face/camera readiness. It creates an archived JSON profile and updates the profile loaded on the next launch.

- **Load saved** restores the last saved values into Custom.
- **Reset to C** restores the original C starting values without overwriting the saved profile.
- Edits alone do not overwrite the saved profile. Each save retains a separate timestamped archive.
- Numeric profiles, diagnostic image/geometry samples and the automatic timeline journal are separate outputs. The timeline does not automatically export source RGB or full geometry for each frame.
- Profiles are checked against the ROM and image geometry. An incompatible or damaged profile falls back to C.

These controls belong to the separate calibration app. The normal face sample retains its service camera calibration. The existing adb capture commands remain available for agent-controlled diagnostic exports; the removed headset capture panel is no longer part of the procedure.

## Retrieve later

Reconnect USB and run from the project root:

```sh
bash FaceRegistrationLabApp/tools/registration_lab_device.sh profiles
bash FaceRegistrationLabApp/tools/registration_lab_device.sh pull
```

The first command copies profiles to `artifacts/facelandmarker/registration-lab/profiles/RegistrationLabProfiles/`. The second copies camera/mesh samples to `artifacts/facelandmarker/registration-lab/captures/RegistrationLab/`. Both preserve files on the headset. System screen recordings are stored separately by the headset and can be retrieved when it is reconnected.

On-device exported profiles are under:

```text
/sdcard/Android/data/com.pico.spatial.ml.sample.facelandmarker.registrationlab/files/RegistrationLabProfiles/
    saved-calibration.json
    calibration-<UTC timestamp>-<id>.json
```

The automatic-load copy is in app-private storage, `files/face-intrinsics-calibration-v1.json`. Normal replacement installation preserves it. Clearing app data or uninstalling removes app-owned profiles, so use replacement installation for subsequent builds.

## Build and runtime boundary

APK: `FaceRegistrationLabApp/build/outputs/apk/debug/registrationlab-1.0-debug.apk`.

Build and installed-device evidence are in [VALIDATION.md](VALIDATION.md). Android profile persistence across launches and physical mesh alignment remain separate acceptance checks. Existing forced-restart and intermittent camera/capture limitations remain open. Use a normal app launch and keep the session open while recording; repeated forced restarts have previously left the ROM camera service unavailable.
