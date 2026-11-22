var cropAffine;
var imageTransform;
var sourceToCrop;
(function () {
    for (let r = 0; r < 2; ++r) for (let c = 0; c < 3; ++c) {
        let value = 0;
        for (let k = 0; k < 3; ++k) value += cropAffine[r*3+k] * imageTransform[k*3+c];
        sourceToCrop[r*3+c] = value;
    }
})();
