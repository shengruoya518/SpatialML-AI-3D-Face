"""Exercise production helmet pose, pose-only smoothing and absolute-time faceplate motion."""
import argparse
import os
from pathlib import Path
import subprocess


def validate(output):
    root=Path(__file__).resolve().parents[2]
    source=root/'FaceLandmarkerApp/src/main/java/com/pico/spatial/ml/sample/facelandmarker'
    output.mkdir(parents=True,exist_ok=True)
    fixture=output/'HelmetPoseFixture.kt'
    fixture.write_text(r'''package com.pico.spatial.ml.sample.facelandmarker
import kotlin.math.*
import java.io.File
fun main(args:Array<String>) {
    fun rotation(axis:Int,angle:Double):FloatArray {
        val m=floatArrayOf(1f,0f,0f,.31f,0f,1f,0f,-.17f,0f,0f,1f,-1.3f,0f,0f,0f,1f)
        val j=(axis+1)%3;val k=(axis+2)%3
        m[j*4+j]=cos(angle).toFloat();m[k*4+k]=cos(angle).toFloat()
        m[j*4+k]=-sin(angle).toFloat();m[k*4+j]=sin(angle).toFloat()
        return m
    }
    fun transformed(p:FaceHelmetPose.Pose,v:FloatArray):FloatArray {
        val q=p.quaternion;val u=floatArrayOf(q[0],q[1],q[2]);val dot=(0..2).sumOf{u[it].toDouble()*v[it]}
        val length=(0..2).sumOf{u[it].toDouble()*u[it]}
        return FloatArray(3){i->val j=(i+1)%3;val k=(i+2)%3
            (p.position[i]+p.scale*(2*dot*u[i]+(q[3]*q[3]-length)*v[i]+2*q[3]*(u[j]*v[k]-u[k]*v[j]))).toFloat()}
    }
    var tested=0;var error=0.0
    for(axis in 0..2) for(degrees in listOf(-180,-179,-120,-90,-30,0,30,90,120,179,180)) for(scale in listOf(.5f,1f,1.7f)) {
        val m=rotation(axis,degrees*PI/180).also{for(r in 0..2)for(c in 0..2)it[r*4+c]*=scale}
        val decomposed=FaceHelmetPose.decompose(m)
        for(point in listOf(floatArrayOf(0f,0f,0f),floatArrayOf(.12f,.1f,-.02f),floatArrayOf(0f,0f,.15f))) {
            val expected=StageRegistration.transformVertices(m,point)
            val actual=transformed(decomposed,point)
            for(i in 0..2) error=max(error,abs(actual[i]-expected[i]).toDouble())
        }
        tested++
    }
    // A rotated Stage parent must be removed once before applying the local entity transform.
    val parent=rotation(2,.4)
    val head=rotation(1,-.8)
    val local=StageRegistration.multiply(StageRegistration.inverseRigid(parent),head)
    val point=floatArrayOf(.1f,.03f,-.02f)
    val localPoint=transformed(FaceHelmetPose.decompose(local),point)
    val expected=StageRegistration.transformVertices(head,point)
    val actual=StageRegistration.transformVertices(parent,localPoint)
    check(actual.indices.all{abs(actual[it]-expected[it])<1e-5})
    check(error<1e-5)
    // Pose-only filtering must match the rigid-pose part of the established mesh filter.
    val poseOnly=FacePoseMeshStabilizer();val withMesh=FacePoseMeshStabilizer()
    val base=floatArrayOf(-.07f,.03f,.05f,.07f,.03f,.05f,0f,-.08f,.02f)
    for(n in 0..180) {
        val m=rotation(n/61,min(n/180.0,1.0)*.7)
        val a=poseOnly.update(FloatArray(0),m,n/18.0,1f,"helmet")
        val b=withMesh.update(StageRegistration.transformVertices(m,base),m,n/18.0,1f,"helmet")
        check(a.vertices.isEmpty()&&a.correctionRmsMetres==0.0)
        check(a.pose.contentEquals(b.pose))
        FaceHelmetPose.decompose(a.pose)
    }
    for(bad in listOf(FloatArray(16),head.copyOf().also{it[0]=Float.NaN},head.copyOf().also{it[15]=0f},head.copyOf().also{it[0]*=2f},head.copyOf().also{for(i in 0..2)it[i*4]*=-1f})) {
        check(runCatching{FaceHelmetPose.decompose(bad)}.isFailure)
    }
    fun angle(t:Double)=FaceHelmetMotion.angleRadians(t).toDouble()*180/PI
    // Check requested holds, authored end angle, midpoint easing and every boundary independently.
    for((t,expectedAngle) in listOf(0.0 to 0.0,9.999 to 0.0,10.0 to 0.0,10.575 to -55.0,
        11.15 to -110.0,19.999 to -110.0,20.0 to -110.0,20.575 to -55.0,21.15 to 0.0,
        29.999 to 0.0,30.0 to 0.0,31.15 to -110.0,40.0 to -110.0)) {
        check(abs(angle(t)-expectedAngle)<1e-4){"motion at $t: ${angle(t)} vs $expectedAngle"}
    }
    for(boundary in listOf(10.0,11.15,20.0,21.15,30.0,40.0)) {
        check(abs(angle(boundary-1e-6)-angle(boundary+1e-6))<1e-4)
    }
    var animationSamples=0
    var previous=0.0
    for(n in 0..2400) {
        val t=n/120.0+10;val a=angle(t)
        check(a in -110.0001..0.0001)
        if(t<11.15)check(a<=previous+1e-4)
        if(t in 20.0..21.15)check(a>=previous-1e-4)
        check(abs(a-angle(t+20000))<1e-4){"cycle accumulated drift"}
        previous=a;animationSamples++
    }
    for(bad in listOf(-1.0,Double.NaN,Double.POSITIVE_INFINITY)) {
        check(runCatching{FaceHelmetMotion.angleRadians(bad)}.isFailure)
    }
    File(args[0]).writeText("{\"status\":\"PASS\",\"rotationScaleCases\":$tested,\"maxPointErrorMetres\":$error,\"poseOnlyFilterParityFrames\":181,\"animationSamples\":$animationSamples}\n")
    println("PASS: pose rotations/scale/parent, invalid inputs, pose-only filter parity, hinge timing/easing/boundaries and repeat without drift")
}
''')
    cache=Path.home()/'.gradle/caches/modules-2/files-2.1'
    def jar(group,name,version):return next((cache/group/name/version).glob('*/*.jar'))
    stdlib=jar('org.jetbrains.kotlin','kotlin-stdlib','2.0.21')
    compiler=[jar('org.jetbrains.kotlin',n,'2.0.21') for n in ['kotlin-compiler-embeddable','kotlin-script-runtime','kotlin-reflect','kotlin-daemon-embeddable']]
    compiler += [stdlib,jar('org.jetbrains','annotations','13.0'),jar('org.jetbrains.intellij.deps','trove4j','1.0.20200330'),jar('org.jetbrains.kotlinx','kotlinx-coroutines-core-jvm','1.6.4')]
    java='/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java'
    classes=output/'classes'
    subprocess.run([java,'-cp',os.pathsep.join(map(str,compiler)),'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-nowarn','-no-stdlib','-no-reflect','-classpath',str(stdlib),'-d',str(classes),str(fixture),*[str(source/n) for n in ['FaceHelmetPose.kt','FaceHelmetMotion.kt','FacePoseMeshStabilizer.kt','StageRegistration.kt']]],check=True)
    subprocess.run([java,'-cp',str(classes)+os.pathsep+str(stdlib),'com.pico.spatial.ml.sample.facelandmarker.HelmetPoseFixtureKt',str(output/'validation.json')],check=True)
    print((output/'validation.json').read_text())

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    validate(parser.parse_args().output)
