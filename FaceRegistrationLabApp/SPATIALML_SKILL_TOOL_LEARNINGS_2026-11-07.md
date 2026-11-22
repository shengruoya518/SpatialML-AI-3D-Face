# SpatialML skill and tool learnings — 2026-11-07

Scope: the Kotlin Spatial SDK 6.1.9 Face Registration Lab on Swan, checkpoint `bb11e716a2d768ca03da74de6273c9e9a5c380b2`. This saves reusable material for enhancing existing SpatialML authoring/debugging, app integration and performance tools. It does not install or update a plugin. The wearer reports good stereo alignment and good pose/mesh smoothing, followed by improved balanced lag response.

Contents: [Reference](#reference), [Evidence](#verified-case-study-and-limits), [Skill integration](#integration-into-existing-skills), [Tools](#tool-enhancement-handoff), [Evaluation](#evaluation-and-promotion).

## Reference

Use [temporal geometry and final-output guidance](skill_handoff/temporal-output-reference.md) as the concise reusable reference. It covers coherent frame contracts, independent calibration, coordinate/scale semantics, ROI tracking, pose/local-shape filtering, completion fences, immutable handoff, render backpressure and paired latency measurement. Keep this general guidance separate from the numbers below.

## Verified case study and limits

| Learning | Evidence | Limit |
|---|---|---|
| A near-only translation patch did not transfer | A 40 mm downward offset helped close viewing but overcorrected far, according to the wearer. Measured source K plus board-derived rigid D was applied as a pair. | Distance effects can arise from rotation/ray errors; do not infer a universal distance formula or a factory E fault. |
| Independently calibrate the camera, then registration | Existing 22 source board views, nine uniquely posed stereo board exposures and 15 paired face snapshots supported the frozen profile. Board RMS close/middle/far 3.91/0.94/1.46 px; separate face replay mean 8.69 px versus old-current 55.73 px. | Stereo/anatomical observations and physical-origin semantics have uncertainty. Different subjects were visible. This is an effective registration, not accepted factory calibration. |
| Pair K and D with the image affine | `LabStereoCalibration.kt`, mode 5 and `LabPoseCorrection.kt` apply `K_work=A×K_source`, scale 1, and `H_capture×D×E`. Kotlin/JS/fused-model tests check exact constants and vertex/pose inversion. | The preserved C affine is specific to this source. Custom virtual K uses a different input contract and must not be transformed twice. |
| Detector-per-frame behavior can defeat steady tracking | The first smoothing journal contained 2,474 positive detector frames. Normal-view ROI tracking was enabled; the later journal has 1,319 accepted tracking frames and 55 detection frames. | These are workload counts, not a controlled causal latency comparison or distinct-person counts. Diagnostics still intentionally force detection. |
| Whole-mesh adaptive smoothing opened too often | V1 median alpha 0.785; 47.4% of filtered frames exceeded 0.8. It reset straight to 86 large same-track jumps. | These logs do not distinguish every real movement from bad fits. |
| Separate rigid pose and local shape | V2 filters Stage translation/quaternion/similarity scale separately from face-local deformation. The wearer reported that it works really well. | Raw measured frames and exports remain untouched; held presentation output is labelled. UI feedback is not instrumented physical ground truth. |
| Balanced response is a measurable tradeoff | At 18 Hz synthetic noise: v2 RMS 0.4387 of raw, equivalent movement lag 69.17 ms; balanced RMS 0.4893, lag 43.26 ms; faster RMS 0.5404, lag 31.19 ms. Balanced stop test has zero overshoot. | Synthetic movement error divided by known speed is equivalent filter delay, not end-to-end latency. Balanced uses derivative 1.5 Hz, translation coefficient 12, angular coefficient 2.5; no prediction. These values are not universal defaults. |
| Final packet size is not the whole latency story | Current all-output result is 6,332 bytes. On 1,319 accepted tracking frames: submission→readback median 40.98 ms; camera age 70.81 ms; readback→visible upload acknowledgement 18.89 ms; exposure→upload 90.86 ms. | Quantiles are not additive. Upload acknowledgement is not compositor presentation. The 19 ms includes filtering/preparation/scheduling, not just transfer. |
| Some CPU work is already cheap | Current decode median 0.465 ms and Stage registration 0.579 ms. The renderer still converts coordinates, allocates vector lists, computes normals/bounds and replaces a mesh resource. | Renderer substages are not separately measured. Proposed caching, background preparation and unlit-normal skipping are not deployed speedups. |
| Audit build flags and logical image movement | Current accepted build has GPU preprocessing but byte-first sampling disabled. Byte-first avoids an explicit full-frame FP32 CAST; source RGB is about 24 MB and a full float image about 96 MB. | Earlier byte-first model-call gains did not consistently improve full-path latency. Logical tensor elimination does not prove elimination of delegate packing/copies. |
| Completion transport deserves a call budget | The current helper reads/maps/unmaps a four-byte marker every 2 ms, then reads the final packet. | Current data does not isolate marker IPC cost. A callback/fence requires verified SDK support; retaining an unfenced mapped buffer is unsafe to assume. |
| Runtime reliability matters to promotion | Reused SpatialML GPU state produced `LiteRt create input buffer failed`; a fresh exclusively owned service process recovered the same binary. Install receipts check APK identity, saved calibration and existing recordings. | This establishes a service-reuse association/recovery boundary, not an exact LiteRT allocator root cause. Empty service bindings and zero-exit missing-file messages must be handled. |

The accepted installed balanced APK is `e430972fc9759f05ef39a782d91c5bc3d4776ec6a80a742cf374189a7ea26764`. Build/lint/format, filter/calibration regression and staged model/APK parity passed at checkpoint `bb11e71`. Installed startup checks had no face; later current-session telemetry verifies normal tracking/filter operation. Subsequent performance suggestions have not changed the app.

Primary sources:

- [MediaPipe first-principles audit](MEDIAPIPE_TRANSFORM_AUDIT_2026-11-05.md) and [frozen effective calibration](calibration/stereo-face-existing-data-2026-11-06.json).
- [Final calibration evidence](../artifacts/facelandmarker/registration-lab/final-calibration-existing-2026-11-06/FINDINGS.md).
- [V2 implementation, tests and deployment](../artifacts/facelandmarker/registration-lab/pose-mesh-stabilization-2026-11-07/IMPLEMENTATION.md).
- [Balanced implementation, tests and deployment](../artifacts/facelandmarker/registration-lab/balanced-lag-2026-11-07/IMPLEMENTATION.md).
- [Current paired performance analysis](../artifacts/facelandmarker/registration-lab/pipeline-speed-review-2026-11-07/FINDINGS.md).
- [Earlier compact/fused operator trace](COMPACT_FUSED_CONTROL_PIPELINE_2026-11-03.md), [RGB-first comparison](RGB_FIRST_PIPELINE_BENCHMARK_2026-11-02.md) and [retained-tile experiment](PREFERRED_RETAINED_VST_BENCHMARK_2026-11-03.md). These are different versions/populations.

## Integration into existing skills

| Owner | Concrete reference change | Evaluation focus |
|---|---|---|
| SpatialML implementation/authoring | Link the temporal-output reference from camera→model, geometry placement and readback partitioning. Require source/working K and frame revision contracts. | Double-affine errors, mixed frames and false final-output boundaries. |
| SpatialML debugging | Add completion versus snapshot checks, producer/configuration identity and explicit raw/display distinction. Record initialization failures separately. | Current prefix with stale tail, hidden outputs, held pose mistaken for measurement. |
| Kotlin/Unity integration | Describe app-specific pose/local-shape filtering and one-upload-in-flight/latest-pending handoff. Keep SDK APIs and render owners separate. | Quaternion resets, capture exports, cancellation starvation, nonidentity parents. |
| Performance analysis | Add paired upload timing and polling call counts to stage/byte budgets. Allow bounded reviews of already authorized existing evidence; follow capture workflow when new traces are needed. | Nonadditive percentiles, mixed populations, kernel gains without product gains. |
| Device operation | Reuse known authorization/target context while refreshing device state. Check bound clients, installed artifact hashes and preservation; distinguish missing content from exit code. | Shared-device isolation, empty client lists, app data preservation. |

Suggested short insertion into the SpatialML implementation reference:

> For camera-derived pose/mesh or temporal-output problems, read the temporal-output reference before changing coordinates, filters or readback boundaries. Keep a coherent source-image/K/capture-pose/configuration/completion tuple, preserve raw measurements, and measure through useful renderer output.

Do not duplicate this entire case study in every SKILL.md. Put the general reference in the maintained plugin source and link versioned evidence/evaluations. Plugin cache edits alone are not a durable distribution change.

## Tool enhancement handoff

[Machine-readable contracts](skill_handoff/tool-enhancement-contracts.json) define five concrete improvements and their acceptance checks. One local reference tool is implemented: [summarize_runtime_timeline.py](tools/summarize_runtime_timeline.py). It uses only Python's standard library, reads an existing single-session journal and never contacts a device.

```sh
python3 FaceRegistrationLabApp/tools/summarize_runtime_timeline.py   --timeline artifacts/facelandmarker/registration-lab/pipeline-speed-review-2026-11-07/timeline.jsonl   --output artifacts/facelandmarker/registration-lab/skill-tool-learnings-2026-11-07/runtime-report.json
```

[Boundary tests](tools/validate_runtime_timeline_summary.py) exercise paired clocks, hidden/omitted outputs, duplicate/ambiguous acknowledgements and invalid/partial input. The tool hashes its input, separates workload/output/evidence populations, rejects duplicate packet identities for timing, requires a unique matching capture/correction acknowledgement for uploads, reports exclusions/warnings, and rejects partial/nonfinite JSON. It records both cadence and readback→next-submission gaps. It reports actual distributions and never adds percentile rows into a fabricated budget. Version 1 accepts the current lab schema; generic CLI adoption should use explicit SDK/app adapters, calibration/configuration dimensions and upload substage instrumentation.

The existing [pose/mesh validator](tools/validate_pose_mesh_stabilization.py) and [calibration/packet validator](tools/validate_intrinsics.py) provide production-code examples for temporal filter and geometric-contract checks. Keep their project-specific fixtures separate from generic plugin tests.

## Evaluation and promotion

[Evaluation cases](skill_handoff/evaluation-cases.json) cover plausible prompts, minimal fixture requirements, expected checks and disallowed claims. Keep expected checks with the grader; pass only prompts and raw fixtures to forward-test agents. These new cases are saved evaluation material, not claimed to have passed a fresh skill-agent evaluation.

Promote an enhancement when its contract checks pass on coherent data, the intended workload runs on the target SDK/device, end-to-end results improve under suitable controls, and accepted calibration/presentation behavior remains valid. Prefer measured evidence to a target-backend flag or successful startup alone. Preserve originals and add the new learning as a versioned case study rather than overwriting historical evidence.
