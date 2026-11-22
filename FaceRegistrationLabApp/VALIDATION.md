# Registration lab validation — 2026-10-28

**Balanced lag response installed (2026-11-07 UTC):** Wearer confirms that v2 smoothing works really well and authorizes the tested balanced profile. [Implementation and deployment](../artifacts/facelandmarker/registration-lab/balanced-lag-2026-11-07/IMPLEMENTATION.md). Derivative cutoff 1.5 Hz, translation motion coefficient 12, angular coefficient 2.5; static damping and local-shape/outlier/capture contracts preserved. No prediction. Production tests reproduce 43.26 ms equivalent filter lag versus 69.17 ms before, 51.07% synthetic RMS jitter reduction, and zero stop overshoot. Both builds/lint/format and calibration regressions pass. APK `e430972fc9759f05ef39a782d91c5bc3d4776ec6a80a742cf374189a7ea26764` installed/hash-verified on PB311XHGKC220141G; 78 finite startup frames with no rejection and exact stereo K/D. Mesh smoothing On / POS STEREO verified. No face visible during startup. All 1127 app files, 53 recordings and private calibration state preserved; lease released and app running. This supersedes older lag-setting deployment states below.

**Pose/mesh stability v2 installed (2026-11-07 UTC):** User reports weak v1 improvement and asks to continue. [Implementation and tests](../artifacts/facelandmarker/registration-lab/pose-mesh-stabilization-2026-11-07/IMPLEMENTATION.md). Normal viewing now uses the existing landmark ROI tracking instead of detector-per-frame; capture/preview contracts still force detection. `FacePoseMeshStabilizer.kt` filters Stage translation/quaternion/scale separately from face-local shape, and uses bounded confirmation for isolated same-track jumps. It controls both displayed pose and mesh through the existing On/Off button. Camera K/D and raw diagnostic packets/exports remain unchanged. Synthetic 18 Hz RMS is 56% lower than raw and 35% lower than v1 under the same noise; translation test lag is about 69 ms. Both builds/lint/format and host filter/calibration regression pass. **The previously built APK `66adab1decfc6cc3036e20acf4f96666fe964af11013a90f7dc266afde6e347b` is installed/hash-verified on PB311XHGKC220141G.** Startup has 52 finite packets with zero rejection and unchanged K/D; the UI shows Mesh smoothing On. No face was available for live filter/tracking validation. All 1,126 existing app files, 53 recordings and private calibration are preserved; lease released. Subsequent lag-comparison settings are not applied. No new recording requested.

**Mesh stabilization (2026-11-07 UTC):** The wearer reports good colleague face overlap with the stereo calibration and asks to reduce residual jiggle. [Recording analysis, implementation and validation](../artifacts/facelandmarker/registration-lab/mesh-stabilization-2026-11-07/IMPLEMENTATION.md). The lab now defaults to **Mesh smoothing: On**, with an Off comparison button. Adaptive filtering runs on displayed Stage vertices after existing capture-head compensation; K/D, raw packets, face pose and all calibration exports stay unchanged. Shared mesh weight, motion-dependent response, 20 mm maximum correction, and tracking/configuration/time-gap resets bound lag and prevent carrying a stale face. Capture/preview paths bypass filtering. Production filter and existing calibration regressions, both app builds, lint and formatting pass. Synthetic 18 Hz jitter RMS falls 38%, with 23 ms equivalent lag for 0.2 m/s translation; this is not yet a measured wearer improvement. Installed/hash-verified on PB311XHGKC220141G as APK `d5ab8ea49d64257bedfc2987483c3e887f4118e26b0ab43495391c6778e5647d`; 76 finite startup packets, zero rejection, unchanged stereo K/D, and the On control visible. No face was available for runtime filtering validation. All 1,125 existing app files, 53 recordings and private calibration are preserved; lease released. No new calibration recording is required.

**Stereo calibration implemented and installed (2026-11-07 UTC):** [Implementation and deployment evidence](../artifacts/facelandmarker/registration-lab/stereo-calibration-app-2026-11-07/IMPLEMENTATION.md). Lab startup now selects mode 5 with the exact final measured source K and board-derived rigid D, scale 1. Working K is A×K_source; D replaces DOWN40 and transforms both vertices and pose. The headset shows **POS STEREO** and **Stereo calibration active**. **Use previous camera** restores the previous Custom camera with Current registration; the paired Stereo calibration can be restored with the same button. Saved custom/optical values and all original recordings are preserved. Kotlin/JS and fused-model regressions, both app builds, lint and formatting pass. The final APK `3dfc6be61b62a16b4f43ce90b9630c792e08e28eb006fa62943d83ae35e36b00` is verified installed. All 59 startup packets are finite with zero rejection, and all 59 scene records have exact mode-5 K/D within FP32 precision; no face was visible. The device lease is released; physical face overlap is not established by that check. The documented LiteRT GPU relaunch fault required a restart of the existing SpatialML service, with its APK unchanged. No new calibration collection is required. This entry supersedes older undeployed/startup/capture directions below.

**Final existing-data conclusion (2026-11-06):** [Full analysis and stereo predictions](../artifacts/facelandmarker/registration-lab/final-calibration-existing-2026-11-06/FINDINGS.md), [exact recommendation JSON](calibration/stereo-face-existing-data-2026-11-06.json). User explicitly requests a conclusion with no more collection. All 22 source board views, nine unambiguous stereo board exposures and 15 paired raw face snapshots are analyzed. Recommend measured source K plus board-derived D: translation [−4.311, −44.095, +42.197] mm, rotation vector [+0.328370, +1.256514, +0.068583] degrees, scale 1. Final board RMS close/middle/far 3.91/0.94/1.46 px; omitted-distance mean 2.21 px. Independent face mean 8.69 px versus old-current 55.73 px; ten turn/distance holds 9.51, four roll holds 6.65, earlier check 3.84. Different face subjects are visible across recordings; face-scale fits do not transfer consistently. Old DOWN40 scores slightly better on these face snapshots but remains rejected as general calibration by board evidence and wearer feedback. Multi-axis source/head fit now uses the existing ±30° rotations, supports vertical/yaw correction but fails the physical calibration residual gate. The frozen final JSON records the offline recommendation before deployment; the implementation entry above records its subsequent app integration. It is not accepted factory calibration. Reconstruct with K_work=A×K_source before D; do not stack DOWN40. **Analysis complete; no additional capture requested.** Application/service code and device settings were unchanged during that offline analysis. This supersedes all older next-capture requests below.

## Two-distance board measurement and limited offline fit — 2026-11-07 device date

Latest two-distance result (2026-11-07 device date / November 6 UTC): [findings and offline candidate](../artifacts/facelandmarker/registration-lab/board-distance-check-2026-11-07-eeb5d2/FINDINGS.md). Six new exports, all48 corners in source/both eyes, exact same-PTS sequence/CRC/reference and native checks pass. Source depths1.169–1.210m /1.759–1.779m, tilt30.6–32.0°, all frozen K variants unique. Same-ten-point X/Y bias close18.35/41.43mm, middle32.42/34.69mm, far44.67/33.45mm; millimetres inherit recording uncertainty. A fixed rigid D fitted close+middle reduces held-out far RMS37.63→1.56px; full48 far1.57/1.69px, six additional pairs0.56–2.60px; K-family far1.499–1.731px. Translation-only far17.84px; DOWN40 leaves ~6px downward error at both new distances. Candidate D translation[-4.27,-44.49,+42.08]mm, rotation vector[0.367,1.261,0.064]degrees, scale1; frozen/offline/unaccepted, measured-source-K only. Close fit3.92px, stereo span bias/noisy point depth, physical origin and orientation transfer unresolved. No app/service/build/install/restart/calibration change. 25 session files and432,968,607-byte stereo video hash verified, APK unchanged, lease released. **Historical proposal, superseded by the final existing-data analysis above; no additional capture requested.** [Capture steps](BOARD_CAPTURE_STEPS.md). Supersedes earlier pending distance-capture instructions below.

Source RMS0.188–0.225px; max reference/held-out tag0.995/1.132px; source-to-upload max2.008mm/0.179degrees. Full48 stereo consistency<0.278px; physical identities inspected from all18 crops, crop-margin sensitivity<=0.500px. Independent synthetic rigid recovery4.5e-17 maximum parameter error. Original/profile hashes and Python compilation checked. Full-board stereo centroid stability2.84/9.52mm but individual point spread20.56/40.48mm, so pixel transfer is not factory metric calibration. Source camera and app unchanged.

## Root calibration metadata inspection — 2026-11-06 device date

[Findings and reproducible comparison](../artifacts/facelandmarker/registration-lab/device-calibration-root-2026-11-06/FINDINGS.md). User-enabled root shell verified on PB311XHGKC220141G with the retained Swan fingerprint. Root stat proves `config_head.txt` absent, correcting the earlier permission-error uncertainty. Eight system sensor/configuration files and two installed capture libraries have matching local and before/after device SHA-256. Focused retrieval leases released; later static reads use supported devmux read-only commands without a lease. Another session's lease was not altered.

`calib/imu0/sensor.yaml` labels `T_IH` as `IMUFromHead`, translation [−45.0,−24.8,+46.5]mm with identity rotation. The app and local service fixed IMU-to-head matrices agree exactly; inverse-file/basis ordering is not established, and both unaccepted interpretations remain in the numerical report. The raw sensor files use 2720×3056 / equiDis62Bilinear /32 coefficients, unlike the inference source. Camera-centre separation63.9695mm; recovered retained API-left position is1.877mm from cam5, with90.099° relative rotation. This is suggestive mapping evidence, not an accepted file/frame identity. Named installed capture entry points forward through interfaces and do not resolve head-origin semantics. Original input hashes, all three retained E matrices and frozen-source-profile hash verified; no registration fit, source K change, application/service edit/build/install/restart, device calibration write or deletion. The next two-distance board check is unchanged; capture instructions now define oblique viewing.

## Recorded oblique board check — 2026-11-06 device date

[Findings, original video, corrected partial measurements and comparison](../artifacts/facelandmarker/registration-lab/board-oblique-check-2026-11-06-afea05/FINDINGS.md). Session afea05 / run e444e986 DONE three exports, 13 original files and 264,367,514-byte / 61.830633 s stereo video hash verified. All source/native/no-face and exposure/reference contracts pass; source RMS 0.414–0.443 saved px versus alternate planar 9.35–10.11, tilt ~35°, source depth 0.515–0.537 m. All K sensitivity variants are unambiguous. Same-PTS eyes decode exact sequences/CRC for all three, twelve tags per eye, max reference/held-out tag RMS0.957/1.128px. Installed diagnostic APK unchanged, retrieval lease released.

HUD overlap prevents full48 detection, so that observer is REJECTED. The separate partial protocol uses only visible IDs0–7/40–41 in original pixels, subpixel window sensitivity max0.348px and stereo consistency max0.207px. The middle source detector reverses enumeration; physical printed-header anchors47/40 establish its correct order, and the initial mistaken comparison is retained/INVALIDATED. Corrected mean selected head XYZ bias [+18.353,+41.430,-20.182]mm, Y repeatability SD0.379mm; full K family Y envelope +38.432–43.268mm. Selected Stage stationarity max1.787mm predicted /3.509mm observed. Recorded stereo spans measure104.04–106.53mm for physical100mm, mean105.55mm, limiting head-space metric truth. Old same-ten-point frontal envelope Y+29.35–37.45mm differs in both angle/distance and remains source ambiguous; no correction/curve is inferred.

The exported optical transform is unchanged (Y translation +43.337mm); local source uses a fixed IMU-to-OpenXR-view conversion and SDK HMD tracking for H. Its physical origin/rectified-image contract remains unverified. Config-head read initially failed offline; after user reconnect it returned Permission denied under normal device access. No root or configuration change, leases released. Next: middle/far Board checks at the same oblique angle with the whole pattern clear of HUD, three exports each. No close-check/source-set repeat or eight-hold trial. Host analysis/docs plus read-only retrieval/config inspection; no app/service source/build/install/restart/calibration/deletion/commit/push.

## Combined source camera fit and physical pilot envelope — 2026-11-06 device date

[Findings, frozen diagnostic profile, source models and figures](../artifacts/facelandmarker/registration-lab/board-supplement-2026-11-06-f5e56b/FINDINGS.md). Combined original 12/4 plus predeclared supplement 4/2 gives 22 distinct views, 16 fit / 6 held out. All six new 48-corner source detections succeed without manual crops. Pinhole K at saved 1624×1232 is fx/fy/cx/cy 1179.435/907.695/780.631/611.090, zero distortion; pooled fit 0.3664 px, held-out 0.2452/0.2479/0.1757/0.4471/0.8521/0.8044 px. Worst omitted-view held-out 0.8786 px, focal range 1.95%/1.94%, cx/cy range 11.629/6.858 px. Centre-ray X/Y spread 9.296/7.443 mm at Z=1 m; close board-centre sensitivity about 3–4 mm X, 2–3 mm Y, 6–8 mm Z. Thirty/three hundred iterations agree exactly; four supplementary fit views alone agree closely with combined K and pass all held-out images. Radial model fails B14/S6 at 2.7300/4.1081 px, still 2.6584/3.9457 after source pose refinement. Declared service K gives 5.32–9.12 px on the new close images after pose refinement. Undefined formal uncertainty for the four-view-only diagnostic fit is explicitly stored as null; completed per-model results were reused for finalization.

The source-selected profile is **frozen for offline diagnostics**, `acceptedDeviceCalibration=false`, before any eye residual is examined. Across its full/omitted K family and all admissible planar source branches, the original physical pilot remains predicted roughly 31–39 mm high and 22–32 mm to the right in reference-derived head-centre estimates. All three strict source poses remain ambiguous. Virtual tags alone fit eye projections; physical correspondences were established from the printed header before comparison. No branch or correction is chosen by minimizing registration residual. The prior ~4% stereo board-span discrepancy limits those millimetre estimates; a single frontal hold cannot establish a universal correction. Next: one recorded oblique Board check, three exports, with a unique source pose before a wider trial. Source/intrinsics and predicted-eye figures were visually checked. Host-only analysis/docs/profiles; no device/app/service source change, build/install, calibration application, deletion, commit or push.

## Six-view supplement retrieved — 2026-11-06 device date

[Retrieval receipt, capture summary and source images](../artifacts/facelandmarker/registration-lab/board-supplement-2026-11-06-f5e56b/RETRIEVAL.md). Run `f53e0155` saved six distinct source exposures, then CANCELLED at view 7 with saved=6 and settings restored. Fresh expanded snapshot: 109 files / 302,436,394 bytes, all headset-hash verified, including the live journal at copied prefix length. The earlier 84 static file hashes and journal prefix match the preceding snapshot. New directories 022–027 pass source/native snapshot/pose contracts with zero faces, Mode A / Current / scale 1 and unchanged ROM/stream/resolution. Installed diagnostic APK hash unchanged, MediaProjection null before/after, devmux lease released. No rebuild/install/restart/calibration/service/deletion/commit/push. Combined fitting, corner coverage and sensitivity are pending on these six new views; K remains unfrozen. Analyze retained data before further capture.

## Completed source board views — 2026-11-06 device date

[Findings, camera profiles and current six-view follow-up](../artifacts/facelandmarker/registration-lab/board-views-2026-11-06-f5e56b/FINDINGS.md). Completed run `a936c733` has 16/16 usable distinct no-face exposures; all source/native/pose gates pass. All 85 session files are device-hash verified at retrieval and installed diagnostic APK `37842ba9684a75dc1b8bca86779d9b2e6a86b227de37f8d3bf280ea17242dae6` matches. Earlier failed two-view run and original pilot are preserved. Source crops recover two whole-image detector failures while keeping original image coordinates.

Pinhole pooled/held-out RMS is 0.1533 / 0.2375, 0.3001, 0.1618, 0.4815 saved pixels. Radial k1/k2 gives 0.1378 training but fails one held-out view at 1.8975 pixels. Pinhole source gates pass, but K is **unfrozen**: leave-one-training-view-out fx/fy/cx/cy ranges are 182.390/140.662/13.552/51.953 saved pixels, and centre-pixel vertical ray spread is 51.367 mm at Z=1 m. Solver iterations 30/300 agree. Most training boards span less than 12% of source width; large close oblique source views are needed before precise registration.

All three earlier pilot source poses are rejected as planar-ambiguous; branch RMS gaps 0.0053–0.0259 pixels with up to 13.7 mm corner separation. Independent reference-based stereo estimates the measured 100 mm spans at 103.523–104.147 mm, with 0.255–0.296 px stereo consistency and 2.002–2.157 mm planarity RMS. This does not certify source-camera scale or identify the cause of the recording-chain discrepancy. No branch, orientation or K is selected by reducing the registration residual.

Production board/reference regression passes after the host calibration crop addition. The new six-view supplement helper passes synthetic known-camera recovery, original held-out preservation, fixed four-fit/two-held-out allocation, production `--source-regions` calibration and duplicate-exposure rejection. It retains original app split metadata and refuses output overwrite. Physical supplemental captures are pending. Follow [six-view instructions](BOARD_CAPTURE_STEPS.md); the eight-hold trial remains deferred. Host tools/evidence/docs only; no app/service source, rebuild, reinstall, device calibration change, deletion, commit or push. Device lease was released after retrieval.

## Physical board pilot passed — 2026-11-06 device date

[Findings and retained evidence](../artifacts/facelandmarker/registration-lab/board-check-2026-11-06-f5e56b/FINDINGS.md). The installed APK matches diagnostic SHA-256 `37842ba9684a75dc1b8bca86779d9b2e6a86b227de37f8d3bf280ea17242dae6` on PB311XHGKC220141G. All 13 original session files and stereo video are hash verified. Three no-face packets pass native snapshot checks; all three source/stereo observations have 48 corners per image, matching CRC sequences, all twelve tags and valid pose/metadata. Maximum reference RMS 0.9532 px, worst held-out tag 1.2784 px. Pilot readability passes; physical registration accuracy and metric calibration remain pending.

Host-only detector update adds explicit bounded board crops while preserving full-image coordinates and full-image reference fits. All six recorded-eye detections pass; varying crop margins gives maximum 0.193 px corner change. Synthetic board/camera/reference regression, 16-view calibration, coordinate restoration and invalid-bounds checks pass. No app rebuild or reinstall was needed. This retrieval/analysis preserved originals and device calibration/services; device lease released. The subsequent source-view analysis above supersedes this pilot's next-capture status; the user has supplied 100 mm five-square spans in both axes.


## Board diagnostic update — 2026-11-05

[Implementation evidence](../artifacts/facelandmarker/registration-lab/board-diagnostic-2026-11-05/IMPLEMENTATION.md) and [pilot steps](BOARD_CAPTURE_STEPS.md). Both apps' compact/fused/GPU build, lint and Spotless pass. Production Kotlin exercises all three board sequences without a face and preserves the existing face sequences and settings restoration. Synthetic camera/board/reference checks pass, including pilot readability, 16-view source fitting and unit/axis/identity/timing failure detection. Final APK SHA-256: `37842ba9684a75dc1b8bca86779d9b2e6a86b227de37f8d3bf280ea17242dae6`. Device PB311XHGKC220141G disconnected: install, startup, no-face device export and physical pilot **NOT RUN**. No device data/calibration/service changes. Generic generated-app entry/manifest scanner is not compatible with this existing scaffold; UI style itself passes with zero warnings/errors.

## Comparison installed and startup/UI verified — 2026-11-05 UTC

[Installation, runtime and preservation evidence](../artifacts/facelandmarker/registration-lab/head-down-comparison-2026-11-05/install/installation.json). Archived/installed APK SHA-256 `04a856ee75853705be24d00e40b9d3479dda738543901ef4970a6966cb59d560` matches on PB311XHGKC220141G. PID 16503, fresh Spatial service PID 8793; finite fresh output advances 7→52 with all outputs, automatic IDLE and rendered Current revision 0. Screenshot shows Use head down 40 mm, Roll trial and original capture/output controls, with POS CURRENT and no observed clipping. Startup has 107 frames / zero faces; real-face physical comparison remains pending.

Old runner was stopped with DONE/12 state, and MediaProjection null. Prior APK backed up. Optical cache hash and absence of custom intrinsics JSON match, service APK hashes/paths match, 962 pre-existing app files retain paths/minimum sizes and 47 recordings retain paths/sizes. Both face apps and OpenMR processes stopped before replacement; APKs/data retained. Lease released; no recording or automatic trial started, no service update/calibration write or Git operation. [Record the 30–60 second comparison](LAB_POSITION_COMPARISON.md) next.

## Reversible position comparison built — 2026-11-05 UTC

[Implementation, archived APK and checks](../artifacts/facelandmarker/registration-lab/head-down-comparison-2026-11-05/IMPLEMENTATION.md). Current / Head down 40 mm is a lab-only immutable registration selection shared by pose/vertices before H_capture. Native/K/scale unchanged, queued/automatic locks tested, reopen defaults Current. Scene badge and export matrices/IDs retain rendered selection; independent references and raw face geometry are preserved.

Both apps' optimized build/lint/Spotless pass. Production Kotlin checks pass, including all 478 vertices and pose translations on 12 real roll packets within 0.5 µm; corrected host fixtures pass native analyzer 12/12. Synthetic stereo raw/rendered separation and missing/unsupported metadata rejection pass. UI-style verifier has no errors/warnings; placement source check passes with one retained advisory. APK `04a856ee75853705be24d00e40b9d3479dda738543901ef4970a6966cb59d560` is **not installed** because the headset is disconnected. On-device startup/button layout, preservation and physical overlap acceptance remain pending. No service/calibration update, recording, commit or push. See [comparison instructions](LAB_POSITION_COMPARISON.md).

## Roll correction transfer and checkerboard analysis — 2026-11-05 UTC

[Complete analysis, figures and raw evidence](../artifacts/facelandmarker/registration-lab/roll-trial-2026-11-05-b8c6a3/FINDINGS.md). All 69 marked uploads decode in both eyes; anatomy two-view RMS median/max 0.276/0.558 px. Stillness selection retains 38 exposures across four holds. Earlier head-Y −40.0875 mm transfers without refit: current 41.037 px → 4.424 px, eye 0/1 4.450/4.397. Initial-frame and Stage-Y alternatives give 8.753/8.615 px; earlier XYZ+scale gives 6.367 px. New head-Y fit −39.581 mm; combined 172 exposures / 14 holds gives −39.870 mm. Rounded −40 mm candidate gives 4.413 px roll and 2.895 px earlier-check RMS. Eye-corner exclusion and ±10% crop checks retain the direction ranking.

Earlier measured 20 mm board source images (10+3) revalidate K at 0.460 versus service 3.797 saved-pixel RMS on later held-out views. The board video is ordinary H.264 2560×1440 without stereo view IDs/current references; board-only optical translation inference is unstable. Correct production replay with K_virtual=A×K_board worsens recorded face overlap on four new/ten prior raw marked snapshots, so no metric scale is accepted. Recommend a reversible lab-only head-relative translation before H_capture, shared by pose and vertices. No correction/source/device changes applied; physical acceptance pending. Original roll files/video and built production-source hashes remain unchanged; analysis manifest is beside the report.

## Roll trial retrieved and initial checks — 2026-11-05 UTC

[Original video, exports, motion truth and retrieval evidence](../artifacts/facelandmarker/registration-lab/roll-trial-2026-11-05-b8c6a3/RETRIEVAL.md). Run 672dcdaf reached DONE with four holds / twelve exports. All 49 session files and the 637,428,516-byte / 117.268 s Spatial video are hash verified; all twelve native packets and Stage/exposure checks pass. Actual baseline-relative median export rolls are +0.17/+16.41/−15.43/−0.82°, with yaw/pitch within 5° and unchanged baseline. All 69 marked uploads report accepted pose/face clearance. One sampled same-PTS pair per hold has all twelve tags and identical valid CRC in both eyes, with max reference RMS 1.003 px, worst held-out-reference RMS 1.358 px and green RMS 0.993 px. Sampled layout/readiness passes; dense anatomical correction transfer and physical-display acceptance remain pending. No app/service/calibration changes or new capture; originals preserved, lease released.

## Roll-only update installed — 2026-11-05 UTC

[Implementation, checks and installation evidence](../artifacts/facelandmarker/registration-lab/roll-only-update-2026-11-05/IMPLEMENTATION.md). Four measured holds 0/+15/−15/0° with ±3° roll and ≤5° yaw/pitch gates, frozen initial baseline, side-column references and 12 exports are implemented. The existing three capture flows remain. Production Kotlin and synthetic both-eye layout/CRC/clearance/mismatch checks pass; both apps' compact/fused build/lint/Spotless and UI-style checks pass. Source placement check passes with one heuristic advisory.

Installed APK SHA-256 `cf8a79414c32f621a2f38ae7ef3376430fe39dc703fd7aa1187e7b29f8bf614a` matches on PB311XHGKC220141G. Lab PID 15662, fresh Spatial service PID 20962; journal frames 1699→1740 advance with finite fresh full-output packets, 0.061/0.086 s camera ages and IDLE automatic state. The Roll button and original capture/output controls are visible without observed clipping. The startup window has 1744 pipeline frames / zero face frames, so real-face roll gates, active capture layout and recorded both-eye acceptance remain pending. No automatic capture or recording started.

Optical calibration hash and absence of custom intrinsics JSON match; service APK paths/hashes match, 913 pre-existing app files retain their paths/minimum sizes and 46 recordings retain paths/sizes. Previous APK backed up; no active MediaProjection at install. Both face apps/OpenMR processes stopped before replacement; service APKs/data retained, lease released. No fitted correction, commit or push. Follow [the roll-only instructions](AUTOMATIC_CAPTURE_STEPS.md#roll-only-test--next-capture); do not repeat the full ten-hold trial.

## Measured motion audit after wearer clarification

[Transform audit and repeat-test decision](../artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-712cf5/HEAD_TRANSFORM_AUDIT.md). All 195 marked reference transforms and 30 export capture transforms are compared with a first-hold baseline. All 134 selected transforms match their journal source exactly; export capture/reference matrices agree within 1e-6. Holds 6–7 show yaw; 8–9 mainly lateral translation. All-marked roll range −3.28° to +4.30° confirms that intended ±15° roll was not recorded in a discarded window. Prompt-label/whole-hold-ID permutation produces exactly zero weighted-residual difference for every fitted model and preserves held-out partitions. Existing correction scores remain valid as diagnostic predictions. No refit or full repeat is needed for the label clarification; a short level/left-roll/right-roll/level follow-up is proposed. No app/service/calibration/device change.

## Full Geometry trial analysis — 2026-11-05 UTC

[Findings, original video, scripts and figures](../artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-712cf5/FINDINGS.md). The scan accepts 463 of 1,148 sampled stereo pairs and recovers 181/195 distinct reference uploads across all ten holds. Across these 181 observations, per-eye fitted reference RMS median/max is 0.908/1.043 px, worst held-out-tag RMS 1.125/1.953 px, and green-marker RMS 0.803/1.147 px. Both-eye sequence/CRC, exact original PTS, projection, green-marker, exposure and owner-conversion gates remain unchanged. Anatomy inference succeeds for all 181 after the early hold-9 ROI repair; 175 pass two-view compatibility. Excluding panel-occluded points and selecting contiguous still windows with common IDs leaves 134 exposures. Their two-view floor is median/max 0.379/1.519 px and each hold's centre range is ≤15 mm.

Full-trial equal-hold mean RMS with entire holds omitted from fitting: identity 62.144 px; head Y-only 9.184; XYZ translation 8.813; rigid 8.791; Y+ray scale 7.315; XYZ+ray scale 5.457; rigid+ray scale 5.381. Ray-scale-only reaches its bound and is rejected. Y-only is −40.088 mm. XYZ+ray scale uses [−2.883,−42.061,+12.470] mm and s=1.145823, with mean left/right held-out RMS 5.306/5.584 px. On the earlier 14-exposure check, without refitting: identity 48.042 px; Y-only 2.882; XYZ+ray scale 4.766. A registration offset transfers; a universal metric-depth scale is not established.

The stereo prediction figure is visually reviewed. Crop ±10% sensitivity succeeds in 40/40 cases with median/max RMS change 0.867/2.128 px and maximum point change 4.218 px. Chin/turned-face residuals remain. Actual roll spans only about −2.92° to +1.32° in hold medians; nominal 2 m is not measured physical coverage. No independent board was analyzed and physical-display acceptance is pending. Proposed next revision: temporary correction comparisons, measured roll gating and references outside the face. No calibration applied, no app/service source or device change, no new build/hardware validation. Metadata finalization verifies unchanged numerical fitting inputs; hashes and machine-readable results are in `analysis/analysis-summary.json` beside the report.

User-authorized cleanup removed 723 older generated images (645,339,480 bytes), preserving original recordings/PPMs/JSON, reports, report-linked figures and current trial/check evidence. The manifest is `artifacts/facelandmarker/registration-lab/cleanup-2026-11-05-analysis-images.json`.

## Full Geometry trial retrieval — 2026-11-05 UTC

[Retrieval and completeness report](../artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-712cf5/RETRIEVAL.md). Run `7aeeab26`, session `2026-11-05T00-04-06.918138Z-712cf5`, reached DONE with 10/10 holds, 30/30 exports and 195 distinct projection-reference uploads. All 121 session files and the 1,788,623,050-byte original Spatial video match device hashes. Video duration is 261.576789 s with 7,844 encoded frames; both 1920×1080 MV-HEVC views decode at the same PTS. Video SHA-256: `927c80b083e8599a92b8cfdd59287d1e5ce47c2ef3b29ab5c7be4d7fb12a1432`.

Native checks accept all 30 exports; all 2,994-float snapshot comparisons are exact, including signed zeros, and every export is EXPOSURE_STABLE. Maximum native reprojection RMS is 0.000187 px, Stage round-trip RMS 7.567e-8 m, owner round-trip error 1.192e-7 m, and upload-minus-capture age 0.412293 s. At retrieval, full-video reference/anatomy validation and correction fitting were pending; they are now reported above. The native analyzer decoded original images and ran its numerical checks, suppressing only duplicate PNG writes due to about 190 MB remaining host disk space.

The installed repaired APK hash is unchanged. No recording was active during retrieval; all device originals are retained and the devmux lease is released. This was retrieval and host validation only: no app/service/calibration change, restart, commit or push.

## Repaired geometry check — 2026-11-04 host / November 5 headset

[Run 16540581 findings and original stereo video](../artifacts/facelandmarker/registration-lab/geometry-check-2026-11-05-cc0ddf/FINDINGS.md). The repaired APK `f6f57e262556a55c4e8b7ef57b3d9714ccbedc89c58c87d1086672ca00edc870` matches on PB311XHGKC220141G. Session `2026-11-04T23-26-42.103539Z-cc0ddf` reaches DONE with 3/3 exports (6895, 6915, 6929), all native checks passing. All 13 session files and the 267,064,534-byte / 57.4346 s stereo video are hash verified. Both 1920×1080 eyes are preserved.

Of 65 same-PTS sampled stereo pairs, 44 pass the existing geometry gates; 19 have no usable references and two fail held-out-tag RMS. Every accepted pair has all twelve targets and matching CRC-valid sequences. All 20 unique uploads (6896–6915) are recovered. Across the 44 accepted pairs, fitted reference RMS median/max is 0.926/1.047 px, worst held-out-tag RMS is 1.951 px, and green-marker RMS median/max is 0.753/0.953 px. This verifies the corrected atlas on hardware.

All 20 estimated anatomical observations pass the 2 px two-view compatibility gate (median/max 0.359/0.560 px). Mesh-to-anatomy RMS is 48.32/49.01 px left/right; median vertical error is 47.22/47.87 px high. Estimated anatomy is about 38 mm below and 28 mm farther away in the capture-head frame for this hold. Anatomy uses recorded face crops and MediaPipe after marker inpainting, including uncertain eye corners behind glasses; no measured board or physical ground truth. The full hold spans 15.668 mm in reconstructed anatomical centre, over the 15 mm fitting gate. The contiguous 6902–6915 subset passes at 14.516 mm over 2.1667 s / 14 distinct exposures.

**Geometry trial is ready on the current build.** No correction fit was run for this single frontal pose, and no correction was applied. The ten-hold trial must establish distance/orientation generalization. This turn retrieved/analyzed evidence and updated documentation only; no install, restart, calibration change, data deletion, service change, commit or push. MediaProjection was null during retrieval; originals retained and devmux lease released. Prior build/host regression results below remain applicable; no source rebuild was needed.

## Texture repair installation — 2026-11-04

[Installed APK and preservation evidence](../artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-7eebca/texture-fix/install/installation.json). APK SHA-256 `f6f57e262556a55c4e8b7ef57b3d9714ccbedc89c58c87d1086672ca00edc870` matches the archived repaired build. The helper stopped both face apps and both OpenMR processes, installed only the lab and launched it. The old app was cached-empty with no Activity and a closed journal whose final capture was DONE. No recording was active.

Lab PID 12235, Spatial OpenMR PID 31581, session `2026-11-04T23-26-42.103539Z-cc0ddf`: 3,181 finite 6,332-byte output packets, 1,393 face frames and automatic IDLE. Fresh journal samples advance 3134→3179. Geometry controls are visible. Remote COMMAND status broadcasts are registered but deferred by the ROM with INFINITE_DEFER, including the foreground variant; verification uses journal, logs and screenshot. Headset capture controls remain the next entry point. Corrected reference texture rendering still needs a recorded Geometry check.

Both private calibration hashes, service APK hashes/paths, all 778 prior external app files and all 44 recording sizes are preserved. The old APK and calibration files are backed up. No new capture, profile save, app-data clear or service APK update. Lease released.

## Recorded geometry check and texture repair — 2026-11-04

[Run 7271d44e findings](../artifacts/facelandmarker/registration-lab/geometry-trial-2026-11-05-7eebca/FINDINGS.md) document all three accepted native exports and the hash-verified stereo recording. The coded atlas is vertically inverted on hardware: only eight mirrored IDs survive, face markers are white, and the frame code is blank. The check cannot support an accepted binocular projection/correction. This supersedes the startup-only readiness below.

The atlas Bitmap rows are now reversed before upload; production geometry/UVs and face calibration are unchanged. The synthetic renderer models the observed bottom-origin texture V and samples face colour from the actual atlas. It reproduces the previous failure and passes corrected twelve-tag/CRC/association and held-out-pose regressions. Both apps build/lint/format and the production Kotlin harness pass. Corrected APK SHA-256: `f6f57e262556a55c4e8b7ef57b3d9714ccbedc89c58c87d1086672ca00edc870`. The replacement is now installed: see the installation entry above. Inspect a new Geometry check before a full trial. No calibration change, service replacement, data deletion, commit or push.

## Binocular geometry installation — 2026-11-04

Installed and launched the geometry diagnostic build on `PB311XHGKC220141G` with the four
compact/fused/GPU flags. Installed APK SHA-256 is
`872605118128ee96520e2a8e45f678abdd545ff4f4df8896b65e2eb7757d6ae1`, matching the archived build.
Lab PID `12189`, fresh Spatial OpenMR PID `23901`, session `2026-11-04T22-13-54.029664Z-7eebca`.
Runtime samples advance through frames 954, 1000 and 1046 with fresh 6,332-byte output, mask 7,
Custom C values, unlocked controls, active logging and automatic phase IDLE. No face is detected in
these samples. Both Geometry controls are visible in the screenshot. Reference atlas rendering,
face-bearing exports and binocular optical acceptance still require the user's recorded Geometry check.

The install helper stopped both face apps and both OpenMR packages before replacing only the lab APK.
No recording or capture was active. The previous lab APK and private calibration files were backed up.
Both calibration hashes and both existing service APK hashes/paths are unchanged; the installed
services remain system updates under `/data/app`, not a newly asserted factory-ROM rollback.
All 765 pre-existing external app files remain present without shrinking, and all 42 recording files
retain their sizes. No profile was saved, capture or recording started, data cleared, or service APK
installed. The focused devmux leases are released. No commit or push.

Evidence: `artifacts/facelandmarker/registration-lab/binocular-geometry-2026-11-04/install/`, including
`installation.json`, before/after inventories and hashes, old APK backup, runtime statuses, startup
logcat/timeline and raw/upright screenshots. See the host regression results in the geometry section
below and [recording instructions](BINOCULAR_GEOMETRY_INVESTIGATION.md#recording-instructions).

## Compact pipeline flicker correction — 2026-11-03

The latest lab APK is installed and running on `PB311XHGKC220141G`, SHA-256
`abc6fe66aaf9500586eb8c825feeb55ced6d5c8ad301fd15106034cf63a42957`.
It includes square compact VST access and the calibrated detector-coordinate mapping described
in [the recording and root-cause findings](MESH_FLICKER_RECORDING_FINDINGS_2026-11-03.md).
The same four compact/fused/GPU flags remain enabled; retained VST remains disabled.
Both apps and both OpenMR packages were stopped before replacement and launch. No service APK
was installed for this correction; both service APK hashes match before/after.

Lab PID `31583` and Spatial service PID `9270` supplied fresh startup face frames 45, 98 and 152.
Session `040d4d`, frames 356–897, contains 542 pipeline frames and matching scene-update rows:
537 valid face frames with visible mesh, plus five rejected repeated-timestamp frames with hidden
mesh. All 537 fresh exposures produce a valid native face and pose status 1. All 542 packets are
finite. Median detector confidence is 0.9471, median landmark presence 0.99999994; the previous
every-other-frame alternation is absent. Median submit-to-readback is 29.94 ms in this diagnostic
window; it is not a controlled performance comparison. All 11 remote samples report a face.

All outputs are enabled. Custom mode 4 and the original values are retained:
fx=fy=1746.4713, cx=1623.5, cy=1231.5. The controls report unlocked, the runner is active and no
automatic sequence is running. Optical calibration SHA-256 remains
`1dd838b47d6a8b129c04b7c227df87f815a8ee12332f3c18ef6c88febd21d097`.
All 321 pre-existing external app files remain present with sizes at least as large as before.
No profile was saved, recording started, calibration sequence run or app data cleared.
Debug remains `0`; the device lease is released. Headset clock: `2026-11-04T10:04:07+0800`.

Host gates pass: 39 detector/utility and 18 landmark parity cases, the production Kotlin
intrinsics/profile/runtime harness, and both apps' build/lint/format checks with JDK 21.
The GPU preprocessing model has four nodes and the resize-only candidate logged 4/4 OpenCL
delegation. Final initialization succeeds with the identical model; the bounded final log no
longer contains its initialization line. Physical alignment and a recorded One check's three
calibration exports still require inspection before Full trial.

Evidence: `artifacts/facelandmarker/flicker-compact-fix-install-20261103/installation.json`,
`face-window-analysis.json`, `performance-data/face-timeline.jsonl`, APK backup and file inventories;
`artifacts/facelandmarker/flicker-square-coordinate-host/`;
`/private/tmp/registrationlab-square-coordinate-final-build.log`.

## Latest pipeline installation — 2026-11-03

Installed the registration lab from source commit `97a24dd` on `PB311XHGKC220141G` with
`faceCompactVstPipeline`, `faceFusedControlModels`, `faceGpuPreprocessing` and
`faceGpuSampleBytes` enabled, and retained VST disabled. Installed APK SHA-256 matches the
built artifact: `49037fedc23cf903375dbe093080cde24a46e0786b12df73d86c7289b82d2bec`.
The previous APK was backed up and signing certificates matched before replacement.

The app and OpenMR packages were stopped before installation so GPU initialization used a
fresh Spatial service process. The original service APK hashes remain unchanged. Lab PID
`10955` and Spatial OpenMR PID `16966` supplied fresh advancing frames `14`, `20`, `26`, then
`33`; terminal readback is 6,332 bytes. The app reports **Ready for One check or Full trial**,
`trialsAvailable=true`, automatic phase `IDLE`, and active timeline logging. No face was in view
during this check, so face-bearing calibration capture and optical alignment remain unverified.

The optical calibration file hash is unchanged, and all 303 pre-existing external files remain
present with sizes at least as large as before installation. No calibration sequence or recording
was started, no profile was saved, and no app data was cleared. The device lease is released.

Evidence: `artifacts/facelandmarker/latest-lab-install-20261103-1608/installation.json`,
`startup-status.json`, previous APK backup, before/after file inventories, and startup logcat.
Headset clock at verification: `2026-11-04T08:01:38+0800`.
Use [the current capture instructions](AUTOMATIC_CAPTURE_STEPS.md) for a recorded One check
before another Full trial.

- Combined GPU/RGB-first preprocessing + inline fit (2026-11-02): [measured operation table](COMBINED_RGB_INLINE_BENCHMARK_2026-11-02.md). Only the new configuration was measured: two 30-second off/on windows; 336 completions, 167 untraced eligible faces and 150 matched traced face chains. Untraced median/p95 157.84/199.18 ms, cadence 5.66 Hz. GPU detector/landmark preprocessing 10.28/9.22 ms with 48/48 and 68/68 OpenCL nodes; inline CPU fit 1.61 ms. Lab diagnostic crop recovery adds 22.46 ms; decode JS 28.16 ms. All 25 operations and app boundaries listed. Prior performance/numerical suites were not repeated. One fresh SpatialML process for GPU initialization; original APK/debug and user pose-only selection restored; calibration and 286 original external files preserved; healthy final face frame 48; lease released. Capture acceptance remains separate. Artifacts: `artifacts/facelandmarker/combined-rgb-inline-20261102/session-output-20261102-152817/`.

- Inline geometry and measured component inventory (2026-11-02): [implementation](INLINE_GEOMETRY_MODELS_2026-11-02.md), [headset benchmark / all operations](INLINE_GEOMETRY_PIPELINE_BENCHMARK_2026-11-02.md). One weightless CPU model includes three Horn/Jacobi proper-rotation solves; no external SVD. Opt-in `-PfaceInlineGeometry=true`, precedence over split flag, both default false. 126 OpenCV-referenced full-fit cases, 7,001 rotation stress cases, 36 serialized bindings, runtime regressions and inline/default build/lint/format pass. Nine device windows / 676 completions / 182 eligible linked face chains: fit means original/split/inline 34.71/1.77/1.76 ms; untraced pipeline medians 256.73/230.34/237.78 ms. Inline removes model boundaries but shows no meaningful fitting gain over split; native preprocessing remains dominant. 25 inline operations and app work are listed with mean/p95. Original APK `7ae804e2e3606d81eb7c2ab64f649abad940731d1feab5a7578d68afd99ef023`, debug and selection restored; calibration and 271 original external files preserved; final face frame 137; lease released. No service restart/change, commit or push. Calibration/controlled device parity remains pending. Evidence: `artifacts/facelandmarker/inline-geometry-20261102/session-output-20261102-151103/`.

- Fused geometry models (2026-11-02): [implementation and validation](FUSED_GEOMETRY_MODELS_2026-11-02.md), [ordered component inventory](PIPELINE_COMPONENT_INVENTORY_2026-11-02.md). Three weightless CPU model assets in four calls replace eight fitting JS operations; three native SVDs and service tracker/validity feedback remain. Opt-in `-PfaceFusedGeometry=true` (default false). 126 real host LiteRT parity cases, 24 production model bindings, all graph variants, existing capture regressions and both apps' fused/default build/lint/format gates pass. Original 31.61 ms fit includes 30.89 ms JS and 0.72 ms native SVD; no new headset speedup claim. Headset reports no face; no experimental install or device measurement. Existing installed dynamic APK/data/calibration preserved. Artifacts: `artifacts/facelandmarker/fused-geometry-20261102/`.

- Dynamic-output headset benchmark (2026-11-02): [DYNAMIC_FACE_OUTPUTS_BENCHMARK_2026-11-02.md](DYNAMIC_FACE_OUTPUTS_BENCHMARK_2026-11-02.md). All seven combinations and all-off/resume pass. Native-preprocessing all-three median 260.38 ms versus pooled old-build controls 348.55/353.77 ms (25.3–26.4% lower; individual-control comparison 15.5–27.5%). All-three packet 6,332 bytes (47.1% smaller); pose 312, blendshapes 456. Fourteen trace-off mode windows, seven operator windows and repeated old-build off/on/off controls; 361 eligible face chains have validated type/owner/dependency/clock association. New model calls ~0.34 ms each for all-three; app decode/reconstruction 0.69 ms mean. Native preprocessing/shared fit remain dominant. Dynamic APK `7ae804e2e3606d81eb7c2ab64f649abad940731d1feab5a7578d68afd99ef023` restored, healthy face frame 51; all outputs enabled, debug unset, lease released, 268 original external files and camera calibration preserved. AndroidX compilation-cache file changed on install, tracked separately. Host build/lint/format and 168 parity/selection cases pass. No new calibration capture, optical/switch-interaction acceptance, service/SDK change, commit or push. Artifacts and validated HTML: `artifacts/facelandmarker/dynamic-outputs/session-output-20261102-141408/`.

Readback architecture analysis (2026-11-02): `READBACK_PIPELINE_OPTIMIZATION_2026-11-02.md` and `tools/analyze_readback_boundary.py`. Static checks use the existing RGB-first 27 eligible face chains, all 39 operators and current source tensor dimensions; operator/component and whole-frame budgets reconcile. 24 JS operators total 239.18 ms (78.2%); the post-landmark tail is 198.91 ms to audit/optimize, including internal dependencies that cannot all move to the app. Proposed live packet allowance is 5,992 bytes, versus current 11,976; this is a design allowance, not an implemented readback. User clarification restricts readback to final app outputs: keep detector/ROI, service tracker state and service expression dependencies internal; the previous intermediate app-decode/upload candidate is withdrawn. Diagnostic-copy/snapshot overlap is accounted for explicitly. No app/model/service implementation, build, install, new device measurement or optical validation in this pass. Existing runtime acceptance boundaries below remain in force.

Latest RGB-first runtime/performance: `RGB_FIRST_PIPELINE_BENCHMARK_2026-11-02.md`. Both new 48/68-node models execute fully on OpenCL. Face-bearing model-call mean savings 6.51–6.91 ms combined against repeated previous-GPU controls; untraced median 281.33 ms sits between controls 277.33/295.98 ms, so no consistent end-to-end gain. Mixed windows are explicitly stratified; 124 eligible face service chains (35/27/27/35) have unique wall/monotonic journal association, complete operator/type/dependency checks and reconciling same-frame budgets. RGB operator means total 305.99 ms; wrapper/gap/submission-readback remainder yields 323.93 ms tracing-on mean. 39 operator comparisons, remaining ranking, signatures/hashes/provenance and generated HTML are retained. Original native build restored, debug unset, calibration/files preserved, lease released. Fresh service processes used for each GPU variant; no service APK/SDK change, calibration capture/profile change, clear/uninstall, commit or push. Controlled pixels, coherent exports and optical correctness remain unverified; flag stays experimental.

Latest RGB-first implementation: `RGB_FIRST_PREPROCESSING_2026-11-01.md`. Separate uint8-source Resampler models omit full-frame CAST (48/68 ops). Pinned OpenCV 4.11 reference, small exact old/new serialized parity, graph selection and existing packet/completion/motion/profile regressions pass; both app builds/lint/format/signatures/model hashes pass. Mac Metal compilation passes but uint8 input-buffer execution remains blocked. Headset disconnected; no install or device change, and Android correctness/performance are unverified. Both flags are opt-in, old models/defaults retained.

Latest face-present GPU benchmark: `GPU_PREPROCESSING_FACE_BENCHMARK_2026-11-01.md`. Fresh run after user-requested OpenMR stop: 572 completions / 571 faces. Native/GPU/native eligible submit/readback medians 227.33/186.14/239.06 ms, cadence 4.15/4.98/3.97 Hz. Traced detector preprocessing 36.42 → 18.44 ms and landmark preprocessing 52.21 → 17.87 ms. All 39 operator changes plus end-to-end readback/upload boundaries are retained. Complete task/type/dependency checks admit 64 native and 79 GPU chains. Full runtime ring retains complete 49/69-node OpenCL delegation in new service PID 16632. Earlier GPU input-buffer failures preceded the service reset; lifecycle root cause remains unconfirmed. Original APK restored/hash-verified, final face tracking healthy, debug unset, original app files/private calibration preserved and lease released. Controlled pixels, coherent exports and optical correctness remain unverified; GPU stays experimental. No calibration capture/profile change, clear/uninstall, service APK/SDK change, commit or push.

Earlier no-face GPU benchmark: `GPU_PREPROCESSING_BENCHMARK_2026-11-01.md`. Native/GPU/native no-face windows measure eligible median submit/readback 205.57/153.49/203.03 ms; throughput 4.59/5.98/4.64 Hz. 652 journal completions, zero faces. Complete native/GPU service tasks and startup OpenCL/NPU delegate evidence are retained. Two controlled pixel-probe attempts failed before producing comparisons; no accuracy pass or face-bearing speedup is claimed. Original completion-repair APK restored and hash verified, debug unset, data preserved, device lease released. The restored camera stream recovered and reached frame 496/stopped=false. Test-only instrumentation and float-image allocation helper build/lint/format checks pass. GPU flag stays experimental; no service/SDK/calibration change or commit.

Latest boundary: the failed repeated C check exposed a wall-clock fallback bug in the newly added frame guard. The fix, brief-exposure motion gate and two headset start buttons pass host/build/style checks; the latest installation/layout verification is recorded at the end of this file. The capture flow no longer requests a PC connection. Real-face capture and physical alignment acceptance remain pending.

## Build and host checks

- Spatial SDK BOM 6.1.9, JDK 21, arm64-v8a, NPU inference.
- Final managed `spatial-3d-generation` run: `run-437b28be-0cd6-4e67-9917-09d992f802ed`; Codegen source artifacts and deterministic `assembleDebug` build evidence delivered, validation passed.
- Both face and registration-lab `lintDebug` and `spotlessCheck` passed.
- SpatialUI design-style verifier passed with no errors/warnings. It preserves PicoTheme and built-in Button/Text, component-owned foregrounds and transparent layout regions; preview images are diagnostic domain content. No root background or custom hover implementation was added.
- Placement source gate passed. Its containment advisory is a heuristic match on the `SpatialViewContent` import; this unbounded Stage mesh has no containment/fit requirement.
- Existing port checks passed: model hashes, fixed topology, JavaScript binding completeness, 24 transform/deformation fixtures, face-loss/NaN handling and APK platform-stub exclusion. Existing float32 geometry fixtures also passed.
- APK v2 signature verified. Latest local and installed APK SHA-256: `12ea6b76c7af3c2edb92e04e002530ac43cd6130699fd6314056ed944a843d2b`.
- Analyzer fixtures passed for all three image modes with rotated crops, nonidentity camera/face/Stage transforms, and stale-sequence rejection. Actual shipped camera/affine scripts passed six output checks. Synthetic known-camera recovery maximum error: 0.345 saved pixels.
- End-to-end synthetic rendered-board set: 16/16 boards detected, 0.120 saved-pixel calibration RMS, stationary-board Stage-position RMS 0.184 mm. This validates the analyzer, not headset camera calibration.

## Device evidence

ROM fingerprint:

```text
Pico/swan/swan:16/BQ2A.260122.002-BP2A.250705.008/20261014024400:userdebug/test-keys
```

The initial launch encountered a native platform abort after camera configure failed. Logs showed a previous face app session was still active and the metadata calibration query preempted its camera stream. The install helper now stops the normal face app and any previous lab instance before launching the lab. A subsequent clean startup reached `pipeline_ready`; the final installation did so again and advanced past frame 100 with capture-time Stage registration available. No service restart or device-wide readback bypass was used.

Runtime samples from the first validated installation (`8ee19ac96b9cd0a425564c27c78284dc19f33ee04a44337665a36fccd4bc2eca`) were retrieved and analyzed. The final build differs only in the project-required formatting of the tensor constructor; its APK identity and clean startup were verified separately. These captures show a face photograph on a monitor, not a live person's physical face.

| Mode | Sequence | Head stable | Raw crop → packed landmarks RMS, native px | Mesh → packed landmarks RMS, native px | Service → Stage vertex RMS, m |
|---|---:|---|---:|---:|---:|
| A | 50 | No | 17.228 | 11.217 | 6.84e-8 |
| B | 151 | Yes | 9.824 | 7.499 | 7.32e-8 |
| C | 210 | No | 0.000185 | 4.444 | 6.95e-8 |

The numeric Stage transform matches the exported service vertices. These samples expose source-projection discrepancies worth investigating; they do not establish a correct physical depth, a compositor calibration, or that C is best. Head pose and image position varied between modes. The lab reports these measurements and does not adopt any correction.

The raw camera/model images were inspected: the RGB model crop contains the detected portrait and landmarks, and source overlays are readable. The precise wireframe/passthrough overlap and per-eye placement are **UNOBSERVED** in this validation; host camera exports are not a compositor recording. The current Kotlin public capture path does not export per-eye renderer matrices. HMD history uses callback arrival times, which can differ from hardware tracking time.

Evidence is under `artifacts/facelandmarker/registration-lab/`: managed build results, lint/format log, source/style checks, synthetic reports, retrieved sample images/JSON, device analysis, initial crash/service logs, final markers, and artifact identity. The debug property remained unset, no bypass was enabled, and the devmux lease was released. The final lab was left running in initial Mode A with Wireframe and the first face step.

## User calibration capture set

The two completed face/checkerboard recordings and 10+10 finalized samples were retrieved and analyzed after the initial validation. See [the results](CALIBRATION_RESULTS_2026-10-28.md). Actual VST mesh overlap is now observed, but accepted camera/extrinsic calibration remains pending. Ten sharp board images support an exploratory horizontal focal-length mismatch; the full motion gate accepts one, and four face packets exhibit native output inconsistencies.

## Measured-camera trial ready for installation

- APK: `FaceRegistrationLabApp/build/outputs/apk/debug/registrationlab-1.0-debug.apk`, package `com.pico.spatial.ml.sample.facelandmarker.registrationlab`, arm64-v8a, APK v2 signature verified.
- Current trial SHA-256: `eadeb802521db9d6c397962f2a82cba5bdf9cd04c1228976a21c9d15dc9ebb83`. This supersedes the earlier local APK hash; the headset still has the earlier build until reinstallation.
- Both normal face and lab `assembleDebug`, `lintDebug`, and `spotlessCheck` passed. Commands used JDK 21 at `/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home` with `JAVA_TOOL_OPTIONS=-Djavax.net.ssl.trustStore=/private/tmp/facelandmarker-port/trusted-cacerts`.
- SpatialUI style check passed with zero errors/warnings. Existing PicoTheme, built-in Button/Text, component-owned control colors, transparent layout and container backgrounds are retained. No custom UI color, background, hover treatment or spatial panel placement was added.
- Real Kotlin profile/motion/decoder fixtures passed using the shipped JS snapshot operators: 66 producer, 1995 fit and 9395 final mesh floats. They reject stale producer/fit/mesh sequences, timestamp/mode mismatches, NaNs and incomplete packets. Steady exposure remains accepted when the later export window moves; exposure translation/rotation and missing history are rejected.
- All four camera/affine modes passed shipped-operator checks. Schema 3 synthetic analysis passed Stage/source conversions, native-boundary pack/metric replay, deliberate corrupted metric detection and stale fit rejection. A rendered new board view detected all corners and gave lower fixed-candidate residual than service K. Known-camera recovery error remained 0.344 saved pixels.
- Existing 24 coordinate/deformation fixtures, 40-frame float32 raw-pose reconstruction checks, asset/model hashes, JavaScript binding completeness and APK platform-stub exclusion passed. These establish host behavior and packaging, not native service correctness or physical alignment.
- D uses the exact preserved B affine with the exploratory measured source K. The normal face sample remains on service K. Schema 3 exports nested native intermediate snapshots with frame identity and separates ±50 ms exposure motion from export motion; 2048 HMD callback samples are retained.
- Native inconsistency is still under investigation. The new snapshots are intended to locate it; no root cause or runtime fix is claimed from host checks alone. Per-eye renderer matrices remain unavailable and HMD times remain callback-arrival times.
- Device runtime for this APK: **NOT RUN — headset charging**. No install, device-data mutation, service change, debug bypass, commit or push was performed for this increment.

Use [TRIAL_CAPTURE_STEPS.md](TRIAL_CAPTURE_STEPS.md) after installation: six A/D face exposures and four independent new board views, with offline recording/saves supported. Four board views validate the fixed candidate; they do not replace the full 12-view calibration requirement. Local build, signature/packaging and numerical artifacts are under `artifacts/facelandmarker/registration-lab/measured-trial/`; the build log is `measured-trial-build.txt`.

## Latest headset installation and startup limits

Latest APK SHA-256: `9d3288e129017af1f6f2f7dc89da729565fe2d3a02c005fe87ab45a3bbafdcb5`. Installation succeeded and the new process `24570` logged `camera_calibration source=device_cache`, `pipeline_ready` with Full Space Mixed / 0×0×0, and `camera_stream_ready` at sequence 1, capture age 0.387 s. USB disconnected during the subsequent ten-second observation, so the final process could not be rechecked. Last configured state was A, frontal 1 m, Wireframe, initial counters. The devmux lease was released.

The initial trial (`eadeb802…`) saved D sample 163 in schema 3. Native virtual K was fx=2027.879761, fy=2036.955322, cx=1661.005737, cy=1230.337524; maximum difference from A×measured source K was 0.0000311 px. Producer/fit/mesh sequence markers and result snapshots matched. Both motion gates passed (exposure translation 0.096 mm, rotation 0.0105°). All four exported files were pulled and SHA-256 matched the device; the analyzer accepted the sample. It shows the room without a measured face, so it verifies camera/profile/capture plumbing, not positive face geometry or physical alignment.

A final forced restart exposed delayed service camera teardown. Waiting for Full Space tracking and delaying startup alone did not resolve that case. An attempted in-process camera recreation encountered a native abort and was removed. The delivered code persists the validated optical camera-to-head matrix in app-private storage, tied to the ROM fingerprint, and completes a cold metadata query before SpatialML connects. Cold query/cache reuse and a later fresh stream were observed; immediate forced reentry still failed in testing. This is an open ROM/runtime limitation, not a claimed solved startup regression. No service or firmware change was made.

Both apps passed `assembleDebug`, `lintDebug`, and `spotlessCheck` after the startup/cache change. APK v2 signature, assets, JS bindings, coordinate fixtures and platform-stub exclusion passed. The geometry/profile operators and models retain their validated payloads. All four pre-existing calibration session directories were observed intact after installation. The earlier crash buffer and user files were preserved; debugging stayed unset. Final sustained operation and a new D save on this APK remain unverified because the USB transport disappeared.

The environment preflight returned `PARTIAL`, described as usable with non-blocking warnings: CLI `0.6.0 (public)`; global Plugin `pico-unity-agentic-tools@0.1.0`; SDK `no-project` in the root doctor (the repository BOM is 6.1.9); PICO development knowledge `6.0`; Emulator and Editor unprovisioned in this overview. The CLI update/platform/context warnings did not block device operations. No host setup/update or knowledge query was performed.

Follow [the short capture guide](TRIAL_CAPTURE_STEPS.md) once advancing frames and Ready are visible. Keep the current session open. Evidence is under `artifacts/facelandmarker/registration-lab/measured-trial/`: build manifest, native D export and hashes, startup/restart/error logs, latest installation markers and host checks.

## Returned A/D trial and capture repair

This section supersedes the earlier installation boundary above. See [TRIAL_RESULTS_2026-10-28.md](TRIAL_RESULTS_2026-10-28.md) for analysis of the completed trial. Five finalized exports were recovered: two positive faces and three boards. All 20 capture files and four recordings matched headset hashes. The fixed candidate gives pooled board RMS 0.459648 saved pixels versus 3.797982 for service K. Both face probes are internally coherent; direct camera-to-Stage invariant RMS is 1.01e−7 and 1.42e−7 m. Physical VST/stereo overlap and the cause of earlier intermittent native inconsistency remain unverified.

The recordings expose a readiness problem: the runner used frame duration as freshness. The repair exports actual freshness in diagnostics[30], consumes saves only after frame eligibility is known, retains pending saves on ineligible frames, suppresses previews while pending, preserves countdown/export messages and resets readiness on step changes. Timing exports/logs record camera age at submit/readback and frame readback latency. No geometry, calibration or Stage rendering equation changed in this repair. The board sequence's terminal watchdog stall remains unexplained.

Both apps passed `assembleDebug`, `lintDebug` and `spotlessCheck` after the repair. Targeted host regression runs shipped diagnostics JS into the actual Kotlin `FaceFrame` decoder and save-state methods: fresh with zero duration, stale with positive duration, pending-request retention, single consumption, locked message preservation and step readiness reset all pass. Shipped-JS/Kotlin decoder/profile/motion fixtures pass. Asset hashes, JS bindings, coordinate fixtures and APK platform-stub exclusion pass; all packaged operator payloads match current source. Evidence: `artifacts/facelandmarker/registration-lab/trial-results-2026-10-28/`.

Repaired lab APK SHA-256: `498f230c79a5701db80e338d44705b473d3897f4a02517a1a4d1e9792b0fc22b`. Replacement installation and explicit activity launch succeeded on PB311XHGKC220141G; the installed `base.apk` hash matches. New PID 25212 logged device-cache optical calibration, Full Space Mixed / 0×0×0 pipeline readiness, and camera stream availability at sequence 1 with capture age 0.402 s. The first frame's actual freshness flag was false, so that startup marker alone does not prove lab readiness. Subsequent diagnostic-save/liveness results are recorded below.

All seven pre-existing calibration session directories remain visible after replacement. No app-data clear, uninstall, recording deletion, service/firmware change, debug bypass, commit or push was performed. Host preflight was reused from this unchanged session's usable `PARTIAL` result.

The same PID subsequently logged fresh advancing camera frames at sequences 100 and 200 (09:27:45.492 and 09:28:47.948 headset time). Sequence 200 camera age was 0.613 s and submit/readback latency was 0.290 s. Stage registration was available, but neither log contained a detected face. Shell step/mode/save commands were delivered; the attempted diagnostic save produced no finalized export during observation. Consequently the repaired app's startup and advancing freshness are verified, while UI readiness, a new successful save and positive-face rendering on this APK remain unverified. The final commands requested A and the initial frontal step; panel state was not independently observed. The devmux lease was released and the app was left running.

## Latest C/D video analysis

The newer 09:42:04 recording was pulled and hash-matched to the headset. It is 174.766 s at 2560×1440. Sampled full frames, face crops and panel OCR show A/B/C/D comparisons and confirm frequent unready status with Saved 0. The wearer prefers C and reports its slightly small/high residual similarly in each eye; D made overlap worse. This establishes a visual preference, not calibrated depth or extrinsics. Audio was not assessed.

A same-landmark host replay on the earlier positive D far sample gives C depth 1.8997 m versus D 2.2126 m while retaining approximately 14.3×19.0 cm face dimensions. Small focal/cy perturbations around C establish sensitivity directions without identifying accepted corrections. No source-code or APK changes were made during this analysis. Read [MODE_C_REFINEMENT_FINDINGS.md](MODE_C_REFINEMENT_FINDINGS.md) for evidence paths, limits and the next controlled trial.

## Adjustable intrinsics build — 2026-10-29

This section is the current build boundary. User instructions are to finish the build and instructions for now; installation and headset verification are deferred. The device was disconnected at the availability check. Nothing was installed and no device files were changed during this increment.

- Launcher: **SpatialML Face Calibration**; existing lab package `com.pico.spatial.ml.sample.facelandmarker.registrationlab`.
- APK: `FaceRegistrationLabApp/build/outputs/apk/debug/registrationlab-1.0-debug.apk`, 32,698,519 bytes.
- SHA-256: `46bdd4e16c3200b3d38d57c23c29c7bf982b8c8a21a24641cca0ffb9a83af515`.
- Both apps passed `assembleDebug`, `lintDebug` and `spotlessCheck`. Final build completed in 13 seconds with JDK 21, the existing task trust store and Spatial SDK BOM 6.1.9.
- APK v2 signature verified. All 16 packaged JS operators match source bytes. Model hashes, operand bindings, Full Space Stage manifest, 24 coordinate/deformation fixtures and platform API stub exclusion passed.
- SpatialUI design-style verifier passed with zero errors and warnings. NumberField/Slider APIs compile against the resolved SpatialUI design 0.11.3 artifact.

Custom mode 4 starts from C or a valid saved profile and edits effective virtual-image fx/fy/cx/cy independently. It preserves C's image affine and supplies K directly. Normal sample behavior still uses service calibration. The graph applies edits between completed frames, preserves the accepted camera clock for K-only edits and resets geometry smoothing when needed. Captures pin mode, values and revision and check actual captured K. Values are saved independently of camera/face readiness, with private automatic-load storage and external latest/archive JSON files.

The production Kotlin profile codec/store, constructor/autoload, asynchronous save/load, control state, capture-queue methods, graph reset method and packet decoder passed targeted host fixtures. Cases include independent parameter changes and clamping, JSON roundtrip, wrong ROM/dimensions/coordinate-space/profile rejection, invalid focal/principal-point values, scalar/matrix and affine mismatch, archive preservation, restart autoload, reset/load, corrupt-profile fallback, old-revision rejection, queued-save retention/countdown/single consumption/timeout, locked status preservation, and saving numeric values after a fatal camera stop. The fixture uses real `org.json` 20240303 with small host Android context/storage adapters; it does not certify Android AtomicFile behavior or real device persistence.

Shipped diagnostics JS passed fresh-zero-duration/stale-positive-duration cases through the actual Kotlin FaceFrame decoder, including effective K. Shipped camera/affine operators passed all five modes, including asymmetric Custom focal lengths and shifted principal points without a second affine multiplication. The numerical analyzer accepted five synthetic modes, rejected stale identities and four corrupt Custom profiles, and retained the native-boundary replay/corruption checks. Known-camera recovery maximum error was 0.3442 saved pixels. Separate shipped-JS/Kotlin snapshot/profile/motion fixtures passed, including the Custom ROM guard.

Reproduce the targeted host checks:

```sh
# Obtain org.json:json:20240303 as a host-only fixture dependency; it is not an app dependency.
curl -fL https://repo.maven.apache.org/maven2/org/json/json/20240303/json-20240303.jar \
  -o /tmp/face-calibration-json-20240303.jar
python3 FaceRegistrationLabApp/tools/validate_intrinsics.py \
  --json-jar /tmp/face-calibration-json-20240303.jar \
  --output artifacts/facelandmarker/registration-lab/intrinsics-tuner-validation
python3 FaceRegistrationLabApp/tools/validate_lab_runtime.py \
  --output artifacts/facelandmarker/registration-lab/intrinsics-tuner-runtime
uv run --no-project --with numpy==2.5.3 --with opencv-python-headless==5.0.0.93 \
  python FaceRegistrationLabApp/tools/validate_registration_lab.py \
  --output artifacts/facelandmarker/registration-lab/intrinsics-tuner-analysis
```

The generic design-to-app patch scanner does **not** pass: it expects a `mainApp` entry function and explicit immersion/min/max manifest keys, whereas the inherited sample uses `MainApplication`/`DefaultStage` and Stage style 1. It identifies the Stage root and unchanged container correctly. Its UI whitelist also does not recognize the sample's compiled ECS/SpatialML APIs. The separate architecture checker recognizes the documented demo waiver and downgrades package-layout findings, but still rejects the inherited controller for lacking a `ui/*ViewModel.kt`. These are recorded checker failures, not reported as passes; this bounded sample extension retains the existing lifecycle/controller structure. See [CALIBRATION_CONTROLS_DESIGN.md](CALIBRATION_CONTROLS_DESIGN.md).

Evidence: `artifacts/facelandmarker/registration-lab/intrinsics-tuner-validation/` contains build manifest, logs, profile/state fixture report and generated host inputs; sibling `intrinsics-tuner-runtime/` and `intrinsics-tuner-analysis/` contain snapshot/math reports. The shell helper passes `bash -n` and now supports profile retrieval and parameter commands; no new device command was executed.

**Not verified:** in-headset control layout/input, Android save/load across real app launches, applied native Custom K, successful new face captures, or physical mesh overlap. Existing forced-restart/service-camera and intermittent capture limitations remain open. No camera/extrinsic correction has been accepted from these host checks. No commit or push was made. The next user procedure is [CALIBRATION_TUNING_STEPS.md](CALIBRATION_TUNING_STEPS.md).


## Calibration installation — 2026-10-29 host date

The user subsequently requested headset installation. Replacement installation (`install -r`) and explicit activity launch succeeded on PB311XHGKC220141G with the expected Swan ROM fingerprint. The installed base APK SHA-256 matches `46bdd4e16c3200b3d38d57c23c29c7bf982b8c8a21a24641cca0ffb9a83af515`. All 128 pre-existing app files remained present after installation. No app-data clear, uninstall or recording deletion was performed.

PID 10764 logged factory optical calibration from the device cache, `pipeline_ready stage=full_space passthrough=mixed container=0x0x0`, and Custom mode 4. The applied working values were fx=1746.47, fy=1746.47, cx=1623.5, cy=1231.5. Camera streaming started at sequence 1 with age 0.272 s; sequence 2 and subsequent frames were fresh, advancing and Stage-registered. Their readiness reason reached **Waiting for a measured face**, which is checked after the Custom effective-K match guard. No measured face was observed during this short startup window; no new face capture or physical-alignment acceptance is claimed.

Headset log times were 10-30 05:58:52–05:59:02. The process remained alive at the end of the check and the devmux lease was released. The app was left running for tuning. No extra forced lab restart or service change was used.

Evidence: `artifacts/facelandmarker/registration-lab/intrinsics-tuner-install/` contains installation/launch output, before/after file inventories, installed hash, startup logcat, selected markers, lease release and `installation.json`. Android profile save/load across actual app launches and in-headset control/mesh validation remain unverified. Follow [CALIBRATION_TUNING_STEPS.md](CALIBRATION_TUNING_STEPS.md); USB may be disconnected for tuning and saving.


## One-parameter tuning UI — 2026-10-29 host date

The user's requested UI is implemented and installed: a selector Button cycles fx → fy → cx → cy; only the selected value is shown. Decrease/Increase Buttons apply the selected adjustment step, the Slider spans the panel width, and the step Button retains 0.5/5/25 px increments. The value is plain read-only Text. NumberField and direct text entry are removed. Selection changes preserve all calibration values and do not change the graph revision. Save values, Load saved and Reset C retain their behavior.

Both apps passed assembleDebug, lintDebug and spotlessCheck; the build took 26 seconds. SpatialUI style verification passed with zero errors/warnings. The UI uses built-in `com.pico.spatial.ui.design.Button`, `Slider` and `Text`, under the existing `PicoTheme` in FaceLandmarkerSample. Native colors, built-in hover/haptics and component foregrounds remain in use; the Stage attachment layout is transparent with no new root background, surface, border, custom color or custom interactive component.

APK SHA-256: `f9d1d3a0a82f06f93d8d15489955a0cfd9308701b88733c9d7a71a6174814a52`. APK v2 signature verified. Replacement installation and launch succeeded on PB311XHGKC220141G; the installed base APK hash matches. All 128 pre-existing app files remain present. PID 10765 reached Full Space Mixed / zero-sized container, Custom mode and fresh advancing Stage-registered frames. The initial C values remained full precision (1746.4713/1746.4713/1623.5/1231.5), revision 0. No measured face was observed in the short startup window. In-headset controller interaction and physical alignment are not certified by these startup checks.

The app was left running and the devmux lease released. Evidence is in `artifacts/facelandmarker/registration-lab/single-control-install/`, including build/style output, installed hash, file inventories, startup markers and installation result. [The tuning guide](CALIBRATION_TUNING_STEPS.md) describes the updated controls. No commit or service change was made.


## Desktop controls over adb — 2026-10-29 host date

The preferred control surface is now the local browser at **http://127.0.0.1:47835**. [DESKTOP_CALIBRATION.md](DESKTOP_CALIBRATION.md) documents startup and use. The running server serves four numeric/slider controls, keyboard steps, Save on headset, Load saved and Reset C. It reads current state on connection, coalesces rapid edits, orders pending edits before Save, and distinguishes accepted values from effective intrinsics read back from a camera frame. Failed edits are discarded on disconnect; reconnect reads current state without replaying them.

The Android-DUMP-protected command receiver returns versioned base64 JSON in ordered-broadcast results. Invalid/out-of-range/locked commands report rejection, and status remains readable while stopped. Per-frame telemetry records actual K, applied revision, face state and elapsed time since readback. The Python bridge is loopback-only, checks origin/token and command allowlists, validates finite ranges, and invokes pinned devmux/adb arguments without shell interpolation. It uses separate short transactions, not a lease spanning the browser session. No external web framework is required at runtime.

Both apps passed assembleDebug, lintDebug and spotlessCheck (18-second build). The APK v2 signature verified. Installed SHA-256: `a10212f79902d4021729a230f41a8b85f4c2a0ff9bc644adb573451305d318d8`. Replacement installation and explicit launch succeeded on PB311XHGKC220141G, with installed hash match and all 128 pre-existing app files retained. PID 10804 reached Full Space Mixed, 0×0×0 container, Custom mode and fresh Stage-registered camera frames.

Production Kotlin host fixtures passed remote status serialization, edits and revision updates, actual-frame telemetry, invalid values/unknown commands, locked rejection and stopped-state readback, in addition to existing profile/queue/clock fixtures. HTTP tests passed value validation, broadcast decoding, missing receiver, origin/token checks and disconnect reporting. Real Chrome tests against a fake headset passed numeric, keyboard and slider input, rapid-edit coalescing, save ordering, external edits, disconnect/reconnect and zero application JavaScript exceptions. The app's actual HTTP/adb path then changed fx from 1746.471313 to 1745.971313, observed the changed value in native frame 501, and restored 1746.471313. The restore was also read back from a frame. No test profile was saved. A real browser page connected to the actual headset, displayed matching requested/effective values and passed the live status check.

Evidence: `artifacts/facelandmarker/registration-lab/desktop-validation/` contains host/browser logs, fake and live screenshots, roundtrip/restoration JSON and manifest; `desktop-install/` contains installation and data-preservation evidence. The background server PID is 8078 and its log/PID are in the validation directory. The user page was opened, the app left running, and the installation/probe leases released. Physical face overlap and user mouse/keyboard ergonomics remain user acceptance, independent of these verified control/readback paths. Existing camera-runtime limitations are not declared fixed. No service change, commit or push was made.


## Badge-only timing update — 2026-10-29 host date

This is the latest installed build boundary and supersedes the manual-headset-control descriptions above. The user removed the existing calibration UI; the headset now shows only a three-line timing badge. Desktop/adb calibration commands remain available. Full Space Mixed, Stage style 1, the zero-sized SpatialML container and app-owned Stage mesh are preserved.

- APK: `FaceRegistrationLabApp/build/outputs/apk/debug/registrationlab-1.0-debug.apk`.
- SHA-256: `42e1f63cc49edde03002b7411e60ec664f9b59ce86fe3f4e2a39f17627e453e8`; installed base APK hash matches.
- Package: `com.pico.spatial.ml.sample.facelandmarker.registrationlab`; headset `PB311XHGKC220141G`.
- ROM: `Pico/swan/swan:16/BQ2A.260122.002-BP2A.250705.008/20261014024400:userdebug/test-keys`.
- Replacement installation and explicit activity launch succeeded; PID 11099 reached `pipeline_ready stage=full_space passthrough=mixed container=0x0x0` and camera streaming. All 129 pre-existing app files remained present. The devmux lease was released.

Both modules passed assembleDebug, lintDebug and spotlessCheck; the final 240 dp badge build completed in 12 seconds with JDK 21 and the existing task trust store. SpatialUI style verification passed with zero errors/warnings. Actual Kotlin fixtures exercised timing-label/journal agreement, immutable frame metadata through Stage conversion, mesh visibility and normal-close journal draining, alongside the existing profile, command, freshness and frame-pinning checks. The generic design scanner and architecture checker retain their documented inherited failures (entry/immersion metadata expectations and missing UI ViewModel despite the demo waiver); these are not reported as passes. The environment doctor remains the usable PARTIAL result described above.

The first installed 180 dp layout clipped the third badge line. The final layout uses a 640×240 dp attachment with 12 dp outer padding. Inspection of `install-final/headset-ui.png` confirms all three lines fit in both eye views. The rotated crop shows `SYNC b8f55e #000062`, `UI 6.258 s | CAM -- s`, and `F-- K-- M-- | NO MESH`. Session `2026-10-30T00-44-12.461977Z-b8f55e` contains tick 62 with `relativeSeconds=6.257605102` and null mesh, exactly matching the displayed state after rounding. This screenshot preceded the first completed mesh update; it verifies badge layout and timeline association, not positive mesh appearance.

The subsequently retrieved journal contains 86 complete JSONL rows, ticks 1–79, and 11 visible-mesh tick rows. Ordered status reports actual frame 4, Custom mode 4, revision 0, `hasFace=true`, `visible=true` and `logging=true`. Effective K remains the C defaults (fx=fy=1746.4713134765625, cx=1623.5, cy=1231.5); no new correction profile was saved. The collected crash log is empty. This is short startup evidence, not sustained camera-runtime or physical alignment acceptance.

`LabTimeline.kt` flushes each row on a bounded IO worker and stores it in the existing session directory. The UI shows LOG ERROR on queue/write failure. Scene metadata is attached to the exact immutable FaceFrame and published after the SDK update returns. UI state generation and SDK update completion are not compositor-present timestamps. USB is not required by the on-device journal; a separate disconnected endurance run was not performed. Normal close drains queued rows; abrupt shutdown can lose a final row. Marker phases, automatic sweeps, video fitting and corrected physical registration remain unimplemented.

Evidence: `artifacts/facelandmarker/registration-lab/timeline-validation/`, including `host/`, `final-build.log`, checker outputs and `install-final/installation.json`, `badge-verification.json`, `badge-inspection.png`, `status.json`, `timeline.jsonl`, app/crash logs and lease release. Current wearer instructions are [TIMELINE_RECORDING.md](TIMELINE_RECORDING.md). No app-data clear, uninstall, recording deletion, service/firmware change, commit or push was performed.


## Automatic capture update — 2026-10-29 host date

The new update implements a bounded capture controller, sparse Stage markers and automatic tagged exports. It is built and host-validated, but **device acceptance is BLOCKED: PB311XHGKC220141G is disconnected**. No installation or runtime/physical alignment acceptance is claimed. The badge APK documented above remains the last verified installed version.

- APK: `FaceRegistrationLabApp/build/outputs/apk/debug/registrationlab-1.0-debug.apk`; 32,718,043 bytes.
- SHA-256: `35683f449993446dfa9da94df01f9768019cb75df35449a27063c63263128e84`; APK v2 signature verifies.
- Package: `com.pico.spatial.ml.sample.facelandmarker.registrationlab`.
- Both modules pass `assembleDebug`, `lintDebug` and `spotlessCheck`; final run completed in 12 seconds. JDK 21 and the existing task trust store were used.
- Production Kotlin fixtures pass one-check and full 84-export phase order, matching scene/frame acknowledgements, stale/head-motion rejection, timeout/cancellation, starting-value restoration without saving a profile, marker centres, and immutable tag propagation through Stage conversion. Existing profile, receiver, clock and journal fixtures pass.
- Real Chrome plus HTTP tests against a fake headset pass automatic command delivery, queued-edit ordering before Start, disabled edits/saves while running, Cancel during an export lock, restored values, active-run reconnect and older-app compatibility. These tests do not establish native headset behavior.
- SpatialUI style verification passes with zero errors/warnings. The desktop screenshot was inspected; automatic controls/status are visible without clipping. The new 740×420 dp headset badge still needs on-device layout inspection.

The refreshed desktop server is PID 76911 at `http://127.0.0.1:47835`; an HTTP read confirmed it serves the new controls. Refresh an existing browser page. Automatic buttons stay disabled on the previous APK and ask for the update. Server PID/log are under `automatic-validation/`; the older `desktop-validation/server.pid` pointer was also updated.

`auto_check` runs C once with three exports. `auto_start` runs seven candidates across four prompted poses, with reversed order in odd pose groups, for up to 84 exports. Both begin with a 15-second countdown. Each new pose has eight seconds of preparation. Three fresh exposures across at least two seconds, exposure age at most 0.9 seconds, matching K/revision, stable HMD history and Stage marker positions gate progress. Clean phases hold at least two seconds and marked phases at least three seconds after scene acknowledgement. Each phase has a 60-second timeout. The eight markers are 3 mm radius green octahedra at landmark IDs 33, 133, 362, 263, 1, 61, 291 and 152.

Every sampled export carries the immutable run/trial/candidate/pose/phase tag, effective K, source/model images and native/Stage geometry. Automatic export requires a matching scene tag and sequence, stable exposure and exact native mesh-result/readback equality. Journal events retain scene marker positions and exported folder names. Scene completion is an SDK update boundary, not a compositor-present timestamp. Pose/distance labels are prompts, not measured truth. Green marker identity and visible anatomical correspondence still need video analysis.

Completion, failure or cancellation restores starting working values with a new revision and never saves a calibration profile. An export already in flight may finish after Cancel; it remains tagged and cannot advance a cancelled sequence. Automatic status consistently asks the wearer to keep still. Preview RGB/bitmap work is skipped when preview tools are disabled. Full Space Mixed, Stage style 1, the zero-sized SpatialML container, app-owned Stage rendering and normal sample behavior remain in the source; their final runtime regression check is pending.

Managed scene run `run-7d053f5b-4bc4-4093-b7e4-a6d6fa48f21d` reached delivery validation and ended **BLOCKED**, not passed. The delivery validator recognizes only `scene_generated` and `project_builds`; the submitted required custom ID `stage_markers` therefore remains unverified. The source/build path produced an APK, and the separate final Gradle run above explicitly passes. Earlier run `run-57496ea0-9efb-4b71-a694-3351e52b092a` failed because the default scene output path did not match `FaceMeshScene.kt`. No workflow infrastructure was changed. Previously documented generic architecture/design scanner failures remain unresolved.

Evidence: `artifacts/facelandmarker/registration-lab/automatic-validation/` contains the build manifest with source hashes, Android/signature/host/desktop/style logs, fixture output, browser screenshot, managed workflow status and disconnected device snapshot. No device files were changed, and no service/firmware change, commit or push was made.

Next: connect the headset, replace-install with app data preserved under one devmux lease, check startup and badge layout, then record **one check sample** using [AUTOMATIC_CAPTURE_STEPS.md](AUTOMATIC_CAPTURE_STEPS.md). Inspect its two video views, readable tags, matching exports and landmark/marker overlay before asking for the full wearer sequence. Automatic video fitting, corrected calibration and disconnected device endurance remain unverified or unimplemented.


## Automatic update installed — 2026-10-29 host date

Replacement installation succeeded on PB311XHGKC220141G. Installed base APK SHA-256 matches `35683f449993446dfa9da94df01f9768019cb75df35449a27063c63263128e84`. The ROM remains the recorded Swan `20261014024400` fingerprint. All 130 pre-existing external app files remain present; no saved intrinsics profile existed before installation. No uninstall, data clear or recording deletion occurred.

The first process (25603) reached Full Space Mixed / 0×0×0 pipeline setup but supplied no fresh camera frame; the app stopped and correctly rejected automatic Start. Its failure is retained in `automatic-install/installation.json`. A single app-only stop/relaunch, after the failed session had closed, recovered camera acquisition. PID 25294 logged the cached factory optical calibration, Full Space Mixed pipeline readiness and fresh advancing camera frames. No service/firmware restart or camera permission bypass was used. This recovery does not establish that the existing intermittent startup issue is fixed.

The retry supplied actual C intrinsics (fx=fy=1746.4713134765625, cx=1623.5, cy=1231.5). An adb `auto_check` started COUNTDOWN; the screenshot was captured and `auto_cancel` stopped it before trial execution, with zero exports and the original working values restored. The later live desktop status observed frame 232, applied revision 1 matching requested revision 1, matching effective K, no automatic tag on the current scene frame, `stopped=false` and healthy timeline logging. The app was waiting for a measured face: positive face/marker rendering is not certified by this startup check.

The 740×420 dp countdown panel fits in the screenshot. The inspected crop reads session 6b8558 / tick 275, UI 22.834 s, CAM 22.388 s, F47 K0 M4 / NO FACE, AUTO 0/1 COUNTDOWN, and the recording countdown instruction. Journal tick 275 has UI relativeSeconds 22.833663846 and captureRelativeSeconds 22.387596798333107, with frame 47, revision 0 and the COUNTDOWN tag. This verifies the visible clock association and countdown layout, not compositor-present timing or the later marked-phase layout.

A real Chrome page and HTTP status call at `http://127.0.0.1:47835` connected to the actual app, confirmed the one-check button enabled and Cancel disabled after cancellation, and read back the restored K/revision. The app was left running, all devmux leases were released, and no automatic sequence remains active. The panel's CANCELLED message is the expected result of the installation probe.

Evidence: `artifacts/facelandmarker/registration-lab/automatic-install/installation-final.json`; initial install/failure/data inventories are in that directory, and successful recovery, camera logs, countdown screenshot/crop, timeline, command JSON, live desktop screenshot/status and lease release are in `retry/`.

Next: use [AUTOMATIC_CAPTURE_STEPS.md](AUTOMATIC_CAPTURE_STEPS.md) for **one** real-face Spatial recording, keeping both heads still through clean/marked/clean and waiting for Capture complete. Inspect both video views and three matching exports before requesting a full trial. Native marker/export execution, disconnected endurance, full-sequence timing and physical registration remain unverified. The video fitter remains unimplemented. No commit or push was made.

## Automatic one-sample check inspected — 2026-10-30 headset date

Retrieved Spatial recording `ScreenRecording_2026.10.30-09.50.36-AM.mp4` (422,952,782 bytes, SHA-256 `f3aa475ad8a5a812b48d2204ddf5e2dabc4c4ae707ffa880bc1ca9fcb7642890`) and session `2026-10-30T01-36-02.472865Z-6b8558` from PB311XHGKC220141G under one devmux lease, then released it. The headset copies, app data and profiles were preserved. Per-file hashes and the device-matching timeline prefix hash are in `retrieval.json`.

Run 1cfc5957 (C, prompted frontal pose) reached DONE and produced `001`/`002`/`003-mode4-step1` from CLEAN_BEFORE/MARKED/CLEAN_AFTER frames 2808/2882/2896. All are exposure-stable, revision 2, with C K. Native analysis accepted 3/3 with 0.0001 native px mesh RMS and 1.013–1.021 m inferred depth.

The recording decodes to 3,355 equal-PTS stereo pairs. Badge OCR gives app ≈ video + 875.4397 s from 51 anchors (residuals −0.049 to +0.050 s). Frame numbers match 41/41 and phases 36/38; the two mismatches are at transitions. Clean phases contain no false marker detections.

Marker/anatomy medians over 181 non-stale MARKED pairs:

| Measurement | Left | Right |
|---|---:|---:|
| dy | −50.64 px | −50.89 px |
| dx | +3.80 px | +0.95 px |
| Scale | 0.968 | 0.974 |

The markers have +2.86 px more crossed disparity than the face, so they appear nearer. Metric conversion relies on unverified recording metadata.

The installed gates are not ready for the full sequence:
- **Slow marked phase:** MARKED took 35.9 s. Replay reproduces export frame 2882, with 15 stale-frame resets, 3 missing-update resets and 1 drift reset. With 1.0 s freshness, or by skipping stale frames instead of resetting, the replay exports at frame 2816/2817.
- **Misplaced markers:** frame 2810 drew five markers at one non-face point after a repeated exposure changed `hasFace` from false to true.

Details and recommendations: [AUTOMATIC_CHECK_FINDINGS.md](AUTOMATIC_CHECK_FINDINGS.md). Scripts and JSON results: `artifacts/facelandmarker/registration-lab/automatic-check-2026-10-30/analysis/`.

No source code or installed APK changed in this inspection. Physical correction, compositor-present timing and the video fitter remain unverified or unimplemented. No commit or push was made.

## Approved automatic-capture fixes — 2026-10-30

The user approved all three changes from the one-sample findings. They are implemented and build successfully. **Device acceptance is BLOCKED: PB311XHGKC220141G was disconnected in the current devmux/adb snapshot.** No replacement installation, fresh native run, new recording or physical alignment acceptance is claimed by this entry.

- APK: `FaceRegistrationLabApp/build/outputs/apk/debug/registrationlab-1.0-debug.apk`, 32,725,623 bytes.
- SHA-256: `e9a1c1b7ba6511948fda75ae0df4547eb6a8742503049b3a75e87a37dd350345`; `apksigner verify` passed.
- Package: `com.pico.spatial.ml.sample.facelandmarker.registrationlab`; target PB311XHGKC220141G.
- Both modules pass `assembleDebug`, `lintDebug` and `spotlessCheck`; combined Gradle run completed in 27 seconds using JDK 21 and the existing task trust store.
- Actual Kotlin host fixtures and shipped diagnostics JS pass. Capture regressions cover unchanged three-phase order and all 84 full-run exports, exact scene/sequence acknowledgements, wider candidate values and reversal, preservation of a valid hold across old/repeated exposures, continued head-motion reset on old frames, repeated-exposure false-to-true face rejection, timestamp regression, collapsed/NaN marker rejection, Stage-transform invariance, timeouts and cancellation. Existing profile, command, revision, clock, freshness and journal fixtures pass.

`LabAutoCapture.frame` retains the 0.9-second freshness limit. Old/repeated face exposures cannot count as new stable samples or authorize an export; they preserve an existing hold only when head history, calibration and geometry remain valid. Head motion, face loss, unusable fresh frames, changed configuration/K or corrupt geometry still reset stability. Each phase retains its 60-second timeout.

The lab runner now evaluates `LabFaceFrameGate` on every packet. Face-bearing packets on repeated/non-advancing exposures, nonfresh face results or invalid selected marker geometry are hidden before receiving automatic presentation tags; they cannot authorize manual or automatic exports. Selected marker pairs must be more than 1 mm apart. The guard is lab-only and does not change normal sample `FaceFrame.hasFace` semantics. Reviewing all 69 recorded eight-marker scenes against that geometry threshold rejects exactly the prior collapsed scene; the minimum valid separation is 23.607 mm. This is evidence from the previous recording, not an updated rendered-device test.

The seven candidates are C, F98, F97, Y40, Y75, Y110 and C-repeat. They use the fixed C image affine; cy candidates keep C focal lengths and focal candidates keep C principal point. The full run remains seven candidates at four prompted poses, with reversed order in odd groups and three exports per trial. Completion/failure/cancellation still restores the initial working values without saving a profile.

The offline journal adds `pipeline_frame` on every completed inference, including submission/readback/capture clocks, aggregate latency, detector-path choice, freshness and rejection reason. Individual model/operator costs and compositor timing remain unmeasured for this Kotlin build. [PIPELINE_TIMING_PLAN.md](PIPELINE_TIMING_PLAN.md) and [UNITY_OPTIMIZATION_COMPARISON.md](UNITY_OPTIMIZATION_COMPARISON.md) document the current 451–538 ms selected-export timing and the saved Unity component profile. The comparison confirms identical landmark/blendshape model hashes and several identical scripts, but different detector bytes and XR/Spatial service paths. No Unity graph optimization, service change, latency improvement or corrected calibration is claimed.

The desktop at `http://127.0.0.1:47835` returned HTTP 200 and serves the automatic controls. No browser/control implementation changed. The current environment doctor returned usable `PARTIAL` with zero errors: Node 25.9.0, npm 11.12.1, CLI 0.6.0 public (0.6.1 update warning). Its six-row overview reports CLI `0.6.0 (public)`, Plugin `pico-unity-agentic-tools@0.1.0`, SDK `no-project` at this multi-module root, PICO development knowledge `6.0`, Emulator null, Editor null. Gradle source independently declares Spatial BOM 6.1.9. Root project-context and one plugin warning remain; no setup/plugin/SDK update was performed, and no MCP API lookup depended on that mismatched knowledge line. Host restart is not needed for the source-only update. Read-only device discovery used the existing devmux/adb helper; no device was attached and no lease was acquired.

Evidence: `artifacts/facelandmarker/registration-lab/automatic-fixes-2026-10-30/` contains `android.log`, production host outputs, `build-manifest.json` with final source/APK hashes and previous-scene geometry checks, and `environment-doctor.json`. Changes remain uncommitted.

Next: connect the target after any current recording finishes; preserve app data and recordings during replacement installation under one devmux lease, verify fresh-frame startup/effective C values, then record **one C check** using [AUTOMATIC_CAPTURE_STEPS.md](AUTOMATIC_CAPTURE_STEPS.md). Inspect three matching exports and both recorded views before the full sequence. If the wearer is already recording on the old build, retain that evidence and install only after the run/recording is finished.


## Approved fixes installed — 2026-10-30 host date

The headset reconnected and the verified APK was replacement-installed on PB311XHGKC220141G. The installed base APK matches SHA-256 `e9a1c1b7ba6511948fda75ae0df4547eb6a8742503049b3a75e87a37dd350345`. PID 10863 reached `pipeline_ready stage=full_space passthrough=mixed container=0x0x0`, camera streaming, Custom mode 4/revision 0, and actual C K (fx=fy=1746.4713134765625, cx=1623.5, cy=1231.5). Ordered status advanced through frames 3, 10 and 18. No automatic sequence was active at installation; final status was IDLE and unlocked.

All 144 existing external app files remain present, and the existing private `left-camera-to-head-v1.json` hash is unchanged. No saved intrinsics profile was present before or after installation. No app-data clear, recording deletion, uninstall, service/firmware change, debug-property write, commit or push was performed. The installation helper's initial attempt resolved the APK one directory too high and stopped before replacing the APK; its corrected path completed installation and verification. The devmux lease was released after both attempts.

The new `pipeline_frame` journal is live. A retrieved 30-frame prefix (frames 150–179) contains 20 advancing exposure steps, nine repeated exposure steps, zero regressions and zero face-bearing frames. All 30 producer freshness flags were true, so the explicit exposure-timestamp gate remains necessary; a freshness flag alone does not prove an advancing capture. Its median submission-to-readback interval is 281.4 ms in a no-face population, which is not comparable to the prior real-face export timings and is not a claimed optimization. Journal logging remains healthy. The actual Spatial service is `com.bytedance.pico.openmr.spatial`, PID 15780 in the process snapshot. The nonpersistent debug property is unset (disabled); no tracing was enabled during this check.

Evidence: `artifacts/facelandmarker/registration-lab/automatic-fixes-2026-10-30/install/` includes `installation.json`, replacement-install/launch output, before/after file inventories and private calibration hashes, startup statuses, app/full logcat, process/property snapshots, journal prefix and `journal-verification.json`, plus lease release. The source build manifest points to this installed result.

**Wearer acceptance remains PENDING:** put a real face about 1 m away, start Spatial recording, use **Capture one check sample** at `http://127.0.0.1:47835`, keep both heads still through clear/marked/clear, wait for Capture complete, stop recording and reconnect. Inspect all three exports and both stereo views for eight distinct markers, correct frame tags, phase duration and residual physical offset before a full sweep. Component profiling and any Unity optimization port remain separate follow-up work.


## Timeout repair and headset-only start controls — 2026-10-30 host date

Run `3ae2cc9f`, session `2026-10-30T18-28-13.921371Z-a05649`, timed out in SETTLE after 60.028 seconds with zero exports. It had 137 completed frames, 134 with a face; the new guard rejected all face frames after frame 77's wall-clock fallback poisoned its high-water mark. The fallback capture was `1793384960.7078192`, while monotonic readback was `3578.845314571`. Five fallback timestamps occur in the pulled journal. This was a source bug in the previous guard, not evidence of wearer failure. Clocks outside −0.1…2.0 seconds of readback now cannot advance guard/controller exposure history. Legitimate no-face exposures still prevent repeated-exposure false-to-true face acceptance. Clock/freshness-only replay yields 107 advancing face candidates; missing raw geometry/head motion in that failed build prevents replaying full export eligibility.

The wearer requested relaxed stillness, One check / Full trial buttons and removal of PC prompts. The app now checks ±50 ms exposure motion using the existing coverage/1 cm/1 degree limits and requires three usable frames over ≥0.8 seconds. Selected marker movement is bounded to 12 mm between usable frames rather than against the phase's original anchor. Sudden movement, bad geometry, unmatched calibration and old/repeated frames still cannot authorize an export. Independent save-time exposure and scene/snapshot identity checks remain. The journal now includes exposure motion coverage, translation, angle and acceptance per completed frame.

The existing 740×420 dp Stage panel contains two native SpatialUI buttons, One check and Full trial, with shared synchronized start logic, disabled active/locked/stopped/logging/capacity states and local click errors. The 15-second countdown and 3/84-export sequence contracts remain. Ready, timeout and completion states give headset recording/retry/storage instructions. The app uses the existing PicoTheme and native Button/Text colors/interactions; no custom color, root material, border or window was added. The inherited generic architecture/design scanner limitations remain as previously documented; this patch does not claim their resolution.

Both modules passed assembleDebug, lintDebug and spotlessCheck in 23 seconds. Actual Kotlin/JS host regressions pass clock-fallback recovery (including no-face/future/NaN packets), retained duplicate/collapsed rejection, natural drift, brief exposure versus the former long hold, sudden 2 cm rejection and all existing capture/profile/command/clock contracts. SpatialUI style checks pass with zero errors/warnings. APK signature verifies. Initial UI APK SHA-256 was `08d10e9b62423b2d336696d7f0ae4baeef1f1481784cc3db20208e06ff571cc7`; the final readable-hint build below supersedes it.

Evidence: `artifacts/facelandmarker/registration-lab/automatic-timeout-2026-10-30/` contains retrieved journal/status/app logs, `timeout-analysis.json`, production host results, style/format/Android logs and final source/APK manifest. Installation evidence is in `install/`. `HEADSET_CAPTURE_UPDATE.md` preserves the cause, repair and UI state contract. `AUTOMATIC_CAPTURE_STEPS.md` is the wearer entry point. Device-only scope covers capture controls/run/local evidence storage; fitting and applying a correction from the stereo recording remains unimplemented on headset.


## Headset capture update installed and layout verified — 2026-10-30 host date

Final APK SHA-256 `68ac56e426c560d8a944d159139bb695e3c0b6ce93dec8c904a7dcf7c3b41a0e` is installed on PB311XHGKC220141G and matches the host artifact. Final both-module build/lint/format checks pass (9 seconds), signature verification passes, and SpatialUI checks have zero errors/warnings. The earlier controller/clock/motion host regressions remain applicable; the last source change only moves the hint/error into the existing high-contrast badge.

PID 10968 reached Custom C mode/revision 0, effective C values, and advancing status frames 7, 15 and 22 with healthy logging. All 146 pre-existing external app files and the existing private camera calibration hash were preserved. No saved intrinsics profile existed. The devmux lease was released. Neither recordings nor app data were cleared. No service/firmware/debug-property change or commit/push was performed.

The captured headset views show One check and Full trial, the local recording instruction and Small movements are okay hint, without clipping. The earlier footer's dark semantic text was not visible in the raw composite; the final build puts the hint/errors inside the existing diagnostic background with its readable foreground. The screenshot lacks passthrough because adb screencap does not expose that compositor layer; it validates UI visibility/layout, not physical registration. `headset-ui-verification.json` records that boundary.

Current wearer flow is entirely on the headset: start Spatial recording, press One check, keep the face in view with natural small movement, wait for Capture complete and stop recording. There is no runtime PC/USB requirement or connect-to-PC prompt. The shared start method and sequence are host-tested; physical headset tap plus the new real-face three-export recording remain wearer acceptance. Full trial is available through the second button. Fitting/applying a correction from the recorded footage is still unimplemented on device.

Evidence: `artifacts/facelandmarker/registration-lab/automatic-timeout-2026-10-30/install/installation.json`, inventories/private hashes, startup status, final app logs, raw/upright final headset screenshot and `headset-ui-verification.json`; parent directory contains final build/style logs and source/APK manifest. See `AUTOMATIC_CAPTURE_STEPS.md` for the current device-only instructions and `HEADSET_CAPTURE_UPDATE.md` for the timeout cause and repair.


## Returned headset check and packet diagnostics — 2026-10-31 headset date

The headset-only One check run 5474a68b started successfully and the relaxed SETTLE phase completed in 1.032 seconds (three face frames, all exposure-stable). CLEAN_BEFORE contained six face frames, all exposure-stable, over 3.970 seconds. Its first export failed the raw/result comparison, so the run has zero accepted exports and no MARKED phase. This is not a successful calibration capture. `HEADSET_CHECK_FINDINGS_2026-10-31.md` records the detailed timing and boundary.

Retrieved `ScreenRecording_2026.10.31-03.04.14-AM.mp4`, 142,605,981 bytes, SHA-256 `634000ca39fede406f0a9a41720570e033d6b604be8764e495e1be624c2ad4e3`, with host/device hash parity and the matching journal. Both originals remain on the headset. Explicit view-ID decoding produced 1,626 equal-PTS stereo pairs, 1920×1080 per eye, view 0 left/view 1 right, spanning 54.7993 seconds. The preview shows the headset controls and face, then clean capture and failure; it cannot establish eight-marker acceptance.

A separate manual no-face packet-coherence save was captured, then its step restored. Its native snapshot/result packets match numerically and bit-for-bit. It is diagnostic evidence only and excluded from automatic/calibration acceptance. The actual rejected face packets were not saved by the previous build, so the mismatch cause is UNCONFIRMED. Current local JNI source sends readback acknowledgement before returning the duplicated snapshot FD; no missing-ack repair or service change was made.

The sample now compares exact finite float32 bit patterns, treating only positive/negative zero as numerically equivalent. Nonzero differences, including Float.MIN_VALUE, wrong sizes, NaN and infinity remain rejected. Every automatic export includes comparison details. On rejection the app saves the existing full raw/probe JSON, mismatch indices, values and original float bits under RejectedCaptures and journals the path before stopping. Signed-zero equivalence is a valid policy repair and possible prior false-rejection mechanism, not a confirmed diagnosis of the unretained packet.

Host JS/Kotlin snapshot fixtures pass the new comparator cases and prior motion/ROM/schema checks. Both apps pass final assembleDebug/lintDebug/spotlessCheck in six seconds; APK signature verifies. Diagnostic APK SHA-256 `26b7b626ad0b5281b5b0cb7d3db2e1f0f3428ee6cc00c2aa52170cbcbe902e60` is installed and matches. PID 15796 supplies advancing frames 8/16/23, C K and healthy logging. All 151 existing app files/private camera calibration are preserved; lease released. Headset controls and device-only runtime instructions are unchanged. No profile save, data clear, recording deletion, service/firmware change, commit or push occurred.

Evidence: `artifacts/facelandmarker/registration-lab/headset-check-2026-10-31/` contains retrieval/stereo verification and preview, original recording, journal/run summary, diagnostic background capture, host/build logs, final source/APK manifest and installation evidence. The requested face-bearing One check follow-up is validated below. Physical registration and corrected calibration remain pending.


## Completed face-bearing headset check — 2026-10-31

Run `b2b8c9a3`, session `2026-10-30T21-38-42.265313Z-4e9683`, completed CLEAN_BEFORE/MARKED/CLEAN_AFTER with accepted frames 92/100/109 and DONE/saved=3. All 13 retrieved session files match headset SHA-256 hashes; original files remain on the headset. The app was already closed and was not relaunched for retrieval. The retrieval lease was released. No code, build, install, calibration or service change was made in this follow-up. The diagnostic APK hash above is the last verified installed build; it was not rehashed this retrieval.

All three exports compare 2994/2994 values with zero numerical mismatches and zero signed-zero differences. They pass EXPOSURE_STABLE with valid ±50 ms history, camera ages 455.42/411.94/496.74 ms, exposure movement 0.59848/0.82609/0.92425 mm and rotation 0.06746/0.11261/0.08966 degrees. Export tags match saved journal and scene-acknowledgement entries. Six visible MARKED uploads each have eight distinct selected vertices; none is collapsed. The marked export's closest pair is 25.5021 mm.

The native analyzer accepts 3 and rejects 0. Mesh-to-source RMS is 0.0000834/0.0000843/0.0001194 native pixels; Stage-transform replay RMS is approximately 8e-8 m. The marked source-overlay image was inspected and shows coherent raw-landmark/projected-mesh placement on the detected face. Inferred depths of 1.039/1.062/1.082 m are model/calibration results, not independently measured ground truth. Exact packet equality in this successful run does not explain the previous unretained mismatch; no signed-zero difference occurred here.

The journal records SETTLE 1.4301 s, MARKED 5.0701 s including export work and capture-start-to-DONE 42.2744 s. Natural small movement passed the exposure checks. This is a successful single C capture, not a full candidate/pose sweep or component performance benchmark.

Evidence: `artifacts/facelandmarker/registration-lab/packet-check-2026-10-31/`, including `capture-session/`, `retrieval.json`, `native-analysis/report.md`, `native-analysis/report.json`, the marked `source-overlay.png` and `check-summary.json`. Reproduction script `analysis/validate_packet_check.py` passes file integrity, phase order/DONE, export tags, recorded packet equality, exposure acceptance and distinct marked-scene checks. The native analyzer ran with NumPy 2.5.3/OpenCV headless 5.0.0.93. Full details are in `PACKET_CHECK_FINDINGS_2026-10-31.md`.

The wearer can now run **Full trial** with Spatial recording on the headset, following the four prompts with natural small movement and stopping the recorder at Capture complete. Allow roughly 10 minutes as a single-check extrapolation. No PC connection is required for starting/running/storing this capture. No new stereo video was requested for the packet check; physical marker/anatomy alignment, binocular disparity, candidate choice and corrected calibration remain unverified. On-headset fitting/application remains unimplemented. No recording deletion, app-data clear, profile save, commit or push occurred.


## Full-trial mismatch evidence and terminal completion repair — 2026-10-31 host date

The returned session `2026-10-31T18-10-01.419367Z-a197a4` contains three Full trials stopping on packet equality after 0/2/13 accepted exports, one failed One check and subsequent successful One check `b9603afb` (frames 953/967/976, DONE/saved=3, 34.6702 s). All 18 accepted exports compare exactly and pass independent native analysis; round-trip RMS is about 0.0001–0.0002 native pixels. The successful check's marked source overlay is coherent. A later session `2026-10-31T18-15-04.644520Z-67ef4b` stops a separate Full trial on camera freshness during SETTLE, with zero exports.

Four retained rejected packets contain 199/1886/1166/2672 real float32 differences at frames 137/369/679/822; no signed-zero differences occur. Their expected sequence and initial prefix match, then remaining result fields diverge. The nested producer/fit/mesh snapshots are internally consistent; the raw result's camera timestamp is 233–300 ms older than the snapshot. All four pass exposure motion (0.151–0.423 mm, 0.032–0.158 degrees). This confirms inconsistent result readback and the app's missing completion barrier; the installed service's internal writer/readback behavior was not instrumented. The separate camera-freshness failure's cause remains unconfirmed.

The lab mesh pipeline now writes a separate `completedSequence` in its last operator, after result packing and geometry snapshotting. The inference coroutine waits for this marker before reading/presenting the packet; its returned sequence still must match. Normal sample graph behavior is unchanged. Exact finite comparison, rejected-packet retention, camera/geometry/motion/scene/calibration gates and the headset capture controls remain enabled. No service or SDK edit was made.

Production completion regressions pass a current-header/stale-tail simulation with zero premature reads, coherent post-commit acceptance, stale-sequence retry and bounded timeout. Shipped JS/Kotlin decoder/comparator/ROM/motion regressions pass. Controller/profile/clock regressions pass, including all 84 exports and existing candidate/restoration/rejection contracts. Both apps pass assembleDebug/lintDebug/spotlessCheck; final build 27 seconds. APK v2 signature verifies.

Installed diagnostic APK SHA-256 `39861cdf012e99ddfcbb8218dfe5c08a6f28ef00add89915bb0a85753e4906fb` matches the host build on PB311XHGKC220141G, the same verified Swan fingerprint. PID 7711 supplies frames 2/12/22 then 347/678 with C/revision 0, healthy logging and no stopped state. Startup has no face in view; it establishes streaming, not repaired face-bearing export or Full trial completion. All 245 existing external app files and the private optical calibration hash were preserved. The debug property is unset; no tracing/bypass was enabled. The installation lease was released.

Evidence: `artifacts/facelandmarker/registration-lab/full-trial-failures-2026-10-31/`, with both sessions, four rejected JSON files, 18 exports, independent native analysis, `attempt-summary.json`/`analyze_attempts.py`, source/APK manifest, host/build logs and `install/`. `retrieval.json` records hash parity for 78 session files plus the 1,306,083,173-byte recording `ScreenRecording_2026.11.01-02.09.51-AM.mp4`. The encoded HEVC video has 10,790 frames/359.666 s; both-eye decoding and physical residual analysis are pending. Device local date is November 1 at UTC+08:00; session UTC and host October 31 labels are preserved. Originals remain on the headset.

Current wearer step: run a recorded One check with a real face on the repaired build, allow small natural movement and stop recording at Capture complete. Inspect its three exports before requesting another Full trial. Capture/start/storage remain device-only; on-headset fitting/application, physical binocular alignment and candidate selection remain pending. See `FULL_TRIAL_MISMATCH_FINDINGS_2026-10-31.md` and current `AUTOMATIC_CAPTURE_STEPS.md`. No app-data clear, recording deletion, profile save, firmware/service change, commit or push was made.
# GPU preprocessing integration — 2026-10-31 (host only)

See `GPU_PREPROCESSING_IMPLEMENTATION.md` and `artifacts/facelandmarker/registration-lab/gpu-fusion-2026-10-31/`. Two generated weightless GPU models are integrated behind `-PfaceGpuPreprocessing=true`; default builds retain native preprocessing. Both apps' GPU and default variants pass assembleDebug/lintDebug/spotlessCheck; APK signatures and packaged model hashes verify. Existing terminal completion, exact packet, snapshot/motion/profile/ROM regressions pass. Production constructor checks map both variants and preserve the final completion marker.

Serialized model math passes 24 OpenCV synthetic cases with RMS under 0.5 byte levels (maximum edge difference 8); FP32 Metal float-input probes match normalized outputs within 5.96e-8. Default reduced precision shows material sampling errors. Mac uint8 GPU input-buffer execution fails, and CPU model-info inspection cannot resolve the GPU-only Resampler. These limitations are retained as evidence, not counted as device passes. No Android GPU/precision/face/capture/latency validation occurred: headset disconnected. No APK was installed or device data changed. Existing installed completion-repair One check / Full trial readiness remains unaltered. Decode/ROI tensor rewrite passes 40 production-JS comparisons; production decode/snapshot scripts remain unchanged.


## Binocular geometry capture — 2026-11-04

See [the investigation and next recording instructions](BINOCULAR_GEOMETRY_INVESTIGATION.md).
Added Geometry check (3 exports), Geometry trial (10 holds / 30 exports), and headset cancellation.
C intrinsics and pipeline scale 1 remain the measurement reference; the starting K is restored on
completion/cancellation. No inferred extrinsic/depth correction is applied or saved.

Both apps pass assembleDebug, lintDebug and spotlessCheck with faceCompactVstPipeline,
faceFusedControlModels, faceGpuPreprocessing and faceGpuSampleBytes enabled. The production Kotlin
harness checks the retained 84-export flow, the new geometry flow, fixed C, metadata propagation,
profiles, motion/freshness, restoration and exact scene acknowledgements. Native completion/snapshot
regressions pass. Python compile and device-helper shell syntax checks pass.

Synthetic tests project the actual Kotlin reference mesh and atlas into both eye views. All twelve
ArUco markers and the full sequence/CRC decode; worst held-out-tag projection RMS is below 0.5 px.
Known translation, rotation and camera-ray scale are recovered, including all ten held-out poses.
Coplanar references, bad CRC, missing tags, moving head history, duplicate observations and
incompatible stereo correspondences are rejected. Exact-PTS MV-HEVC extraction was also exercised
on the retained real video at 39.134367 seconds, both 1920x1080 eye views.

APK: registrationlab-binocular-geometry-debug.apk, 34,323,361 bytes; SHA-256
872605118128ee96520e2a8e45f678abdd545ff4f4df8896b65e2eb7757d6ae1.
Artifacts: artifacts/facelandmarker/registration-lab/binocular-geometry-2026-11-04/.

The initial host validation completed while PB311XHGKC220141G was disconnected. Installation and
startup verification subsequently passed as recorded at the top of this file. The next hardware gate
is a recorded Geometry check to verify actual texture orientation, reference visibility and decoding
before a full geometry trial. Host and startup results do not certify physical overlap.
