// The same packing order is used for the fit and final mesh. Upstream snapshots retain
// the values actually observed at each boundary; sequence tags alone cannot prove native coherence.
var command;
var frame;
var roi;
var affine;
var rawLandmarks;
var projected;
var firstTargets;
var secondTargets;
var metric;
var pose;
var rawWorldPose;
var worldPose;
var firstScale;
var secondScale;
var depthOffset;
var intrinsics;
var leftCameraToXr;
var result;
var upstream;
var snapshot;
(function () {
    let offset = 0;
    for (const tensor of [command, frame, roi, affine, rawLandmarks, projected,
        firstTargets, secondTargets, metric, pose, rawWorldPose, worldPose,
        firstScale, secondScale, depthOffset, intrinsics, leftCameraToXr, result, upstream]) {
        for (const value of tensor) snapshot[offset++] = value;
    }
    if (offset !== snapshot.length) throw new Error("Lab geometry snapshot size mismatch");
})();
