"""Compile production tracking, face effects and renderer methods with controlled host SDK adapters.

This checks dropout and upload ordering; it does not prove device draw order or visual fit.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess


def validate(output: Path, json_jar: Path):
    root = Path(__file__).resolve().parents[2]
    source = root / 'FaceLandmarkerApp/src/main/java/com/pico/spatial/ml/sample/facelandmarker'
    output.mkdir(parents=True, exist_ok=True)
    geometry = json.loads((root / 'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker/data/face_geometry.json').read_text())
    (output / 'geometry.json').write_text(json.dumps(geometry))
    scene = (source / 'FaceHelmetScene.kt').read_text()
    methods = scene[scene.index('    fun select('):scene.index('    // Called on the Compose frame clock')]
    adapter = output / 'RendererProduction.kt'
    adapter.write_text('''package com.pico.spatial.ml.sample.facelandmarker
import kotlinx.coroutines.*
import org.json.*
internal class Scene {
    var closed = false
    val head = Entity()
    val owner = Entity()
    val fitting = Entity()
    val asset: Any? = Any()
    val occlusion = Occlusion()
    val augmentation = Augmentation()
    var surfaceGeneration = -1L
    var surfaceSequence = -1
    var renderedSequence = -1
    var renderedGeneration = -1L
    var selected = FaceEffect.MESH
    var appliedEffect: FaceEffect? = null
    var visibilityRevision = 0L
    var applied = 0
    var appliedFitScale = Float.NaN
    var fitScale = 1f
    var lastReadback = Double.NEGATIVE_INFINITY
    val visible get() = !closed && head.enabled
    val faceplateAngleRadians = 0.0
    val animationElapsedSeconds = 0.0
    fun applyFit() { appliedFitScale = fitScale }
    fun animateFaceplate(time: Long) {}
''' + methods + '}\n')
    fixture = output / 'FaceEffectsFixture.kt'
    fixture.write_text(r'''package com.pico.spatial.ml.sample.facelandmarker
import kotlinx.coroutines.*
import org.json.*
import java.io.File
import kotlin.math.*
internal object FaceLandmarkerRunner { const val TAG = "fixture" }
internal object Log { fun i(tag: String, value: String) {} }
internal data class Vector3(val x: Float, val y: Float, val z: Float)
internal data class Quat(val x: Float, val y: Float, val z: Float, val w: Float)
internal data class Transform(val position: Vector3, val quaternion: Quat, val scale: Vector3) {
    fun toFloatArray() = floatArrayOf(position.x, position.y, position.z)
}
internal class TransformComponent {
    var writes = 0
    var position = Vector3(0f, 0f, 0f)
        set(value) { field = value; writes++ }
    var quaternion = Quat(0f, 0f, 0f, 1f)
        set(value) { field = value; writes++ }
    var scaleVector = Vector3(1f, 1f, 1f)
        set(value) { field = value; writes++ }
}
internal class Components {
    val transform = TransformComponent()
    @Suppress("UNCHECKED_CAST") fun <T> get(): T? = transform as T
}
internal class Entity {
    var enabled = false
    val components = Components()
    fun convertTransformFrom(value: Transform, parent: Any?) = value
}
internal class Occlusion {
    var entered = CompletableDeferred<Unit>()
    var finish = CompletableDeferred<Unit>()
    var uploads = 0
    fun setEffect(effect: FaceEffect) {}
    suspend fun update(frame: FaceFrame, local: FloatArray): JSONObject {
        uploads++
        entered.complete(Unit)
        finish.await()
        return JSONObject().put("sdkUploadMs", 10)
    }
    fun next() { entered = CompletableDeferred(); finish = CompletableDeferred() }
}
internal class Augmentation {
    fun select(effect: FaceEffect) {}
    fun render(face: TrackedFace, fit: Float) {}
    fun animate(time: Long) {}
    fun hide() {}
    fun dragonEvidence() = JSONObject()
    suspend fun updateSurface(face: TrackedFace) {}
}
internal data class FaceOutputs(val mask: Int) { companion object { val ALL=FaceOutputs(7); val HELMET=FaceOutputs(3) } }
internal class Outputs(val pose: Boolean = true, val mesh: Boolean = true, val mask: Int = 7)
internal class FaceFrame(val sequence: Int = 1, val hasFace: Boolean = true,
                        val readbackSeconds: Double? = System.nanoTime()*1e-9,
                        val captureSeconds: Double = checkNotNull(readbackSeconds) - .04,
                        val trackingIdentity: Float = 1f, val labConfiguration: Int = 5,
                        val poseCorrection: Int = 0, val freshCameraFrame: Boolean = true,
                        val outputs: Outputs = Outputs(), val x: Float = .1f) {
    val pose = floatArrayOf(1f,0f,0f,x,0f,1f,0f,.2f,0f,0f,1f,-1f,0f,0f,0f,1f)
    val vertices = FloatArray(478*3)
    val blendshapes = FloatArray(52)
    val tongueConfidence: Float? = null
    val presentationStabilization: JSONObject? = null
    val presentationTiming: JSONObject? = null
}
fun main(args: Array<String>) = runBlocking {
    val now = System.nanoTime()*1e-9
    val state = FaceTrackingState()
    val good = checkNotNull(state.offer(FaceFrame(readbackSeconds=now), now))
    check(state.offer(null, now+.05) == null)
    check(state.offer(FaceFrame(hasFace=false, readbackSeconds=now+.05), now+.05) == null)
    check(state.offer(FaceFrame(freshCameraFrame=false, readbackSeconds=now+.08), now+.08) == null)
    check(state.current(now+.1) === good)
    check(state.offer(FaceFrame(readbackSeconds=now+.1, captureSeconds=good.frame.captureSeconds), now+.1) == null)
    check(state.current(now+.349) === good)
    check(state.current(now+.351) == null)
    val regained = checkNotNull(state.offer(FaceFrame(readbackSeconds=now+.4), now+.4))
    check(regained.generation != good.generation)
    val other = checkNotNull(state.offer(FaceFrame(readbackSeconds=now+.45, trackingIdentity=2f), now+.45))
    check(other.generation != regained.generation)
    val config = checkNotNull(state.offer(FaceFrame(readbackSeconds=now+.5, trackingIdentity=2f, labConfiguration=4), now+.5))
    check(config.generation != other.generation)
    state.clear(); check(state.current(now+.51) == null)
    check(state.offer(FaceFrame(readbackSeconds=now+1), now) == null)

    fun tracked(seq: Int=1, generation: Long=1, x: Float=.1f, age: Double=0.0): TrackedFace {
        val frame = FaceFrame(sequence=seq, x=x, readbackSeconds=System.nanoTime()*1e-9-age)
        return TrackedFace(frame,generation,frame.vertices,frame.blendshapes)
    }
    val scene = Scene()
    val first = tracked()
    val initialUpload = async { scene.updateSurface(first) }
    scene.occlusion.entered.await()
    scene.render(first, 1); check(!scene.visible && scene.head.components.transform.writes == 0)
    scene.occlusion.finish.complete(Unit); initialUpload.await()
    val firstApplied=checkNotNull(scene.render(first, 2))
    check(firstApplied.getBoolean("visible") && !firstApplied.getBoolean("poseBeforeOcclusion"))
    val before = scene.head.components.transform.writes
    scene.occlusion.next()
    val next = tracked(2, x=.3f)
    val pending = async { scene.updateSurface(next) }
    scene.occlusion.entered.await()
    check(scene.render(next, 3)?.getBoolean("poseBeforeOcclusion")==true)
    check(scene.visible && scene.head.components.transform.position.x == .3f)
    check(scene.head.components.transform.writes == before+3)
    scene.render(next,4); check(scene.head.components.transform.writes == before+3)
    scene.select(FaceEffect.HELMET); scene.render(next,5); check(scene.visible && scene.fitting.enabled)
    scene.select(FaceEffect.FLAG); scene.render(next,6); check(scene.visible && !scene.fitting.enabled)
    scene.hide(); scene.occlusion.finish.complete(Unit)
    check(pending.await().getBoolean("discarded") && !scene.visible)
    scene.render(next,7); check(!scene.visible)

    scene.occlusion.next()
    val changed = tracked(3, generation=2)
    val changedUpload = async { scene.updateSurface(changed) }
    scene.occlusion.entered.await(); scene.render(changed,8); check(!scene.visible)
    scene.occlusion.finish.complete(Unit); changedUpload.await(); scene.render(changed,9); check(scene.visible)
    scene.render(tracked(4,generation=2,age=.36),10); check(!scene.visible)

    val cancelled = Scene()
    val cancelledUpload = async { cancelled.updateSurface(tracked()) }
    cancelled.occlusion.entered.await(); cancelledUpload.cancelAndJoin()
    check(cancelled.surfaceGeneration == -1L && !cancelled.visible)
    val closed = Scene()
    val closingUpload = async { closed.updateSurface(tracked()) }
    closed.occlusion.entered.await(); closed.closed=true; closed.occlusion.finish.complete(Unit)
    check(closingUpload.await().getBoolean("discarded") && closed.render(tracked(),11) == null)

    val geometry = JSONObject(File(args[0]).readText())
    val canonical = geometry.getJSONArray("canonical").let { a -> FloatArray(a.length()){a.getDouble(it).toFloat()} }
    val names = geometry.getJSONArray("blendshapeNames").let { a -> List(a.length()){a.getString(it)} }
    val morph = FaceMaskGeometry(canonical,names)
    val neutral = morph.deform(FloatArray(52))
    val jaw = FloatArray(52).also{it[names.indexOf("jawOpen")]=1f}
    check(morph.coefficient(FloatArray(52){2f}, "jawOpen")==1f)
    check(morph.coefficient(FloatArray(52){-1f}, "jawOpen")==0f)
    val open = morph.deform(jaw)
    check(open[152*3+1] < neutral[152*3+1]-.02f)
    jaw[names.indexOf("mouthClose")]=1f
    check(morph.deform(jaw).contentEquals(neutral))
    for(name in listOf("mouthSmileLeft","mouthSmileRight","eyeBlinkLeft","eyeBlinkRight","browInnerUp","browDownLeft","browDownRight")) {
        val weights=FloatArray(52).also{it[names.indexOf(name)]=1f}
        val deformed=morph.deform(weights)
        check(deformed.all(Float::isFinite) && !deformed.contentEquals(neutral)){name}
    }
    check(morph.deform(FloatArray(52){Float.NaN}).contentEquals(neutral))
    check(morph.deform(FloatArray(0)).contentEquals(neutral))
    val anatomy=FloatArray(478*3){i->if(i/3<468)canonical[i/3*4+i%3]*.01f else 0f}
    val anchor=FaceHeadPlacement.anchors(anatomy)
    check(anchor.crownY>anatomy[10*3+1]+.06f)
    val openJawAnatomy=anatomy.copyOf().also{it[152*3+1]-=.035f}
    check(FaceHeadPlacement.anchors(openJawAnatomy).crownY==anchor.crownY)
    check(anchor.crownY-.055f>anatomy[10*3+1]+.02f)
    val meshes=FaceBaseballCapGeometry.parts()+FaceDragonGeometry.parts()+FaceDragonGeometry.flame()
    for(mesh in meshes) {
        check(mesh.vertices.all(Float::isFinite) && mesh.indices.all{it in 0 until mesh.vertices.size/3})
        check(mesh.indices.size%3==0)
    }
    val peak=FaceBaseballCapGeometry.parts().first{it.name.contains("peak")}
    check(peak.vertices.indices.filter{it%3==2}.maxOf{peak.vertices[it]}>.14f)
    check(peak.vertices.indices.filter{it%3==2}.minOf{peak.vertices[it]}>-1e-6f)
    // Every inner visor vertex matches the front elliptical hem of the crown.
    for(i in 0..28) {
        val x=peak.vertices[i*3];val y=peak.vertices[i*3+1];val z=peak.vertices[i*3+2]
        check(abs(y)<1e-6f && abs(x*x/(.093f*.093f)+z*z/(.092f*.092f)-1f)<1e-5f)
    }
    check(FaceDragonGeometry.parts().count{it.jaw}==3)
    val gate=FaceDragonFireGate()
    gate.update(1f,null,100.0,100.04,1);check(!gate.burning(100.05))
    gate.update(1f,0f,100.04,100.08,1);check(!gate.burning(100.09))
    gate.update(.5f,1f,100.10,100.14,1);check(!gate.burning(100.15))
    gate.update(.5f,1f,100.16,100.20,1);check(!gate.burning(100.21))
    gate.update(.5f,1f,100.22,100.26,1);check(gate.burning(100.27))
    check(!gate.burning(100.47))
    gate.update(.5f,1f,100.3,100.34,2);check(!gate.burning(100.35))
    gate.update(0f,1f,100.36,100.4,2);check(!gate.burning(100.41))
    val atlas=FacePaintAtlas(canonical)
    for(point in listOf(33,133,263,362,0,17,61,291)) check(atlas.paintCoverage(atlas.uv[point*2],atlas.uv[point*2+1])==0f)
    for(point in listOf(234,454)) check(atlas.paintCoverage(atlas.uv[point*2],atlas.uv[point*2+1])>.9f)
    check(atlas.uv.all{it.isFinite() && it in 0f..1f})
    fun pixelAt(pixels:IntArray, u:Float, v:Float):Int {
        val x=(u*FacePaintAtlas.SIZE).toInt().coerceIn(0,FacePaintAtlas.SIZE-1)
        val y=((1-v)*FacePaintAtlas.SIZE).toInt().coerceIn(0,FacePaintAtlas.SIZE-1)
        return pixels[y*FacePaintAtlas.SIZE+x]
    }
    fun atPoint(pixels:IntArray, point:Int)=pixelAt(pixels,atlas.uv[point*2],atlas.uv[point*2+1])
    val flags=atlas.pixels(FaceEffect.FLAG)
    val grin=atlas.pixels(FaceEffect.EYES)
    for(point in listOf(1,4,10,33,133,159,145,263,362,386,374,0,17,61,291,13,14,152))
        check(atPoint(flags,point) ushr 24==0){"Flag outside cheek at $point"}
    for(point in listOf(50,280)) check(atPoint(flags,point) ushr 24==255)
    check(flags.count{it ushr 24>0}<flags.size*.08){"Flags cover too much of the face"}
    for(point in listOf(0,17,61,291,13,14,78,308))
        check(atPoint(grin,point) ushr 24==255){"Real mouth is not fully covered at $point"}
    for(point in listOf(1,4,10,33,263,159,386,50,280,152)) check(atPoint(grin,point) ushr 24==0)
    check(grin.any{(it and 0xFFFFFF)==0xFFF9E8}){"Missing teeth"}
    check(FacePaintAtlas.MOUTH_FILL.size==18*3)
    for(triangle in FacePaintAtlas.MOUTH_FILL.chunked(3)) {
        check(triangle.toSet().size==3 && triangle.all{it in 0..467})
        val a=triangle[0]*4;val b=triangle[1]*4;val c=triangle[2]*4
        val area=(canonical[b]-canonical[a])*(canonical[c+1]-canonical[a+1])-
            (canonical[b+1]-canonical[a+1])*(canonical[c]-canonical[a])
        check(area>0){"Mouth fill winding or degenerate triangle: $triangle"}
    }
    for(effect in listOf(FaceEffect.FLAG,FaceEffect.TEAM,FaceEffect.EYES)) {
        val pixels=atlas.pixels(effect)
        check(pixels.toSet().size>=2)
        val image=java.awt.image.BufferedImage(FacePaintAtlas.SIZE,FacePaintAtlas.SIZE,java.awt.image.BufferedImage.TYPE_INT_ARGB)
        image.setRGB(0,0,FacePaintAtlas.SIZE,FacePaintAtlas.SIZE,pixels,0,FacePaintAtlas.SIZE)
        javax.imageio.ImageIO.write(image,"png",File(File(args[1]).parentFile,"paint-${effect.name.lowercase()}.png"))
    }
    val geometryJson=JSONArray(meshes.map{mesh->JSONObject().put("name",mesh.name).put("color",JSONArray(mesh.color)).put("jaw",mesh.jaw).put("vertices",JSONArray(mesh.vertices)).put("indices",JSONArray(mesh.indices))})
    File(File(args[1]).parentFile,"scene-geometry.json").writeText(JSONObject().put("meshes",geometryJson).put("capHem",anchor.crownY-.055f).toString())
    check(FaceEffect.entries.size==9)
    check(FaceEffect.entries.filter{it.outputs.mask==7}.toSet()==setOf(FaceEffect.EYES,FaceEffect.DRAGON))
    File(args[1]).writeText("""{"status":"PASS","dropoutHoldSeconds":0.35,"lateUploadCannotRestoreVisibility":true,"poseDuringUpload":true,"identityAndConfigurationGate":true,"cancellationAndClose":true,"unchangedPoseWrites":0,"capForwardPeak":true,"capUnaffectedByJaw":true,"dragonJawParts":3,"tongueTemporalGate":true,"eyeAndMouthPaintCutouts":true,"cheekOnlyFlags":true,"opaqueGrinMouthCoverage":true,"mouthFillTriangles":18,"effectChoices":9,"deviceVisuals":"UNOBSERVED"}"""+"\n")
    println("PASS: dropout hold, independent rendering, late upload, identity/configuration, cancellation, baseball cap, dragon fire gate and paint cutouts")
}
''')
    cache = Path.home() / '.gradle/caches/modules-2/files-2.1'
    def jar(group, name, version):
        return next((cache / group / name / version).glob('*/*.jar'))
    stdlib = jar('org.jetbrains.kotlin', 'kotlin-stdlib', '2.0.21')
    coroutines = jar('org.jetbrains.kotlinx', 'kotlinx-coroutines-core-jvm', '1.6.4')
    compiler = [jar('org.jetbrains.kotlin', name, '2.0.21') for name in ['kotlin-compiler-embeddable', 'kotlin-script-runtime', 'kotlin-reflect', 'kotlin-daemon-embeddable']]
    compiler += [stdlib, coroutines, jar('org.jetbrains', 'annotations', '13.0'), jar('org.jetbrains.intellij.deps', 'trove4j', '1.0.20200330')]
    java = '/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java'
    classes = output / 'classes'
    classpath = os.pathsep.join(map(str, [stdlib, coroutines, json_jar]))
    production = ['FaceTrackingState.kt', 'FaceHelmetPose.kt', 'FaceOcclusionGeometry.kt', 'FaceEffect.kt', 'FaceMaskGeometry.kt', 'FacePaintAtlas.kt', 'FaceHeadPlacement.kt', 'FaceAugmentationGeometry.kt', 'FaceDragonFireGate.kt']
    subprocess.run([java, '-cp', os.pathsep.join(map(str, compiler)), 'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler', '-nowarn', '-no-stdlib', '-no-reflect', '-classpath', classpath, '-d', str(classes), str(adapter), str(fixture), *[str(source/name) for name in production]], check=True)
    subprocess.run([java, '-cp', str(classes)+os.pathsep+classpath, 'com.pico.spatial.ml.sample.facelandmarker.FaceEffectsFixtureKt', str(output/'geometry.json'), str(output/'validation.json')], check=True)
    print((output / 'validation.json').read_text())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--json-jar', type=Path, required=True)
    args = parser.parse_args()
    validate(args.output, args.json_jar)
