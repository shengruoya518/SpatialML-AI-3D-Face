# Dynamic face outputs — 2026-11-02

Implemented in the shared Kotlin sources for Face Landmarker and Face Registration Lab.
Three headset switches select **Face pose**, **Face mesh**, and **Face blendshapes** in
any combination. All start enabled. Turning all off suspends new frame submissions;
turning an output back on resumes with detector acquisition. Switching during tracking
applies to the next complete frame without rebuilding sessions/models or resetting tracking.
Selections last for the current runner session.

The current work is installed and measured on headset PB311XHGKC220141G. See the
[device benchmark](DYNAMIC_FACE_OUTPUTS_BENCHMARK_2026-11-02.md): all seven combinations and
all-off/resume pass; all-three median is 260.38 ms versus pooled old-build controls
348.55/353.77 ms. The dynamic build is left installed with all outputs enabled.
Calibration recordings and camera parameters are preserved; new optical/capture acceptance is pending.

## Execution and ownership

```text
SpatialML: camera → detector/ROI or tracking ROI → landmark model → shared fit/quality/state
                                                               ↓
                         optional weightless blend input → optional blendshape head
                                                               ↓
                         selected compact output → separate terminal completion marker
                                                               ↓
App: validate schema/mask → optional mesh reconstruction → optional Stage conversion → UI/render
```

Detector decode, ROI prediction, tracking state, sparse geometry fitting, `face_pose`, and
`registration_diagnostics` remain in SpatialML. The latter two update validity/tracker state;
disabling the public pose output must not silently remove those internal checks. All raw
landmarks needed by the optional expression head remain inside SpatialML. No result is read
back for processing and uploaded to continue the graph.

For mesh output, the final app handoff includes the measured landmarks, ROI and fit parameters.
The app finishes the full 478-point unprojection and service-to-Stage rendering transform.
This removes `mesh_landmarks`, full `geometry_project`, full `geometry_unproject`, and
`pack_service_result` JavaScript execution from ordinary frames. It avoids transferring both
normalized landmarks and reconstructed vertices. Internal sparse fit operators remain.

When blendshapes are selected, `face_blend_input.tflite` gathers 146 XY pairs directly from raw
model landmarks, inverts the ROI crop, and divides image-pixel coordinates by 1024. The trained
52-score head consumes this internally. When deselected, neither model is submitted.

Seven tiny publication variants each use one CONCATENATION operation to copy only their
required final fields into a schema-2 packet. They and the blend input model explicitly use
**CPU LiteRT (backend 0)**: these small FP32 operations avoid JS array marshaling and another
accelerator transfer. Publication must preserve sequence/timestamp bits; reduced-precision GPU
packing would be unsafe. Host CPU execution and successful installed model calls are verified. In the all-three device
trace, blend input and publication each average about 0.34 ms. Installed delegate partition
attribution remains unverified. This is not a claim of zero-copy execution.

The image preprocessing models remain separate and GPU-selectable with the existing flags.
Both flags still default to false; their device pixel/optical acceptance is unchanged.

## Final-output contract

| Selection | Mask | Packet floats | Readback bytes | Reduction from 11,976 bytes |
| --- | ---: | ---: | ---: | ---: |
| Pose | 1 | 78 | 312 | 97.4% |
| Mesh | 2 | 1,531 | 6,124 | 48.9% |
| Pose + mesh | 3 | 1,531 | 6,124 | 48.9% |
| Blendshapes | 4 | 114 | 456 | 96.2% |
| Pose + blendshapes | 5 | 130 | 520 | 95.7% |
| Mesh + blendshapes | 6 | 1,583 | 6,332 | 47.1% |
| All three | 7 | 1,583 | 6,332 | 47.1% |
| None | 0 | 0 | 0 | No frame submission |

These counts exclude the separate four-byte completion polling response and IPC overhead.
They describe transport size, not predicted latency. Mesh already needs the raw pose internally
for reconstruction, so also exposing pose adds no transport bytes.

All packets begin with command[4], validity[2], ROI[6], diagnostics[32], and capture-camera
matrix[16]. Selected sections follow in order: raw world pose[16] for pose or mesh; raw
landmarks[1434], fit pose[16], first/second scale[1 each], depth[1] for mesh; scores[52] for
blendshapes. The final two floats are schema `2` and the output mask. All values are float32.

`FaceOutputPacket` checks length/schema/mask and rejects nonfinite results as unmeasured.
`FaceFrame.outputs` is immutable. Unselected public arrays are empty; callers must check the
mask before accessing them. The legacy-size array is an app-internal storage adapter only;
unused zeros are not public outputs. Ordinary compact packets are not saved as legacy lab evidence.

Pose is the current raw similarity transform: row-major 4×4, Stage coordinates after rebasing,
translation in metres, basis including the face-fit scale. Mesh uses that same current raw fit.
Blendshape-only results do not require app Stage rebasing. Rendering hides the prior mesh when
mesh is deselected and skips vertex conversion, normals, bounds and resource replacement.

Each publication pipeline ends in the existing one-value completion operator. The runner waits
for this terminal value before reading in **every mode**, including the normal app. One frame
remains in flight through readback and any calibration exports. A leading sequence alone never
authorizes a new submission. Models/pipelines are constructed once and owned by the existing session.

## Calibration compatibility

One check and Full trial automatically force all three outputs while active; output controls
are disabled during capture. Manual queued exports and capture tools use the same full evidence
path. The previous selection resumes afterward. Starting from all-off also works because
calibration demand overrides the idle selection.

These frames retain the original full service mesh, 2,994-float packet, nested snapshots,
exact packet comparison, terminal barrier, immutable presentation tags and marker checks.
Existing capture/export schemas and recorded files are unchanged. Compact results cannot
authorize `submitCapture()`. No new evidence is fabricated for absent outputs.

Lab producer/fit snapshots, diagnostic crop copies, and forced per-frame detection are still
constructed/executed in the lab's shared stages even outside capture. Removing those costs
requires a separate diagnostic-stage split; normal-app timings and lab timings must be compared
separately. This implementation eliminates the large full-mesh snapshot on ordinary lab frames,
but does not claim to remove all diagnostic overhead.

## Evidence and reproduction

Artifacts: `artifacts/facelandmarker/dynamic-outputs/`. Signed, model-hash-verified default
(native preprocessing) APKs are archived under `apks/face-landmarker-dynamic-outputs.apk` and
`apks/registration-lab-dynamic-outputs.apk`. `build-manifest.json` records APK and source hashes;
`build-lint-format.log` contains the final successful gates. No commit or push was made.

- `tools/generate_face_outputs.py` generates eight weightless assets and a hash/shape manifest.
- `tools/validate_face_outputs.py` runs real host CPU LiteRT, then compiles and executes the
  production Kotlin decoder and FaceFrame. 24 fixtures × seven combinations pass. Publication
  is bit-exact, including sequence 100001+ and fractional capture times. Maximum blend input
  absolute difference from the service reference is 2.3841858e-7. Mesh values match the existing
  JS operators exactly at their float32 boundaries in these fixtures (maximum difference 0).
  Coverage includes invalid frames, corrupted packets, schema/mask/length rejection, omitted
  arrays, and immutable configuration through Stage conversion. The production runner selection
  policy also passes all eight masks, capture overrides, locked-switch rejection and restoration.
- `tools/face_pipeline_layout.py` executes the production graph constructor and submit method
  against recording host adapters. All seven masks, acquire/tracking producers, repeat switches,
  native/GPU/RGB-first preprocessing, dependency handles, packet sizes, and calibration routing
  pass. Switching only resets the command tensor, preserving internal tracker state.
- Existing terminal-completion/snapshot/packet-equality and intrinsics/automatic-capture host
  regressions pass, including the 84-export sequence and exposure-motion gates.
- Both apps pass assembleDebug, lintDebug, and spotlessCheck. The SpatialUI style checker reports
  zero errors/warnings. Android lint has zero errors and existing advisory warnings for dependency
  updates, unknown lint IDs, backup rules, icon and a KTX suggestion. One combined formatting/lint
  run briefly reported stale line indentation; rerunning lint against the formatted source and then
  the complete gates passed. The controls reuse the existing Full Space attachment and native Switch
  components; headset layout/interaction remains unverified.

```sh
python3 FaceRegistrationLabApp/tools/generate_face_outputs.py
uv run --no-project --with ai-edge-litert python \
  FaceRegistrationLabApp/tools/validate_face_outputs.py \
  --output artifacts/facelandmarker/dynamic-outputs/model-validation
python3 FaceRegistrationLabApp/tools/face_pipeline_layout.py \
  --output artifacts/facelandmarker/dynamic-outputs/layout \
  --json-jar /private/tmp/face-calibration-tuner/json.jar
```

Tooling check: pico-cli 0.6.0 public, Node 25.9.0/npm 11.12.1; recorded plugin
`pico-unity-agentic-tools@0.1.0`; doctor reports SDK `no-project`, knowledge `6.0`, emulator/editor
not installed. The project itself declares Kotlin SDK 6.1.9. The doctor returned PARTIAL with
Unity/platform and project-context warnings plus a CLI update notice. No tooling was changed.
SDK details for this patch are grounded in installed 6.1.9 AARs, existing bindings, local service
source and builds; the mismatched knowledge server was not used as Kotlin API authority.

## Device measurement and next calibration check

Device measurements validated all seven combinations, all-off/resume, face loss/recovery,
selected packet fields and numerical pose/mesh reconstruction. The DUMP-protected optional
`outputs` command accepts masks 0–7 so `tools/measure_face_outputs.py` can repeat the benchmark;
ordinary headset controls remain device-only. Rapid switch/wearer interaction and calibration
overrides still need an observed check. Run One check and inspect its three exact native exports
before another Full trial. Keep natural small motion allowed.

Compare identical face populations and preprocessing flags against the previous APK. New lab
`pipeline_frame` events include `outputMask`, `resultSchema`, `readbackBytes`,
`calibrationEvidence`, `appDecodeSeconds` and `appRegistrationSeconds`. The decode timing starts
at readback completion and includes frame validation; registration timing also includes freshness
checks and pose lookup. Existing upload acknowledgements remain distinct from compositor presentation.
The device report records service operators, submit/readback, app work and exposure-to-upload
latency for the Registration Lab with native preprocessing. Normal-app tracking reuse and the
experimental GPU preprocessing combination were not measured. No optical-accuracy claim is made.

Sparse-fitting follow-up: [fused weightless model experiment](FUSED_GEOMETRY_MODELS_2026-11-02.md), guarded by `faceFusedGeometry`; see the [full ordered component inventory](PIPELINE_COMPONENT_INVENTORY_2026-11-02.md) for current measured costs.
