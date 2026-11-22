# A/D face-registration trial results

The new trial strongly supports correcting the source-camera intrinsics. It does not yet establish complete physical face/VST alignment. Mode D already implements the measured candidate in the lab; the normal face sample still uses service intrinsics. The latest two face exports are internally consistent through native fitting, packing and camera-to-Stage conversion.

**Subsequent visual evidence:** the newer 09:42 recording and wearer assessment favor C; D made overlap worse. C remains slightly small/high, similarly in both eyes. [MODE_C_REFINEMENT_FINDINGS.md](MODE_C_REFINEMENT_FINDINGS.md) updates the next experiment. The independent board measurements below remain valid; they do not establish D as the physically aligned face model.

The headset used 2026-10-29 CST filenames; this report uses the project's 2026-10-28 Los Angeles date. Evidence is under [trial-results-2026-10-28](../artifacts/facelandmarker/registration-lab/trial-results-2026-10-28/). Start with [FOV_2D_TO_3D_FINDINGS.md](FOV_2D_TO_3D_FINDINGS.md) for the complete math and [VALIDATION.md](VALIDATION.md) for build/install boundaries.

## Independent camera check

Three new Mode A checkerboard images contain all 48 detectable internal corners. The measured candidate was fixed before these views were collected; this check fits each board pose without refitting intrinsics.

| New view | Measured K RMS, saved pixels | Service K RMS, saved pixels |
|---|---:|---:|
| 001 | 0.3203 | 3.1183 |
| 002 | 0.5421 | 5.4032 |
| 003 | 0.4871 | 2.0869 |
| Pooled | **0.4596** | **3.7980** |

The candidate gives 8.26 times lower RMS. Saved images are 1624×1232, uniformly half the native 3248×2464 image. This independently strengthens the camera-intrinsics finding from the original board session. Three held-out images do not provide a complete new camera/extrinsic calibration.

| Native source parameter | Service K | Measured candidate K |
|---|---:|---:|
| fx | 2065.589844 | 2642.704699 |
| fy | 2089.435547 | 2036.955265 |
| cx | 1623.500000 | 1672.376919 |
| cy | 1231.500000 | 1230.337555 |
| Horizontal pinhole FOV | 76.350° | 63.131° |
| Vertical pinhole FOV | 61.050° | 62.333° |

The largest correction is horizontal focal length, +27.94%. These are source-camera FOV values, not display/per-eye FOV measurements. After the lab's image resampling, geometry must use `K_virtual = A_img × K_source`. Mode D preserves B's affine and produces virtual fx/fy/cx/cy approximately 2027.880/2036.955/1661.006/1230.338.

## Positive face geometry

Only two finalized face exports were returned: A, left-facing at approximately 1 m, and D, frontal at approximately 2 m. The recordings show additional A/D attempts. Missing files reflect incomplete/disabled saves, not an absence of user comparisons.

| Check | A, sequence 85 | D, sequence 155 |
|---|---:|---:|
| Head translation near exposure | 0.396 mm | 0.819 mm |
| Native fit/mesh metric RMS | 0.00000386 cm | 0.00000595 cm |
| Shipped pack replay / native vertex RMS | 0.0000343 mm | 0.0000675 mm |
| Direct camera-to-Stage invariant RMS | 0.000101 mm | 0.000142 mm |
| Source reprojection RMS | 0.0000444 native px | 0.0001583 native px |
| Inferred median camera depth | 1.288 m | 2.213 m |

Producer, fit and mesh snapshots match. Native first/second scales and fitted camera poses closely match host SVD. For these two samples, the full packed path agrees with the direct invariant at lab size 1:

```text
V_Stage = H_capture × E_camera_to_head × (P_camera_cm / 100)
```

This verifies internal transform consistency on the saved samples. It does not measure the correctness of H's physical timing, E's optical registration, K's complete calibration or monocular face depth. The two poses/distances differ, so their depth values do not quantify an A/D improvement. Earlier four inconsistent native exports remain an intermittent issue with an unproven cause; two coherent new samples do not establish universal resolution.

The A exposure passes the ±50 ms motion gate despite 11.87 mm movement later during export. The D exposure also passes. This supports keeping exposure motion separate from diagnostic export motion.

## Recording observations and capture limitation

Four recordings were retrieved: the main face sequence, a board/recovery/menu sequence, a short recorder-control clip, and the main board sequence. Local analysis inspected video frames, contact sheets and panel text. Audio was not transcribed or assessed.

In comparable-looking frontal video moments, D narrows the mesh with a similar height: approximately 138–140 versus 110 pixels wide near, and 94–95 versus 78 pixels wide far. Head position, subject pose and video timing differ between these moments. These widths describe the recording and are not calibrated physical alignment or stereo measurements.

The panel frequently says **Waiting for fresh frames** while tracking. The face sequence reaches **Saved 2 / accepted 2 / repeat 2**. Board saves were rejected as stale at headset times 08:58:05.671, 08:58:36.400 and 08:59:40.770. At 08:59:41.170 the app watchdog stops the stream. Collected service logs show subsequent cleanup; they do not establish a preceding native camera error or explain that terminal stall.

All 20 files from the five finalized captures and all four recordings matched headset SHA-256 hashes. Existing recordings and calibration data were preserved.

## Capture repair

The runner had treated `registration_diagnostics[3]` as a freshness flag. That value is camera frame duration, `frame[2]`. A valid camera timing rebase can yield `frame[3] = 1` with duration zero, so the old readiness check could reject a fresh frame.

The repair publishes actual freshness in `diagnostics[30]`. The runner validates advancing capture time, age, this flag, matching Stage pose and a measured face for face steps before consuming a queued save. Ineligible frames retain the pending request. Preview readbacks are suppressed while a save waits, pending/saving messages are preserved, and changing step resets readiness. Timing exports distinguish camera age at submission/readback from frame readback latency. The geometry, profile and Stage equations are unchanged by this repair.

Both applications passed build, lint and formatting checks. A host regression runs the shipped diagnostics JS through the actual Kotlin `FaceFrame` decoder, exercising fresh/duration-zero and stale/positive-duration cases. It also exercises the actual Kotlin save-state methods for request retention, single consumption, message preservation and readiness reset. Existing shipped-JS/Kotlin snapshot, camera-profile and motion fixtures passed, as did asset/binding/coordinate/APK checks. See validation for the latest installation/runtime outcome.

## Next measurement

Use the repaired lab for a short stationary A/D comparison at approximately 1 m and 2 m: four accepted face saves. Keep the subject and headset position fixed within each A/D pair. Compare nose, eye line, chin and cheeks with each eye separately, and report whether D improves overlap or leaves a consistent shift. Record the panel and wait for **Saved … Exposure accepted** after each save. Offline capture still works after installation.

No further checkerboard views are needed to establish this held-out intrinsics result. If D leaves a physical offset, the next investigation is camera-to-head registration and capture-pose timing using a known stationary target, with any depth-dependent or eye-dependent discrepancy recorded separately. A constant world translation cannot be inferred from the current evidence. The public Kotlin capture path lacks per-eye renderer matrices and hardware HMD timestamps, which limits automated diagnosis of stereo/compositor registration.

Raw numerical sources: [report.json](../artifacts/facelandmarker/registration-lab/trial-results-2026-10-28/analysis/report.json), [direct-camera-stage-invariants.json](../artifacts/facelandmarker/registration-lab/trial-results-2026-10-28/analysis/direct-camera-stage-invariants.json), and the capture/recording manifests in the same evidence directory. Current work remains uncommitted on `dev/facelandmarker`, after baseline `1243bfb`.
