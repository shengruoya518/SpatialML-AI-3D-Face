// Calibrated capture-time camera -> tracking space, then adaptive pose filtering.
// Scale metric geometry about the left optical center before applying calibrated extrinsics.
var pose;
var validity;
var leftCameraToXr;
var command;
var settings;
var frame;
var trackState;
var poseState;
var worldPose;
var rawWorldPose;
var poseStatus;
(function () {
    worldPose.fill(0); worldPose[0] = worldPose[5] = worldPose[10] = worldPose[15] = 1;
    rawWorldPose.fill(0); rawWorldPose[0] = rawWorldPose[5] = rawWorldPose[10] = rawWorldPose[15] = 1;
    poseStatus[0] = 0;
    const age = frame[0] - poseState[0] + frame[1] - poseState[1];
    const sizeScale = Number.isFinite(command[2]) && command[2] > 0 ? Math.max(.5, Math.min(1.5, command[2])) : 1;
    function norm(v) { const n = Math.hypot(...v); return v.map(x => x / n); }
    function dot(a, b) { return a.reduce((s, x, i) => s + x * b[i], 0); }
    function matrix(q, s, p) {
        const [x,y,z,w] = q;
        return [(1-2*(y*y+z*z))*s,2*(x*y-z*w)*s,2*(x*z+y*w)*s,p[0],
            2*(x*y+z*w)*s,(1-2*(x*x+z*z))*s,2*(y*z-x*w)*s,p[1],
            2*(x*z-y*w)*s,2*(y*z+x*w)*s,(1-2*(x*x+y*y))*s,p[2],0,0,0,1];
    }
    function quaternion(m, s) {
        const r = [m[0]/s,m[1]/s,m[2]/s,m[4]/s,m[5]/s,m[6]/s,m[8]/s,m[9]/s,m[10]/s];
        const trace = r[0]+r[4]+r[8];
        let q;
        if (trace > 0) { const t = 2*Math.sqrt(trace+1); q = [(r[7]-r[5])/t,(r[2]-r[6])/t,(r[3]-r[1])/t,t/4]; }
        else if (r[0] > r[4] && r[0] > r[8]) { const t = 2*Math.sqrt(1+r[0]-r[4]-r[8]); q = [t/4,(r[1]+r[3])/t,(r[2]+r[6])/t,(r[7]-r[5])/t]; }
        else if (r[4] > r[8]) { const t = 2*Math.sqrt(1+r[4]-r[0]-r[8]); q = [(r[1]+r[3])/t,t/4,(r[5]+r[7])/t,(r[2]-r[6])/t]; }
        else { const t = 2*Math.sqrt(1+r[8]-r[0]-r[4]); q = [(r[2]+r[6])/t,(r[5]+r[7])/t,t/4,(r[3]-r[1])/t]; }
        return norm(q);
    }
    let good = validity[0] > 0 && pose.every(Number.isFinite) && leftCameraToXr.every(Number.isFinite);
    let s = Math.hypot(pose[0],pose[4],pose[8]);
    good = good && s > .05 && s < 20 && pose[11] < -1 && pose[11] > -1000;
    if (good) {
        const camera = leftCameraToXr;
        const metric = pose.slice();
        // Scale translation and basis together: all left-image projection rays stay unchanged.
        for (let r=0;r<3;++r) for (let c=0;c<4;++c)
            metric[r*4+c] *= sizeScale * (c === 3 ? .01 : 1);
        s *= sizeScale;
        const raw = new Array(16).fill(0);
        for (let r=0;r<4;++r) for (let c=0;c<4;++c) for (let k=0;k<4;++k) raw[r*4+c]+=camera[r*4+k]*metric[k*4+c];
        // A live mesh must use its current fit. Filtered/held poses belong to rigid overlays.
        if (raw.every(Number.isFinite)) for (let i=0;i<16;++i) rawWorldPose[i]=raw[i];
        let p = [raw[3],raw[7],raw[11]], q = quaternion(raw,s);
        const smooth = settings[4] > 0 && poseState[2] > 0 && poseState[3] === trackState[11] && age > 0 && age < .5 && Math.abs(poseState[19]-sizeScale) < 1e-6;
        const rawP = p.slice(), rawQ = q.slice();
        if (smooth) {
            const speed = Math.hypot(...p.map((v,i)=>(v-poseState[12+i])/age));
            const angleSpeed = 2*Math.acos(Math.min(1,Math.abs(dot(q,poseState.slice(15,19)))))/age;
            const a = 1-Math.exp(-2*Math.PI*(4+12*speed)*age);
            const b = 1-Math.exp(-2*Math.PI*(4+3*angleSpeed)*age);
            p = p.map((v,i)=>poseState[5+i]+a*(v-poseState[5+i]));
            const oldQ = poseState.slice(8,12), sign = dot(q,oldQ)<0 ? -1:1;
            q = norm(q.map((v,i)=>oldQ[i]+b*(sign*v-oldQ[i])));
            s = Math.exp(Math.log(poseState[4])+(1-Math.exp(-2*Math.PI*5*age))*(Math.log(s)-Math.log(poseState[4])));
        }
        const filtered = matrix(q,s,p);
        if (filtered.every(Number.isFinite)) {
            poseState[0]=frame[0]; poseState[1]=frame[1]; poseState[2]=1; poseState[3]=trackState[11]; poseState[4]=s;
            for(let i=0;i<3;++i) { poseState[5+i]=p[i]; poseState[12+i]=rawP[i]; }
            for(let i=0;i<4;++i) { poseState[8+i]=q[i]; poseState[15+i]=rawQ[i]; }
            for(let i=0;i<16;++i) worldPose[i]=filtered[i];
            poseState[19]=sizeScale;
            poseStatus[0]=1;
            return;
        }
    }
    validity[0]=0;
    if (trackState[17] === 0) { trackState[17]=5; trackState[0]=0; }
    // Held is explicit, never counted as a measured pose. No render-time prediction is claimed.
    if (poseState[2]>0 && Math.abs(poseState[19]-sizeScale)<1e-6 && frame[3]>0 && age>=0 && age<=settings[8] && trackState[17]!==3 && trackState[17]!==4) {
        const held = matrix(poseState.slice(8,12),poseState[4],poseState.slice(5,8));
        for(let i=0;i<16;++i) worldPose[i]=held[i];
        poseStatus[0]=2;
    } else poseState[2]=0;
})();
