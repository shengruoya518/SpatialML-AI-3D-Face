// Near-plane projection in a calibrated camera frustum; canonical geometry uses centimeters.
var landmarks;
var intrinsics;
var settings;
var canonical;
var validity;
var projected;
var targets;
var depthOffset;

(function () {
    const fx = intrinsics[0], fy = intrinsics[4], cx = intrinsics[2], cy = intrinsics[5];
    const good = validity[0] > 0 && fx > 0 && fy > 0 && Number.isFinite(fx + fy + cx + cy);
    let depth = 0;
    for (let i = 0; i < 478; ++i) {
        const j = i * 3;
        projected[j] = good ? (landmarks[j] * settings[0] - cx) / fx : 0;
        projected[j + 1] = good ? (cy - landmarks[j + 1] * settings[1]) / fy : 0;
        projected[j + 2] = good ? landmarks[j + 2] * settings[0] / fx : 0;
        if (i < 468) depth += projected[j + 2];
        // Invalid frames still provide a nondegenerate covariance to native SVD.
        for (let a = 0; a < 3; ++a) targets[j + a] = good ? projected[j + a] * (a === 2 ? -1 : 1) :
            (i < 468 ? canonical[i * 4 + a] : 0);
    }
    depthOffset[0] = depth / 468;
    validity[0] = good ? 1 : 0;
})();
