// Expand render-only outputs after shared tracking. Pose mode never executes this stage.
var rawLandmarks;
var roi;
var settings;
var validity;
var subset;
var landmarks;
var blendInput;
(function () {
    landmarks.fill(0); blendInput.fill(0);
    if (validity[0] <= 0) return;
    const width = settings[0], height = settings[1], side = roi[4];
    const cosine = Math.cos(roi[5]), sine = Math.sin(roi[5]);
    for (let i=0;i<478;++i) {
        const j=i*3, x=rawLandmarks[j]/256-.5, y=rawLandmarks[j+1]/256-.5;
        landmarks[j]=(roi[2]+side*(cosine*x-sine*y))/width;
        landmarks[j+1]=(roi[3]+side*(sine*x+cosine*y))/height;
        landmarks[j+2]=rawLandmarks[j+2]/256*side/width;
    }
    for (let i=0;i<146;++i) {
        blendInput[i*2]=landmarks[subset[i]*3]*width;
        blendInput[i*2+1]=landmarks[subset[i]*3+1]*height;
    }
})();
