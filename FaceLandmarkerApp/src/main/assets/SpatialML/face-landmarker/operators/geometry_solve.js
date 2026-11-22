// Finish Procrustes from native SVD, correcting reflections and solving uniform scale/translation.
var canonical;
var targets;
var centers;
var u;
var vt;
var pose;
var scale;

(function () {
    function determinant(m) {
        return m[0] * (m[4] * m[8] - m[5] * m[7]) - m[1] * (m[3] * m[8] - m[5] * m[6]) +
            m[2] * (m[3] * m[7] - m[4] * m[6]);
    }
    const sign = determinant(u) * determinant(vt) < 0 ? -1 : 1;
    const rotation = new Array(9).fill(0);
    for (let r = 0; r < 3; ++r) for (let c = 0; c < 3; ++c) for (let k = 0; k < 3; ++k)
        rotation[r * 3 + c] += u[r * 3 + k] * (k === 2 ? sign : 1) * vt[k * 3 + c];
    let numerator = 0, denominator = 0;
    for (let i = 0; i < canonical.length / 4; ++i) {
        const w = canonical[i * 4 + 3], source = [0, 0, 0];
        for (let a = 0; a < 3; ++a) { source[a] = canonical[i * 4 + a] - centers[a]; denominator += w * source[a] * source[a]; }
        for (let r = 0; r < 3; ++r) {
            let rotated = 0;
            for (let c = 0; c < 3; ++c) rotated += rotation[r * 3 + c] * source[c];
            numerator += w * rotated * (targets[i * 3 + r] - centers[3 + r]);
        }
    }
    const s = numerator / denominator;
    scale[0] = Number.isFinite(s) && s > 1e-9 ? s : 1;
    pose.fill(0); pose[15] = 1;
    for (let r = 0; r < 3; ++r) {
        pose[r * 4 + 3] = centers[r + 3];
        for (let c = 0; c < 3; ++c) {
            pose[r * 4 + c] = scale[0] * rotation[r * 3 + c];
            pose[r * 4 + 3] -= pose[r * 4 + c] * centers[c];
        }
    }
})();
