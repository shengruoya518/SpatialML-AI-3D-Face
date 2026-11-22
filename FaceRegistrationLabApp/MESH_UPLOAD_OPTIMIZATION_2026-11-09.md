# Background face mesh preparation and upload timing

**Latest live face capture (15:21–15:22 PST):** [Full measured breakdown](../artifacts/facelandmarker/registration-lab/performance-capture-2026-11-09/session-output-20261109-232150/FINDINGS.md). A 60.53s window supplies673 paired tracking uploads: readback-to-ack19.50/27.97ms median/p95, SDK call9.26/15.76ms, numeric preparation0.183/0.850ms. Full-session1577 tracking uploads give17.30/27.37ms. Current measurements show run-to-run variation; the historical comparison is not controlled A/B. Same APK/service/calibration; no restart or camera probe.

**Latest measured state:** the complete November 9 session now contains 11,022 face uploads. Across 10,962 admitted tracking/wireframe/balanced replacements, readback-to-scene-ack is **15.72 ms median / 23.29 ms p95**, SDK call **7.34/11.37 ms**, and numeric preparation **0.171/0.515 ms**. This is an observed comparison with the historical 18.89/33.86 ms, not matched A/B attribution. [Complete performance and repeated service-failure report](SPATIAL_SERVICE_REPEAT_FAILURE_2026-11-09.md). The later running pipeline stopped for an unresolved reason and app relaunch repeated the LiteRT allocation error; failed state is preserved. The initial startup/no-face observations below are historical snapshots, not the latest performance population or device state.

The first rendering optimization is implemented and host-validated. Per-frame numeric mesh preparation now runs on a worker immediately before the serialized SDK upload. Unlit wireframe, markers and projection-reference geometry omit normals; shaded solid geometry retains them. The balanced pose/shape filter and stereo calibration are unchanged.

**Runtime status: INSTALLED; startup verified.** After the headset was connected, the archived APK was installed and hash-verified on `PB311XHGKC220141G` (expected Swan ROM), with app PID 10679 and session `2026-11-09T20-11-57.038184Z-7e1c56`. The startup snapshot contains 51 finite pipeline frames, zero rejection and exact stereo K/D; none contains a face, so dynamic mesh upload latency and visual acceptance are still pending. The screenshot shows POS STEREO and Mesh smoothing On. The crash buffer is empty. All 1,129 existing app files and 54 recordings remain present by path/size; private calibration hashes are unchanged. The previous APK is backed up, the service APK is unchanged, no service restart was requested, and the lease is released. [Installation receipt](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/install/installation.json). The historical tracking baseline remains **18.89 ms median / 33.86 ms p95** from readback to the app's scene acknowledgement. That endpoint includes the UI coroutine's return from SDK upload; it is not compositor presentation.

A later [hash-verified runtime snapshot](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/runtime-window-1/capture.json) contains **2,003 finite pipeline frames, zero rejections, exact stereo K/D and an empty crash buffer**. No face was in view and there are zero mesh-upload timing events. The app remains running for the wearer's face test; the device lease is released.

## Later service relaunch failure

A subsequent app launch failed before inference with the known GPU input-buffer initialization error under a reused Spatial service. The same APK is now recovered under a fresh Spatial service process; see [failure, recovery and permanent-fix boundary](MESH_UPLOAD_SERVICE_RELAUNCH_2026-11-09.md). This supersedes the earlier session/PID as the current running state. Upload performance remains unmeasured because no face was visible during the recovered run.

## Changes

- `FaceMeshScene.kt` samples the four native Stage-to-owner basis points on the UI thread, then sends the copied numeric transform to `Dispatchers.IO`. Marker/reference construction, vertex extraction/conversion, normal calculation, bounds, UV construction and MeshModel creation run in that worker, immediately followed by SDK create/replace. It introduces no extra preparation-to-upload dispatcher hop.
- `FaceMeshPreparation.kt` performs direct scalar coordinate arithmetic, constructs only the final SDK position vectors, and computes bounds in one pass. Normal accumulation reuses private scratch storage. Published position/normal lists are fresh and never recycled while the SDK might consume them. Normal face triangles and marker triangles retain their shared static topology. Sequence-dependent projection-reference geometry remains generated per frame.
- The existing StateFlow collector completes each upload and then consumes the latest frame. A scene mutex also protects against overlapping updates during coroutine replacement, including reuse of scratch storage. Native replacements are not cancelled mid-call. Cancellation is checked after preparation and before upload, and after return before scene acknowledgement.
- Scene closure defers closing an in-flight mesh resource until the worker exits. A wireframe-to-solid switch waits for an upload containing normals before making the solid mesh visible, including switches during an upload. No-face, mesh-off and automatic clean phases still hide the face.
- `FaceLandmarkerRunner.kt` timestamps filtering and publication. `FaceRegistrationLab.kt` emits a frame-paired `mesh_upload_timing` event after the existing `scene_update_complete` event. Raw packets, capture-time registration, correction matrices and capture acknowledgement semantics are retained.

The four native owner conversion calls remain per-frame. A nonidentity SpatialView parent is supported; caching needs a verified invalidation signal for parent/Stage/recenter changes. Pose/shape separation in the renderer, inference pacing, trained models and preprocessing are outside this increment.

## Timing contract

The new event uses monotonic seconds from `System.nanoTime()`, plus frame sequence, capture/readback clocks, styles, geometry counts and create/replace operation. Its publication object is set once before the frame enters StateFlow.

| Report metric | Boundary |
|---|---|
| `post_registration_ms` | Registered frame to filtering start; includes current journal/automatic bookkeeping |
| `smoothing_ms` | Filter start to completion, including presentation-frame construction |
| `publication_to_collector_ms` | Publication timestamp to UI collector receipt |
| `serialization_wait_ms` | Collector receipt to ownership of the scene update |
| `owner_basis_snapshot_ms` | Four native conversion calls and copied affine basis |
| `worker_scheduling_ms` | Dispatch to the start of the worker |
| `mesh_preparation_ms` | Worker start to finished numeric mesh, before SDK invocation |
| `coordinate_ms`, `normals_ms`, `bounds_ms` | Numeric preparation subtimers; included in mesh preparation |
| `other_preparation_ms` | Remaining preparation, including packet/topology/reference/UV/model construction |
| `sdk_upload_call_ms` | SDK create/replace invocation to return, including SDK scheduling, adaptation and blocking replacement |
| `ui_resume_wait_ms` | SDK return to resumption of the UI coroutine |
| `scene_finalize_ms` | UI resume through material/visibility updates and reference round-trip checks |
| `readback_to_sdk_return_ms` | Readback to SDK call return, before UI resume |
| `readback_to_scene_ack_ms` | Readback to the preserved app scene acknowledgement; comparable to the historical endpoint |

The report includes smaller intervening bookkeeping spans so the ordered boundaries reconcile per frame. Quantiles of different spans are not additive. CPU time spent filtering differs from the filter's temporal response lag. The SDK interval does not isolate native GPU work, and neither endpoint measures presentation on screen. Journal instrumentation has overhead; measure the final instrumented build before attributing a speedup.

## Validation

Evidence: [artifact directory](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/), [build manifest](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/build-manifest.json), [final build log](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/build-final.log).

- Both face apps pass assemble, Android lint and Spotless checks with `faceCompactVstPipeline=true`, `faceFusedControlModels=true`, `faceGpuPreprocessing=true`; `faceGpuSampleBytes=false` remains the default, matching the balanced baseline. Final Gradle gate: **BUILD SUCCESSFUL**.
- [Production mesh/scene host regression](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/mesh-validation/validation.json): 80 numerical cases against independent previous-coordinate/normal math, degenerate triangles, one-pass bounds and scratch reuse across topology changes. SDK adapters assert UI-only entity access and worker-only mesh calls. Solid/wireframe/marker/reference/board/hidden paths, rejected SDK replacement, cancellation with a queued update, style switching during upload and close-during-upload pass. Maximum simultaneous SDK uploads: **1**. Adapters do not prove native SDK behavior.
- Existing `validate_intrinsics.py` passes, including exact stereo K/D, every vertex/pose under recorded roll, raw-reference inverse, original packet immutability, capture gates and restoration.
- Existing `validate_pose_mesh_stabilization.py` passes. Balanced coefficients and response are unchanged: synthetic equivalent translation lag remains approximately 43.26 ms, separately from CPU/upload timing.
- `validate_mesh_upload_summary.py` passes boundary/join checks, missing/duplicate event rejection, invalid clocks, workload exclusions, style transitions and old-journal handling. Running the new summarizer on the 6,114-packet historical journal reports zero new upload-timing events and no fabricated stage measurements.
- `git diff --check` passes. Pre-existing documentation, skill-handoff and runtime-summary changes were preserved. No commit was made.

Host commands (from repository root):

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
JAVA_TOOL_OPTIONS=-Djavax.net.ssl.trustStore=/private/tmp/facelandmarker-port/trusted-cacerts \
./gradlew :FaceLandmarkerApp:assembleDebug :FaceRegistrationLabApp:assembleDebug \
  :FaceLandmarkerApp:lintDebug :FaceRegistrationLabApp:lintDebug \
  :FaceLandmarkerApp:spotlessCheck :FaceRegistrationLabApp:spotlessCheck \
  -PfaceCompactVstPipeline=true -PfaceFusedControlModels=true \
  -PfaceGpuPreprocessing=true --console=plain

python3 FaceRegistrationLabApp/tools/validate_mesh_upload.py \
  --json-jar artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/json-20240303.jar \
  --output artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/mesh-validation
python3 FaceRegistrationLabApp/tools/validate_mesh_upload_summary.py
```

The JSON JAR for host validators is org.json 20240303 from Maven Central. It is not packaged into either app. The remembered temporary JAR had been removed and was refreshed inside this artifact directory.

Environment preflight reported Node 25.9.0 / npm 11.12.1, CLI 0.6.0 public (0.6.1 available), recorded plugin `pico-unity-agentic-tools@0.1.0`, SDK `no-project`, knowledge 6.0, emulator/editor not installed. The multi-module repo actually declares Spatial BOM 6.1.9 and the Gradle builds succeed. The knowledge query returned Unity documentation, so Kotlin API decisions use the local SDK source and compilation, not that query. No CLI, plugin, SDK or environment upgrade was made.

## Headset acceptance and next decision

The archived lab APK is [registrationlab-1.0-debug.apk](../artifacts/facelandmarker/registration-lab/mesh-upload-optimization-2026-11-09/registrationlab-1.0-debug.apk), SHA-256 `5b937e029ab4ea28089237af00cc747511c77bb2493035d669260975af56d4df`. The manifest records the normal app APK and source hashes as well.

The archived APK is now installed on `PB311XHGKC220141G`. For follow-up observation, hold a focused devmux lease and verify the same installed hash/session. Preserve app data, private calibration and recordings. Do not clear data or restart/replace the SpatialML service as an implicit part of this optimization.

For useful acceptance, observe a face during normal tracking with all outputs, balanced smoothing, stereo registration and green wireframe. Check solid-to-wireframe-to-solid switching, output off/on, lost/reacquired tracking and Stage close/reopen. Retain the existing reference round-trip check and verify native unlit rendering with absent normals. No new calibration collection is required for the performance comparison.

Pull the complete session journal and run:

```sh
python3 FaceRegistrationLabApp/tools/summarize_mesh_upload.py path/to/timeline.jsonl \
  --output path/to/mesh-upload-summary.json
```

The report excludes warmup (first 20 sequences), rejected/unfresh/nonfinite/nonface/evidence/no-mesh frames, hidden/style-transition uploads, duplicate identities and mismatched clocks. Detection and tracking, output masks, styles, filter profiles and create/replace operations remain separate. Every metric in a group uses the same admitted frame population.

Compare the tracking/wireframe/balanced/replace group's `readback_to_scene_ack_ms` against the historical **18.89 / 33.86 ms**, and retain population counts and inference timings to expose workload changes. A matched before/after face workload on the same headset is required to attribute a speedup. Then choose the next change from the measured cost:

- Dominant SDK call: investigate the face-local mesh plus entity-pose renderer and supported positions-only updates.
- Dominant owner snapshot: establish Stage/parent invalidation before caching its transform.
- Dominant scheduling/UI resume: inspect dispatcher and UI workload before changing inference or filter settings.
