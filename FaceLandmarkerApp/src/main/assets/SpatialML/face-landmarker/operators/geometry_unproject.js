var projected;
var depthOffset;
var firstScale;
var secondScale;
var canonical;
var validity;
var targets;

(function () {
    const scale = firstScale[0] * secondScale[0];
    for (let i = 0; i < projected.length / 3; ++i) {
        const j = i * 3, z = (projected[j + 2] - depthOffset[0] + 1) / scale;
        targets[j] = projected[j] * z;
        targets[j + 1] = projected[j + 1] * z;
        targets[j + 2] = -z;
        if (validity[0] <= 0) for (let a = 0; a < 3; ++a) targets[j + a] = i < canonical.length / 4 ? canonical[i * 4 + a] : 0;
    }
})();
