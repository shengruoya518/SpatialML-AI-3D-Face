# Mode C visual result and refinement direction

Latest wearer clarification: the small/inward residual is symmetric for both turn directions. See [OBSERVATION_GUIDED_REFINEMENT.md](OBSERVATION_GUIDED_REFINEMENT.md) for a 2% coupled-focal trial followed by a separate cy adjustment, with fresh same-landmark host replay evidence.

Current adjustable-intrinsics build: [CALIBRATION_TUNING_STEPS.md](CALIBRATION_TUNING_STEPS.md). It starts from C or saved Custom values; the historical trials below remain evidence, not accepted correction constants.

The latest wearer test favors **C: Renderer trial**. D made face overlap worse. C is close, with the mesh slightly too small and too high; the wearer reports a similar residual in each eye separately. C is now the leading end-to-end visual candidate. The independent checkerboard result still favors the measured source K, but that result has not established physically correct face rendering.

This updates the interpretation of [TRIAL_RESULTS_2026-10-28.md](TRIAL_RESULTS_2026-10-28.md) and [FOV_2D_TO_3D_FINDINGS.md](FOV_2D_TO_3D_FINDINGS.md). It does not establish a final camera calibration or a measured world-position correction.

## Latest recording

The inspected recording is [ScreenRecording_2026.10.29-09.42.04-AM.mp4](../artifacts/facelandmarker/registration-lab/latest-recording-2026-10-29/ScreenRecording_2026.10.29-09.42.04-AM.mp4), 174.766 seconds, 2560×1440 H.264 with AAC audio. The headset copy and local copy match SHA-256 `59d14ea1c92ec68c195fd667b215187f663de5cbbc58d334cfa515a169d75b0e`.

Full-frame inspection and panel OCR identify A near 10–30 s, B near 40–50 s, C near 60–100 s and D near 110–160 s. These ranges describe sampled frames rather than exact switch timestamps. The label remains **Face front - 1 m**, although the person also turns. The C frontal frames show close overlap with a residual above the real face; D includes a narrower, displaced mesh and larger errors on turned poses. Positions and poses differ between moments, so screenshots do not provide a calibrated C/D size ratio or exact physical translation.

The [face comparison](../artifacts/facelandmarker/registration-lab/latest-recording-2026-10-29/inspection/c-d-face-comparison.jpg), [contact sheets](../artifacts/facelandmarker/registration-lab/latest-recording-2026-10-29/inspection/contact-sheet-1.jpg) and [panel OCR](../artifacts/facelandmarker/registration-lab/latest-recording-2026-10-29/inspection/panel-ocr.jsonl) preserve the observations. Audio was not transcribed or assessed; the per-eye conclusion comes directly from the wearer’s text response.

Sampled panels remain at **Saved 0 / Exposure accepted 0 / Repeat 0** and frequently **Waiting for fresh frames**, including tracking frames. Therefore this recording supplies visual comparison but no successful saved packet shown in the panel. The freshness/save repair has not yet established successful user capture. An isolated B frame around 50 s contains stretched green geometry; without matching intermediate data, its cause is unproven.

## C and D differ in depth as well as ray direction

C and D preserve effectively the same source-to-virtual image affine. Their effective geometry K differs:

| Virtual parameter | C | D |
|---|---:|---:|
| fx | 1746.471267 | 2027.879814 |
| fy | 1746.471267 | 2036.955265 |
| cx | 1623.500000 | 1661.005689 |
| cy | 1231.500000 | 1230.337555 |

D has roughly 16–17% higher virtual focal lengths. Its horizontal principal point is also 37.506 virtual pixels farther right. These parameters enter the monocular canonical-face reconstruction, not only a final image projection.

To isolate that effect, the shipped geometry operators were replayed with host SVD on the same landmarks from the earlier positive D frontal/far export (sequence 155). All input landmarks were held fixed while changing only geometry K. This is a host counterfactual on an earlier sample, not numerical capture from the latest video.

| Same-input replay | Median camera depth | Camera-space X span | Camera-space Y span |
|---|---:|---:|---:|
| C K | 1.8997 m | 0.14301 m | 0.19046 m |
| D K | 2.2126 m | 0.14277 m | 0.19014 m |

The face dimensions remain almost unchanged, while D moves the reconstructed face approximately 31 cm farther away on this sample. Under a fixed eye view this tends to reduce apparent size. The horizontal center also changes from +24.8 mm to −16.1 mm in camera space. These results explain a mechanism by which D can worsen rendered overlap despite its better board fit. They do not identify whether the physical discrepancy originates in monocular face scale, camera/head registration or compositor projection.

## Two independent parameters to probe around C

Keep C's image affine fixed while varying the geometry focal lengths and vertical principal point independently. Small symmetric perturbations around C are diagnostic trials; their values must not be treated as accepted calibration.

1. **Focal multiplier:** a small decrease in both fx and fy moves the canonical-face estimate closer while largely preserving its physical dimensions. In the same-input host replay, −3% focal length moves median depth from 1.8997 to 1.8422 m, with X/Y spans still approximately 14.3×19.0 cm. This tests the size/depth residual. It also changes the center ray, so vertical alignment must be reassessed afterward.
2. **Vertical principal-point offset:** decreasing cy moves reconstructed rays downward because camera Y is `(cy − v) × depth / fy`. At unchanged C focal length, a −20 virtual-pixel diagnostic perturbation lowers the replayed face center by 21.8 mm at about 1.9 m while changing median depth by only 1.2 mm. This is approximately a 0.66° ray shift near the center. The perturbation demonstrates direction and sensitivity; it is not a measured correction for the wearer.

The existing `sizeScale` multiplies camera-space positions about the optical center, including distance. It preserves source-camera rays and is not an independent face-outline enlargement control. A face-centered scale at fixed depth would enlarge the outline, but it would alter the inferred physical face dimensions. A focal perturbation and a vertical-ray perturbation provide a more direct test of the current reconstruction hypothesis. Similar residuals in both eyes favor beginning with shared geometry/registration; they do not rule out eye/compositor effects.

The next lab increment should preserve original A/B/C/D and record both parameters with each frame. Compare unmodified C, the focal perturbation alone, the vertical perturbation alone and their combination, at stationary near/far views and one turned pose. Before requesting another capture pass, expose readiness reasons and establish one successful save; the current recording shows that capture readiness remains a practical blocker to numerical comparison.

No refinement parameters were applied to the app in this analysis. The exact size and vertical corrections remain unmeasured. Evidence and replay outputs are in [latest-recording-2026-10-29/inspection](../artifacts/facelandmarker/registration-lab/latest-recording-2026-10-29/inspection/), including [profile-sensitivity.json](../artifacts/facelandmarker/registration-lab/latest-recording-2026-10-29/inspection/profile-sensitivity.json). Source geometry, models, Full Space Mixed, the zero-sized SpatialML container and factory optical metadata retain their current contracts. Current work remains uncommitted.
