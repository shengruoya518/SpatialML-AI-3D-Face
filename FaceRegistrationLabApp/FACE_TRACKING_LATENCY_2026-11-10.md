# Face tracking latency — 2026-11-10

The best measured configuration in this run combines **fast streaming pacing and RGB-first GPU preprocessing**. Its two no-face windows measured **31.07–33.06 ms median graph request → app readback** and **60.60–61.26 ms median exposure → app readback**. The repeated control, with fast pacing and the previous preprocessing, measured **34.52–34.70 ms** and **62.75–63.50 ms**, respectively.

**No real face was visible in any comparison window.** These results establish camera/acquisition throughput and result timing. Tracked-face pose latency, jitter, optical accuracy and screen presentation still need a face-in-view run. The helmet's earlier pose application is covered by host scheduling regressions; its visible device branch was not exercised here. There is no claim that an absolute minimum face-tracking latency has been reached.

## Changes

1. `FaceTrackingPacing.FAST` removes the fixed ten-millisecond wait after each completed streaming frame, yielding cooperatively instead. One frame stays in flight. Terminal publication, exact sequence matching, cancellation, the stale-camera watchdog and output/configuration checks remain in place. Calibration evidence uses the legacy scheduling policy.
2. The existing RGB-first preprocessing model omits an explicit full-image `CAST`. The full image has 24,009,216 RGB bytes; its logical float32 intermediate has 96,036,864 bytes. Actual GPU allocation and memory traffic savings were not measured. The image tensor still crosses the service's ordinary copy path.
3. A visible helmet applies its new rigid pose before awaiting the occlusion mesh upload. Both helmet and occluder inherit the same head transform; the previous face-local surface follows that rigid motion until its shape update finishes. First appearance waits for the first measured mesh. Hide, close, cancellation and stale-frame checks still prevent a late upload from restoring visibility. `legacy` preserves the previous order for comparison.
4. Publication/filter clocks now reach the helmet journal, together with separate pose and occlusion completion times. The earlier pose timestamp describes transform setter return; it is distinct from the later mesh upload completion.

The accepted stereo K/D and balanced smoothing parameters are preserved. No trained model, facial topology, helmet asset, inference backend, service APK or recorded calibration was replaced by this task. The RGB-first build flag remains opt-in while GPU pixel/face accuracy acceptance is pending.

## Same-build pacing comparison

Headset `PB311XHGKC220141G`, Spatial SDK 6.1.9, output mask 3: pose plus the anatomical mesh used for helmet occlusion, 6,124 result bytes. All windows have operator tracing disabled. Counts below exclude five transition frames plus unfresh, nonfinite, rejected or calibration-evidence frames.

| Window | Eligible no-face frames | Completions/s | Request → readback median / p95 ms | Exposure → readback median / p95 ms | Gap after readback median ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Legacy before: idle 10 ms, poll 2 ms | 434 | 20.24 | 35.91 / 42.32 | 65.07 / 91.45 | 12.72 |
| Fast: idle 0 ms, poll 2 ms | 570 | 27.61 | 33.64 / 38.29 | 66.50 / 79.45 | 2.22 |
| Eager: idle 0 ms, poll 1 ms | 542 | 24.99 | 36.42 / 48.62 | 68.82 / 86.22 | 2.12 |
| Fast repeat | 596 | 27.79 | 33.66 / 38.66 | 65.09 / 78.88 | 2.08 |
| Legacy after | 448 | 20.74 | 35.27 / 42.23 | 64.98 / 82.87 | 12.20 |

Removing the fixed wait improved completion cadence by about **33–37%**, while median exposure age changed little. Completion cadence counts every packet. Every eligible packet above has a distinct exposure timestamp; the 30 and seven excluded fast packets include unfresh frames and must not count as useful camera updates. A one-millisecond polling interval performed worse in this run and is not selected.

[Raw capture, hashes and preservation receipt](../artifacts/facelandmarker/latency-2026-11-10/comparison-2/manifest.json) · [Statistics](../artifacts/facelandmarker/latency-2026-11-10/comparison-2/summary.json)

## RGB-first comparison with repeated control

Same app source, output mask, pacing, service binary and calibrated geometry. Each app replacement uses a fresh instance of the existing Spatial service process because this ROM has a documented GPU teardown/reuse fault. Two twenty-second windows per configuration; this is a sequential comparison with repeated controls, without a fixed face or isolated system load.

| Configuration | Eligible no-face frames | Completions/s | Request → readback median / p95 ms | Exposure → readback median / p95 ms |
| --- | ---: | ---: | ---: | ---: |
| Previous preprocessing, fast, before 1 | 570 | 27.61 | 33.64 / 38.29 | 66.50 / 79.45 |
| Previous preprocessing, fast, before 2 | 596 | 27.79 | 33.66 / 38.66 | 65.09 / 78.88 |
| RGB-first, fast, window 1 | 616 | 29.30 | 31.07 / 35.85 | 60.60 / 75.74 |
| RGB-first, fast, window 2 | 585 | 26.95 | 33.06 / 43.02 | 61.26 / 80.62 |
| Previous preprocessing, fast, after 1 | 525 | 26.27 | 34.52 / 43.08 | 63.50 / 81.36 |
| Previous preprocessing, fast, after 2 | 550 | 26.13 | 34.70 / 45.66 | 62.75 / 81.60 |

RGB-first had lower median request latency and exposure age than all four fast controls. Tail/cadence variation prevents treating the improvement as a universal fixed saving. The observed exposure-age reduction versus the repeated control is approximately 1.5–2.9 ms. Do not substitute the much larger cadence percentage for latency reduction.

The actual candidate logs show **68/68 landmark preprocessing nodes delegated to one OpenCL partition**. The trained detector and landmark models also have runtime QNN partition/dispatch initialization records. Requested backend alone was not used to infer successful delegation. A QNN-options parsing fallback is present in startup logs; no pipeline initialization, input-buffer, camera-watchdog or app crash failure was observed in the bounded successful comparisons.

[RGB-first capture](../artifacts/facelandmarker/latency-2026-11-10/rgb-first-comparison/manifest.json) · [Repeated control](../artifacts/facelandmarker/latency-2026-11-10/repeated-control/manifest.json) · [Machine-readable comparison table](../artifacts/facelandmarker/latency-2026-11-10/comparison-table.json)

## Validation and final delivery

- Both app modules pass assemble, lint and formatting with the original and RGB-first optimized configurations. Build logs and signed APK hashes are under `artifacts/facelandmarker/latency-2026-11-10/`.
- Twenty-four serialized RGB-first/OpenCV 4.11 reference cases pass the existing maximum-eight-byte/RMS-below-0.5 crop bound. Twenty-four old/new serialized reference outputs match exactly. This is reference math validation; actual GPU pixel parity remains separate.
- Both 1 ms and 2 ms completion policies preserve the terminal barrier. Torn-tail publication, stale packet retries, bounded timeout and cancellation regressions pass.
- The production helmet update passes controlled asynchronous-upload regressions: early visible motion, first appearance, legacy order, hide during upload, close, cancellation and stale rejection.
- Ninety-nine anatomical occluder rotation/scale/expression cases preserve Stage coordinates, with maximum round-trip error `1.192e-7 m`. Existing jitter, outlier, identity/configuration reset and camera/calibration/capture regressions pass.
- Accepted filtering remains at the existing synthetic movement-equivalent delay of `43.256 ms`, with zero stop overshoot. This is a signal-response measurement and is not the filter's execution time or a measured display delay.

Selected registration-lab APK: `d2ec68edaebc4c4310f10c840fea9a4d653aac9c9303dd4428f94e489eb73bc3`. Companion normal-app APK: `a0b0168eaee0269632833336e0585561724b8da715eb55b3a6433c3d8b7a6756`. Only the registration-lab package is installed by this task. Its final installation/liveness/preservation receipt is [final-validation/manifest.json](../artifacts/facelandmarker/latency-2026-11-10/final-validation/manifest.json).

The final selected-build check passes: 420 eligible distinct no-face exposures; request → readback **30.90 / 36.03 ms median/p95**, exposure → readback **60.16 / 75.97 ms**, and **29.26 packet completions/s**. Fifty-one unfresh/rejected frames are excluded from latency statistics. App/Spatial PIDs are 25075/4334 at that receipt. The subsequent [live status](../artifacts/facelandmarker/latency-2026-11-10/final-status.json) verifies `fast`, advancing frames, unlocked/running controls, output mask 3, mode 5 and the effective stereo K/D.

The original 1,140 app files and all 55 recording files were retained through the comparisons. App-file sizes never shrank; recording sizes remained identical. Cached camera-to-head calibration was hash-verified; no app-private face-intrinsics file was present before or after. Spatial service APK SHA-256 remains `482da7ac78ae141bce280e5e45de3b3c771dd61901900294fce893cabf5e1519`. Debug remained unset and leases were released after each focused block.

The long-paused baseline had stopped producing pipeline packets while UI ticks continued. Its full journal and app logs were saved before replacement; the final packet was 4,784.96 seconds older than the final saved UI tick. The process reset recovers that run and does not establish a permanent camera/lifecycle fix.

## Reproduce

Build the selected configuration from the repository root using the existing JDK/trust-store configuration:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home ./gradlew \
  -Djavax.net.ssl.trustStore=/private/tmp/facelandmarker-port/trusted-cacerts \
  -PfaceCompactVstPipeline=true -PfaceFusedControlModels=true \
  -PfaceGpuPreprocessing=true -PfaceGpuSampleBytes=true \
  :FaceLandmarkerApp:assembleDebug :FaceRegistrationLabApp:assembleDebug \
  :FaceLandmarkerApp:lintDebug :FaceRegistrationLabApp:lintDebug \
  :FaceLandmarkerApp:spotlessCheck :FaceRegistrationLabApp:spotlessCheck --console=plain
```

With a face in view, run the repeatable comparison against the installed selected build. Gentle head turns, a static hold and brief disappearance/reappearance exercise the visible pose/mesh path. Use a new output directory each time:

```sh
python3 FaceRegistrationLabApp/tools/benchmark_tracking_latency.py \
  --output artifacts/facelandmarker/latency-2026-11-10/face-validation \
  --seconds 30 --profiles legacy fast eager fast legacy
```

The helper acquires the serial-specific lease, checks for recording/other Spatial clients, separates face/no-face populations, excludes invalid sensor clocks, verifies the journal prefix hash and restores `fast`. `--install <apk>` also preserves/backs up the previous APK and restarts only the existing app/Spatial service processes. It never clears app data, changes the debug property or deletes recordings. Runtime profiles are temporary; FAST is the startup default.

## Remaining larger opportunities

The [saved face-present trace](../artifacts/facelandmarker/operator-readback-2026-11-09/FINDINGS.md) measured VST access at 17.11 ms median, GPU landmark preprocessing at 12.30 ms, landmark inference at 2.62 ms, fused landmark control at 3.29 ms, service graph duration at 42.04 ms, and completion-to-readback at 6.03 ms. Those figures belong to an earlier traced, pose-only population. They cannot be subtracted from this no-face run or added as unrelated percentiles.

The next substantial fix boundary is **service camera-buffer ownership and GPU input binding**, especially `VSTSession::getVstData` and the LiteRT input-copy path. Local source holds the image mutex while locking the camera buffer and materializing RGB; the model wrapper then handles a separate input buffer. Retaining one exposure/stride/fence and sampling directly into a bounded GPU input could remove full-frame materialization while allowing camera publication to continue. It needs same-exposure metadata and proper buffer lifetime; existing retained-VST operators are a starting point, not proof of fast direct GPU import. Simply lowering tensor resolution is unsafe with the current non-square resize and intrinsic-scaling defects.

A useful regression for that service change compares controlled **same-exposure** crop pixels and landmarks against the current path, verifies exposure/K/pose identity and buffers/fences across cancellation and relaunch, then repeats this benchmark with a real moving face. Calibrated overlap, jitter, hide/reappearance, camera freshness and actual presentation timing should be evaluated separately. No service-source edit or replacement was made in this task.

## Tool environment

The CLI environment check was usable with warnings: Node 25.9.0, npm 11.12.1, PICO CLI 0.6.0 (cached update notice for 0.6.1), globally recorded Unity plugin 0.1.0, local app SDK 6.1.9 (root doctor reports no project), knowledge 6.0, emulator/editor not provisioned. Knowledge alignment was not changed. Verified local SDK bindings, source and compiler output were the authority for this scheduling work. Model reference validation used an isolated pinned OpenCV/NumPy environment; shared tool environments were retained.
