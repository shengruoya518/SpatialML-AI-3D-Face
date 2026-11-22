// Canonical-local centimeters -> meters -> service OpenXR Local coordinates.
// Kotlin rebases this packet to the app's Stage using the capture-time HMD pose and optical extrinsics.
// No Unity S*pose*S reflection: both spaces use right-handed coordinates.
var command;
var validity;
var roi;
var landmarks;
var metric;
var pose;
var worldPose;
var blendshapes;
var detectorInfo;
var diagnostics;
var leftCameraToXr;
var result;

(function () {
    result.fill(0);
    result[0] = command[0]; result[2] = roi[1]; result[3] = validity[1];
    for (let i = 0; i < 3; ++i) result[2940 + i] = detectorInfo[i];
    for (let i = 0; i < diagnostics.length; ++i) result[2946 + i] = diagnostics[i];
    for (let i = 0; i < 16; ++i) result[2978 + i] = leftCameraToXr[i];
    if (validity[0] <= 0) return;
    const squaredScale = pose[0] * pose[0] + pose[4] * pose[4] + pose[8] * pose[8];
    if (!(squaredScale > 1e-12) || !Number.isFinite(squaredScale)) return;
    for (let i = 0; i < 1434; ++i) result[4 + i] = landmarks[i];
    for (let i = 0; i < 478; ++i) {
        const j = i * 3, local = [0, 0, 0];
        for (let a = 0; a < 3; ++a) {
            for (let b = 0; b < 3; ++b)
                local[a] += pose[b * 4 + a] * (metric[j + b] - pose[b * 4 + 3]);
            local[a] *= 0.01 / squaredScale;
        }
        for (let r = 0; r < 3; ++r) {
            let value = worldPose[r * 4 + 3];
            for (let c = 0; c < 3; ++c) value += worldPose[r * 4 + c] * local[c];
            result[1438 + j + r] = value;
        }
    }
    for (let i = 0; i < 52; ++i) result[2872 + i] = blendshapes[i];
    for (let i = 0; i < 16; ++i) result[2924 + i] = worldPose[i];
    for (let i = 4; i < result.length; ++i) if (!Number.isFinite(result[i])) {
        result.fill(0); result[0] = command[0]; return;
    }
    // Publish validity only after all of this capture's geometry has been packed.
    result[1] = 1;
})();
