// Inverse crop, quality checks, persistent ROI, sparse projection and the full depth mean.
// No image-space smoothing: pose smoothing happens after the capture-time camera transform.
var rawLandmarks;
var presenceLogit;
var roi;
var settings;
var frame;
var intrinsics;
var indices;
var canonical;
var subset;
var trackState;
var landmarks;
var blendInput;
var projected;
var targets;
var depthOffset;
var validity;
(function () {
    const width = settings[0], height = settings[1], side = roi[4];
    const probability = 1 / (1 + Math.exp(-presenceLogit[0]));
    const age = frame[0] - trackState[1] + frame[1] - trackState[2];
    const retained = trackState[0] > 0 && age >= 0 && age <= settings[6];
    const threshold = retained ? settings[5] : settings[3];
    let reason = 0;
    if (roi[0] <= 0 || !Number.isFinite(probability) || probability < threshold) reason = 1;
    if (frame[3] <= 0) reason = 3;
    const fx = intrinsics[0], fy = intrinsics[4], cx = intrinsics[2], cy = intrinsics[5];
    if (!(fx > 0 && fy > 0) || !intrinsics.every(Number.isFinite)) reason = 4;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (let i = 0; i < 478; ++i) {
        const j = i * 3, x = rawLandmarks[j], y = rawLandmarks[j + 1], z = rawLandmarks[j + 2];
        if (!Number.isFinite(x + y + z) || Math.abs(x) > 512 || Math.abs(y) > 512 || Math.abs(z) > 512) reason = 2;
        if (i < 468) { minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y); }
    }
    const extent = Math.max(maxX - minX, maxY - minY);
    if (extent < 24 || extent > 300 || minX < -48 || maxX > 304 || minY < -48 || maxY > 304) reason = 2;
    validity[0] = reason === 0 ? 1 : 0;
    validity[1] = Number.isFinite(probability) ? probability : 0;
    landmarks.fill(0); blendInput.fill(0); projected.fill(0); depthOffset[0] = 0;
    for (let i = 0; i < indices.length; ++i) for (let a = 0; a < 3; ++a)
        targets[i * 3 + a] = canonical[i * 4 + a];
    trackState[16] = frame[4]; trackState[17] = reason;
    if (frame[3] > 0) { trackState[13] = frame[0]; trackState[14] = frame[1]; trackState[18] = 1; }
    if (reason !== 0) {
        trackState[10] += 1;
        // One enlarged local retry, only while the last actual measurement is recent.
        trackState[0] = retained && trackState[10] <= 1 && reason !== 3 && reason !== 4 ? 2 : 0;
        return;
    }
    const cosine = Math.cos(roi[5]), sine = Math.sin(roi[5]);
    const points = new Array(1434);
    for (let i = 0; i < 478; ++i) {
        const j = i * 3, x = rawLandmarks[j] / 256 - 0.5, y = rawLandmarks[j + 1] / 256 - 0.5;
        points[j] = (roi[2] + side * (cosine * x - sine * y)) / width;
        points[j + 1] = (roi[3] + side * (sine * x + cosine * y)) / height;
        points[j + 2] = rawLandmarks[j + 2] / 256 * side / width;
        if (i < 468) depthOffset[0] += points[j + 2] * width / fx / 468;
    }
    // Helmet mode emits only the 33 weighted points; mesh mode also emits all screen points.
    if (landmarks.length === 1434) for (let i = 0; i < 1434; ++i) landmarks[i] = points[i];
    for (let i = 0; i < indices.length; ++i) {
        const j = indices[i] * 3, k = i * 3;
        projected[k] = (points[j] * width - cx) / fx;
        projected[k + 1] = (cy - points[j + 1] * height) / fy;
        projected[k + 2] = points[j + 2] * width / fx;
        targets[k] = projected[k]; targets[k + 1] = projected[k + 1]; targets[k + 2] = -projected[k + 2];
    }
    if (blendInput.length === 292) for (let i = 0; i < 146; ++i) {
        blendInput[i * 2] = points[subset[i] * 3] * width;
        blendInput[i * 2 + 1] = points[subset[i] * 3 + 1] * height;
    }
    // Crop bounds in the current roll frame. Retain roll when the eye separation collapses at yaw.
    const x = (minX + maxX) / 512 - .5, y = (minY + maxY) / 512 - .5;
    const nextX = roi[2] + side * (cosine * x - sine * y);
    const nextY = roi[3] + side * (sine * x + cosine * y);
    const nextSide = Math.max(32, Math.min(Math.max(width, height), side * extent / 256 * 1.5));
    const eyeX = (points[263 * 3] - points[33 * 3]) * width;
    const eyeY = (points[263 * 3 + 1] - points[33 * 3 + 1]) * height;
    let roll = roi[5];
    if (Math.hypot(eyeX, eyeY) > nextSide * .18) {
        const measured = Math.atan2(eyeY, eyeX);
        const delta = Math.atan2(Math.sin(measured - roll), Math.cos(measured - roll));
        roll += Math.max(-.2, Math.min(.2, delta));
    }
    const velocityLimit = nextSide * 2;
    function velocity(value, old, previous) {
        if (!retained || age < .005) return 0;
        return .5 * previous + .5 * Math.max(-velocityLimit, Math.min(velocityLimit, (value - old) / age));
    }
    trackState[7] = velocity(nextX, trackState[3], trackState[7]);
    trackState[8] = velocity(nextY, trackState[4], trackState[8]);
    trackState[9] = velocity(nextSide, trackState[5], trackState[9]);
    if (!retained) trackState[11] += 1;
    trackState[0] = 1; trackState[1] = frame[0]; trackState[2] = frame[1];
    trackState[3] = nextX; trackState[4] = nextY; trackState[5] = nextSide; trackState[6] = roll;
    trackState[10] = 0; trackState[12] = roi[1]; trackState[15] = probability;
})();
