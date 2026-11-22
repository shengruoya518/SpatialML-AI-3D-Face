// Weighted orthogonal Procrustes preparation. SpatialML SvdOperator decomposes covariance.
var canonical;
var targets;
var covariance;
var centers;

(function () {
    let total = 0;
    centers.fill(0); covariance.fill(0);
    for (let i = 0; i < canonical.length / 4; ++i) {
        const weight = canonical[i * 4 + 3]; total += weight;
        for (let a = 0; a < 3; ++a) {
            centers[a] += weight * canonical[i * 4 + a];
            centers[3 + a] += weight * targets[i * 3 + a];
        }
    }
    for (let a = 0; a < 6; ++a) centers[a] /= total;
    for (let i = 0; i < canonical.length / 4; ++i) {
        const weight = canonical[i * 4 + 3];
        for (let r = 0; r < 3; ++r) for (let c = 0; c < 3; ++c)
            covariance[r * 3 + c] += weight * (targets[i * 3 + r] - centers[3 + r]) *
                (canonical[i * 4 + c] - centers[c]);
    }
})();
