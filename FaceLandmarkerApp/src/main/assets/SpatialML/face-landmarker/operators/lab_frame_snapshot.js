// Snapshot immediately after the producer has resolved the camera, ROI and crop.
var command;
var frame;
var roi;
var affine;
var intrinsics;
var serviceIntrinsics;
var imageTransform;
var leftCameraToXr;
var labMode;
var snapshot;
(function () {
    let offset = 0;
    for (const tensor of [command, frame, roi, affine, intrinsics, serviceIntrinsics,
        imageTransform, leftCameraToXr, labMode]) {
        for (const value of tensor) snapshot[offset++] = value;
    }
    if (offset !== snapshot.length) throw new Error("Lab frame snapshot size mismatch");
})();
