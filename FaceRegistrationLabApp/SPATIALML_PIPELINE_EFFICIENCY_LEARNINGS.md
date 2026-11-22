# SpatialML pipeline efficiency: knowledge-base and skill guidance

**Latest temporal-output extension (2026-11-07):** [Reusable skill/tool handoff and verified case study](SPATIALML_SKILL_TOOL_LEARNINGS_2026-11-07.md) adds independent camera/registration contracts, pose/local-shape smoothing, ROI tracking, balanced lag response, completion/immutable-data rules, and current upload timing. It includes a working timeline summarizer, five tool enhancement contracts and 14 grader cases. The accepted app is checkpoint `bb11e71`; measured values below describe the older November 2 graph and must not be treated as the current performance baseline.

Scope: SpatialML applications whose mode and permissions allow the required readback. These learnings come from the Kotlin face-tracking pipeline, local service source inspection and the November 2, 2026 headset benchmark. The principles apply across SDKs; API names, buffer support, coordinate conventions and measured timings remain version-specific.

**Optimize exposure-to-useful-output latency across SpatialML, readback, app computation and rendering. Read compact results early only when they are final SpatialML outputs for the app. Keep intermediates needed by later SpatialML stages inside SpatialML.**

Contents: [design rules](#reusable-design-rules), [task boundaries](#starting-boundaries-by-task), [evidence](#what-this-investigation-measuredand-what-it-did-not), [skill workflow](#workflow-to-add-to-existing-skills), [integration](#suggested-skill-and-knowledge-base-integration), [sources](#sources-and-reproduction).

## Reusable design rules

1. **Design from the consumer backward.** Establish whether the app needs a pose, boxes, landmarks, a mesh, expression scores or an image. Keep only the stages and outputs required for that result. A pose-only consumer should not pay for a full mesh; a mesh consumer need not receive both raw points and every derived representation.

2. **Budget movement as well as computation.** For each boundary record shape, dtype, bytes, producer/consumer, process, accelerator, copy/map/convert operations, call frequency and synchronization. Distinguish CPU↔accelerator movement inside SpatialML from SpatialML↔app IPC. Logical tensor size is not measured physical traffic; shared memory is not proof of zero-copy processing.

3. **Read back compact final app results, not pipeline intermediates.** First complete the SpatialML stages that consume the data internally. Transfer the final output the app needs, then perform app-owned computation and rendering. Small size alone does not justify readback. Do not export an intermediate for app processing and send it or its derived features back to continue SpatialML execution. If a value is also needed for service tracking, retain and process that dependency internally. There is no universal byte threshold: fixed call, allocation, mapping and wait costs matter too.

4. **Prefer weightless tensor models or compiled app code over hot JavaScript.** A weightless transformation uses tensor operations and fixed constants without trained parameters. In the inspected service, JS calls create a runtime/context and marshal tensor arrays. Static gathers, reshapes, affine math, normalization, masks and reductions are model candidates. Branching, state, filters and small iterative solves are app candidates when their inputs are compact. Camera access, pose lookup, IPC and fences remain native I/O/lifecycle operations. Do not replace one JS operation with hundreds of tiny dispatched operators.

5. **Fuse at a useful boundary.** Prefer attaching compatible fixed postprocessing to an existing model when that preserves efficient delegation. A separate weightless model adds input/output copies, dispatch and synchronization. Tiny concatenations, snapshots or completion tokens seldom justify an independent accelerator model. Compare separate, fused and app implementations; do not move a fast NPU network to GPU merely to join graphs.

6. **Sample the small image before full-frame float conversion.** Feed byte RGB into crop/scale/affine sampling, convert sampled values and normalize the small output. Bilinear interpolation still needs fractional arithmetic: this does not mean every sampling operation is integer-only. Specialize detector and landmark preprocessing when their transforms differ. Preserve channel order, affine direction, half-pixel/coordinate conventions, borders, rounding and normalization.

7. **Prove residency and delegation.** A GPU/NPU target integer, full model delegation or a DynamicTexture flag does not prove shared accelerator buffers between models. Verify the service wrapper and actual runtime. Genuine sharing requires compatible allocation, dtype/layout/row stride, ownership, buffer import and fences. Check CPU fallback and precision as well as execution. Keep service/SDK interop work distinct from app graph changes.

8. **Treat completion and frame identity as part of the data contract.** Snapshot readback may return a previous or partially published result. A current leading sequence is insufficient. Publish completion after all required fields, verify length/version/sequence/configuration, and consume immutable data. Preserve one frame in flight until separately owned buffers and fences are proven. Keep timestamps and identifiers exact and outside reduced-precision model arithmetic.

9. **Preserve temporal and geometric meaning when moving code.** Retain the same source exposure, crop, intrinsics, coordinate basis and capture-time transform. Keep ROI state and prediction needed by later SpatialML crops inside the service, evaluated at the acquired camera timestamp. Move only app-consumed downstream work across the final-output boundary. Lower latency can reduce motion-related misalignment; it cannot establish optical calibration or fix systematic intrinsics/extrinsics errors.

10. **Separate live computation from diagnostics and rendering overhead.** Run large snapshots, byte-crop reconstruction and exports only for selected, frozen frames. A branch inside JS may still pay input marshaling/dispatch. Version app-derived diagnostic data instead of labeling it as service output. Reuse topology, materials and buffers where supported; measure normals, bounds, allocations and upload. Complete an in-flight mesh replacement, then consume the newest frame, so faster inference does not continually cancel rendering.

## Starting boundaries by task

| App consumer | Service work worth retaining | Candidate readback/app work |
| --- | --- | --- |
| Classification or embedding | Preprocessing, inference, optional normalization/top-k | Small result; app behavior |
| Boxes or sparse keypoints | Inference and reduction/decode when raw outputs are large | Compact detections; app tracking/rendering |
| Face/body mesh | Image processing, landmark inference and all required internal consumers, including service tracking and any expression head | Completed landmarks/parameters and requested scores; app-only fitting and mesh |
| Pose only | Full-output validity/reductions plus selected fit points | Sparse fit data and sufficient statistics; app pose solve |
| Dense mask/depth used for display | Inference and required resize/representation conversion | Verified shared texture path where available; avoid raw CPU readback followed by full re-upload |

For face tracking, detector outputs and ROI are intermediates consumed by landmark cropping, so they stay inside SpatialML. Landmarks qualify for readback only as the final app-facing output, with required service tracking and any service-side blendshape computation handled internally. The app can then fit and render the mesh without returning intermediate results to SpatialML. For a detector-only app, completed detections may themselves be final app results.

## What this investigation measured—and what it did not

| Finding | Evidence and limit |
| --- | --- |
| JavaScript dominated this face graph | 24 JS operators: **239.18 ms**, **78.2%** of the 305.99 ms operator budget, on 27 matched eligible face chains with tracing on. Includes wrappers/marshaling; not a universal per-JS cost. |
| A compact final landmark output is a candidate | Raw landmarks are **5,736 bytes**. Proposed landmarks + metadata are **5,992 bytes**, versus the existing **11,976-byte** final packet. Eligibility depends on completing internal service consumers. The new packet and app geometry are **not implemented or benchmarked**. |
| A large service tail warrants optimization | Work after landmark inference is **198.91 ms** in the same traced population. It includes dependencies that must remain in SpatialML; the whole tail is not automatically eligible to move to the app. Replacement/retained work and transfer costs remain unmeasured. |
| Diagnostic work is significant | Crop copies + nested snapshots total **72.75 ms**; **46.22 ms overlaps** the preceding tail. Do not add these as independent savings. |
| RGB-first helped model calls without a consistent full-path gain | Combined preprocessing model means improved **6.51–6.91 ms**; tracing-off submit/readback median was **281.33 ms**, between previous-GPU controls **277.33/295.98 ms**. Component gains alone do not establish product gains. |
| Both RGB-first models executed on GPU | Startup logs show all **48/68 nodes** on OpenCL. Controlled device pixel equivalence and coherent optical/export acceptance remain unverified. |
| Model wrappers still copy | Inspected local service copies Engine inputs/outputs around LiteRT and materializes camera RGB through CPU access. Installed source/binary equivalence and internal copy/kernel timings were not proved. |

The RGB-first change removed a logical **96,036,864-byte** full-frame FP32 tensor. It did not establish that all runtime packing or conversion disappeared. Each model still receives a **24,009,216-byte** full RGB input through the inspected wrapper. DynamicTexture does not remove that copy path; its current local implementation also limits supported formats and tensor ownership.

## Workflow to add to existing skills

Use the following procedure when authoring or optimizing a readback-enabled pipeline:

1. Identify SDK/version/mode, permitted outputs, consumer needs and exact model contracts. Verify facts in the appropriate SDK; Unity documentation cannot validate a Kotlin API spelling.
2. Draw the full dependency path through capture, preprocessing, inference, postprocessing, readback, app processing and upload. Classify every proposed export as a final app output or an internal dependency; keep the latter inside SpatialML.
3. Produce a movement table: `tensor | shape/dtype | bytes | producer → consumer | process/backend | copies/maps | calls/frame | completion/lifetime`. Mark unknown costs for measurement.
4. Measure a representative baseline. Separate tracking, acquisition, no-face, startup and exports. Record exposure-to-upload and useful frame rate alongside operator/model times.
5. Compare viable final-output boundaries, including compact app-consumed results and service-side reduction/fusion alternatives. Reject intermediate readback that later SpatialML work depends on. Include publication, calls, polling and renderer costs. Avoid adding overlapping intervals.
6. Replace hot JS with one useful fused computation or compiled app math. Preserve the algorithm: tie rules, suppression semantics, masks, finite-value handling, normalization and state transitions. Sanitize invalid operands before arithmetic; `NaN * 0` remains NaN.
7. Author portable LiteRT/TFLite transformations using supported tooling, such as PyTorch conversion where appropriate. Inspect the exported graph and test actual delegate coverage/precision; supported operations are runtime-specific. Keep exact timestamps/configuration outside lossy math.
8. Verify serialized/reference math, controlled device tensors, same-frame coherence and downstream output accuracy separately. Pin numerical reference dependencies; investigate version drift instead of weakening tolerances to force a pass.
9. Run tracing-off control → candidate → control windows and separate bounded traces. Retain model/app/runtime provenance, load/thermal state, workload counts and startup failures. A run that fails to initialize or detect the intended workload is not a fast sample.
10. Report what improved at the full-path boundary, what remains expensive and what remains unverified. Promote only after correctness and runtime reliability pass. Restore temporary diagnostics and preserve user captures/configuration.

Required report outputs: selected partition and alternatives; byte/call budget; temporal/tensor contract; numerical/delegation evidence; matched latency distributions and useful output rate; remaining costs and validation boundaries. Distinguish upload acknowledgement from display presentation unless presentation is instrumented.

## Suggested skill and knowledge-base integration

Keep the general rules and workflow in one referenced document; keep versioned measurements in a linked case study. Add a short entry-point instruction to read that reference when selecting a computation/readback boundary. Avoid copying the entire benchmark into every SKILL.md.

| Existing owner | Guidance to add |
| --- | --- |
| SpatialML implementation/authoring | Consumer-first partitioning, final-output-only readback, internal dependency retention, data-movement table, RGB-first sampling, weightless models and explicit temporal contracts |
| SpatialML debugging | Terminal publication versus snapshot availability; stale/mixed packets; delegate/fallback/precision evidence; buffer ownership; initialization failures as separate evidence |
| App performance analysis | Same-population end-to-end timing; calls and bytes; tracing overhead; overlap accounting; repeated controls; app computation/render upload breakdown |
| Kotlin/Unity app integration | SDK-specific app math/render owner, resource reuse, immutable handoff and backpressure; JNI/Burst only in the appropriate SDK |

Suggested skill evaluation cases: (a) a 6 KB final landmark output behind expensive app-only geometry; (b) megabytes of detector intermediates needed by a later SpatialML crop; (c) a request to make every tensor DynamicTexture; (d) a faster model with unchanged frame latency; (e) a current sequence with a stale packet tail; (f) small landmarks still needed by a service-side blendshape head. A successful response must distinguish final app outputs from internal dependencies even when both are small, keep required service work internal, and verify correctness and performance.

This file is a local handoff for knowledge-base and skill integration. It does not modify installed skills or publish to an external knowledge base.

## Sources and reproduction

- [Detailed boundary design and implementation candidates](READBACK_PIPELINE_OPTIMIZATION_2026-11-02.md).
- [Face-only benchmark, all operators and runtime limitations](RGB_FIRST_PIPELINE_BENCHMARK_2026-11-02.md).
- [RGB-first model contracts and reference validation](RGB_FIRST_PREPROCESSING_2026-11-01.md).
- [DynamicTexture and service buffer-copy audit](DYNAMIC_TEXTURE_PIPELINE_ASSESSMENT_2026-11-01.md).
- [Detector fusion algebra and tiny snapshot tradeoffs](GPU_PREPROCESSING_IMPLEMENTATION.md).
- [Historical Unity comparison and native-operator regression](UNITY_OPTIMIZATION_COMPARISON.md); do not pool those times with the Kotlin benchmark.
- [Reproducible byte and timing analysis](tools/analyze_readback_boundary.py) and [recorded analysis](../artifacts/facelandmarker/registration-lab/readback-boundary-design-20261102/boundary-analysis-final-output-only.json). The script checks face-only counts, component reconciliation and overlap; it does not predict a new runtime.
