# Face-pose helmet sample

This records the earlier Hornet implementation. The active app now uses the [Sentinel helmet and animated faceplate](SENTINEL_HELMET_2026-11-09.md).

[Process/data-flow visualization and matched latency breakdown](../artifacts/facelandmarker/helmet-dataflow-2026-11-09/index.html) · [Explanation and measurement boundaries](../artifacts/facelandmarker/helmet-dataflow-2026-11-09/FINDINGS.md).

The sample now places one retained Hornet helmet on the detected face and updates its position, orientation and uniform scale from the calibrated face pose. The entry point is `FaceHelmetSample`; both face APKs use it. The registration-lab package retains the frozen Stereo camera calibration and balanced pose smoothing.

The user explicitly requested that this feature not use the face mesh. The renderer never creates `FaceMeshScene`, and the runner selects output mask **1 (pose only)**. It reads **78 floats / 312 bytes** per result, with no face vertices or blendshapes. The existing detector/landmarker graph still computes the measurements required to estimate face pose; this change does not replace that inference graph with a different pose-only model.

## Rendering and controls

- `FaceHelmetScene.kt` loads `asset://helmet/hornet.glb` once. It converts each face-to-Stage pose into the placement owner's local coordinates, then changes the tracked head entity's translation, quaternion and scale. There is no per-frame geometry replacement, coordinate conversion for face vertices, or triangle normal calculation.
- The hierarchy is placement owner → tracked head → fitting transform → authored GLB. Static fitting stays in face-local space and therefore follows yaw, pitch and roll. The loaded visual bounds set a nominal 24 cm width, with a −2 cm local Z fitting offset and a size slider from 80% to 120%. Real-person fit has not been verified.
- The model is Y-up and faces +Z, consistent with the face coordinate frame. `FaceHelmetPose.kt` decomposes the row-major similarity matrix and rejects invalid, reflected or nonuniform transforms. It preserves the measured uniform scale.
- Missing/invalid/no-face output hides the helmet. A 100 ms check also hides the retained model when its last readback is older than 500 ms. Pause hides it; Resume restarts submissions. Reset fit restores the default size; Close exits the Stage.
- The asset is **The Hornet (Military Helmet)** by nip88nip, CC-BY-4.0, reused unchanged from the local SDK sample. Attribution ships in `assets/helmet/NOTICE.txt`. This is a sci-fi helmet, not an Iron Man model.

## Diagnostics and compatibility

The registration-lab package still records its pipeline journal. `helmet_pose_applied` events record visible/hidden state, the face Stage pose and converted parent transform, output mask, zero face vertices and filtering details. Visible updates include `readbackToPoseApplyMs` and `poseApplyMs`; their endpoint is **entity transform setters returning**, not SDK mesh upload acknowledgement or screen presentation. These timings cannot be directly compared with earlier mesh-upload completion numbers.

Remote `status` reports `renderer=helmet`, `helmet`, output selection and payload bytes. Helmet mode accepts only `status` and `outputs` (mask 0 or 1). Existing calibration capture commands are rejected so they cannot enable face-mesh output behind the helmet view. The previous diagnostic UI and mesh renderer remain in source; select `FaceLandmarkerSample()` in `platform/MainApplication.kt` to return to that interface. This replaces the current entry for both APKs, rather than adding a launcher choice.

No service source, saved camera profile or calibration constant was changed. This feature retains the existing ROM's separate GPU-environment relaunch issue; the prepared installation sequence resets only the lab and Spatial service before launch, as previously authorized.

## Validation and delivery boundary

**Installed and runtime-verified on PB311XHGKC220141G after reconnection.** The hash-pinned registration-lab APK is running under app/Spatial PIDs 28257/19959. The captured window has 976 pose-only packets and 974 helmet updates, with one hide/reappearance transition, zero face-mesh uploads, exact Stereo K/D and balanced filtering. Final live status reached frame 2008. Physical helmet overlap and broad head-turn acceptance remain unverified. [Deployment evidence](../artifacts/facelandmarker/helmet-2026-11-09/install-20261110T011055.311273Z/FINDINGS.md).

- Both `FaceLandmarkerApp` and `FaceRegistrationLabApp`: assembleDebug, lintDebug and spotlessCheck pass. Final successful log: [`build-fixed.log`](../artifacts/facelandmarker/helmet-2026-11-09/build-fixed.log). The earlier `build.log` records a resolved nullable-timestamp compilation error.
- `tools/validate_helmet_pose.py`: 99 rotation/scale cases, including all rotation axes, 180-degree turns, invalid inputs and a rotated parent; maximum transformed-point error **1.1921e−7 m**. Pose-only smoothing equals the existing full-output pose result over 181 frames.
- Existing balanced-filter and stereo calibration/output decoder regressions pass. Source placement validation reports no violations. Asset bounds and four-axis preview establish the selected model's orientation; those do not establish face overlap in the headset.
- Build flags remain `faceCompactVstPipeline=true`, `faceFusedControlModels=true`, `faceGpuPreprocessing=true`, default `faceGpuSampleBytes=false`; SDK BOM 6.1.9.
- The managed codegen workflow failed its build stage; the explicit repository Gradle build above is the successful validation. No managed runtime success is claimed.

The APKs, hashes, host test reports and prepared install script are in [`artifacts/facelandmarker/helmet-2026-11-09`](../artifacts/facelandmarker/helmet-2026-11-09). Exact hashes are recorded in [`build-manifest.json`](../artifacts/facelandmarker/helmet-2026-11-09/build-manifest.json):

| Package | APK | SHA-256 |
| --- | --- | --- |
| Registration Lab | `registrationlab-1.0-debug.apk` | `7764cf06ecf8e35f810febc625b2a1ae611b374618077e35c416b0f5191b4d79` |
| Face Landmarker | `facelandmarker-1.0-debug.apk` | `d6462a128b45931b0c863dc308b913d7d5469eefc7ea7977d0dc74ae70b7160d` |

## Reproduce installation

The APK is already installed and running; no repeat install is needed for this result. The successful command, from the repository root:

```sh
python3 artifacts/facelandmarker/helmet-2026-11-09/install_and_verify.py
```

The script checks the pinned APK hash, acquires the serial-specific devmux lease, snapshots private calibration/file and recording inventories, backs up the installed APK, checks for active recording/calibration work and other Spatial clients, replaces the APK, resets the Spatial service and launches. It samples status for 60 seconds, verifies advancing pose-only frames, captures logs/journal and verifies preservation before releasing the lease. Each attempt writes a separate receipt directory. The script completed successfully after reconnection. All 1136 pre-existing app files and 55 recording files were preserved; private calibration hashes match. The installed service APK and debug property were preserved, and the lease was released.

A real face must be in view to verify the retained helmet updates. Check front, left/right yaw, up/down pitch, roll, near/far movement, disappearance and reappearance, then Pause/Resume and size/reset controls. Verify that the visor faces the same direction as the person's face and that it remains attached during head turns. Journal transform updates prove app-side behavior; visual overlap and actual presentation latency require headset observation or a suitable recording. Do not claim a tracking performance improvement until there is a new comparable runtime capture.
