# Face effects revision: baseball cap, paint cutouts, dragon and closed helmet

The selectable hat now looks like a baseball cap, with a curved forward visor joined to the crown, six stitched panels and a top button. Hat and pigtails use forehead/temple anchors above the face-pose origin. Flag/team paint clears the eyes and lips. Chinese dragon replaces the rejected expression-mask option, and a separate closed glTF helmet keeps its face cover fixed.

This revision is **installed and hash-verified, not launched** on `PB311XHGKC220141G` following the user's installation request. [Installation receipt](../artifacts/facelandmarker/face-effects-revision-2026-11-10/device-install-2026-11-10/installation.json). The optimized registration-lab APK matches SHA-256 `b53ba36ea24ca20a4bbf30ed59f12ae5910c1ca32ed558bdeb86ad873298a972`. All 1,148 pre-existing external app files and the private calibration hash are preserved; the SpatialML service APK hash remains unchanged. The old app/service were running at preflight. After replacement, both packages were explicitly stopped to retain the earlier user request: no PIDs and `stopped=true` verified. No app-data clearing, service APK changes, SDK upgrades or commits occurred. Keep both processes stopped until the user asks to run it.

Branch: `dev/facelandmarker`. Existing dirty worktree changes and accepted stereo calibration/filter settings are preserved. The previous installed revision is documented in [FACE_EFFECTS_2026-11-10.md](FACE_EFFECTS_2026-11-10.md); its device observations are historical and do not validate this revision.

## Visible choices and behavior

| Choice | Behavior |
| --- | --- |
| Face mesh | Visible wireframe for checking tracked geometry; default selection |
| Helmet | Original Sentinel shell and opening faceplate, with revised depth ordering |
| Closed helmet | CC0 Khronos SciFiHelmet, fixed face cover and zero animation tracks |
| Buggy eyes | Attached eyes with blink, widening and gaze coefficients |
| Joker smile | Existing face-local painted smile |
| Baseball cap | Blue crown, navy curved forward visor, stitching and button |
| Red pigtails | Raised crown cap, side tails and bows |
| Flag paint | Flag atlas with feathered eye/lip exclusions |
| Team colors | Team atlas with the same exclusions |
| Chinese dragon | Emerald head, gold antlers/whiskers/eyes, red brows/crest/beard, fangs, moving lower jaw and animated fire |

Buggy eyes and Chinese dragon request pose/mesh/blendshape output mask 7. Other choices request pose/mesh mask 3. Selecting dragon also enables the optional tongue pipeline; it is omitted from submissions for other effects and calibration evidence captures.

The selector uses SpatialUI `Button`, `Text` and `Slider` under the existing `PicoTheme`. The existing Full Space Mixed Stage and app-owned geometry remain the rendering owners. There are no new window containers, custom hover handlers or solid root backgrounds. The selector/style gate passes with zero errors and warnings. The ten choices use a 660 × 640 dp panel.

## Placement and rendering ownership

`FaceHeadPlacement.anchors()` operates on the filtered vertices in head-local metres. Crown height is forehead landmark 10 plus 0.55 times the horizontal temple width between landmarks 127/356; anchor X/Z are the temple midpoints. Cap hem is crown minus 55 mm. Pigtail mount is crown minus 110 mm; the hair cap extends up to the crown. Lowering the chin does not move the estimated crown. Accessories inherit the measured face transform and intentional fit slider scale.

The baseball cap crown has radii 93/65/92 mm. Its visor covers only the forward half of the hem, with the inner arc matching the crown ellipse exactly. It extends to +167 mm in local Z and curves down slightly at the sides. Code and inspected previews establish +Y up and +Z forward.

Pose acquisition/filtering, display-frame rendering and conflated surface uploading keep their separate owners. The prior 350 ms bounded tracking hold, advancing-capture checks and generation guards remain. A late mesh upload cannot re-enable a hidden generation. Dragon jaw/flame animation also runs on retained display frames without waiting for another surface upload.

Flag/team atlas alpha is zero inside expanded eye/lip ellipses and feathers outward. It uses canonical UVs and the existing verified bottom-origin mesh V convention. The shared facial topology has 906 triangles; it has no eye/mouth holes needing new triangulation. Paint exclusions use texture alpha rather than changing the depth surface.

## Jaw and tongue controls

The shipped 52-category blendshape contract has **no `tongueOut` coefficient**. Fire therefore uses actual same-capture image appearance, rather than deriving a fake tongue signal from `jawOpen`.

`tongue_visibility.tflite` is a 122-operation portable CPU color/geometry heuristic. It receives the normalized 256 × 256 landmark crop, pixel-space landmarks, face validity and command sequence. It requires tongue-like pink tissue inside the mouth and below the outer lower lip, compared with adjacent skin. Protected image pixels remain inside SpatialML. Only two floats, `[sequence, confidence]`, are read back. The result must match the completed face sequence and have finite confidence in [0,1].

The optional pipeline runs after expressions and before the final output/completion marker. Host construction verifies that it uses exactly the landmark detector's input tensor across GPU/native and full/retained/compact configurations. The default lab path retains both its original diagnostic byte crop and normalized crop; the GPU diagnostic copy still comes from that same normalized crop.

The dragon jaw targets up to 0.85 rad (48.7°) around its lower-jaw hinge, driven by `jawOpen` and smoothed on the display clock. Fire requires jaw opening at least 0.08 and tongue confidence at least 0.55 over at least three distinct captures spanning 100 ms. It stops on closed jaw, missing/low confidence, changed tracking generation, effect switch/hide, or evidence older than 200 ms. Six retained transparent unlit flame instances animate around the mouth socket.

Pose journal events now include `tongueAppearanceConfidence` and dragon jaw target/angle plus fire visibility. These are application state, not compositor presentation timestamps.

**Limitation:** this detector is a prototype heuristic, not a trained tongue classifier. Twenty-one synthetic fixtures pass for protruding tongue versus empty mouth, teeth, lip rim, tongue inside the mouth, closed mouth and invalid face at three brightness levels. Real tongue accuracy under headset lighting, skin tones, makeup, occlusion and head turns is unverified. Actual fire appearance and gesture latency also require the headset.

## Helmet depth and closed asset

The previous invisible face and imported helmet occupied different render passes, and helmet nodes shared draw indices. `FaceRenderOrder` now places the facial depth surface, paint and all model-bearing nodes in one transparent draw group with unique indices. Existing imported PBR/unlit material textures and properties are retained; blending, opacity and depth test/write are set explicitly.

The face uses base-color alpha 0, material opacity 1, depth test/write enabled and no culling. Leaving material opacity at one avoids relying on a possible optimization for zero-opacity materials. The rendering guide describes larger indices drawing first: face 10000, model nodes 1 upward, paint 0. The API reference gives a conflicting general description of direction.

**Depth occlusion remains unverified.** Public core 6.1.9 exposes no confirmed depth-only/color-write material control, and documentation does not prove that zero-alpha fragments retain depth writes. Neither build success nor the host geometry preview establishes Sentinel rear-shell occlusion. A future runtime probe should distinguish a hidden rear surface from a visible foreground surface with face depth writes on/off; check order direction on the actual runtime.

`helmet/scifi-helmet.glb` packs the unchanged Khronos SciFiHelmet mesh/material/images, credited in [SCIFI_HELMET_LICENSE.md](../FaceLandmarkerApp/src/main/assets/helmet/SCIFI_HELMET_LICENSE.md). It is CC0, has one original OPAQUE material and zero animation tracks. Composed source geometry has +Y up/+Z front, verified in the isolated preview. Loaded bounds determine a uniform scale to 250 mm width; the center is placed at head-local `(0, 35, -20)` mm while preserving authored rotation. The full face cover provides an alternative to the animated Sentinel. Actual headset fit remains unverified.

## Validation and artifacts

Evidence root: [face-effects-revision-2026-11-10](../artifacts/facelandmarker/face-effects-revision-2026-11-10/).

- Both apps pass assemble, Android lint and Spotless in default and optimized configurations.
- Production effects/renderer regression passes: held pose, advancing captures, independent rendering during uploads, no duplicate unchanged-pose writes, stale upload/hide/cancel/close, cap/visor connection, jaw-independent crown, dragon geometry/fire gate and paint cutouts.
- Actual graph construction passes 25 supported configurations, including optional tongue paths and invalid sequence/NaN/out-of-range confidence rejection. Serialized weightless model binding checks pass for 146 call sites.
- Packaged tongue model passes 21 controlled RGB fixtures, preserving sequence 17001.
- Existing balanced pose/local-shape smoothing, 99 anatomical coordinate cases, frozen stereo K/D and calibration/capture restoration, terminal completion and freshness regressions pass. Balanced synthetic delay remains 43.256 ms; anatomical round-trip maximum remains 1.192e-7 m.
- APK ZIP contents match source bytes for the tongue model, closed SciFiHelmet and original Sentinel. Each archive has a SHA-256 manifest. Only the optimized registration-lab APK is installed; the normal sample and default APKs remain archived.
- Source/asset hashes and summarized checks are in `verification.json`; detailed host JSON/logs are retained alongside it.

Standalone host previews, generated from production mesh exports and actually inspected:

- [Baseball cap](../artifacts/facelandmarker/face-effects-revision-2026-11-10/previews/baseball-cap.png)
- [Dragon, neutral jaw](../artifacts/facelandmarker/face-effects-revision-2026-11-10/previews/dragon-closed.png)
- [Dragon, open jaw and flame geometry](../artifacts/facelandmarker/face-effects-revision-2026-11-10/previews/dragon-open-fire.png)
- [Closed helmet source geometry](../artifacts/facelandmarker/face-effects-revision-2026-11-10/previews/scifi-view-plus-z.png)

These use matplotlib triangle shading and are geometry evidence. The flame preview shows one opaque silhouette; the app uses six animated transparent instances. They do not prove SDK materials, transparent depth behavior, UI layout or on-face fit. Per-image inspection/orientation records live in `previews/`.

Managed Codegen run `run-8167937d-e246-401b-8379-14e57ea85483` built an earlier source snapshot, then blocked at `module:validate-delivery`; no managed delivery pass is claimed. Editor startup previously timed out. The final source is validated by the independent local checks above. Managed Editor status at handoff reports no running editor/backend.

## Build and deployment boundary

Optimized registration-lab APK: [registrationlab-1.0-debug.apk](../artifacts/facelandmarker/face-effects-revision-2026-11-10/apks/optimized/registrationlab-1.0-debug.apk), SHA-256 `b53ba36ea24ca20a4bbf30ed59f12ae5910c1ca32ed558bdeb86ad873298a972`.

Optimized normal sample APK: [facelandmarker-1.0-debug.apk](../artifacts/facelandmarker/face-effects-revision-2026-11-10/apks/optimized/facelandmarker-1.0-debug.apk), SHA-256 `93ad2cc4a2a1ef546fbf16c22ad4bb588cae6da3a5a71e72fbce07129f1a68b5`.

Default APKs are also archived under `apks/default/`. Complete hashes are in the respective `manifest.json` files. Reproduce the optimized build from the workspace root:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home ./gradlew \
  :FaceLandmarkerApp:assembleDebug :FaceRegistrationLabApp:assembleDebug \
  :FaceLandmarkerApp:lintDebug :FaceRegistrationLabApp:lintDebug \
  :FaceLandmarkerApp:spotlessCheck :FaceRegistrationLabApp:spotlessCheck \
  -PfaceCompactVstPipeline=true -PfaceFusedControlModels=true \
  -PfaceGpuPreprocessing=true -PfaceGpuSampleBytes=true \
  --offline --console=plain
```

Omit all four flags for the default configuration. Do not substitute the unrelated fused-geometry flag for compact VST.

Future runtime acceptance, when the user asks to run: use a focused devmux lease on `PB311XHGKC220141G`, confirm the installed optimized lab APK hash, launch it without clearing data and leave the service APK unchanged. Check cap/pigtails across head turns and jaw motion; inspect paint margins while blinking/speaking; compare neutral/open/tongue gestures and journal confidence/fire state; verify both helmets and the depth probe. Release the lease after the focused block. Preserve all calibration files and recordings.
