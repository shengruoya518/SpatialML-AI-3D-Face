// UFO's longer-range MediaPipe SSD decode, weighted suppression, and detected-face crop,
// executed inside SpatialML.
var boxesFine;
var boxesCoarse;
var scoresFine;
var scoresCoarse;
var settings;
var roi;
var affine;
var detectorInfo;
var trackState;
var timestamp;

(function () {
    const width = settings[0], height = settings[1];
    const letterbox = settings.length > 9 && settings[9] > 0;
    const scaleX = letterbox ? 256 / Math.max(width, height) : 256 / width;
    const scaleY = letterbox ? scaleX : 256 / height;
    const padX = (256 - width * scaleX) / 2, padY = (256 - height * scaleY) / 2;
    if (typeof detectorInfo !== 'undefined') {
        let best = -Infinity, anchor = -1;
        for (let i = 0; i < scoresFine.length + scoresCoarse.length; ++i) {
            const v = i < scoresFine.length ? scoresFine[i] : scoresCoarse[i - scoresFine.length];
            if (Number.isFinite(v) && v > best) { best = v; anchor = i; }
        }
        detectorInfo[0] = Number.isFinite(best) ? best : 0;
        detectorInfo[1] = Number.isFinite(best) ? sigmoid(best) : 0; detectorInfo[2] = anchor;
    }
    const candidates = [];
    function sigmoid(x) { return 1 / (1 + Math.exp(-Math.max(-100, Math.min(100, x)))); }
    function appendCandidates(boxes, scores, count, grid, anchorsPerCell) {
      for (let i = 0; i < count; ++i) {
        const score = sigmoid(scores[i]);
        if (!Number.isFinite(score) || score < settings[2]) continue;
        const cell = Math.floor(i / anchorsPerCell);
        const ax = (cell % grid + 0.5) * 256 / grid;
        const ay = (Math.floor(cell / grid) + 0.5) * 256 / grid;
        const offset = i * 16, cx = boxes[offset] + ax, cy = boxes[offset + 1] + ay;
        const w = boxes[offset + 2], h = boxes[offset + 3];
        const decoded = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2];
        for (let j = 0; j < 6; ++j) decoded.push(boxes[offset + 4 + j * 2] + ax, boxes[offset + 5 + j * 2] + ay);
        if (w > 0 && h > 0 && decoded.every(Number.isFinite)) candidates.push({ score: score, box: decoded });
      }
    }
    appendCandidates(boxesFine, scoresFine, 512, 16, 2);
    appendCandidates(boxesCoarse, scoresCoarse, 384, 8, 6);
    // All outputs are overwritten, including the no-face case. A safe center crop keeps inference well-defined.
    roi.fill(0);
    let cx = width / 2, cy = height / 2, side = Math.min(width, height), angle = 0;
    if (candidates.length) {
        // During brief recovery prefer a nearby identity; release the lock after the configured timeout.
        const now = typeof timestamp !== 'undefined' ? timestamp[0]*4294967296+(timestamp[1]>>>0)+
            (timestamp[2]*4294967296+(timestamp[3]>>>0))*1e-9 : 0;
        const age = typeof trackState !== 'undefined' ? now-trackState[1]-trackState[2] : Infinity;
        const locked = typeof trackState !== 'undefined' && trackState[11]>0 && age>=0 && age<settings[10];
        for (let i=candidates.length-1;i>=0;--i) {
            const c=candidates[i], x=((c.box[0]+c.box[2])/2-padX)/scaleX, y=((c.box[1]+c.box[3])/2-padY)/scaleY;
            const distance=locked ? Math.hypot(x-trackState[3],y-trackState[4])/Math.max(32,trackState[5]) : 0;
            c.rank=c.score-.35*distance;
            if (locked && distance>.8) candidates.splice(i,1);
        }
        candidates.sort(function (a, b) { return b.rank - a.rank; });
        if (candidates.length) {
        const best = candidates[0], weighted = new Array(16).fill(0);
        let total = 0;
        for (let i = 0; i < candidates.length; ++i) {
            const item = candidates[i], a = best.box, b = item.box;
            const overlap = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])) *
                Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
            const union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - overlap;
            if (i !== 0 && overlap / union <= 0.3) continue;
            total += item.score;
            for (let j = 0; j < 16; ++j) weighted[j] += b[j] * item.score;
        }
        for (let i = 0; i < 16; ++i) weighted[i] /= total;
        cx = ((weighted[0] + weighted[2]) / 2 - padX) / scaleX;
        cy = ((weighted[1] + weighted[3]) / 2 - padY) / scaleY;
        side = 1.5 * Math.max((weighted[2] - weighted[0]) / scaleX,
            (weighted[3] - weighted[1]) / scaleY);
        // Undo the detector's non-uniform full-frame resize before measuring roll.
        angle = Math.atan2((weighted[7] - weighted[5]) / scaleY,
            (weighted[6] - weighted[4]) / scaleX);
        roi[0] = 1; roi[1] = best.score;
        }
    }
    roi[2] = cx; roi[3] = cy; roi[4] = side; roi[5] = angle;
    const a = 256 * Math.cos(angle) / side, b = 256 * Math.sin(angle) / side;
    // OpenCV warpAffine uses source-to-destination coordinates.
    affine[0] = a; affine[1] = b; affine[2] = 128 - a * cx - b * cy;
    affine[3] = -b; affine[4] = a; affine[5] = 128 + b * cx - a * cy;
})();
