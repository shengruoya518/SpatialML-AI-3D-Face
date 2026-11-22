# Face tracking app snapshot — November 12, 2026

The latest optimized APKs were built at **14:03 PST on November 12, 2026** and
passed the precommit host checks again on the same day. Both apps share the
current face-effects implementation. Use **Registration Lab** for the calibrated
stereo face-tracking workflow; its application ID is
`com.pico.spatial.ml.sample.facelandmarker.registrationlab`.

| App | Archived APK, relative to the repository | SHA-256 |
| --- | --- | --- |
| Registration Lab | `artifacts/facelandmarker/precommit-20261112/apks/registrationlab-1.0-debug.apk` | `644aabe45d8da0873867244ea6a0efe2e99c5409747cc5c098031a88af4387d3` |
| Face Landmarker | `artifacts/facelandmarker/precommit-20261112/apks/facelandmarker-1.0-debug.apk` | `d01a8261ccded8e2a43667010198b2c57b411286b45dcee98063dc1d807e44cd` |

Identical copies are in each module's `build/outputs/apk/debug/` directory.
Both still report version name `1.0` and version code `1`; use the hashes to
identify this revision. APKs and verification artifacts remain locally archived
under the ignored `artifacts/` directory rather than stored in Git.

## Included behavior

- Retained, filtered head pose drives rendering independently of mesh uploads,
  with bounded dropout holding and cancellation/visibility guards.
- Nine choices: Face mesh, Opening helmet, Closed helmet, Buggy eyes + grin,
  Baseball cap, Red pigtails, USA cheek flags, Team colors, and Chinese dragon.
- The closed helmet uses `damaged-helmet.glb`; cheek flags and the combined
  eyes/grin effect include today's paint and mouth-coverage changes.
- The exported native facial occlusion material, optional same-capture tongue
  model, fast streaming pacing, and mesh-upload timing tools are included.
- The Registration Lab preserves its paired stereo calibration and balanced
  pose/local-shape filtering.

## Verification and reproduction

Both modules passed `assembleDebug`, `lintDebug`, and `spotlessCheck` with:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home ./gradlew \
  :FaceLandmarkerApp:assembleDebug :FaceRegistrationLabApp:assembleDebug \
  :FaceLandmarkerApp:lintDebug :FaceRegistrationLabApp:lintDebug \
  :FaceLandmarkerApp:spotlessCheck :FaceRegistrationLabApp:spotlessCheck \
  -PfaceCompactVstPipeline=true -PfaceFusedControlModels=true \
  -PfaceGpuPreprocessing=true -PfaceGpuSampleBytes=true --offline --console=plain
```

`validate_face_effects.py` passed retained rendering, upload ordering, identity,
cancellation, cap, dragon gate, cheek flags, and opaque grin checks.
`validate_face_occlusion.py` passed 99 poses with 478 vertices each and a maximum
Stage round-trip error of `1.1920928955078125e-7` metres. All 63 source assets
match both APKs byte-for-byte; the four latest source digests match the existing
managed build report. Logs and the APK manifest are in
`artifacts/facelandmarker/precommit-20261112/`.

This revision has **not been installed or visually tested in this commit task**.
The earlier same-day headset probe in
[the native occlusion report](FACE_DEPTH_OCCLUSION_2026-11-12.md) used lab APK
`8687279ae6c45b8e672eeec3c81070a81cea65c268b22858b8e65897710358a7`,
which predates the latest effects changes. Its synthetic occlusion result does
not establish wearer acceptance for this newer APK.
