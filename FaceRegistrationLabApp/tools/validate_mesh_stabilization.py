"""Compile the production mesh filter and exercise jitter, motion and coordinate invariants."""
import argparse
import json
import os
import subprocess
from pathlib import Path


def validate(output):
    root = Path(__file__).resolve().parents[2]
    source = root / 'FaceLandmarkerApp/src/main/java/com/pico/spatial/ml/sample/facelandmarker'
    output.mkdir(parents=True, exist_ok=True)
    fixture = output / 'StabilizationFixture.kt'
    fixture.write_text(r'''package com.pico.spatial.ml.sample.facelandmarker
import kotlin.math.*
import java.io.File
import java.util.Random

fun main(args: Array<String>) {
    // Nonplanar face-sized point cloud in Stage metres. Independent ground truth, not
    // a second implementation of the filter under test.
    val base = FloatArray(478*3) { i ->
        val p = i/3; val angle = p * 2.399963229728653
        val radius = sqrt((p+1)/478.0)
        when(i%3) {
            0 -> (.075*radius*cos(angle)).toFloat()
            1 -> (1.4+.105*radius*sin(angle)).toFloat()
            else -> (-1.2+.035*(1-radius*radius)).toFloat()
        }
    }
    fun rms(a: FloatArray,b: FloatArray) = sqrt(a.indices.sumOf { (a[it].toDouble()-b[it]).pow(2) } / (a.size/3))
    val metrics = linkedMapOf<String,Double>()
    for (hz in listOf(10,18,30,60)) {
        val f = FaceMeshStabilizer(); val rng = Random(73)
        var rawError=0.0;var filteredError=0.0;var count=0
        for(n in 0 until hz*8) {
            val shift=DoubleArray(3){rng.nextGaussian()*.002}
            val noise=FloatArray(base.size){i -> (base[i]+shift[i%3]+rng.nextGaussian()*.0004).toFloat()}
            val out=f.update(noise,n.toDouble()/hz,1f,"stereo").vertices
            if(n>hz) {rawError+=rms(noise,base).pow(2);filteredError+=rms(out,base).pow(2);count++}
        }
        val ratio=sqrt(filteredError/rawError)
        check(ratio<.8) {"Insufficient static jitter reduction at $hz Hz: $ratio"}
        metrics["staticRmsRatio${hz}Hz"]=ratio
        metrics["staticFilteredRmsMm${hz}Hz"]=sqrt(filteredError/count)*1000
    }
    // No artificial static offset and invariance under a change of Stage axes/origin.
    val f=FaceMeshStabilizer();val g=FaceMeshStabilizer()
    val transform=floatArrayOf(.8660254f,-.5f,0f,2f,.5f,.8660254f,0f,-1f,0f,0f,1f,.3f,0f,0f,0f,1f)
    var maximumEquivariance=0.0
    for(n in 0..180) {
        val mesh=FloatArray(base.size){i -> base[i]+(.002*sin(n*1.7+i%3)).toFloat()}
        val a=f.update(mesh,n/18.0,1f,"stereo").vertices
        val b=g.update(StageRegistration.transformVertices(transform,mesh),n/18.0,1f,"stereo").vertices
        maximumEquivariance=max(maximumEquivariance,rms(StageRegistration.transformVertices(transform,a),b))
    }
    check(maximumEquivariance<.000002)
    metrics["stageEquivarianceMaxMetres"]=maximumEquivariance
    // Simulated headset movement cancels in capture-time registration before filtering.
    val h=FaceMeshStabilizer()
    for(n in 0..180) {
        val theta=.3*sin(n/20.0);val c=cos(theta).toFloat();val s=sin(theta).toFloat()
        val head=floatArrayOf(c,0f,s,.02f*sin(n.toFloat()),0f,1f,0f,.01f,-s,0f,c,.04f,0f,0f,0f,1f)
        val camera=StageRegistration.transformVertices(StageRegistration.inverseRigid(head),base)
        val stage=StageRegistration.transformVertices(head,camera)
        check(rms(h.update(stage,n/18.0,1f,"stereo").vertices,base)<.000002)
    }
    // Real translation at .2 m/s must remain responsive; bound delay versus ideal motion.
    val moving=FaceMeshStabilizer();var maxLag=0.0
    for(n in 0..180) {
        val x=if(n<36)0f else ((n-36)/18.0*.2).toFloat()
        val points=FloatArray(base.size){i->base[i]+if(i%3==0)x else 0f}
        val out=moving.update(points,n/18.0,1f,"stereo").vertices
        maxLag=max(maxLag,rms(out,points))
        check(out.indices.all { i -> abs(out[i]-points[i])<=.02001 })
    }
    check(maxLag<.02);metrics["translationMaxLagMm"]=maxLag*1000
    metrics["translationEquivalentDelayMs"]=maxLag/.2*1000
    // A large relocation/reacquisition must never interpolate a ghost between two faces.
    val relocated=base.map{it+.4f}.toFloatArray()
    check(moving.update(relocated,11.0,2f,"stereo").vertices.contentEquals(relocated))
    check(moving.update(base,11.06,2f,"stereo").reason=="large_jump")
    check(moving.update(relocated,11.12,2f,"camera-changed").vertices.contentEquals(relocated))
    check(moving.update(base,11.1,2f,"camera-changed").reason=="capture_gap")
    check(moving.update(base,12.0,2f,"camera-changed").reason=="capture_gap")
    moving.reset()
    check(moving.update(base,12.06,2f,"camera-changed").vertices.contentEquals(base))
    // One affine blend preserves relative shape for translation; rotations cannot distort >1 mm.
    val turns=FaceMeshStabilizer();var maximumSpanError=0.0
    for(n in 0..180) {
        val a=if(n<36)0.0 else min((n-36)/18.0,1.0)*PI/3
        val raw=FloatArray(base.size){i ->
            val j=i/3*3;val x=base[j];val z=base[j+2]+1.2
            when(i%3){0->(cos(a)*x+sin(a)*z).toFloat();1->base[i];else->(-sin(a)*x+cos(a)*z-1.2).toFloat()}
        }
        val out=turns.update(raw,n/18.0,1f,"stereo").vertices
        fun span(v:FloatArray):Double {
            val cx=(v.indices step 3).map{v[it].toDouble()}.average()
            return sqrt((v.indices step 3).sumOf{(v[it]-cx).pow(2)}/478)
        }
        maximumSpanError=max(maximumSpanError,abs(span(raw)-span(out)))
    }
    check(maximumSpanError<.001);metrics["turnSpanMaxErrorMm"]=maximumSpanError*1000
    // Guard time/point validity and external mutation of returned/caller-owned arrays.
    val isolated=FaceMeshStabilizer();val input=base.copyOf()
    val first=isolated.update(input,0.0,1f,"test");input.fill(0f);first.vertices.fill(0f)
    check(rms(isolated.update(base,.06,1f,"test").vertices,base)<1e-6)
    for(bad in listOf(FloatArray(0),floatArrayOf(1f),base.copyOf().also{it[3]=Float.NaN})) {
        check(runCatching{isolated.update(bad,.1,1f,"test")}.isFailure)
    }
    File(args[0]).writeText("{\"status\":\"PASS\",\"metrics\":{"+metrics.entries.joinToString(","){"\"${it.key}\":${it.value}"}+"}}\n")
    println("PASS: static jitter, motion lag, shape, capture-head compensation, Stage equivariance, reset and isolation")
}
''')
    cache=Path.home()/'.gradle/caches/modules-2/files-2.1'
    def jar(group,name,version): return next((cache/group/name/version).glob('*/*.jar'))
    stdlib=jar('org.jetbrains.kotlin','kotlin-stdlib','2.0.21')
    compiler=[jar('org.jetbrains.kotlin',name,'2.0.21') for name in ['kotlin-compiler-embeddable','kotlin-script-runtime','kotlin-reflect','kotlin-daemon-embeddable']]
    compiler += [stdlib,jar('org.jetbrains','annotations','13.0'),jar('org.jetbrains.intellij.deps','trove4j','1.0.20200330'),jar('org.jetbrains.kotlinx','kotlinx-coroutines-core-jvm','1.6.4')]
    java='/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java'
    classes=output/'classes'
    subprocess.run([java,'-cp',os.pathsep.join(map(str,compiler)),'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-nowarn','-no-stdlib','-no-reflect','-classpath',str(stdlib),'-d',str(classes),str(fixture),str(source/'FaceMeshStabilizer.kt'),str(source/'StageRegistration.kt')],check=True)
    subprocess.run([java,'-cp',str(classes)+os.pathsep+str(stdlib),'com.pico.spatial.ml.sample.facelandmarker.StabilizationFixtureKt',str(output/'validation.json')],check=True)
    print((output/'validation.json').read_text())

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    validate(parser.parse_args().output)
