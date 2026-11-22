# Face mesh shading and residual alignment

The wearer reported flat rendering and a smaller remaining offset after the Stage-origin repair.
Comparison with the current Unity XR sample identified two differences in the Kotlin port.

## Surface shading

The mesh already contains all three coordinates and recalculates area-weighted vertex normals.
However, `UnlitMaterial` ignores lighting and normals. Unity creates a double-sided URP Lit material
and a directional light. Kotlin now uses `PhysicallyBasedMaterial`, the Unity cyan base color,
roughness `0.7`, metallic `0`, and two headset-relative directional lights: a `1500` lux oblique key
and a weaker `350` lux fill. Lights and material are released with the existing scene resources.
The mesh continues to update its positions, normals and bounds together.

## Current vertices require the matching pose

The port originally packed current reconstructed vertices with the filtered `worldPose` from
`face_pose.js`. The current Unity graph instead publishes `rawWorldPose` and uses that raw fit for
the live mesh. Filtering position, rotation or scale while retaining current local vertices moves
the final vertices away from their measured image rays.

The corrected path publishes both poses and binds `rawWorldPose` to the live mesh result. If `P` is
the canonical-centimeter to camera-centimeter fit, `C` is the same capture's camera-to-service pose,
`s` is the face-size control, and `m` is a reconstructed camera-centimeter landmark, then:

```text
localMeters = inverse(P) * m * 0.01
W_raw       = C * metricPose(P, s)
servicePoint = W_raw * localMeters = C * (m * 0.01 * s)
stagePoint   = H_stage(capture) * E_cameraToHead * inverse(C) * servicePoint
```

Consequently, camera reprojection of the completed mesh recovers the measured landmarks. The app
checks all 478 vertices before Stage rebasing and logs the maximum error as `reprojection_px`.
This checks the geometry and service transforms; it does not measure the passthrough compositor's
camera calibration or end-to-end display timing.

## Geometry verification

`tools/check_face_geometry.py` executes the shipped JavaScript and simulates native SVD and binding
boundaries with float32 NumPy arrays. Forty independently generated moving, rotating and scaling
nonplanar faces exercise the three similarity fits and both pose paths:

| Check | Result |
| --- | --- |
| Corrected raw-pose maximum reprojection error | `0.0001072` pixels |
| Filtered-pose maximum error in the same moving-face fixtures | `13.7024` pixels |
| Sparse versus full weighted-fit pose difference | `0.0` |
| Minimum reconstructed camera-depth extent | `0.1002245` meters |
| Optical-center size and distance scaling | PASS |

The 33-point fit retains every nonzero canonical weight. The remaining 435 face points have zero
fit weights; adding them to the weighted solve changes neither its result nor its accuracy in
these fixtures. The depth average continues to include all 468 non-iris landmarks, and the final
mesh reconstructs all 478 points. Model assets, thresholds and topology are unchanged.

## Runtime validation

The managed Codegen build passed for the entire Android project with JDK 21. Lint, formatting,
model hashes, script bindings, original coordinate fixtures and APK exclusion of platform stubs
also passed. The corrected APK was installed and launched on B3110 serial `PB311XHGKC220141G`.

APK SHA-256: `b421c30b151ab3407a3924f3feb11f18dd1b87825e61c854dfb236ade3233de6`.

Full Space Mixed passthrough and the `0x0x0` SpatialML container remain active. The camera-calibration
query still finishes before SpatialML opens capture. Device evidence is in
`../artifacts/facelandmarker/shading/`; the managed root run is
`run-04b73548-b2e8-4636-b637-b139d5872518`.

Camera timestamps advanced throughout this run, but no face was detected in the available view.
Physical shading and precise overlap with the passthrough face therefore remain **UNOBSERVED**.
The app was left running for wearer observation; log capture stopped and the device lease released.
A fresh system recording can also establish visual overlap. Remaining offset should be measured while stationary and
during movement: monocular face-size/depth assumptions, callback-timestamp error and display
latency can affect that relationship even when source-camera reprojection is exact. This build
does not add guessed position offsets or pose extrapolation.

The controlled build initially lacked an Android SDK location. An ignored `local.properties`
now points to the existing host SDK. No SDK, service, plugin or build-script source was changed.
