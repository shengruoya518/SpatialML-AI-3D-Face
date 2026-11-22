# Face Landmarker recording and Stage registration

Analyzed the recording requested by the wearer on host date 2026-10-27, from B3110
`PB311XHGKC220141G`. Its headset-local filename is
`ScreenRecording_2026.10.28-02.12.49-PM.mp4`. The headset clock reported 2026-10-28 CST;
file selection used the newest finalized recording on that device.

## Video observations

- Retrieved all **32,640,586 bytes**, **2560×1440**, about **30.00 fps**,
  **594 frames**, **19.80 seconds**.
- Recording SHA-256: `72ee5f32cb1696ea8343438b5fb597415e4eea41fa1c84308a93ab2b6ec86b4e`.
- A face image is visible on the monitor. The green mesh remains down and to the right of it
  through the first roughly 13 seconds, including the small headset viewpoint changes.
- At 2.5 s, the manually measured face region is approximately `[708,512,192,282]` in
  recording pixels. The green material mask gives mesh bounds `[1316,1239,98,131]` and centroid
  `(1357.74,1314.97)`. Relative to the face-region center `(804,653)`, that is approximately
  **554 px right and 662 px down**. The face region is a manual measurement, not an automatic
  accuracy result. This 2D recording does not independently establish a metric distance.
- The green mesh also has a different orientation/profile from the monitor face, consistent with
  a missing origin/rotation registration. Its projected silhouette is substantially smaller.
  The video alone cannot determine whether residual size is inferred depth or camera calibration.
- The control panel is along the left edge of the recorded view. Passthrough is visible;
  the earlier black-surround mode problem is absent from this recording.
- System menus appear after roughly 14 seconds. They are not part of the app UI.
- App log entries during the recording report `visible=true`, `acquire=false`, `presence=1.0`
  at sequences 12000 and 12100. Thus inference continued to detect a face during the bad placement.

Artifacts are under the ignored `../artifacts/facelandmarker/alignment/` directory:

- [Original MP4](../artifacts/facelandmarker/alignment/ScreenRecording_2026.10.28-02.12.49-PM.mp4)
- [Twelve-frame overview](../artifacts/facelandmarker/alignment/contact-sheet.jpg)
- [Annotated 2.5-second frame](../artifacts/facelandmarker/alignment/offset-annotated.jpg)
- `video-metadata.json`, `image-offset.json`, `before.log`, and `after.log`

## Source-backed diagnosis

The first port treated `CameraSpaceToWorld` output as app Stage coordinates. The service's
`Rendering/include/OpenXROptions.h` defaults to `AppSpace="Local"`, and
`OpenXrProgram::GetXrCam2WorldTransform` calls `xrLocateSpace(view, appSpace, captureTime)`.
`Operator_Cam2World` then applies the optical-camera extrinsics. These are **service OpenXR
Local coordinates**, whose origin differs from the app Stage origin.

The missing transform affects translation and orientation. It explains why converting the
already packed vertices into the mesh Entity's parent space did not correct their physical
placement: that conversion assumed the input was already in the Stage.

The corrected chain is:

```text
C_service = H_service * E_leftCameraToHead
T_serviceToStage = H_stage(capture) * E_leftCameraToHead * inverse(C_service)
stageVertex = T_serviceToStage * serviceVertex
stageFacePose = T_serviceToStage * serviceFacePose
```

`H_stage(capture)` comes from an app-side history of Stage HMD tracking callbacks. `C_service`
is published with the same completed SpatialML frame. `E_leftCameraToHead` uses device calibration
queried through PXRCapture's metadata API and the same IMU-to-head conversion as the deployed
OpenMR source. This preserves optical calibration while canceling the unrelated service origin.
There is no manually tuned meter-scale positional correction or Unity handedness conversion.

The metadata query does not open a camera or start a stream. The B3110 matrix observed on-device is:

```text
[ 0.9999972,  0.00046855,  0.00230804, -0.02649026 ]
[-0.0004530,  0.99997723, -0.00673480,  0.04333694 ]
[-0.0023111,  0.00673373,  0.99997467, -0.04793124 ]
[ 0,          0,          0,           1           ]
```

The tracking history records callback arrival on the monotonic clock because Kotlin SDK 6.1.9
keeps the tracking sensor timestamp internal. Capture interpolation uses bounded history;
missing, old, or gapped samples hide the mesh. This is a small timing approximation requiring
motion testing, not a physical calibration measurement.

## Menu change

Moved the camera-anchored control panel from `(-0.45,-0.2,-0.85)` to **`(0,-0.25,-1)` meters**.
Its center is now horizontally centered and approximately 14 degrees below forward view;
the old center was about 28 degrees left. The menu keeps its existing controls and size.

## Validation

- Production Kotlin registration checked over **40 distinct head poses**, with a known origin
  translation `(-1.1,1.3,0.6)` m, rotation, and non-identity optical extrinsics. Maximum error:
  **3.58e-7** in the fixture comparisons. The calculated rebase stayed fixed while head pose changed.
- The first alignment build regressed detection: it released a PXRCapture metadata client after
  SpatialML opened its camera. Service logs then repeatedly reported "camera is not ready or is
  finished", and face presence stayed at `4.2419643E-15`. Pipeline completion alone did not prove
  camera input was valid.
- Corrected lifecycle: query and release metadata before graph creation, cache calibration, and
  report a retryable error after three seconds without advancing monotonic capture timestamps.
- Corrected device run: Stage head tracking `SUCCESS`, support `SUPPORTED`; calibration release at
  `14:38:33.207` preceded service camera opening at `14:38:33.226`. At sequence **264**, the app
  registered a detected face and populated all **478 vertices / 906 triangles**. Sequences **300**
  and **400** remained detected, registered and visible with presence `1.0` and `0.9999997`.
- Full Space uses Mixed passthrough, and SpatialML still uses a `0x0x0` container.
- The wearer confirmed that the corrected build detects a face and places the mesh, and requested
  committing this version. Precise mesh overlap and menu comfort still require wearer observation
  or a fresh recording of the corrected build.

The build and final installed APK identity are recorded in [VALIDATION.md](VALIDATION.md).
