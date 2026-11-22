# Preprocessing and camera acquisition breakdown — 2026-11-01

Headset follow-up: [RGB_FIRST_PIPELINE_BENCHMARK_2026-11-02.md](RGB_FIRST_PIPELINE_BENCHMARK_2026-11-02.md) records successful 48/68-node OpenCL execution, 6.51–6.91 ms combined preprocessing-model savings, and no consistent full-pipeline gain against both controls. It lists the current remaining face-only costs. The implementation/host boundary below is historical; numerical GPU and export/optical acceptance remain pending.

These are the face-present registration-lab operator means from the native/GPU/native benchmark after the user-requested OpenMR reset. The GPU preprocessing group includes two lab export operators after the actual preprocessing model. The RGB/pose group includes three operators. Pure GPU kernels and individual VST buffer/conversion phases were not measured separately.

## GPU preprocessing: what accounts for 18 ms

| Operation | Detector mean | Landmark mean | Work |
| --- | ---: | ---: | --- |
| `lab_affine` | 1.63 ms | 1.33 ms | Compose the 2×3 crop affine with the lab's 3×3 image/calibration transform; six output values |
| GPU preprocessing model | 9.78 ms | 9.98 ms | Full RGB input binding/copy, GPU graph invocation and normalized output copy; affine inverse, coordinate generation, bilinear sampling, byte rounding and normalization |
| Native Arithmetic | 2.46 ms | 2.49 ms | Reconstruct byte-scale values: `normalized * 255 + 0.5` over 256×256×3 float values |
| Native Assignment | 4.57 ms | 4.07 ms | Convert/write that float crop to the lab's uint8 crop tensor for export |
| **Total** | **18.44 ms** | **17.87 ms** | Trained detector/landmark inference follows this group and is measured separately |

The last two operators total 7.03 ms for the detector and 6.56 ms for landmarks: **13.59 ms combined**. They are present whenever the lab supplies `sampledRgb`, including idle tracking without a save request. The regular face app supplies no diagnostic crop and omits these operators. It also omits the lab affine wrapper. This is a graph distinction, not a measured normal-app speedup; the regular app was not benchmarked in this run.

Current integration: `FaceLandmarkerApp/src/main/java/com/pico/spatial/ml/sample/facelandmarker/SpatialMLGraphSession.kt:245`; conditional crop reconstruction at line 271. Affine composition: `operators/lab_affine.js`.

## Exact work inside the two weightless models

Both take uint8 RGB `[1,2464,3248,3]` and a FP32 source-to-crop affine `[1,1,1,6]`, and return normalized RGB `[1,256,256,3]`.

1. Cast the full camera image from uint8 to floating point.
2. Slice the affine coefficients and calculate the inverse mapping. The detector uses the axis-aligned scale/translation inverse; landmarks use the full 2×2 determinant/inverse plus translation, supporting a moving rotated face ROI.
3. Use constant destination x/y grids from 0 through 255 to map each crop pixel back into source-image coordinates.
4. Split integer/fractional coordinate parts and quantize interpolation coordinates at 1/32-pixel resolution to reproduce the intended OpenCV-style sampling convention while avoiding the earlier reduced-precision overflow.
5. Concatenate x/y coordinates and bilinearly sample RGB with the GPU `Resampler`, including zero-border behavior.
6. Round the sampled byte-scale values with `floor(pixel + 0.5)` and divide by 255 to produce normalized float model input.

| Serialized operation | Detector | Landmark |
| --- | ---: | ---: |
| CAST | 1 | 1 |
| SLICE | 4 | 6 |
| ADD | 14 | 15 |
| SUB | 5 | 9 |
| MUL | 7 | 16 |
| DIV | 7 | 9 |
| FLOOR | 9 | 11 |
| CONCATENATION | 1 | 1 |
| Resampler | 1 | 1 |
| **Total** | **49** | **69** |

The run confirms all 49/69 nodes delegate to OpenCL, one partition per model. A partition does not establish a single fused GPU kernel; per-node/kernel durations and delegate fusion decisions are unmeasured.

The full source has 8,003,072 pixels. RGB input is **24,009,216 bytes (22.90 MiB)**, while the normalized crop is **786,432 bytes (0.75 MiB)**. The logical full-image FP32 tensor after CAST is 96,036,864 bytes (91.59 MiB); actual allocation/precision/kernel fusion was not measured, so this is a logical tensor size rather than claimed physical GPU traffic.

The inspected local `TFLiteModel::executeInference` copies every Engine input into a LiteRT buffer, obtains host memory or locks/unlocks the buffer as needed, runs the compiled model, then copies its outputs back into Engine tensors. Thus the ~10 ms model operator includes input/output transport and synchronization as well as graph work. The two models bind the same full-resolution image separately: two 24 MB input payloads per frame in that source path. The trained models consume only the 0.75 MiB crop, which helps explain why their ~2 ms operator times are not directly comparable to preprocessing-model time. The current trace does not assign milliseconds to the copy, lock, GPU run or output-copy phases.

Source: `FaceRegistrationLabApp/tools/generate_face_preprocessing.py:138`, and local `Service/OpenMR/app/src/main/cpp/Utils/src/TFLiteModel.cpp:224`.

## RGB camera and pose acquisition: the 12 ms group

| Operator | Native mean | GPU-build mean | Work |
| --- | ---: | ---: | --- |
| `RectifiedVSTAccess` | 9.91 ms | 10.25 ms | Retrieve/materialize the full-resolution left RGB image, timestamp and service intrinsics |
| `lab_camera` | 2.33 ms | 2.31 ms | Validate service K and select/compose the active lab/virtual K |
| `CameraSpaceToWorld` | 0.24 ms | 0.17 ms | Query the camera pose at the VST timestamp and compose the optical-camera extrinsic into a 4×4 matrix |
| **Total** | **12.48 ms** | **12.72 ms** | The pose lookup is a small fraction of this group |

VST access alone has median 9.78/9.83 ms and p95 14.67/15.31 ms in native/GPU traces. These are complete operator spans with diagnostic logging enabled.

`Operator_RectifiedVSTAccess` delegates to `VSTSession::getVstData`. The inspected source path:

1. Acquire lifecycle and image locks and select the latest available camera image.
2. Read its sensor timestamp and underlying `AHardwareBuffer` dimensions/stride.
3. Lock the camera buffer for CPU access.
4. View the left half of the stereo RGBA buffer. Only the requested left eye is materialized; the right output is unbound.
5. Convert full-resolution RGBA to RGB with `cv::cvtColor(..., COLOR_RGBA2RGB)` into the Engine tensor. A 4-channel destination instead uses `copyTo`. A mismatched requested size has a resize path; this app requests matching 3248×2464 dimensions, and no mismatch warning was found in the retained run.
6. Unlock the buffer, fill the nine values of K from cached camera intrinsics, and write the timestamp output.

For one eye, this conversion logically reads **32.01 MB of RGBA** and writes **24.01 MB of RGB**. The operator is doing full pixel materialization rather than returning only a camera handle or pose. Rectification is upstream in the camera stream; this operator's inspected per-frame path performs transport/color conversion and metadata copying. `getVstData` selects the current latest image and has no explicit wait-for-next-frame loop, although lock/buffer synchronization can contribute to its elapsed time.

The trace cannot yet split the ~10 ms among lifecycle/image lock wait, hardware-buffer access, RGBA→RGB conversion and metadata writes. The source exposes those phases but supplies no phase timings in this capture.

`lab_camera.js` operates on small matrices. In Custom/C it supplies the virtual K directly, while its current loops still compute matrix-product values before selecting those outputs. The inspected JS operator creates a QuickJS runtime/context for every invocation, converts tensors to JS arrays, evaluates the script, writes results back, then destroys the runtime/context. Consequently the 2.31 ms is not an isolated 3×3 multiplication benchmark. `lab_affine` has the same wrapper behavior around six output values. Matrix arithmetic and JS lifecycle costs have not been timed independently.

Sources: local `InferenceEngine/src/VSTSession.cpp:127`, `DataPipeline/src/Operator_RectifiedVSTAccess.cpp:91`, `DataPipeline/src/Operator_Cam2World.cpp:43`, `DataPipeline/src/Operator_JSScripting.cpp:160`, and app `operators/lab_camera.js`.

## What to measure or optimize next

- Measure the byte-crop reconstruction only on selected exports, keeping the existing exact frame/snapshot/barrier contract. Its 13.59 ms current combined cost is a removable idle-lab candidate, not a guaranteed end-to-end gain.
- Cache static profile/K and detector-affine work on calibration changes; the landmark affine remains dynamic and can be composed inside its GPU model. Preserve invalid-camera and profile/revision guards.
- Add bounded phase timing around VST mutex wait, hardware-buffer lock, color conversion and unlock, and around LiteRT input copy/lock, compiled run and output copy/lock. This separates bandwidth/transport overhead from GPU sampling math.
- Investigate sharing/importing the camera hardware buffer into GPU preprocessing, performing channel selection there, and reusing the image across both model calls. This could avoid CPU full-image RGB materialization and repeated input payload copies, but the current public binding does not demonstrate that zero-copy contract. It requires a scoped service/API change and validation before any speedup claim.

The operation durations above are current headset evidence. Service-path explanations come from local OpenMR checkout `17f060be`; native binary/source equivalence was not re-established in this follow-up. Source hashes and provenance are retained at `artifacts/facelandmarker/registration-lab/gpu-face-reset-benchmark-20261101-184143/preprocessing-acquisition-source-provenance.json`. No app/service code or device state was changed for this investigation.
