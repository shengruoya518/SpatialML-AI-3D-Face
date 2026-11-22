// Capture time is timespec encoded as [seconds high, seconds low, ns high, ns low].
// Float globals keep seconds and fractional seconds separate to retain frame precision.
var timestamp;
var settings;
var command;
var trackState;
var roi;
var affine;
var frame;
(function () {
    const sec = timestamp[0] * 4294967296 + (timestamp[1] >>> 0);
    const fraction = (timestamp[2] * 4294967296 + (timestamp[3] >>> 0)) * 1e-9;
    const dt = trackState[18] > 0 ? sec - trackState[13] + fraction - trackState[14] : 0;
    const age = sec - trackState[1] + fraction - trackState[2];
    const sane = Number.isFinite(sec + fraction) && sec >= 0 && fraction >= 0 && fraction < 1;
    const candidateDelta = sec - trackState[20] + fraction - trackState[21];
    const continuous = trackState[18] > 0 && dt > 0 && dt <= 2;
    // A missing camera image can supply a wall-clock fallback instead of sensor uptime.
    // Do not poison the last accepted clock with a single jump. Require two consecutive
    // advancing timestamps to initialize/rebase after a discontinuity or long pause.
    const rebase = trackState[22] > 0 && candidateDelta > 0 && candidateDelta <= 2;
    const fresh = sane && (continuous || rebase);
    if (sane && !fresh) {
        trackState[20] = sec; trackState[21] = fraction; trackState[22] = 1;
    } else if (fresh) trackState[22] = 0;
    if (fresh && !continuous) trackState[0] = 0;
    frame[0] = sec; frame[1] = fraction; frame[2] = continuous ? dt : 0; frame[3] = fresh ? 1 : 0;
    frame[4] = command[3] > 0 ? 0 : 1; // 0 detector, 1 predicted ROI
    frame[5] = Math.max(0, age);
    if (command[3] <= 0) {
        const active = trackState[0] > 0 && age >= 0 && age <= settings[6];
        const horizon = Math.max(0, Math.min(age, settings[7]));
        roi[0] = active && fresh ? 1 : 0;
        roi[1] = trackState[12];
        roi[2] = trackState[3] + trackState[7] * horizon;
        roi[3] = trackState[4] + trackState[8] * horizon;
        const growth = trackState[0] === 2 ? 1.15 : 1;
        roi[4] = Math.max(32, Math.min(Math.max(settings[0], settings[1]),
            (trackState[5] + trackState[9] * horizon) * growth));
        roi[5] = trackState[6];
    }
    if (!fresh || !(roi[4] > 0) || !roi.every(Number.isFinite)) roi[0] = 0;
    if (roi[0] <= 0) {
        roi[2] = settings[0] / 2; roi[3] = settings[1] / 2;
        roi[4] = Math.min(settings[0], settings[1]); roi[5] = 0;
    }
    const a = 256 * Math.cos(roi[5]) / roi[4], b = 256 * Math.sin(roi[5]) / roi[4];
    affine[0] = a; affine[1] = b; affine[2] = 128 - a * roi[2] - b * roi[3];
    affine[3] = -b; affine[4] = a; affine[5] = 128 + b * roi[2] - a * roi[3];
})();
