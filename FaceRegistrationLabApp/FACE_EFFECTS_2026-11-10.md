# Face effects and continuous pose rendering — 2026-11-10

Both app entrypoints now open **Face mesh** first and provide nine selectable face effects. Tracking and smoothing publish measurements independently of rendering. Rendering uses the Compose frame clock; a separate conflated, serialized uploader updates facial surfaces. The accepted stereo calibration, camera projection, balanced filter parameters and Sentinel asset are retained.

## Flashing boundary

The previous renderer called `hide()` on each null, no-face, rejected or unfresh result, and the runner reset its filter on those misses. It also awaited a facial mesh upload inside the same coroutine that applied the head pose. A brief dropped measurement could therefore hide the helmet despite the physical face staying in view. This is a confirmed source path; no new recording establishes the frequency or all causes of the reported flashing.

`FaceTrackingState` now retains the last valid, advancing capture for **350 ms from its readback**. Missing/rejected/repeated measurements do not refresh that deadline. Pause and output mask 0 clear tracking immediately. Expiry clears it; a different tracking identity or calibration/correction starts a new generation. The pose filter survives short streaming misses and retains its existing capture-gap, identity, configuration and outlier guards. It does not predict motion.

Each generation waits for its first measured depth surface before appearing. After that, the retained local surface follows the latest filtered head transform while shape uploads run independently. Pending shapes are conflated instead of queued without limit. Hide revisions, generation checks and cancellation prevent a late upload from restoring visibility. Effect selection does not restart SpatialML or reset the pose filter; changing expression-output selection does not change the filter's configuration key.

## UI options

| Choice | Implementation | Model outputs |
| --- | --- | --- |
| Face mesh | Transparent cyan wireframe over the measured facial surface; startup default | Pose + mesh |
| Helmet | Existing Sentinel GLB, fit and automatic faceplate hinge | Pose + mesh |
| Buggy eyes | Retained eye/pupil spheres anchored to measured eye corners; blink, widen and gaze coefficients drive them | Pose + mesh + blendshapes |
| Joker smile | Red extended smile and green brow paint, attached by canonical face-local UVs to the deforming measured mesh | Pose + mesh |
| Hat | Procedural blue crown and gold brim attached to the filtered pose | Pose + mesh |
| Red pigtails | Procedural red cap/pigtails with blue bows | Pose + mesh |
| Flag paint | Blue, white and red vertical tricolor on the measured mesh | Pose + mesh |
| Team colors | Blue and gold halves on the measured mesh | Pose + mesh |
| Expression mask | Independent purple neutral mask, deformed by named blendshape targets | Pose + mesh + blendshapes |

The new accessories are simple procedural prototypes. The expressive mask is an app-owned morph mesh, with **ten precomputed targets**: jawOpen, left/right mouthSmile, left/right eyeBlink, browInnerUp, left/right browOuterUp and left/right browDown. mouthClose suppresses jawOpen. It reads names from the shipped 52-channel model metadata and clamps finite coefficients; absent expression values remain neutral. It does not claim an imported artist-authored 52-target rig.

The panel remains an attachment in the existing Full Space Mixed Stage. It uses SpatialUI `Button`, `Slider` and `Text` inside `PicoTheme`, with selected labels and component-owned colors/interaction handling. There are no new window containers or app-authored UI backgrounds. The fit slider scales accessories and the mask around the face origin; paint and the depth surface retain the measured anatomical geometry.

Output mask 3 transfers 6,124 bytes; mask 7 transfers 6,332 bytes and also executes expression inference. Selecting the mask or eyes requests mask 7; the other choices request mask 3. The additional expression cost and presentation latency need device measurement.

## Face depth and paint

`FaceOcclusionScene` uses the measured 478-vertex head-local surface with a transparent unlit material, zero opacity, depth testing/writing enabled and no culling. Its draw-order group places the depth face at order 0, visible mesh/paint at order 1 and helmet/effects at order 2. Ordering is assigned to model-bearing helmet descendants. Paint shares the measured mesh resource and uses a 1 mm local forward offset; the invisible surface never changes the passthrough color intentionally.

This configures the requested face-before-helmet depth pass. **The app is now installed and running, but no face was detected during device checks. Actual transparent depth occlusion, rear-shell visibility, texture orientation, physical fit and expression alignment are UNOBSERVED.** A successful build or host SDK adapter does not prove them. Start with the visible Face mesh, check overlap, then inspect the open helmet visor and broad head turns.

## Validation and build

Host regression: `tools/validate_face_effects.py` compiles the production tracker, morph/paint generators and extracted renderer methods with controlled SDK adapters. It covers brief misses, repeated exposure deadlines, expiry, identity/configuration changes, independent pose application during a pending upload, no duplicate transform writes for unchanged poses, effect selection, hide/late upload, cancellation/close, named morph targets, coefficient bounds and paint UVs. `tools/validate_helmet_latency.py` remains a compatible entrypoint for this replacement scheduling contract.

Existing pose/shape jitter and anatomical coordinate regressions pass, as do terminal completion, packet freshness, calibration/profile, capture restoration and frozen stereo K/D checks. The balanced synthetic movement-equivalent delay remains 43.256 ms; the anatomical round-trip maximum is 1.192e-7 m. These are host results, not display timing.

Run the optimized build with the existing four flags:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home ./gradlew \
  :FaceLandmarkerApp:assembleDebug :FaceRegistrationLabApp:assembleDebug \
  :FaceLandmarkerApp:lintDebug :FaceRegistrationLabApp:lintDebug \
  :FaceLandmarkerApp:spotlessCheck :FaceRegistrationLabApp:spotlessCheck \
  -PfaceCompactVstPipeline=true -PfaceFusedControlModels=true \
  -PfaceGpuPreprocessing=true -PfaceGpuSampleBytes=true --offline --console=plain
```

Omit the four flags for the default configuration. Evidence, build logs, validation JSON and archived APK hashes are in `../artifacts/facelandmarker/face-effects-2026-11-10/`. SpatialUI style admission is run on the selector together with its theme-owning host; errors/warnings are zero. The generic managed scene workflow rejected its input contract, and the available knowledge query returned Unity 6.0 content rather than this Kotlin SDK 6.1.9. Public APIs already used in this checkout and successful local compiler/build checks supply the implementation evidence; no managed scene-workflow or device-visual pass is claimed.

## Headset acceptance when reconnected

1. Use `devmux` with serial `PB311XHGKC220141G`; verify idle/recording state. Preserve app data, private calibration and all recordings. Install the archived registration-lab APK, hash-check the installed artifact and launch it. Do not replace the Spatial service APK.
2. Check that Face mesh starts selected. With a face continuously visible, inspect alignment and stability for at least a minute. Brief occlusion should hold up to 350 ms; longer loss should hide. Pause must hide immediately and Resume reacquire.
3. Select Helmet and wait for the visor to open. Confirm the real face remains visible and the rear shell does not show through it. Inspect frontal, yaw, pitch and roll views.
4. Cycle all nine choices while tracking. Check paint follows moving lips/cheeks, eyes blink/gaze correctly, and masks/accessories fit. For the expression mask, test jaw open/close, unilateral smiles/blinks and brow movement; compare names to the left/right side of the subject.
5. Compare pose/readback/application and surface-upload journal events. These events describe app/SDK return boundaries; do not equate them with compositor presentation. Capture a short stereo recording if visual artifacts remain, retain it and release the lease.

The initial build completed while the headset was disconnected. The online installation and runtime results below supersede that boundary.

## Packaged artifacts

Both default and optimized variants pass assemble, lint and formatting for both app modules. The source hashes and APK SHA-256 values are recorded in [delivery.json](../artifacts/facelandmarker/face-effects-2026-11-10/delivery.json). Standard Gradle outputs currently contain the optimized variant.

| App | Variant | APK SHA-256 |
| --- | --- | --- |
| FaceRegistrationLabApp | default | `109eceb4bbde54128d26ad750e381601d1f87806e4c0fe0a2434babd43739054` |
| FaceLandmarkerApp | default | `54cb0b51f1da3fe2104b7b0549a249b799d514e04a3702bc5160a9026f02639c` |
| FaceRegistrationLabApp | optimized | `6dd00e287ad89965332286acb6ba672636bcdeaa8f9b926a22736d752d3e781f` |
| FaceLandmarkerApp | optimized | `a3fe7cb4e853d843bf3a6667542c086122c2efc15eba513b58659194cf22af4c` |

## Online installation and runtime verification

The corrected optimized registration-lab APK is installed and hash-verified on `PB311XHGKC220141G`, SHA-256 `6dd00e287ad89965332286acb6ba672636bcdeaa8f9b926a22736d752d3e781f`. App PID 12495 and Spatial PID 26973 remain stable through the final check at frame 6,655, with fresh/finite mask-3 packets, 6,124-byte readback, fast pacing and no final rejection. The screenshot shows all nine choices in both eye captures, with Face mesh selected and Pause available.

The twenty-second capture has 541 eligible distinct no-face exposures, 39 excluded frames and 26.98 packet completions/s. Median/p95 request-to-readback is 33.89/40.30 ms; exposure-to-readback is 63.74/82.37 ms. These measure no-face processing, not visible-effect latency or presentation. No face was detected, so attachment, dropout behavior, open-visor depth occlusion and expressive deformation remain unobserved on-device.

The first optimized package passed compilation but initialization rejected its flag combination: fused control models had been enabled without compact VST. The archived optimized APKs and build command above are corrected to the previously validated four-flag configuration. Its generated BuildConfig is checked for the compact/fused dependency and retained/compact exclusivity. The failed attempt is retained in `install-online/manifest.json`; the successful replacement is in `install-corrected/manifest.json`. No app/source math fix was needed for that build-selection error.

Preservation was checked across both installations: all 1,145 pre-existing app files remain without shrinking, all 55 recordings retain their sizes, and private camera calibration hashes match. The Spatial service APK remains SHA-256 `482da7ac78ae141bce280e5e45de3b3c771dd61901900294fce893cabf5e1519`; its process was restarted for installation, with its APK retained. The debug property remains unset. Device leases were released.

The optional shell output-7 command returned `result=0` and was not observed in the journal; packets remained mask 3. This is recorded as an unobserved expression-switch check, rather than a successful blendshape test. Restoration commands also requested mask 3, and the final readback confirms mask 3. Use the actual UI with a face in view to verify mask/eye selection and expression movement.

[Installation and preservation receipt](../artifacts/facelandmarker/face-effects-2026-11-10/install-corrected/manifest.json) · [Final runtime](../artifacts/facelandmarker/face-effects-2026-11-10/final-runtime.json) · [Controls screenshot](../artifacts/facelandmarker/face-effects-2026-11-10/controls-online/face-effects-ui.png)
