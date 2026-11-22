# Spatial screen recording verified on Swan

The headset's **Spatial** screen recording mode records two distinct eye views containing passthrough and the app's rendered face mesh. This resolves the previously unverified stereo capture route in [AUTOCALIBRATION_PLAN.md](AUTOCALIBRATION_PLAN.md). Automatic fitting remains unimplemented, and correct physical mesh alignment is not established by this capture test.

## Recording and extraction

- Original: `ScreenRecording_2026.10.30-08.22.40-AM.mp4`, 188,735,586 bytes, about 49.765 seconds. The filename uses the headset's CST clock; this is October 29 on the development machine in Los Angeles.
- Device: `PB311XHGKC220141G`, fingerprint `Pico/swan/swan:16/BQ2A.260122.002-BP2A.250705.008/20261014024400:userdebug/test-keys`.
- SHA-256: `f3d7a5215df6a7d7d5990663f5be3e9dc2cb5cd32c4c88a5d861d5d3185bd89a`. Remote and local sizes and hashes match. The headset copy was retained.
- Container: one AAC audio track and one **MV-HEVC video track**. Both eye views are encoded in that video track; two video tracks or an already side-by-side image are not required.
- Each decoded view is **1920×1080**, approximately **30 fps**. Video has 1,493 presentation samples. The decoder is explicitly configured with `view_ids=-1` to output both views.
- HEVC layer/view IDs are 0 and 1. Frame side data labels view 0 **left** and view 1 **right**. Paired samples have equal presentation timestamps. This establishes synchronization in the recorded stream, not independently measured sensor/display latency.

All outputs are under [`latest-spatial-recording-2026-10-30`](../artifacts/facelandmarker/registration-lab/latest-spatial-recording-2026-10-30/). Start with:

- [Original spatial MP4](../artifacts/facelandmarker/registration-lab/latest-spatial-recording-2026-10-30/ScreenRecording_2026.10.30-08.22.40-AM.mp4).
- [Ordinary side-by-side preview](../artifacts/facelandmarker/registration-lab/latest-spatial-recording-2026-10-30/stereo-side-by-side-preview.mp4): H.264, left eye on the left, right eye on the right, 1920×540 combined, silent. The original retains full per-eye resolution and audio.
- [Face comparison at about 37 seconds](../artifacts/facelandmarker/registration-lab/latest-spatial-recording-2026-10-30/face-stereo-comparison.jpg) and [full contact sheet](../artifacts/facelandmarker/registration-lab/latest-spatial-recording-2026-10-30/stereo-contact-sheet.jpg).
- `recording-retrieval.json`, `video-metadata.json`, `hevc-layer-inspection.json`, `decoded-views.json`, and `stereo-verification.json` contain transfer, codec and decode evidence. `decode_preview.py` reproduces the preview using PyAV 19.0.2 and NumPy 2.5.3.

## Visual result

The paired views show different perspectives of the real room, face and virtual UI. The later portion also includes the green wireframe face mesh in both views, clearly visible in the sampled frames around 37 and 42 seconds. This is a composited recording of real and virtual content, unlike the earlier ordinary adb recording with a black background.

The beginning includes time spent waiting for Full Space head tracking. Do not treat those no-mesh frames as tracking-success or alignment samples. The dense wireframe also obscures some real landmarks; the planned sparse-marker and clean-view phases remain useful for reliable automated scoring.

A normal player or a default decoder can show only the base eye and make this file appear monoscopic. Inspect the multiview bitstream or explicitly decode all views; dimensions and track count alone are insufficient.

## Additional metadata and limits

FFmpeg exposes `VIEW_ID`, `STEREO3D`, `SPHERICAL` and `THREE_D_REFERENCE_DISPLAYS` side data. The stereo descriptor reports a **64,000 micrometre (64 mm) baseline**, **77.899° horizontal field of view**, and zero horizontal disparity adjustment. The saved FFmpeg `stereo3d.h` documents the field layout used to interpret the raw side data.

These are encoded recording/viewing parameters. Their exact relationship to the compositor view, any crop/remapping and the actual headset eye poses has not been independently verified. Do not substitute the recording FOV for the SpatialML source camera intrinsics or assume the metadata baseline is a measured optical-camera baseline. The source camera, recorded eye views and Stage projection are different coordinate/calibration contracts.

The recording lets an analyzer compare real-face and mesh landmarks independently in both views and detect disagreement in their stereo disparity. That is stronger evidence about the inside/outside error than a single view. Turning it into trustworthy metric depth still requires correct projection/baseline interpretation and reliable landmark correspondence. This test neither determines the best fx/fy/cx/cy nor proves correct registration.

Use **Spatial** mode for future calibration recordings. Preserve its FOV/aspect settings throughout a trial. No additional recording is needed merely to prove that stereo capture works; the next capture should exercise the automatic marker/sweep instrumentation once implemented.
