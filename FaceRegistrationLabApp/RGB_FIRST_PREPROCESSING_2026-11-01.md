# RGB-first preprocessing experiment — 2026-11-01

Headset follow-up: [RGB_FIRST_PIPELINE_BENCHMARK_2026-11-02.md](RGB_FIRST_PIPELINE_BENCHMARK_2026-11-02.md) records successful 48/68-node OpenCL execution, 6.51–6.91 ms combined preprocessing-model savings, and no consistent full-pipeline gain against both controls. It lists the current remaining face-only costs. The implementation/host boundary below is historical; numerical GPU and export/optical acceptance remain pending.

Implemented a separate detector/landmark model pair that samples the uint8 RGB source directly, preserving float conversion for sampled values and the small normalized output. The original benchmarked models and their manifest remain byte-for-byte unchanged. Default builds still use native preprocessing; selecting the existing GPU experiment still uses the benchmarked full-frame-CAST pair unless the additional RGB-first property is enabled.

## Changed operation order

Before: uint8 full frame → full-frame CAST to float → inverse-affine sampling → crop byte rounding → normalization.

RGB-first: uint8 full frame → inverse-affine Resampler reading selected byte pixels as float → crop byte rounding → normalization.

Bilinear interpolation requires fractional arithmetic. The Resampler kernel reads the four neighboring source pixels as floating-point values for each output location; conversion occurs at those sampled reads. This removes the explicit full-frame CAST without adding an intermediate rounded uint8 resample or a second interpolation stage. Output remains FP32 RGB `[1,256,256,3]` with the same quantized coordinates, zero borders, sampled-value rounding and normalization.

The detector retains its axis-aligned/profile affine. Landmarks retain the full moving/rotated ROI affine. Camera tensor shape/encoding, channel order, pose and timestamp association, trained models, decode/ROI, geometry, exact packets, terminal completion and lab export bindings are unchanged.

| Model | Operations | File bytes | Source/input → output |
| --- | ---: | ---: | --- |
| `detector_preprocess_rgb_gpu.tflite` | 48 | 17,196 | uint8 RGB `[1,2464,3248,3]` + FP32 affine → normalized FP32 RGB `[1,256,256,3]` |
| `landmark_preprocess_rgb_gpu.tflite` | 68 | 11,976 | Same contract, general affine |

Each model has one fewer node than its benchmarked counterpart and no full-resolution floating-point tensor. The removed logical FP32 image is 96,036,864 bytes (91.59 MiB). This is a graph/tensor-size change, not a measured GPU allocation or bandwidth saving. Actual delegate buffer packing, input conversion, precision and fusion still require device measurement.

The service's full uint8 input copies remain: each preprocessing model still binds a 24,009,216-byte RGB image. The lab's normalized-to-byte arithmetic/Assignment copies also remain. Thus this change addresses operation order without assigning the earlier ~10 ms model-call time entirely to CAST or claiming a measured speedup.

## Integration and build selection

`SpatialMLGraphSession.preprocess` selects the two new assets only when GPU preprocessing and byte sampling are both enabled. The runner logs `rgb_first=true`. Build both apps with:

```sh
./gradlew -PfaceGpuPreprocessing=true -PfaceGpuSampleBytes=true :FaceLandmarkerApp:assembleDebug :FaceRegistrationLabApp:assembleDebug
```

The new model metadata is `model/preprocessing_rgb_models.json`. `generate_face_preprocessing.py --sample-bytes` deterministically creates the separate pair; it does not overwrite the prior model/manifest names. `face_pipeline_layout.py` now records native, benchmarked GPU and RGB-first variants using the actual production constructor.

Archived, signed RGB-first APKs are under `artifacts/facelandmarker/registration-lab/rgb-first-preprocessing-20261102-011145/apks/`. Registration-lab APK SHA-256: `066ea92b5bb14ac1e042c2f6dc3876e08537cb62b1c5e79a4813728f995f5087`. Normal face APK SHA-256: `f297ca81400c20333fd936c73a1055852d9f457acc140a3dae9a74eacc0e7a6d`. Packaged model hashes and both signatures verify. Standard Gradle outputs are returned to default native after archiving; use the archive or explicit properties for this experiment.

## Validation completed

- Both new models have uint8 Resampler source input, 48/68 operators, no CAST node and no full-resolution float tensor.
- All 24 serialized-model/OpenCV 4.11.0 gradient/noise, profile, rotated-ROI and border reference cases pass the existing maximum-8-byte/RMS-below-0.5 bound. Outputs remain finite, bounded and consistent with byte reconstruction/normalization.
- The old/new serialized reference outputs match exactly on one detector and two rotated/border landmark RGB-noise fixtures. This is reference math parity, not GPU pixel parity.
- Both direct-byte models compile on Mac Metal. Host uint8 input-buffer allocation fails with the previously observed unsupported element type/code-5 boundary before execution; zero GPU pixel comparisons completed. This does not establish Android OpenCL acceptance or correctness.
- RGB-first builds for both apps pass assembleDebug, lintDebug and spotlessCheck. Signatures and packaged model hashes verify.
- Actual graph construction records the separate new model names/bindings. Lab detector/fit/mesh remain 11/20/8 outer operators because diagnostic byte crops are retained. Normal detector/fit remain 6/16.
- Existing production terminal-completion, packet equality, stale-frame/mode, snapshot decode, motion and measured-profile/ROM regressions pass.

The host's current pySpatialML environment uses OpenCV 5.0/NumPy 2.5; its sampler differs from the recorded OpenCV 4.11 fixture. The benchmarked old and new reference outputs were identical on the affected case and both exceeded the older RMS threshold against OpenCV 5.0. Validation therefore used an isolated pinned OpenCV 4.11.0/NumPy 2.2.6 environment without weakening the existing bounds or changing the shared tool environment. That check is retained in `current-opencv-baseline-check.json`.

## Headset validation boundary

PB311XHGKC220141G is disconnected. No APK was installed, service stopped/restarted, capture begun, profile changed or device data altered for this increment. No commit or push.

When connected, first verify devmux ownership, idle calibration/recording state and the installed rollback APK/hash. Retain all data. Install the archived experiment only during an idle diagnostic window, capture startup logs from before launch, and verify both new models' OpenCL coverage and actual byte-source behavior. Compare controlled same-source crops/normalized inputs and face outputs with the benchmarked pair, then measure face-present tracing-off and operator windows with native restoration. The prior GPU input-buffer lifecycle failure remains relevant; preserve any recurrence as separate failure evidence rather than treating it as timing data.

The next performance comparison must separate the ~10 ms model operator into input-copy/buffer access, compiled run and output-copy phases where available. A graph-level CAST removal is not proof that the runtime avoids all full-image float packing. The registration lab's immutable snapshot/packet and calibrated affine contracts remain acceptance requirements before promotion or another full calibration trial.

Artifacts and reproducible checks: `artifacts/facelandmarker/registration-lab/rgb-first-preprocessing-20261102-011145/`, including models/probes, structure/parity, pinned OpenCV reference, host GPU compile result, all three constructor layouts, runtime fixtures, preserved benchmark model hashes and signed build manifest.
