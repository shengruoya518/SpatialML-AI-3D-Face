# Sentinel face-tracked helmet

**Face occlusion follow-up:** [Invisible depth-writing face surface](../artifacts/facelandmarker/face-occlusion-2026-11-09/FINDINGS.md) adds pose + mesh output for occlusion while preserving this asset, authored fit and visor motion. The pose-only runtime measurements below describe the earlier checkpoint.

The active Face Registration Lab and Face Landmarker entrypoints use the user-provided Sentinel model. `assets/helmet/sentinel-helmet.glb` is byte-for-byte identical to `/Users/bytedance/Downloads/sentinel-helmet.glb`, SHA-256 `7a0c46a03d56d866abe8be4be06ea31d5953b5cdb21d16a424f2fc13116210db`. The earlier Hornet model and attribution remain available.

The model already has an independent `FaceplateHinge`. Its metadata specifies a −110° local X rotation and a 1.15-second transition. `FaceHelmetMotion` supplies an absolute-time smoothstep curve, and a lifecycle-owned Compose frame loop applies the rotation on the main thread. The loop is independent of face packet arrival, so the visor moves smoothly between tracked pose updates. It checks scene lifetime before writing; composition disposal cancels the frame loop and destroys the retained scene. Pause hides the helmet and stops face submissions; the cycle continues while hidden.

The cycle starts fully closed. Ten-second closed/open phases alternate, with the transition at the beginning of each subsequent phase:

| Time from first display frame | Motion |
| --- | --- |
| 0–10 s | Closed |
| 10–11.15 s | Smooth opening |
| 11.15–20 s | Fully open |
| 20–21.15 s | Smooth closing |
| 21.15–30 s | Fully closed |
| 30 s onward | Repeat at each ten-second boundary |

The first closed hold lasts ten seconds; after that each ten-second phase includes its 1.15-second transition. Clock-based evaluation prevents accumulated delay and retargeting the face pose never resets the cycle.

The hierarchy remains placement owner → tracked face pose → face-local fit → Sentinel model. Only the imported faceplate hinge quaternion changes for opening. Its translation, child geometry and the shell transform are preserved. The supplied GLB has a 0.125 intrinsic scale, a 16 × 20 × 24 cm reference head and a 17.5 cm cheek clearance. The crest expands the outer width to 40.05 cm, so the old 24 cm outer-width fit would excessively shrink the head cavity. The new fit preserves intrinsic scale and aligns the authored head center `(0, 0.26875, 0.00625)` m to the canonical face-pose origin. The size slider scales both the model and its centering offset together, around that origin. This reference alignment is not an empirical claim of real-person helmet fit.

Face tracking retains calibrated Stereo camera K/D, balanced smoothing, output mask 1, 312-byte pose packets, Stage coordinate conversion, stale-pose expiry and existing controls. No face mesh or blendshape output is enabled. Diagnostics now identify the Sentinel asset and record elapsed animation time and commanded hinge angle alongside the existing pose evidence.

Both app assemble/lint/Spotless gates pass with `faceCompactVstPipeline=true`, `faceFusedControlModels=true`, `faceGpuPreprocessing=true`, `faceGpuSampleBytes=false`, SDK BOM 6.1.9. The production Kotlin host validator passes 99 pose cases, 181 smoothing-parity frames and 2,401 animation samples, including endpoints, continuity, invalid times and repeat without drift. Source inspection verifies two mesh objects, 35,108 triangles, physical bounds and an unchanged shell/hinge pivot during opening. The placement source gate passes with no violations; its heuristic containment advisory does not apply to this unbounded tracked Stage attachment.

Evidence and hash-pinned APKs: [sentinel-helmet-2026-11-09](../artifacts/facelandmarker/sentinel-helmet-2026-11-09). The [four-view source preview](../artifacts/facelandmarker/sentinel-helmet-2026-11-09/source-preview.png) shows closed/open front and side views; it is a source-geometry preview, not a Spatial runtime or headset capture. [Tooling limitations](../artifacts/facelandmarker/sentinel-helmet-2026-11-09/tooling-boundary.md) record editor startup failures and the managed codegen workspace rejection. The successful explicit repository build is recorded in `build.log`.

Installation and runtime verification are recorded separately in the artifact directory. The installer checks for active recording/calibration work and other Spatial clients, preserves calibration and all existing recordings/files, backs up the installed APK, installs only the lab app, performs the previously authorized Spatial-process reset for the ROM's GPU relaunch fault, and releases the serial-specific devmux lease. It verifies advancing pose-only packets and at least three visor cycles against an independent timing calculation. Physical face overlap, broad head-turn acceptance and actual display presentation remain headset-observation checks.

## Installed runtime result

The lab APK is installed and hash-verified on PB311XHGKC220141G. [Deployment findings](../artifacts/facelandmarker/sentinel-helmet-2026-11-09/FINDINGS.md) record 4,543 pose-only packets and 4,544 hinge-motion samples over 250.889 s, with 518 transition samples. Independent timing evaluation matches the commanded angle within 0.000008°. All 1,137 pre-existing app files, 55 recordings and private calibration hashes were preserved; service APK/debug property are unchanged and the lease is released.

The original status-broadcast observer failed due to the ROM's broadcast deferral. Direct device-hash-verified journal/log capture instead passes the [runtime validator](../artifacts/facelandmarker/sentinel-helmet-2026-11-09/runtime-observation/validation.json). There were no detected faces in this capture, so visible helmet pose application and physical alignment remain unobserved.
