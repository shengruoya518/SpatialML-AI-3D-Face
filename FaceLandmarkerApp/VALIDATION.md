# Face Landmarker validation

## Compact-VST and fused-control source commit checks — 2026-11-03

Both `FaceLandmarkerApp` and `FaceRegistrationLabApp` passed `assembleDebug`, `lintDebug` and
`spotlessCheck` with JDK 21 and all four latest-pipeline flags enabled: `faceCompactVstPipeline`,
`faceFusedControlModels`, `faceGpuPreprocessing` and `faceGpuSampleBytes`. Generated BuildConfig
files confirm those flags are true and `FACE_RETAINED_VST_PIPELINE` is false.

Host checks passed 30 detector/utility and 18 landmark LiteRT parity cases, 96 serialized model
bindings through the production graph constructor, terminal publication/packet/motion regressions,
and calibration profile, automatic-capture and timeline regressions. Packaged TFLite assets were
compared byte-for-byte with the source assets in both APKs. The
[sample guide](README.md#run) records the reproducible build command.

These are host checks. Existing headset timing evidence, the fresh-service-process requirement,
and the remaining optical/capture acceptance boundaries are in the
[compact pipeline report](../FaceRegistrationLabApp/COMPACT_FUSED_CONTROL_PIPELINE_2026-11-03.md).

- Combined GPU/RGB-first preprocessing + inline fit (2026-11-02): [measured operation table](../FaceRegistrationLabApp/COMBINED_RGB_INLINE_BENCHMARK_2026-11-02.md). Only the new configuration was measured: two 30-second off/on windows; 336 completions, 167 untraced eligible faces and 150 matched traced face chains. Untraced median/p95 157.84/199.18 ms, cadence 5.66 Hz. GPU detector/landmark preprocessing 10.28/9.22 ms with 48/48 and 68/68 OpenCL nodes; inline CPU fit 1.61 ms. Lab diagnostic crop recovery adds 22.46 ms; decode JS 28.16 ms. All 25 operations and app boundaries listed. Prior performance/numerical suites were not repeated. One fresh SpatialML process for GPU initialization; original APK/debug and user pose-only selection restored; calibration and 286 original external files preserved; healthy final face frame 48; lease released. Capture acceptance remains separate. Artifacts: `artifacts/facelandmarker/combined-rgb-inline-20261102/session-output-20261102-152817/`.

- Inline geometry and measured component inventory (2026-11-02): [implementation](../FaceRegistrationLabApp/INLINE_GEOMETRY_MODELS_2026-11-02.md), [headset benchmark / all operations](../FaceRegistrationLabApp/INLINE_GEOMETRY_PIPELINE_BENCHMARK_2026-11-02.md). One weightless CPU model includes three Horn/Jacobi proper-rotation solves; no external SVD. Opt-in `-PfaceInlineGeometry=true`, precedence over split flag, both default false. 126 OpenCV-referenced full-fit cases, 7,001 rotation stress cases, 36 serialized bindings, runtime regressions and inline/default build/lint/format pass. Nine device windows / 676 completions / 182 eligible linked face chains: fit means original/split/inline 34.71/1.77/1.76 ms; untraced pipeline medians 256.73/230.34/237.78 ms. Inline removes model boundaries but shows no meaningful fitting gain over split; native preprocessing remains dominant. 25 inline operations and app work are listed with mean/p95. Original APK `7ae804e2e3606d81eb7c2ab64f649abad940731d1feab5a7578d68afd99ef023`, debug and selection restored; calibration and 271 original external files preserved; final face frame 137; lease released. No service restart/change, commit or push. Calibration/controlled device parity remains pending. Evidence: `artifacts/facelandmarker/inline-geometry-20261102/session-output-20261102-151103/`.

- Fused geometry models (2026-11-02): [implementation and validation](../FaceRegistrationLabApp/FUSED_GEOMETRY_MODELS_2026-11-02.md), [ordered component inventory](../FaceRegistrationLabApp/PIPELINE_COMPONENT_INVENTORY_2026-11-02.md). Three weightless CPU model assets in four calls replace eight fitting JS operations; three native SVDs and service tracker/validity feedback remain. Opt-in `-PfaceFusedGeometry=true` (default false). 126 real host LiteRT parity cases, 24 production model bindings, all graph variants, existing capture regressions and both apps' fused/default build/lint/format gates pass. Original 31.61 ms fit includes 30.89 ms JS and 0.72 ms native SVD; no new headset speedup claim. Headset reports no face; no experimental install or device measurement. Existing installed dynamic APK/data/calibration preserved. Artifacts: `artifacts/facelandmarker/fused-geometry-20261102/`.

- Dynamic-output headset benchmark (2026-11-02): [DYNAMIC_FACE_OUTPUTS_BENCHMARK_2026-11-02.md](../FaceRegistrationLabApp/DYNAMIC_FACE_OUTPUTS_BENCHMARK_2026-11-02.md). All seven combinations and all-off/resume pass. Native-preprocessing all-three median 260.38 ms versus pooled old-build controls 348.55/353.77 ms (25.3–26.4% lower; individual-control comparison 15.5–27.5%). All-three packet 6,332 bytes (47.1% smaller); pose 312, blendshapes 456. Fourteen trace-off mode windows, seven operator windows and repeated old-build off/on/off controls; 361 eligible face chains have validated type/owner/dependency/clock association. New model calls ~0.34 ms each for all-three; app decode/reconstruction 0.69 ms mean. Native preprocessing/shared fit remain dominant. Dynamic APK `7ae804e2e3606d81eb7c2ab64f649abad940731d1feab5a7578d68afd99ef023` restored, healthy face frame 51; all outputs enabled, debug unset, lease released, 268 original external files and camera calibration preserved. AndroidX compilation-cache file changed on install, tracked separately. Host build/lint/format and 168 parity/selection cases pass. No new calibration capture, optical/switch-interaction acceptance, service/SDK change, commit or push. Artifacts and validated HTML: `artifacts/facelandmarker/dynamic-outputs/session-output-20261102-141408/`.

Validation host dates: 2026-10-27–28. Workspace branch: `dev/facelandmarker`.

## Latest: lit face mesh and same-capture geometry — 2026-10-28

The wearer reported flat appearance and a smaller residual offset. Kotlin now uses a double-sided
physically based material, per-frame normals and headset-relative directional key/fill lights.
The live mesh consumes `rawWorldPose` matching the current fit, as the Unity sample does, rather
than the filtered pose. Sampled logs check the final geometry against the measured source-camera
landmarks. See [SHADING.md](SHADING.md) for the diagnosis, math and verification details.

- Local and installed APK SHA-256: `b421c30b151ab3407a3924f3feb11f18dd1b87825e61c854dfb236ade3233de6`
- B3110 serial `PB311XHGKC220141G`; app PID `10625`, service PID `12885`
- Managed whole-project `assembleDebug`, JDK 21: **PASS**, root run
  `run-04b73548-b2e8-4636-b637-b139d5872518`
- Lint, `spotlessCheck`, model hashes, script bindings, coordinate fixtures, APK stub exclusion:
  **PASS**
- Forty float32 geometry fixtures: raw-pose maximum reprojection error **0.0001072 px**, versus
  **13.7024 px** with the filtered pose in the same moving-face fixtures
- Weighted sparse/full fit pose difference **0.0**; minimum reconstructed depth extent **0.1002245 m**
- Device startup: PBR material, key/fill lights, hidden dynamic mesh, camera calibration, Stage head
  history and the zero-sized capture session initialized; live capture timestamps advance
- Shading and exact VST overlap: **UNVERIFIED** until a face is observed in this validation run;
  previous-version detection and placement confirmation is not evidence for this new rendering
- Evidence: `../artifacts/facelandmarker/shading/`; debug bypass was not enabled
- App left running for wearer verification; log capture stopped and device lease released
- An ignored host `local.properties` supplies the SDK path for the controlled build

Earlier artifact identities and validation outcomes remain below for traceability.

## Latest: Stage registration and camera lifecycle correction

The user recording confirmed visible passthrough, a face mesh roughly 554 px right and 662 px
below the face, and a peripheral-left menu. The app now rebases the service's OpenXR Local output
using the same capture's camera matrix, optical calibration, and Stage head pose. The menu anchor
is `(0,-0.25,-1)` meters relative to the headset. See [ALIGNMENT.md](ALIGNMENT.md) for video analysis
and the exact transform chain.

The first alignment build stopped detection because it called `PXRCaptureRelease` after SpatialML
opened its camera. The metadata query now completes and releases its client before graph creation;
the result is cached for retries. Three seconds without fresh monotonic capture timestamps produces
a retryable camera error. This changes only the sample; SDK and service source are untouched.

- Device: `PB311XHGKC220141G`, B3110, ROM `6.3.0`; app PID `12504`, service PID `11392`
- Local and installed APK SHA-256: `ca0337627ef3acaa29ce3a0510d084825f5e340e22dcdfd884b0f0dae6102d61`
- Full Space Mixed Stage style `1`, capture `3248x2464`, SpatialML rendering container `0x0x0`
- Build, lint, `spotlessCheck`, model hashes, script bindings, coordinate fixtures and APK stub
  exclusion: **PASS**
- Production Kotlin registration: **PASS**, 40 head poses, maximum fixture error `3.58e-7`
- Calibration client release: `10-28 14:38:33.207`; service camera opening: `14:38:33.226`
- First detected and registered Stage mesh: **sequence 264**, `14:39:57.581`, 478 vertices /
  906 triangles, bounds center `(0.29953152,1.0904754,0.673069)` meters
- Sampled sequences **300–600**: detected, registered and visible; presence `0.9999997–1.0`
- Capture age at these sampled tracked results: about **0.29–0.30 seconds**; this includes inference
  and readback and does not measure display latency
- Corrected run window `14:38:31.500–14:43:11.430`: **zero** "camera is not ready or is finished"
  errors, **four** "camera has got no image yet" events, and no application error markers
- `debug.pico.spatialml.debug` was unset during this run; no debug bypass was enabled
- Wearer confirmation: **face is detected and the face mesh is placed**; this is the version the
  user requested committing
- Precise mesh overlap, depth and menu comfort: **UNVERIFIED**, require wearer observation or
  a fresh recording; ADB screenshots omit passthrough

Evidence is under `../artifacts/facelandmarker/alignment/`: `camera-fix-build.txt`,
`camera-fix-host-validation.txt`, `camera-fix-full.log`, `camera-fix-app.log`,
`camera-fix-markers.log`, `camera-fix-service.log`, `camera-fix-evidence.json`, and
`camera-fix-screen.png`. The app was left running and the device lease was released. The following
sections retain earlier artifact identities and outcomes.

## Passthrough startup correction — 2026-10-27

The original launcher used Stage style `3` (**Full**), which disables video passthrough. The wearer
reported a black surround at startup that disappeared when moving away. The SDK documents that
**Mixed** style `1` keeps passthrough visible while the app's Stage still occupies **Full Space**.
The launcher now explicitly uses Mixed style. The SpatialML `0x0x0` container and Stage mesh
coordinate path are unchanged.

- Corrected APK SHA-256 (local and installed): `078ed75bb37f9d8ea5e96e97ac71b687842c195c5f544e96f10c16ea77d07636`
- Device: `PB311XHGKC220141G`; latest observed PID: `11299`
- Build, lint, formatting and standalone host validation: PASS
- Fresh headset container lifecycle logs: `stageStyle=1`, `type=stage`; Full Space transition observed
- Persistent hidden mesh creation and matching inference readback: PASS
- No new fatal app exception in the crash-buffer capture
- Before/after logs and capture: `../artifacts/facelandmarker/passthrough-*`
- ADB screenshot: black background remains in the capture; it does not establish headset passthrough visibility
- Wearer confirmation of the black-surround fix: pending

The container configuration logs still carry the default `immersion=50` field. SDK documentation
states that this setting applies to Progressive style; Mixed fixes the rendering immersion at zero.
The visual change must be assessed from a capture or headset observation, not that default field.

The remaining results below describe the initial build, which used style `3`, and retain its
artifact identity for traceability.

## Result

The debug APK builds, installs, launches, initializes its persistent hidden mesh, and receives
sequence-matched inference results on the connected B3110. Real-face mesh alignment is **BLOCKED**
because no face was detected during this validation window. The available captures do not establish
control-panel readability, turning behavior, metric depth, or overlap with a real face.

## Artifact and device

- APK: `build/outputs/apk/debug/facelandmarker-1.0-debug.apk`
- Package: `com.pico.spatial.ml.sample.facelandmarker`
- Device: `PB311XHGKC220141G`; model `B3110`; reported ROM `6.3.0`
- Latest observed app PID: `15260`
- Local and installed APK SHA-256: `ec2c8374ca175e39832938abb95cd663df06512e01692dd595b2690bf527704a`
- Launcher Stage style: `3` (Full)
- SpatialML session: `3248x2464` capture, `0x0x0` rendering container
- Models: three portable TFLite models; Qualcomm compiler/DispatchDelegate initialization observed

The headset logs use the headset's clock, which reports 10-28 during this host-date run.

## Checks

| Check | Result |
| --- | --- |
| `:FaceLandmarkerApp:assembleDebug` | PASS |
| `:FaceLandmarkerApp:lintDebug` | PASS, no errors; existing dependency/version warnings and sample manifest icon/backup warnings |
| `:FaceLandmarkerApp:spotlessCheck` | PASS |
| SpatialUI design-style verifier | PASS, zero errors/warnings; native palette roles, transparent attachment, built-in controls |
| Model inspection through pico-cli/pySpatialML | PASS for all three input/output contracts |
| Model/source asset hashes and topology | PASS: 478 vertices, 906 triangles, 146 blendshape input points, 33 weighted fit points |
| JavaScript variable bindings | PASS for every graph script |
| Stage result coordinate parity | PASS: 24 rotations/scales/deformations; maximum double-precision fixture error `4.44e-16 m` |
| Face loss, non-finite rejection, capture pose publication | PASS in standalone host checks |
| Public platform stubs absent from APK class definitions | PASS |
| Install/launch and installed APK hash | PASS |
| Persistent hidden dynamic mesh creation | PASS on device |
| Matching SpatialML result readback | PASS on device |
| Live face vertices, mesh replacement and physical alignment | BLOCKED: no detected face |
| Controls, calibration, turning shape and live-face performance | UNVERIFIED |

The preserved source tracker harness also passed sparse/full geometry parity at four synthetic yaws,
full depth mean/reprojection, capture-time precision, retention/recovery, stale/duplicate/NaN rejection,
world-space pose, identity lock expiry, optical-center scaling and stereo-disparity checks. The port's
copied operator sources were byte-compared against that harness's Unity sources before the run.
The independently runnable Stage result checks are in `tools/validate_port.py`.

Runtime markers include `scene_ready stage=full`,
`dynamic_mesh_initialized vertices=478 triangles=906 hidden=true`,
`pipeline_ready stage=full container=0x0x0 backend=2`, and matching `face_frame` sequences.
No fatal application exception was observed in the filtered capture. LiteRT logged a QNN-options
parse warning followed by default settings and successful Qualcomm delegation; this warning is
preserved in the service capture. No comparative performance claim is made.

## Reproduce

```sh
./gradlew :FaceLandmarkerApp:assembleDebug :FaceLandmarkerApp:lintDebug :FaceLandmarkerApp:spotlessCheck
python3 FaceLandmarkerApp/tools/validate_port.py \
  --apk FaceLandmarkerApp/build/outputs/apk/debug/facelandmarker-1.0-debug.apk
```

Runtime logs, model inspection JSON, APK-hash verification and screenshots from this run are under
`../artifacts/facelandmarker/`, which is ignored by Git. Place a real face in the outward camera view
and require `first_mesh_ready` plus headset observation before marking physical alignment accepted.

## Host tooling

| Doctor overview row | Observed value |
| --- | --- |
| CLI | `0.6.0 (public)` |
| Plugin | `pico-unity-agentic-tools@0.1.0` |
| SDK | Doctor reported `no-project`; the multi-module project's BOM and compiled artifacts are `6.1.9` |
| PICO development knowledge | `6.0`, currently serving Unity documentation |
| Emulator | Not provisioned |
| Editor | Not provisioned |

Node `25.9.0`, npm `11.12.1`, Gradle `8.13`, JDK `21`, and pySpatialML `0.5.0` were used.
The public CLI is `/opt/homebrew/bin/pico-cli`. Doctor reported PARTIAL with tooling/version and
platform-registration warnings. No plugin, knowledge workspace, SDK/BOM or host setup was changed.
Exact Kotlin semantics were checked against the local SDK source and the published 6.1.9 public
signatures because the loaded knowledge graph did not cover this SDK/mode.

The host JDK initially rejected the download server certificate. Build commands used a temporary
truststore containing the JDK defaults plus the host's System Keychain certificates, via
`JAVA_TOOL_OPTIONS=-Djavax.net.ssl.trustStore=/private/tmp/facelandmarker-port/trusted-cacerts` and
`JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home`. TLS verification stayed
enabled. This host-only setup is not part of the project's build configuration.

## Registration lab

The separate [Face Registration Lab](../FaceRegistrationLabApp/README.md) now shares the face implementation and provides coherent RGB/pose captures, three camera hypotheses and checkerboard analysis. See its [device/host validation](../FaceRegistrationLabApp/VALIDATION.md) and [headset capture steps](../FaceRegistrationLabApp/CAPTURE_STEPS.md). The remaining physical VST offset is not marked solved.
