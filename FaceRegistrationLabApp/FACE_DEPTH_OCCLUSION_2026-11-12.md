# Native facial depth occlusion — installed and stereo probe verified

The helmet, baseball cap and pigtails now use the tracked face mesh with an exported SpatialEngine **Occlusion Surface** material. This replaces the ineffective zero-alpha `UnlitMaterial` strategy. The optimized lab APK is installed and hash-verified on `PB311XHGKC220141G`. A synthetic test using the **same live material as the facial mesh** hides a rear marker and preserves a foreground marker in both eye views, without a grey surface patch.

The test contained no tracked face. Open-visor visibility on a person, cap/pigtail fit and passthrough alpha require a wearer check. ADB screenshots omit the passthrough camera image, so they cannot prove the real face remains visible in passthrough. Do not interpret the synthetic result as completed optical calibration or on-face acceptance.

## Implementation and material contract

- `FaceOcclusionMaterial.kt` holds the exported `AssetBundle` and `ShaderGraphMaterial` for the scene lifetime, makes the material global and enables depth test/write with culling disabled. It preserves exported blending settings.
- Asset URL: `asset://occlusion/face-occlusion.bundle`.
- Material path: `FaceDepthOcclusion/Root/FaceOcclusionMaterial`.
- Graph: `ND__occlusion_surfaceshader.outputs:out` connected to the material's `outputs:mtlx:surface`. No opacity-zero unlit substitute.
- Exported shader metadata records `surfaceType=3`; runtime logs identify `FaceOcclusionMaterial`, `blending=OPAQUE`, `depth_write=true`, `depth_test=true`, `culling=none`.
- The existing shared occlusion owner remains under the filtered tracked-head transform, including when Helmet, Baseball cap or Red pigtails is selected. Surface uploads and pose rendering retain separate clocks.
- Imported accessories retain the prior transparent pass, opacity-one and depth settings. The special exported facial material has its own native surface contract. This task does not change calibration, accessory geometry, filtering or the tracking model.
- A lab-only desktop command exposes a small synthetic depth probe. It loads the Editor-authored marker scene, rebinds the occluder to the production face material and uses its own draw-order group with unique indices. It starts hidden and contributes no normal UI controls.

The Editor project is [FaceDepthOcclusion](../editor-asset/src/main/res3d/FaceDepthOcclusion/FaceDepthOcclusion.spatialproject). The material was validated, previewed, committed and saved through native Editor APIs; Editor-owned USD/project files were not hand-edited. Scene units are metres, Y-up, with an identity root. The APK loads only the material during normal operation; test scene geometry is loaded only for the requested lab probe.

## Verification

Both `FaceLandmarkerApp` and `FaceRegistrationLabApp` pass optimized debug assembly, lint and Spotless checks. The four optimized build flags remain required:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home ./gradlew \
  :FaceLandmarkerApp:assembleDebug :FaceRegistrationLabApp:assembleDebug \
  :FaceLandmarkerApp:lintDebug :FaceRegistrationLabApp:lintDebug \
  :FaceLandmarkerApp:spotlessCheck :FaceRegistrationLabApp:spotlessCheck \
  -PfaceCompactVstPipeline=true -PfaceFusedControlModels=true \
  -PfaceGpuPreprocessing=true -PfaceGpuSampleBytes=true --offline --console=plain
```

The packaged graph/node connection, dedicated surface type, ZIP integrity and runtime-facing material path pass inspection. The production geometry regression passes 99 pose cases across rotation, scale, expression shape and a rotated parent; maximum Stage round-trip error is `1.1920928955078125e-7` metres. The retained-pose/accessory regression passes dropout holding, pose updates during upload, identity/visibility guards, cancellation, unchanged-pose writes, cap geometry, paint cutouts and dragon gates.

Device captures use a fixed camera-relative probe: a blue rear surface at local z=-0.04 m, an occluder at z=0, and a green foreground surface at z=+0.04 m. Markers use the same accessory material/pass settings as production. A baseline capture disables the occluder; the depth capture enables it.

| Eye view | Blue pixels, baseline | Blue pixels, depth | Green pixels, baseline | Green pixels, depth |
| --- | ---: | ---: | ---: | ---: |
| 0 | 54,061 | 3 | 6,772 | 6,860 |
| 1 | 56,741 | 2 | 6,513 | 6,714 |

The rear marker disappears by more than 99.99% in both views; the remaining blue pixels are isolated non-marker pixels. The foreground remains visible, and inspection finds no grey/color patch over the occluder. Originals and the readable [stereo comparison](../artifacts/facelandmarker/face-depth-occlusion-2026-11-10/device-2026-11-12/depth-probe-comparison.png) are saved. The panel overlaps the camera-relative test markers in these captures; the occlusion claim concerns the two 3D markers, not panel layering or accessory fit.

Runtime PID `10878` loads the shader and produces fresh output-mask-3 frames. The saved final app log records continuing frame sequences. No face was detected during this test.

## Editor preview limitation and recovery

Spatial Editor 6.1.7's validator accepts the current node ID, but its offscreen preview logs:

```text
Could not find a matching implementation for node '_occlusion' matching target 'essl'
```

The shipped implementation XML references `ND_extend_occlusion_surfaceshader`, while the node definition/catalog names `ND__occlusion_surfaceshader`. The preview shows a fallback grey surface. This is failed preview evidence, not a passing depth test. Native bundle export succeeds, retains the authored graph and surface type, and the actual headset probe passes. No Editor/SDK library patch was made.

Normal Editor installation initially exceeded available host disk space. The official checksum-verified 6.1.7 archive was extracted to a task-owned 4 GiB RAM volume; project and export artifacts remain in the repo workspace. The task Editor and MCP are stopped, and the temporary volume is detached after export and tests. The project and packaged material are preserved.

## Installed artifact and preservation

- Lab APK: [registrationlab-1.0-debug.apk](../artifacts/facelandmarker/face-depth-occlusion-2026-11-10/apks/registrationlab-1.0-debug.apk), SHA-256 `8687279ae6c45b8e672eeec3c81070a81cea65c268b22858b8e65897710358a7`.
- Normal sample APK is archived alongside it; only the lab package was installed.
- Bundle SHA-256: `dd8a4ead63d81ee4ef8a33b76da7782458dc45fb15f15375bfec0a06ad7d77de`.
- Service APK SHA-256 remains `482da7ac78ae141bce280e5e45de3b3c771dd61901900294fce893cabf5e1519`.
- All 1,149 pre-existing external app files and the private calibration hash are retained. No app-data clearing or recording deletion occurred.
- The app/service were stopped at preflight. The app was temporarily launched for validation, the probe was disabled, then both packages were force-stopped. Final PIDs are absent and the target packages' User 0 state has `stopped=true`. The devmux lease is released.
- No SDK upgrade, service APK replacement or commit was made.

The complete [installation receipt](../artifacts/facelandmarker/face-depth-occlusion-2026-11-10/device-2026-11-12/installation.json), [probe measurements](../artifacts/facelandmarker/face-depth-occlusion-2026-11-10/device-2026-11-12/depth-probe-validation.json), build logs and native Editor responses are under `../artifacts/facelandmarker/face-depth-occlusion-2026-11-10/`.

## Repeat the depth check

After launching the lab app, use the serial-pinned devmux tool to send the existing lab broadcast:

```sh
devmux adb -s PB311XHGKC220141G shell am broadcast \
  -a com.pico.spatial.ml.sample.facelandmarker.registrationlab.COMMAND \
  -p com.pico.spatial.ml.sample.facelandmarker.registrationlab \
  --es command occlusion_probe --es value baseline
```

Capture the baseline, then repeat with `--es value depth`. Rear blue must disappear and foreground green must remain in both eyes. Finish with `--es value off`. Hold one lease for the comparison and release it afterward. The probe is transient, not persisted in calibration.

For the wearer acceptance pass, select Helmet and wait for the visor to open, then select Baseball cap and Red pigtails and turn the face in both directions. Verify real-face visibility and accessory edges against the face while preserving the current calibration. This remains the next visual acceptance step.
