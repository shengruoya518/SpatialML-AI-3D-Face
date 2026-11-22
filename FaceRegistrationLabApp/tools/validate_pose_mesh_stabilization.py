"""Validate the production pose and local-shape filter against known motion, noise and outliers."""
import argparse
import json
import os
import subprocess
from pathlib import Path


def validate(output):
    root = Path(__file__).resolve().parents[2]
    source = root / 'FaceLandmarkerApp/src/main/java/com/pico/spatial/ml/sample/facelandmarker'
    output.mkdir(parents=True, exist_ok=True)
    fixture = output / 'PoseMeshFixture.kt'
    fixture.write_text(r'''package com.pico.spatial.ml.sample.facelandmarker
import kotlin.math.*
import java.io.File
import java.util.Random
fun main(args:Array<String>) {
    val base=FloatArray(478*3){i ->
        val n=i/3;val a=n*2.3999632297;val radius=sqrt((n+1)/478.0)
        when(i%3){0->(.075*radius*cos(a)).toFloat();1->(.1*radius*sin(a)).toFloat();else->(.035*(1-radius*radius)).toFloat()}
    }
    fun pose(x:Double=0.0,yaw:Double=0.0,s:Double=1.0)=floatArrayOf(
        (cos(yaw)*s).toFloat(),0f,(sin(yaw)*s).toFloat(),x.toFloat(),0f,s.toFloat(),0f,1.4f,
        (-sin(yaw)*s).toFloat(),0f,(cos(yaw)*s).toFloat(),-1.2f,0f,0f,0f,1f)
    fun rms(a:FloatArray,b:FloatArray)=if(a.isEmpty())0.0 else sqrt(a.indices.sumOf{(a[it].toDouble()-b[it]).pow(2)}/(a.size/3))
    fun local(v:FloatArray,m:FloatArray):FloatArray {
        val s2=(0..2).sumOf{m[it*4].toDouble().pow(2)}
        return FloatArray(v.size){i->val a=i%3;val j=i/3*3
            ((0..2).sumOf{m[it*4+a]*(v[j+it]-m[it*4+3]).toDouble()}/s2).toFloat()}
    }
    check(FacePoseMeshStabilizer.RESPONSE_PROFILE=="balanced")
    check(FacePoseMeshStabilizer.DERIVATIVE_CUTOFF_HZ==1.5)
    check(FacePoseMeshStabilizer.TRANSLATION_SPEED_COEFFICIENT==12.0)
    check(FacePoseMeshStabilizer.ANGULAR_SPEED_COEFFICIENT==2.5)
    val metrics=linkedMapOf<String,Double>()
    for(hz in listOf(10,18,30,60)) {
        val rng=Random(174);val f=FacePoseMeshStabilizer();val v1=FaceMeshStabilizer()
        val truth=StageRegistration.transformVertices(pose(),base)
        var raw=0.0;var first=0.0;var second=0.0;var poseRaw=0.0;var poseFiltered=0.0
        for(n in 0 until hz*10) {
            val p=pose(rng.nextGaussian()*.005,rng.nextGaussian()*.012,exp(rng.nextGaussian()*.008))
            val shape=FloatArray(base.size){(base[it]+rng.nextGaussian()*.0008).toFloat()}
            val mesh=StageRegistration.transformVertices(p,shape)
            val v=v1.update(mesh,n.toDouble()/hz,1f,"stereo")
            val result=f.update(mesh,p,n.toDouble()/hz,1f,"stereo")
            if(n>hz*2){raw+=rms(mesh,truth).pow(2);first+=rms(v.vertices,truth).pow(2);second+=rms(result.vertices,truth).pow(2)
                poseRaw+=p[3].toDouble().pow(2);poseFiltered+=result.pose[3].toDouble().pow(2)}
        }
        val ratio=sqrt(second/raw);val relative=sqrt(second/first)
        if(hz==18)check(ratio<.51){"Balanced stationary-noise acceptance: $ratio"}
        check(ratio<.65){"jitter ratio $hz = $ratio"}
        check(relative<.85){"v2/v1 jitter ratio $hz = $relative"}
        metrics["meshRmsRatio${hz}Hz"]=ratio;metrics["v2ComparedToV1RmsRatio${hz}Hz"]=relative
        metrics["poseTranslationRmsRatio${hz}Hz"]=sqrt(poseFiltered/poseRaw)
    }
    val f=FacePoseMeshStabilizer();var lag=0.0;var shapeError=0.0;var angleLag=0.0
    for(n in 0..180) {
        val t=n/18.0;val x=if(n<36)0.0 else (n-36)/18.0*.2
        val yaw=if(n<36)0.0 else min((n-36)/18.0,2.0)*PI/3
        val p=pose(x,yaw);val mesh=StageRegistration.transformVertices(p,base)
        val r=f.update(mesh,p,t,1f,"stereo")
        lag=max(lag,abs(r.pose[3].toDouble()-p[3]));shapeError=max(shapeError,rms(local(r.vertices,r.pose),base))
        angleLag=max(angleLag,abs(atan2(r.pose[2].toDouble(),r.pose[0].toDouble())-yaw))
    }
    check(lag/.2<.05);check(angleLag<.0874);check(shapeError<1e-6)
    metrics["movementMaxPositionLagMm"]=lag*1000;metrics["movementEquivalentDelayMs"]=lag/.2*1000
    metrics["rotationMaxLagDegrees"]=angleLag*180/PI;metrics["rigidTurnLocalShapeMaxErrorMetres"]=shapeError
    // Jaw movement changes local shape, without opening the body pose filter.
    val expression=FacePoseMeshStabilizer();val p=pose();var initialPoseAlpha=0.0;var expressionError=1.0
    for(n in 0..40) {
        val shape=base.copyOf();if(n>=20)for(i in 0 until 30)shape[i*3+1]+=.02f
        val r=expression.update(StageRegistration.transformVertices(p,shape),p,n/18.0,1f,"stereo")
        if(n==20)initialPoseAlpha=r.poseAlpha
        if(n==22)expressionError=rms(local(r.vertices,r.pose),shape)
    }
    check(initialPoseAlpha<.3);check(expressionError<.001)
    metrics["expressionBodyPoseAlpha"]=initialPoseAlpha;metrics["expressionErrorAfterTwoFramesMm"]=expressionError*1000
    val outliers=FacePoseMeshStabilizer();val still=StageRegistration.transformVertices(p,base)
    outliers.update(still,p,0.0,1f,"stereo")
    val bad=pose(.3);val badMesh=StageRegistration.transformVertices(bad,base)
    val held=outliers.update(badMesh,bad,.05,1f,"stereo")
    check(held.reason=="outlier_pending"&&rms(held.vertices,still)<1e-6)
    check(outliers.update(still,p,.10,1f,"stereo").reason=="filtered")
    check(outliers.update(badMesh,bad,.15,1f,"stereo").reason=="outlier_pending")
    check(outliers.update(badMesh,bad,.20,1f,"stereo").reason=="confirmed_jump")
    check(outliers.update(still,p,.25,2f,"stereo").vertices.contentEquals(still))
    check(outliers.update(badMesh,bad,.30,2f,"new-camera").vertices.contentEquals(badMesh))
    check(outliers.update(still,p,.29,2f,"new-camera").reason=="capture_gap")
    check(outliers.update(still,p,1.0,2f,"new-camera").reason=="capture_gap")
    val timeout=FacePoseMeshStabilizer();timeout.update(still,p,0.0,1f,"test")
    for(n in 1..5){val jumped=pose(n*.2);val r=timeout.update(StageRegistration.transformVertices(jumped,base),jumped,n*.04,1f,"test")
        if(n==4)check(r.reason=="jump_timeout")}
    val a=FacePoseMeshStabilizer();val b=FacePoseMeshStabilizer()
    val stage=floatArrayOf(.8660254f,-.5f,0f,2f,.5f,.8660254f,0f,-1f,0f,0f,1f,.3f,0f,0f,0f,1f)
    var coordinateError=0.0
    for(n in 0..180){val measured=pose(.003*sin(n*1.3),.01*cos(n*.9));val mesh=StageRegistration.transformVertices(measured,base)
        val one=a.update(mesh,measured,n/18.0,1f,"test")
        val two=b.update(StageRegistration.transformVertices(stage,mesh),StageRegistration.multiply(stage,measured),n/18.0,1f,"test")
        coordinateError=max(coordinateError,rms(two.vertices,StageRegistration.transformVertices(stage,one.vertices)))}
    check(coordinateError<2e-6);metrics["stageEquivarianceMaxMetres"]=coordinateError
    // Exactly cancel small headset motions before filtering. Test large rotations as well.
    val headFilter=FacePoseMeshStabilizer()
    for(n in 0..60){val head=pose(.02*sin(n.toDouble()),n/60.0*PI*1.9);val inverse=StageRegistration.inverseRigid(head)
        val mesh=StageRegistration.transformVertices(head,StageRegistration.transformVertices(inverse,still))
        val fit=StageRegistration.multiply(head,StageRegistration.multiply(inverse,p))
        check(rms(headFilter.update(mesh,fit,n/18.0,1f,"test").vertices,still)<2e-6)}
    // Quaternion branches at large nod/roll angles must retain a rigid local shape.
    for(axis in 0..2) {
        val turn=FacePoseMeshStabilizer()
        for(n in 0..36) {
            val theta=n/36.0*PI*.98;val c=cos(theta).toFloat();val si=sin(theta).toFloat()
            val m=pose();val a=(axis+1)%3;val b=(axis+2)%3
            m[a*4+a]=c;m[b*4+b]=c;m[a*4+b]=-si;m[b*4+a]=si
            val mesh=StageRegistration.transformVertices(m,base)
            val r=turn.update(mesh,m,n/18.0,1f,"branch")
            check(rms(local(r.vertices,r.pose),base)<2e-6)
        }
    }
    val stopped=FacePoseMeshStabilizer();var overshoot=0.0;var stopResidual=0.0
    for(n in 0..90) {
        val x=if(n<18)0.0 else if(n<54)(n-18)/18.0*.2 else .4
        val measured=pose(x);val mesh=StageRegistration.transformVertices(measured,base)
        val r=stopped.update(mesh,measured,n/18.0,1f,"stop")
        if(n>=54){overshoot=max(overshoot,r.pose[3].toDouble()-.4);if(n==56)stopResidual=abs(r.pose[3].toDouble()-.4)}
    }
    check(overshoot<1e-6);check(stopResidual<.003)
    metrics["stopOvershootMm"]=overshoot*1000;metrics["stopResidualAfterTwoFramesMm"]=stopResidual*1000
    val poseOnly=FacePoseMeshStabilizer();check(poseOnly.update(FloatArray(0),p,0.0,1f,"pose-only").vertices.isEmpty())
    check(poseOnly.update(FloatArray(0),pose(.001),.05,1f,"pose-only").pose.size==16)
    val mixed=FacePoseMeshStabilizer();mixed.update(still,p,0.0,1f,"test")
    check(mixed.update(FloatArray(0),p,.05,1f,"test").reason=="topology")
    for(badPose in listOf(FloatArray(16),p.copyOf().also{it[0]=Float.NaN},p.copyOf().also{it[0]=-1f}))
        check(runCatching{mixed.update(still,badPose,.1,1f,"test")}.isFailure)
    mixed.reset();check(mixed.update(still,p,1.0,1f,"test").vertices.contentEquals(still))
    File(args[0]).writeText("{\"status\":\"PASS\",\"metrics\":{"+metrics.entries.joinToString(","){"\"${it.key}\":${it.value}"}+"}}\n")
    println("PASS: pose/mesh jitter, prior filter comparison, rigid turn, expressions, outliers, time/identity/configuration resets, headset cancellation and pose-only outputs")
}
''')
    cache=Path.home()/'.gradle/caches/modules-2/files-2.1'
    def jar(group,name,version): return next((cache/group/name/version).glob('*/*.jar'))
    stdlib=jar('org.jetbrains.kotlin','kotlin-stdlib','2.0.21')
    compiler=[jar('org.jetbrains.kotlin',name,'2.0.21') for name in ['kotlin-compiler-embeddable','kotlin-script-runtime','kotlin-reflect','kotlin-daemon-embeddable']]
    compiler += [stdlib,jar('org.jetbrains','annotations','13.0'),jar('org.jetbrains.intellij.deps','trove4j','1.0.20200330'),jar('org.jetbrains.kotlinx','kotlinx-coroutines-core-jvm','1.6.4')]
    java='/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java'
    classes=output/'classes'
    subprocess.run([java,'-cp',os.pathsep.join(map(str,compiler)),'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-nowarn','-no-stdlib','-no-reflect','-classpath',str(stdlib),'-d',str(classes),str(fixture),str(source/'FaceMeshStabilizer.kt'),str(source/'FacePoseMeshStabilizer.kt'),str(source/'StageRegistration.kt')],check=True)
    subprocess.run([java,'-cp',str(classes)+os.pathsep+str(stdlib),'com.pico.spatial.ml.sample.facelandmarker.PoseMeshFixtureKt',str(output/'validation.json')],check=True)
    print((output/'validation.json').read_text())

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    validate(parser.parse_args().output)
