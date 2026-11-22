// One atomic global result: header, normalized landmarks, canonical-local mesh, blendshapes, pose.
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
var result;

(function () {
    result.fill(0);
    result[0] = command[0]; result[2] = roi[1]; result[3] = validity[1];
    for (let i = 0; i < 3; ++i) result[2940 + i] = detectorInfo[i];
    for (let i = 0; i < diagnostics.length; ++i) result[2946 + i] = diagnostics[i];
    if (validity[0] <= 0) return;
    const squaredScale = pose[0] * pose[0] + pose[4] * pose[4] + pose[8] * pose[8];
    if (!(squaredScale > 1e-12) || !Number.isFinite(squaredScale)) return;
    for (let i = 0; i < 1434; ++i) result[4 + i] = landmarks[i];
    for (let i = 0; i < 478; ++i) {
        const j = i * 3;
        for (let a = 0; a < 3; ++a) {
            let value = 0;
            for (let b = 0; b < 3; ++b) value += pose[b * 4 + a] * (metric[j + b] - pose[b * 4 + 3]);
            // Canonical-local centimeters -> Unity meters, with Z handedness flipped.
            result[1438 + j + a] = value / squaredScale * 0.01 * (a === 2 ? -1 : 1);
        }
    }
    for (let i = 0; i < 52; ++i) result[2872 + i] = blendshapes[i];
    // S * worldPose * S converts the completed pose to Unity handedness.
    for (let r = 0; r < 4; ++r) for (let c = 0; c < 4; ++c) {
        result[2924 + r * 4 + c] = worldPose[r * 4 + c] *
            (r === 2 ? -1 : 1) * (c === 2 ? -1 : 1);
    }
    for (let i = 4; i < 2940; ++i) if (!Number.isFinite(result[i])) {
        result.fill(0); result[0] = command[0]; return;
    }
    result[1] = 1;
})();
