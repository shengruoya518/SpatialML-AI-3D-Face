"""Validate production face-local occlusion coordinates using the packaged anatomical mesh."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main(output):
    root = Path(__file__).resolve().parents[2]
    source = root / 'FaceLandmarkerApp/src/main/java/com/pico/spatial/ml/sample/facelandmarker'
    output.mkdir(parents=True, exist_ok=True)
    geometry = json.loads((root / 'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker/data/face_geometry.json').read_text())
    points = [geometry['canonical'][i * 4 + c] * .01 for i in range(468) for c in range(3)] + [0.0] * 30
    (output / 'anatomy.txt').write_text(' '.join(map(str, points)))
    fixture = output / 'FaceOcclusionFixture.kt'
    fixture.write_text(r'''package com.pico.spatial.ml.sample.facelandmarker
import java.io.File
import kotlin.math.*
fun main(args:Array<String>) {
    val anatomy=File(args[0]).readText().split(" ").map(String::toFloat).toFloatArray()
    var cases=0;var maxError=0.0
    for(axis in 0..2) for(degrees in listOf(-180,-179,-120,-90,-30,0,30,90,120,179,180)) for(scale in listOf(.5f,1f,1.7f)) {
        val pose=floatArrayOf(1f,0f,0f,.31f,0f,1f,0f,-.17f,0f,0f,1f,-1.3f,0f,0f,0f,1f)
        val j=(axis+1)%3;val k=(axis+2)%3;val angle=degrees*PI/180
        pose[j*4+j]=cos(angle).toFloat();pose[k*4+k]=cos(angle).toFloat()
        pose[j*4+k]=-sin(angle).toFloat();pose[k*4+j]=sin(angle).toFloat()
        for(r in 0..2)for(c in 0..2)pose[r*4+c]*=scale
        // Mimic expression change; local surface is not forced back to the neutral template.
        val shape=anatomy.copyOf().also{for(i in 0 until 478)it[i*3+2]+=.003f*sin(i*.1).toFloat()}
        val stage=StageRegistration.transformVertices(pose,shape)
        val recovered=FaceOcclusionGeometry.localVertices(stage,pose)
        val returned=StageRegistration.transformVertices(pose,recovered)
        for(i in shape.indices) {
            check(abs(recovered[i]-shape[i])<1e-5)
            maxError=max(maxError,abs(returned[i]-stage[i]).toDouble())
        }
        cases++
    }
    // Independently rotated Stage owner is removed by the head transform, not a second vertex conversion.
    val parent=floatArrayOf(0f,-1f,0f,.2f,1f,0f,0f,.3f,0f,0f,1f,-.1f,0f,0f,0f,1f)
    val pose=floatArrayOf(1.3f,0f,0f,.5f,0f,1.3f,0f,.1f,0f,0f,1.3f,-1.2f,0f,0f,0f,1f)
    val stage=StageRegistration.transformVertices(pose,anatomy)
    val local=FaceOcclusionGeometry.localVertices(stage,pose)
    val headInOwner=StageRegistration.multiply(StageRegistration.inverseRigid(parent),pose)
    val returned=StageRegistration.transformVertices(parent,StageRegistration.transformVertices(headInOwner,local))
    check(returned.indices.all{abs(returned[it]-stage[it])<1e-5})
    for(vertices in listOf(FloatArray(0),anatomy.copyOf().also{it[0]=Float.NaN}))
        check(runCatching{FaceOcclusionGeometry.localVertices(vertices,pose)}.isFailure)
    check(maxError<1e-5)
    File(args[1]).writeText("{\"status\":\"PASS\",\"poseCases\":$cases,\"verticesPerCase\":478,\"maxStageRoundTripErrorMetres\":$maxError,\"rotatedParent\":true,\"expressionShapePreserved\":true}\n")
    println("PASS: face-local anatomical geometry across rotation, scale, expression and rotated Stage owner")
}
''')
    cache = Path.home() / '.gradle/caches/modules-2/files-2.1'
    def jar(group, name, version):
        return next((cache / group / name / version).glob('*/*.jar'))
    stdlib = jar('org.jetbrains.kotlin', 'kotlin-stdlib', '2.0.21')
    compiler = [jar('org.jetbrains.kotlin', name, '2.0.21') for name in ['kotlin-compiler-embeddable', 'kotlin-script-runtime', 'kotlin-reflect', 'kotlin-daemon-embeddable']]
    compiler += [stdlib, jar('org.jetbrains', 'annotations', '13.0'), jar('org.jetbrains.intellij.deps', 'trove4j', '1.0.20200330'), jar('org.jetbrains.kotlinx', 'kotlinx-coroutines-core-jvm', '1.6.4')]
    java = '/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java'
    classes = output / 'classes'
    subprocess.run([java, '-cp', os.pathsep.join(map(str, compiler)), 'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler', '-nowarn', '-no-stdlib', '-no-reflect', '-classpath', str(stdlib), '-d', str(classes), str(fixture), *[str(source / name) for name in ['FaceOcclusionGeometry.kt', 'FaceHelmetPose.kt', 'StageRegistration.kt']]], check=True)
    subprocess.run([java, '-cp', str(classes) + os.pathsep + str(stdlib), 'com.pico.spatial.ml.sample.facelandmarker.FaceOcclusionFixtureKt', str(output / 'anatomy.txt'), str(output / 'validation.json')], check=True)
    print((output / 'validation.json').read_text())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output)
