# Automatic face alignment: feasibility and capture plan

Status: automatic candidate trials, eight Stage markers, clean/marked/clean phases, pose prompts and tagged source/geometry exports are implemented and host-tested. The new APK is installed. Camera startup, countdown/cancel, live desktop controls and panel layout pass; one real-face recorded sample remains pending. The video fitter and an accepted correction remain **unimplemented**. Start with [AUTOMATIC_CAPTURE_STEPS.md](AUTOMATIC_CAPTURE_STEPS.md).

**Stereo capture is now verified:** the returned Spatial recording contains MV-HEVC left/right views with passthrough and mesh. Read [STEREO_RECORDING_FINDINGS.md](STEREO_RECORDING_FINDINGS.md) for extracted views, preview and metadata. This supersedes the earlier uncertainty about a usable stereo recording route.

We can build a mostly automatic calibration around Mode C: collect the lab's source images and geometry, record the real face and rendered markers together, and choose the settings that minimize their visible separation across several poses. The wearer would start the headset system recorder and follow pose prompts; the app/desktop would handle candidate values, sample capture, scoring and a proposed profile. This measures effective mesh registration in the recorded view. Faces and a single recording viewpoint do not uniquely determine physical camera intrinsics, camera-to-head extrinsics and true face depth.

## Verified capture boundary

| Path | Evidence | Use |
| --- | --- | --- |
| Lab source images and geometry | Existing `FaceRegistrationLab.save()` exports half-resolution source RGB, model inputs, landmarks, effective K, camera/head transforms and Stage vertices, with configuration revision and frame metadata. | Sampled diagnostic input and geometry; continuous synchronized VST video export is not implemented. |
| Headset system recorder | Previously recovered `ScreenRecording_2026.10.29-09.42.04-AM.mp4` contains the passthrough face and rendered mesh, 2560×1440, about 175 seconds. | Proven path for visible alignment. Start/stop from the headset for the proposed first version. Its exact eye or spectator-view geometry has not been established. |
| Headset Spatial recorder | New `ScreenRecording_2026.10.30-08.22.40-AM.mp4` decodes as two 1920×1080 MV-HEVC views, with left/right tags and matching timestamps; both include passthrough and mesh. | Verified stereo recording route. Recorded projection metadata still needs interpretation before metric depth fitting. |
| Automated `pico-cli capture record` | New nominal five-second test saved 4160×2176 video, 360 frames, reported average 76.335 FPS. Inspection shows mostly black background with stereo/rotated UI and no usable VST scene. | Not usable for fitting in this test. Command success alone does not establish capture of passthrough. |
| PICO Developer Center record/cast | Local SDK 6.0 Unity documentation describes Record Screen and LAN screencast, with an **Allow** prompt on the headset for casting. Current CLI capture help exposes record/screenshot. No PDC installation was located under the searched Applications paths. | Candidate future remote route; VST inclusion and Swan/OS6 support have not been verified. Do not depend on it for the first implementation. |
| SystemUI capture service | Installed manifest exposes `ScreenCaptureService` with signature-protected capture permissions. | Manifest entries do not establish a callable public recording API. No private action or permission bypass was used. |

Follow-up stereo investigation: resources read from the connected headset's installed `/system/priv-app/SpatialSystemUI/SpatialSystemUI.apk` expose **Screen Capture → View Recording Mode → Monoscopic / Spatial**. They also expose **Monoscopic View Source → Left Eye / Right Eye**, **Capture Field of View → Standard / Wide**, and aspect-ratio choices. See `recorder-resource-options.txt` in the evidence directory. This is stronger evidence of a system stereo recording candidate than the earlier public documentation, but resource labels alone do not establish that the mode is enabled or that its output includes both VST and mesh. No device setting was changed.

The short Spatial capture check has now succeeded. Both views are encoded in a single MV-HEVC track and require explicit multiview decoding; a default player can display just the base eye. Use **Spatial** for subsequent calibration recordings and keep recording FOV/aspect settings consistent across trials. No further capture is needed merely to prove stereo recording support.

Evidence is in [`autocalibration-feasibility`](../artifacts/facelandmarker/registration-lab/autocalibration-feasibility/): `adb-compositor-test.mp4`, `recording-metadata.json`, `contact-sheet.jpg`, sampled frames and `systemui-package.txt`. The successful prior recording is under [`latest-recording-2026-10-29`](../artifacts/facelandmarker/registration-lab/latest-recording-2026-10-29/).

Documentation checked: local SDK `documentation/Capture, record, and cast screen.md` and `documentation/Mixed Reality Capture.md`. The latter describes a Unity third-person camera/phone workflow, not an established Kotlin first-person VST capture API. Documentation for SDK 6.0 is not proof of behavior on this app's SDK 6.1.9 and current Swan ROM.

The first returned badge capture is analyzed in [TIMED_STEREO_CAPTURE_FINDINGS.md](TIMED_STEREO_CAPTURE_FINDINGS.md). It verifies video-to-journal association and unchanged C values across face positions/rotations. Median positive camera age at UI generation is 0.902 s, with only about 2.1 scene updates/s. The sequence must therefore gate on fresh advancing exposures and use settled holds; moving samples cannot be treated as static calibration correspondences.

## Capture measurements and remaining analysis

Use short **clean / marked / clean** intervals for each accepted sample. Hide the solid face surface; render sparse identifiable markers at known mesh vertices during the marked interval. Eye corners, nose and mouth corners are useful initial anchors. Jaw/outline points are secondary because their visible contour changes with yaw. Reject occluded landmarks instead of matching them to a different visible edge.

The clean intervals let a local face-landmark detector locate the real face without following the synthetic mesh. The marked interval lets the analyzer find rendered marker centers by their appearance and IDs. Check face motion between the two clean intervals; reject a moved/blinking/expressive sample rather than treating temporal error as calibration error. Using the same face-model family in the analyzer remains a source of shared landmark bias, so retain visual overlays and spot checks.

Each sample needs:

- Session/sample ID, candidate ID, actual calibration revision, effective `fx/fy/cx/cy`, fixed image affine, camera sequence and timestamp.
- Source RGB/model crop and model landmarks, matching producer/fit/mesh snapshots, final Stage vertices, optical camera-to-head transform, capture-time head pose and motion history.
- An acknowledged scene-upload ID, the actual uploaded marker positions, and a large machine-readable sample/phase tag visible in the video outside the face region.
- Video presentation timestamps, image dimensions/crop/orientation, marker detections, real-face detections, visibility/confidence and reasons for exclusions.

The timing journal now records `scene_update_complete` after the SDK mesh update returns, with the exact frame's configuration and camera/readback times. This is an upload-completion boundary, not a renderer-present acknowledgement. The automatic update adds immutable sample/phase tags and exact Stage marker positions to scene/export journal events. Clean phases hold for at least two seconds after a matching scene update; marked phases hold for at least three seconds. Actual video visibility still needs inspection. A tag alone does not prove exact display synchronization; reject transitions. Preserve the current timestamp limitation: HMD history uses callback-arrival time, not a public hardware timestamp.

Export only selected stable samples initially. Large RGB readbacks affect the camera pipeline; do not assume continuous full-rate exports are safe. Reject stale camera frames, missing head history, mismatching actual K/revision, non-finite or inconsistent native geometry, incomplete sample/video associations and excessive motion. Stop a failed sweep and retain evidence rather than saving a fitted profile from invalid data.

## First fitting pass

Keep the C image affine fixed. Custom K is already in virtual-image pixels and must not be multiplied by that affine again. Start with two parameters:

```text
fx = fy = 1746.4713134765625 × s
cx = 1623.5
cy = 1231.5 + deltaCy
```

Fit a shared focal multiplier `s` and a vertical principal-point correction `deltaCy`. The symmetric small/inward observation motivates this starting model; it does not prove that these are the only errors. Do not introduce a left/right offset from the earlier observation that the wearer subsequently corrected.

An initial bounded experiment can bracket C with `s = 0.96, 0.98, 1.00, 1.02`, then test `deltaCy = -40, -20, 0, +20` around the best focal candidate. Refine locally and retest their combination because depth and height are coupled. These are proposed search points, not accepted calibration values. Repeat C between groups and vary candidate order to detect tracking or subject drift. A best result at a search boundary calls for reassessment, not automatic acceptance.

The candidate should be assessed through the real rendering path. For candidate `theta`, visible landmark `i`, and stable sample `j`, score:

```text
residual[j,i] = rendered_marker_pixel[j,i] - real_face_pixel[j,i]
score(theta) = pose-balanced robust average of residual lengths / face pixel width
```

Also report raw pixel errors, signed horizontal/vertical offsets, marker-span ratios, per-landmark residuals and repeated-sample spread. Balance pose/distance groups so a long frontal segment cannot overwhelm a bad turned view. Aggregate only visible, confidently associated landmarks. Derive confidence from repeated captures; video compression, detector noise and motion put a floor on meaningful improvements.

Without verified per-eye projection matrices, a host geometry replay cannot faithfully predict arbitrary unseen compositor views. Use actual recorded candidate trials for the first fitter. Host replay remains useful for geometry checks and sensitivity estimates, as in [OBSERVATION_GUIDED_REFINEMENT.md](OBSERVATION_GUIDED_REFINEMENT.md).

If the two-parameter model leaves a clear residual, expand one hypothesis at a time. Consider independent fx/fy only for a consistent aspect error, cx only for a consistent horizontal error, and extrinsics or face-shape parameters only with additional evidence. The existing `sizeScale` scales distance and geometry around the optical center, so it cannot independently enlarge the face at fixed depth. Avoid fitting all intrinsics, face scale, extrinsics and latency together from monocular face footage.

## Later fitting and validation session

The following is the broader fitting plan, not the immediate capture request. First inspect the one-sample check described in [AUTOMATIC_CAPTURE_STEPS.md](AUTOMATIC_CAPTURE_STEPS.md). The implemented sweep covers four prompted poses and seven fixed candidates; off-center and held-out validation remain later work.

1. Start the built-in headset screen recorder. Open the desktop calibration page and start the automatic sequence. Keep one real, neutral-expression face visible in steady light.
2. Hold a frontal face at roughly 1 m while the app cycles candidate settings and captures accepted stable intervals. The app should signal when to move; no manual parameter adjustment is required.
3. Repeat with the **subject's face** turned roughly 25–35° left, then right, with the headset stationary during each interval.
4. Repeat a frontal face at roughly 2 m, then a few off-center positions. These are coverage targets, not known metric ground truth; record measured distances separately if available.
5. Reserve fresh captures for validation, ideally including a second person. Repeat the winning candidate and C at near/far and both turn directions. Between stable captures, move the headset slightly sideways around a stationary face to expose parallax errors; do not fit static calibration from moving frames.
6. Check the final shaded mesh through each eye in the headset, then stop the recording. The analyzer should output a candidate profile, C-versus-candidate overlays, per-pose scores and uncertainty before the profile becomes the saved default.

Closing an eye helps the wearer compare views but does **not** change the eye/view encoded by the system recorder. Use the now-verified Spatial recording to score both views separately and inspect real-face versus mesh disparity. The current app still does not export public per-eye render matrices, and the recording metadata has not been independently validated for metric depth recovery.

A live 3D face is appropriate for the depth test. A face on a flat screen can check detection/image mapping but cannot validate a three-dimensional face surface. Multiple real people help distinguish device-wide registration error from a particular person's mismatch with the canonical face model. Known-size targets remain the stronger input for physical camera calibration.

## Implementation and acceptance

Extend the existing lab and desktop bridge with a bounded sweep controller, a renderer-linked marker/sample phase, and a host video analyzer. Reuse the existing ordered command/readback and profile storage. Preserve Full Space Mixed, Stage style 1, the 0×0×0 SpatialML container, app-owned Stage geometry and the separate diagnostic package. Keep existing captures and saved profiles. No service/firmware change is required by this design.

Before requesting another full wearer session, verify one recorded clean/marked/clean sample end to end: readable tag, correctly associated actual K and uploaded geometry, source export, face and marker detections, and a reviewable overlay. Then validate parameter recovery using synthetic perturbations, exercise invalid/stale data rejection, and run the bounded sequence on device without replacing the saved profile.

Accept a candidate only if its improvement over C exceeds repeat noise on independent captures, remains useful across near/far/yaw/off-center groups, and the wearer confirms depth in both eyes. Describe it as an **effective registration profile** until independent physical calibration supports a stronger claim. If visual overlap improves but the mesh still sits inside the face, retain that failure explicitly and investigate depth/shape or camera-to-eye registration rather than declaring calibration complete.

Current outcome: the automatic-capture APK is installed and passes host/browser checks plus camera startup, countdown/cancel, live desktop and panel-layout checks. Real-face marker/export and full-sequence validation remain pending. Marker phases and automatic sweeps are implemented; the video fitter remains to be implemented. No corrected calibration values or physical stereo alignment have been established. See [VALIDATION.md](VALIDATION.md) for the installed artifact and observed timing/face evidence.
