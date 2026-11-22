// Same-capture reprojection of reconstructed points, kept separate from rigid canonical-fit error.
var projected;
var metric;
var canonical;
var pose;
var validity;
var roi;
var intrinsics;
var frame;
var command;
var trackState;
var poseStatus;
var diagnostics;
(function () {
    diagnostics.fill(0);
    diagnostics[0]=3; diagnostics[1]=frame[0]; diagnostics[2]=frame[1]; diagnostics[3]=frame[2];
    // A rebased camera frame can be fresh with dt=0. Publish freshness independently of dt.
    diagnostics[30]=frame[3];
    diagnostics[4]=trackState[0]; diagnostics[5]=frame[4]; diagnostics[6]=trackState[17]; diagnostics[7]=trackState[11];
    for(let i=0;i<4;++i) diagnostics[8+i]=roi[2+i];
    diagnostics[12]=intrinsics[0]; diagnostics[13]=intrinsics[4]; diagnostics[14]=intrinsics[2]; diagnostics[15]=intrinsics[5];
    diagnostics[25]=trackState[0]>0 ? 0:1; diagnostics[26]=poseStatus[0]; diagnostics[27]=command[2];
    if(validity[0]<=0) return;
    const fx=intrinsics[0],fy=intrinsics[4],cx=intrinsics[2],cy=intrinsics[5];
    const bounds=[Infinity,Infinity,-Infinity,-Infinity], restored=bounds.slice();
    let sum=0, max=0, fit=0;
    function extend(b,x,y) { b[0]=Math.min(b[0],x); b[1]=Math.min(b[1],y); b[2]=Math.max(b[2],x); b[3]=Math.max(b[3],y); }
    for(let i=0;i<canonical.length/4;++i) {
        const j=i*3, x=cx+fx*projected[j], y=cy-fy*projected[j+1];
        const u=cx+fx*metric[j]/-metric[j+2], v=cy-fy*metric[j+1]/-metric[j+2];
        const error=Math.hypot(u-x,v-y); sum+=error*error; max=Math.max(max,error);
        extend(bounds,x,y); extend(restored,u,v);
        const p=[0,0,0];
        for(let r=0;r<3;++r) { p[r]=pose[r*4+3]; for(let c=0;c<3;++c) p[r]+=pose[r*4+c]*canonical[i*4+c]; }
        fit+=(cx+fx*p[0]/-p[2]-x)**2+(cy-fy*p[1]/-p[2]-y)**2;
    }
    const width=Math.max(1,bounds[2]-bounds[0]),height=Math.max(1,bounds[3]-bounds[1]),n=canonical.length/4;
    diagnostics[16]=Math.sqrt(sum/n)/width; diagnostics[17]=max/width;
    diagnostics[18]=(restored[2]-restored[0])/width; diagnostics[19]=(restored[3]-restored[1])/height;
    diagnostics[20]=(restored[0]+restored[2]-bounds[0]-bounds[2])/(2*width);
    diagnostics[21]=(restored[1]+restored[3]-bounds[1]-bounds[3])/(2*height);
    diagnostics[22]=Math.sqrt(fit/n)/width;
    const sizeScale = command[2] > 0 ? Math.max(.5, Math.min(1.5, command[2])) : 1;
    diagnostics[23]=Math.hypot(pose[0],pose[4],pose[8])*sizeScale; diagnostics[24]=-pose[11]*.01*sizeScale;
    diagnostics[28]=width; diagnostics[29]=height;
    if(!diagnostics.every(Number.isFinite)) { validity[0]=0; trackState[0]=0; trackState[17]=5; diagnostics[6]=5; diagnostics[25]=1; }
})();
