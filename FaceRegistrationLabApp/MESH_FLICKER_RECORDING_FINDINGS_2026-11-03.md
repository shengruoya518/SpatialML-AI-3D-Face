# Registration lab mesh flicker in the recordings — 2026-11-03

The recordings show the face mesh appearing and disappearing in both eyes. The matching app
journal shows the same alternation in `hasFace`, followed by matching mesh visibility changes.
This localizes the flicker to the face-result/presentation path within one recorded session;
the footage shows one calibration panel with session suffix `9b31f0`.

The corrected lab is now installed. A 542-frame device window contains 537 valid face frames;
the other five repeat camera timestamps and are rejected by the existing freshness gate. The
previous every-other-frame switching is absent. Both the camera resize defect and the compact
detector's calibration-space mismatch are addressed in app source, without a service update.

## Retrieved evidence

Headset `PB311XHGKC220141G` clock at retrieval was `2026-11-04T09:12:36+0800`.
Both finalized files were pulled from `/sdcard/DCIM/ScreenRecording` and verified by byte count
and SHA-256 parity with the headset:

| Recording | Duration | Bytes | Decoded stereo pairs |
| --- | ---: | ---: | ---: |
| `ScreenRecording_2026.11.04-09.09.21-AM.mp4` | 13.532 s | 53,548,595 | 406 |
| `ScreenRecording_2026.11.04-09.09.37-AM.mp4` | 9.732 s | 36,735,243 | 292 |

The files contain MV-HEVC with 1920×1080 views. PyAV 19.0.2 decoded both views using
`view_ids=-1`; view IDs 0 and 1 were paired by identical PTS. No unmatched views occurred.
Derived side-by-side MP4 previews preserve the video timestamps and contain no audio. The
unaltered originals retain their audio and source metadata.

Evidence root: `artifacts/facelandmarker/flicker-recordings-20261103-171236/`.
Each recording's subdirectory contains `stereo-side-by-side.mp4`, `stereo-first.jpg`,
`stereo-at-3s.jpg`, `consecutive-pairs-at-1s.jpg` and `frames.json`.
`retrieval.json` records original hashes, paths and journal retrieval.

## Journal correlation

The panel identifies session `2026-11-04T01-02-36.705303Z-9b31f0`. In the surrounding
404–432 second interval of that session:

- There are 426 completed pipeline frames: 212 report a face and 214 report no face.
- The reported face state changes on 423 of 425 adjacent frame pairs.
- 424 frames have fresh camera exposures. Only two carry the sensor-timestamp rejection.
- Scene updates contain 211 visible face frames, 212 hidden frames and two null updates.
- No automatic calibration sequence is active, so the clear/marker/clear capture phases do not
  explain the switching.

For example, frames 8057–8076 alternate continuously: odd frames report no face and are hidden;
even frames report a face and are visible. Their exposures advance and have roughly 40–80 ms
camera age. The stereo contact sheet independently shows the green mesh switching on and off
around 1.0–1.2 seconds into the first recording.

The journal's `hasFace` value comes after compact-packet decoding. It does not distinguish a
native validity rejection from a packet/mesh reconstruction failure. It therefore does not yet
establish which control, model or decoding operation originates the alternation.

An isolated host CPU feedback probe ran the existing landmark control model for 40 consecutive
frames with its own returned tracking and pose state. Every frame remained valid and matched
the JavaScript reference. That probe does not reproduce the actual camera, detector/ROI feedback,
GPU preprocessing or Android result path.

## Diagnostic build

The diagnostic app adds native face validity, packet finiteness, detection/presence confidence,
tracking failure reason/state/identity and pose status to the existing journal and remote status.
It changes neither models nor validity/visibility gates. A face-bearing run is required to
separate native rejection from app decoding and locate the first alternating value before
choosing a corrective change.

The diagnostic APK was built with the same four compact/fused/GPU flags and installed after
stopping OpenMR's processes. SHA-256 is
`837885d15402dd8285991fd74533442a0f3f777560cdee77e1edeb2c24b7fcb9`.
Build, lint and formatting checks pass. Fresh frames `48`, `99`, `151` advance; no face was in
view during that installation check. The initial diagnostic status reports rejection reason 1
and presence around `1.1e-9`, which is a no-face observation rather than a reproduction of the
recorded alternation. Existing calibration and all 314 external files are retained; original
service APK hashes match before/after installation. Evidence and source hashes are under
`artifacts/facelandmarker/flicker-diagnostic-install-20261103-1732/`.

The retrieval and offline inspection did not change headset calibration, save profiles, start
capture sequences or delete recordings.

## Face-bearing run and installed resize defect

While the wearer looked at the face, diagnostic frames 7179–7523 included 345 finite native
packets, all rejected with native validity 0, tracking reason 1, state 0 and pose status 0.
Detection confidence alternated between approximately 0.88 and 0; landmark presence was tiny
on both branches. Rejection therefore precedes app decoding and mesh presentation.
Evidence: `artifacts/facelandmarker/flicker-face-diagnostic-20261103-173028/`.

Both current and HEAD service source in `InferenceEngine/src/VSTSession.cpp:252` pass
`cv::Size(destination.rows, destination.cols)` to `cv::resize`. OpenCV expects width, height.
Color conversion then changes the destination Mat to that reversed shape. On the next access,
the destination dimensions reverse again. The image's byte count stays unchanged, so buffer
size validation does not detect this layout error.

The installed Spatial service APK was pulled and hash-verified:
`d1e922a9aec0850808b6d6bfae2bdb4b7523f5d3c5994c931562736c9611565f`.
Its `libopenmr-backend.so` hash is
`52c57bc437b00e0717b953414f00111f11b3b5c91046eaf669ad930c16a88fc1`.
Disassembly confirms the argument order at resize call `0xb19538`: destination Mat rows at
offset `0xc8` become the first Size field, and cols at `0xcc` become the second. The Size
constructor at `0x808c50` stores those arguments in that order.
The disassembly and provenance are in the recording evidence root's `service-binary/`.

A host OpenCV reproduction made six successive non-square accesses. Actual height/width
alternated 336/256 and 256/336, always 258,048 RGB bytes. A square 256×256 control stayed
square on every call. Results are in `resize-dimension-reproduction.json`.

## Scoped app correction

The compact detector now acquires a square 336×336 VST image. The same GPU preprocessing call
casts the bounded square image, resizes nearest-neighbor to the logical 336×256 view, crops
columns 40–295 and normalizes. Its input changes from `[1,256,336,3]` to `[1,336,336,3]`;
output remains `[1,256,256,3]`. The model has four operations (CAST,
RESIZE_NEAREST_NEIGHBOR, SLICE, DIV), replacing three.
The full landmark image, validity thresholds and calibration parameters remain unchanged.
Two-stage vertical sampling can differ by one compact-source
row from a direct full-source resize; exact old-versus-new VST pixel equivalence is not claimed.

The generated preprocessing model is 1,360 bytes, SHA-256
`356780b9290fb8a1b4836a564e96028ede08085d8feffec84f5517db1f90dd88`.
Resize-only host parity passes 30 detector/utility and 18 landmark cases, including an independent OpenCV
reference for every resampled row and both crop edges. Runtime packet/freshness/profile checks
and both apps' build, lint and format gates pass. Evidence:
`artifacts/facelandmarker/flicker-square-workaround-host-final/` and
`/private/tmp/registrationlab-square-view-final-build.log`.

The first square-view candidate used row GATHER and passed host parity, but the installed
GPU compiler rejected its output shape during initialization: requested `[1,256,336,3]`,
reference `[1,1,336,3]`, followed by `Unable to parse bc coord for BATCH axis`. That candidate
did not run a camera frame. The final model uses standard nearest-neighbor resize instead.
Its failed install evidence is retained under `flicker-square-vst-install-20261103-recovered/`.

The resize-only APK initialized the GPU model successfully, with 4/4 nodes delegated to
OpenCL, and resumed fresh camera frames. In 450 subsequent journal frames, even and odd
detector confidence medians were 0.88263 and 0.88141. The former alternating 0.88/0 pattern
was absent. Landmark presence still varied and often failed its existing threshold.
Evidence: `flicker-square-vst-resize-install-20261103/live-timeline.jsonl`.

## Detector coordinate contract

The compact view samples the source image without the lab affine `A`. Its decoded coordinates
were therefore in source-image pixels. The existing landmark stage uses
`sourceToCrop = cropAffine × A`; its ROI and affine must be defined in calibrated image pixels.
Using a raw source center as the calibrated ROI instead sampled `inverse(A) × sourceCenter`,
which displaces off-center faces and changes their crop size.

`CompactFaceDetector.toImage` now computes the detector mapping into that working image space.
For the supported axis-aligned lab transform `A = [ax,0,tx; 0,ay,ty; 0,0,1]`, the mapping is:

```text
sx = 3248 / 336
sy = 2464 / 256
detector_to_source (legacy ABI name) = [ax*sx, ay*sy, ax*40*sx + tx, ty]
```

The graph keeps that four-float calibration mapping in an owned global tensor. It updates it
between completed frames when applying a lab configuration, alongside the existing affine/K
updates. Production identity mapping remains the original source mapping. No camera pixels or
detector outputs are read back to compute this calibration constant.

The actual fused control model now passes nine additional source-crop recovery cases: three
off-center face positions and three calibration affines, including rotated eye vectors. Inverting
the final sampling affine recovers the raw face center with maximum error 0.0003663 pixels.
The full suite passes 39 detector/utility and 18 landmark cases. The production Kotlin mapping
and configuration update also pass the existing intrinsics/runtime harness, including 45 source
points across all five lab profiles and the saved-profile/clock/reset guards.
Evidence: `artifacts/facelandmarker/flicker-square-coordinate-host/`.

This correction avoids a service update. The general service fix is to construct
`cv::Size(destination.cols, destination.rows)`; service source and APKs were not modified
for this correction. The separate warm-service LiteRT initialization failure still requires
stopping both face apps and both OpenMR packages before relaunch.

## Final device verification

APK SHA-256: `abc6fe66aaf9500586eb8c825feeb55ced6d5c8ad301fd15106034cf63a42957`.
Session `040d4d`, frames 356–897: 542 finite packets and scene rows, 537 fresh/native-valid
face frames with visible mesh, plus five repeated timestamps at frames 384, 390, 419, 487 and
552 with hidden mesh. All fresh frames pass native validity and pose status. Median detection
is 0.9470882; median presence is 0.99999994. All 11 remote samples report a face. The final
pipeline has all outputs enabled and unlocked controls; no calibration sequence is active.

Custom mode and its four values are preserved. The optical calibration hash is unchanged and
all 321 existing external app files are retained. Both service APKs match before/after; debug
is 0 and the device lease is released. Neither recording nor calibration capture was started.
The ordinary frame and scene journals verify result/presentation switching; a new stereo
recording and One check are still required to evaluate physical alignment and calibration exports.

Evidence: `artifacts/facelandmarker/flicker-compact-fix-install-20261103/`, including
`installation.json`, `face-window-analysis.json`, `performance-data/face-timeline.jsonl`, the
prior APK backup, file inventories and startup logs. Shared face and lab source build, lint and
format checks pass with JDK 21; final build log:
`/private/tmp/registrationlab-square-coordinate-final-build.log`.
