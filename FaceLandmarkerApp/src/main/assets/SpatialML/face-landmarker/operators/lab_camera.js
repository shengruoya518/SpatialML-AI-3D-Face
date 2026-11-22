// Explicit lab hypotheses. A is the real service K; B preserves its rays after image scaling.
var serviceIntrinsics;
var imageTransform;
var trialIntrinsics;
var labMode;
var intrinsics;
(function () {
    if (serviceIntrinsics.every(v => v === 0)) { intrinsics.fill(0); return; }
    if (!serviceIntrinsics.every(Number.isFinite) || serviceIntrinsics[0] <= 0 || serviceIntrinsics[4] <= 0)
        throw new Error("Invalid service camera calibration");
    for (let r = 0; r < 3; ++r) for (let c = 0; c < 3; ++c) {
        let value = 0;
        const source = labMode[0] === 3 || labMode[0] === 5 ? trialIntrinsics : serviceIntrinsics;
        for (let k = 0; k < 3; ++k) value += imageTransform[r*3+k] * source[k*3+c];
        // C/custom supply virtual K; D/stereo supply source K and therefore use A*K.
        intrinsics[r*3+c] = labMode[0] === 2 || labMode[0] === 4 ? trialIntrinsics[r*3+c] : value;
    }
})();
