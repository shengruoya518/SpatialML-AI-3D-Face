"""Run production mesh preparation and scene lifecycle on host SDK adapters.

Exercises numerical parity and coroutine ownership, not native SDK performance.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess


def validate(output, json_jar):
    if not json_jar.is_file():
        raise FileNotFoundError(f'Real org.json JAR required: {json_jar}')
    root = Path(__file__).resolve().parents[2]
    source = root / 'FaceLandmarkerApp/src/main/java/com/pico/spatial/ml/sample/facelandmarker'
    output.mkdir(parents=True, exist_ok=True)
    files = {
        'Math.kt': '''package com.pico.spatial.core.math
import java.util.concurrent.atomic.AtomicInteger
class Vector3(val x:Float,val y:Float,val z:Float) {
    init { if (!Thread.currentThread().name.contains("fixture-ui")) workerVectors.incrementAndGet() }
    operator fun plus(v:Vector3)=Vector3(x+v.x,y+v.y,z+v.z)
    operator fun minus(v:Vector3)=Vector3(x-v.x,y-v.y,z-v.z)
    operator fun times(v:Float)=Vector3(x*v,y*v,z*v)
    companion object { val workerVectors=AtomicInteger() }
}
class Vector2(val x:Float,val y:Float)
class Color4(val r:Float,val g:Float,val b:Float,val a:Float)
class Quat(v:Vector3,a:Float) { operator fun times(q:Quat)=this }
''',
        'Entity.kt': '''package com.pico.spatial.core.ecs
import com.pico.spatial.core.math.*
import com.pico.spatial.core.ecs.resource.*
fun ui() { check(Thread.currentThread().name.contains("fixture-ui")) { "Entity accessed off UI thread" } }
open class Entity {
    var enabled=false
        set(v) { ui(); field=v }
    val components=Components()
    fun setName(n:String) { ui() }
    fun addChild(e:Entity) { ui() }
    fun removeFromParent() { ui() }
    fun destroy(children:Boolean) { ui() }
    fun convertPositionFrom(v:Vector3,e:Entity?):Vector3 { ui(); return Vector3((v.x-2)/2,(v.y+3)/3,(v.z-4)/4) }
    fun convertPositionTo(v:Vector3,e:Entity?):Vector3 { ui(); return Vector3(v.x*2+2,v.y*3-3,v.z*4+4) }
}
class Components {
    inline fun <reified T> get():T? = null
    fun set(v:Any) { ui() }
}
class AnchorEntity(t:Any):Entity()
class AnchorComponent { var positionOffset=Vector3(0f,0f,0f) }
class TransformComponent { var quaternion=Quat(Vector3(0f,1f,0f),0f) }
class DirectionalLightComponent(c:Color4,l:Float,b:Boolean)
class ModelComponent(m:MeshResource,mat:Any)
class BoundingBox(val center:Vector3,val extents:Vector3)
''',
        'Anchor.kt': '''package com.pico.spatial.core.ecs.anchor
object AnchorTarget { fun createCameraTarget()=Any() }
''',
        'Content.kt': '''package com.pico.spatial.core.container
import com.pico.spatial.core.ecs.Entity
class SpatialViewContent { fun addEntity(e:Entity) {} }
''',
        'Bitmap.kt': '''package android.graphics
class Bitmap {
    enum class Config { ARGB_8888 }
    fun recycle() {}
    companion object { fun createBitmap(a:IntArray,w:Int,h:Int,c:Config)=Bitmap() }
}
''',
        'Log.kt': '''package android.util
object Log { fun i(t:String,m:String)=0 }
''',
        'Resources.kt': '''package com.pico.spatial.core.ecs.resource
import android.graphics.Bitmap
import com.pico.spatial.core.ecs.BoundingBox
import com.pico.spatial.core.math.*
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
class MeshModel(val positions:List<Vector3>,val triangleIndices:List<Int>,val normals:List<Vector3>?=null,val uv0:List<Vector2>?=null)
class MeshResource {
    var closed=false
    var model:MeshModel?=null
    fun toGlobal() {}
    fun close() { check(!closed); check(active.get()==0); closed=true; closes++ }
    fun replaceWithMeshModel(m:MeshModel,b:BoundingBox):Boolean {
        check(!Thread.currentThread().name.contains("fixture-ui")); check(!closed)
        val count=active.incrementAndGet(); peak=maxOf(peak,count)
        try {
            entered?.countDown()
            check(release?.await(5,TimeUnit.SECONDS) != false) { "Upload gate timed out" }
            check(!closed); model=m
            return !reject
        } finally { active.decrementAndGet() }
    }
    companion object {
        val active=AtomicInteger(); var peak=0; var closes=0; var reject=false
        var entered:CountDownLatch?=null; var release:CountDownLatch?=null
        var last:MeshResource?=null
        fun createWithMeshModel(m:MeshModel,b:BoundingBox,n:String):MeshResource {
            check(!Thread.currentThread().name.contains("fixture-ui"))
            return MeshResource().also { it.model=m; last=it }
        }
    }
}
enum class MaterialCullingMode { NONE }
enum class PolygonFillMode { LINE }
open class BaseMaterial {
    fun setBaseColor(c:Color4) {}; fun setCullingMode(c:MaterialCullingMode) {}
    fun toGlobal() {}; fun close() {}
}
class PhysicallyBasedMaterial:BaseMaterial() {
    fun setRoughness(v:Float) {}; fun setMetallic(v:Float) {}
    companion object { fun create()=PhysicallyBasedMaterial() }
}
class UnlitMaterial:BaseMaterial() {
    fun setPolygonFillMode(v:PolygonFillMode) {}; fun setBaseColorTexture(v:TextureResource) {}
    companion object { fun create()=UnlitMaterial() }
}
class TextureResource {
    fun toGlobal() {}; fun close() {}
    companion object { fun create(b:Bitmap)=TextureResource() }
}
''',
        'Lab.kt': '''package com.pico.spatial.ml.sample.facelandmarker
import org.json.JSONObject
class FaceGeometry(val canonical:FloatArray,val triangles:List<Int>)
class StagePoseHistory { fun start() {}; fun close() {}; fun atCapture(t:Double):FloatArray?=null }
object FaceLandmarkerRunner { const val TAG="fixture" }
class Outputs(val mesh:Boolean=true)
class Auto(val board:Boolean=false,val markers:Boolean=true,val protocol:String="reference",val sideReferences:Boolean=false)
class FaceFrame(val sequence:Int,val vertices:FloatArray,val automatic:Auto?=null,val hasFace:Boolean=true,val outputs:Outputs=Outputs()) {
    val presentationStabilization:JSONObject?=null
    val presentationTiming:JSONObject?=null
    val registrationEvidence=if(automatic!=null) LabRegistrationEvidence() else null
    val captureCameraPose=FloatArray(16); val pose=FloatArray(16)
    val captureSeconds=1.0; val readbackSeconds:Double?=1.1
}
class LabRegistrationEvidence {
    val headToStage=floatArrayOf(1f,0f,0f,0f,0f,1f,0f,0f,0f,0f,1f,0f,0f,0f,0f,1f)
    fun json(s:Boolean)=JSONObject()
}
object LabAutoCapture {
    val markerTriangles=listOf(0,1,2)
    fun markerVertices(v:FloatArray)=v.copyOfRange(0,9)
}
object LabProjectionReference {
    const val PROTOCOL="reference"; const val FACE_MARKER_U=0f; const val FACE_MARKER_V=0f; const val ATLAS_SIZE=2
    class Mesh(val positions:FloatArray,val triangles:List<Int>,val uv:FloatArray)
    fun mesh(sequence:Int,sides:Boolean)=Mesh(floatArrayOf(0f,0f,0f,1f,0f,0f,0f,1f,0f),listOf(0,1,2),FloatArray(6))
    fun atlas()=IntArray(4)
}
''',
        'Fixture.kt': r'''package com.pico.spatial.ml.sample.facelandmarker
import com.pico.spatial.core.container.SpatialViewContent
import com.pico.spatial.core.math.Vector3
import com.pico.spatial.core.ecs.resource.MeshResource
import kotlinx.coroutines.*
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlin.math.*
import java.io.File
import org.json.JSONObject
fun near(a:Float,b:Float) { check(abs(a-b)<2e-5f) { "$a != $b" } }
fun main(args:Array<String>)=runBlocking {
    val helper=FaceMeshPreparation()
    val points=FloatArray(478*3) { sin(it*.13).toFloat() }
    val indices=(0 until 477).toList()
    val basis=floatArrayOf(2f,-3f,4f,.5f,.2f,-.3f,.1f,2f,.4f,-.7f,.3f,1.1f)
    var previous:List<Vector3>?=null
    var previousValues:List<Float>?=null
    for(n in 0 until 80) {
        val stage=if(n%2==0) points else FloatArray(9)
        val topology=if(n%2==0) indices else listOf(0,1,2)
        val solid=n%3!=0
        val p=helper.prepare(stage,basis,topology,solid)
        check(p.model.triangleIndices===topology)
        check((p.model.normals!=null)==solid)
        // Independent old vector expression and area-weighted normal accumulation.
        val o=Vector3(basis[0],basis[1],basis[2]); val x=Vector3(basis[3],basis[4],basis[5])
        val y=Vector3(basis[6],basis[7],basis[8]); val z=Vector3(basis[9],basis[10],basis[11])
        val expected=List(stage.size/3) { i -> o+x*stage[i*3]+y*stage[i*3+1]+z*stage[i*3+2] }
        expected.indices.forEach { i -> near(expected[i].x,p.model.positions[i].x); near(expected[i].y,p.model.positions[i].y); near(expected[i].z,p.model.positions[i].z) }
        near(p.bounds.center.x,(expected.minOf{it.x}+expected.maxOf{it.x})*.5f)
        near(p.bounds.extents.y,(expected.maxOf{it.y}-expected.minOf{it.y})*.5f)
        if(solid) {
            val accum=Array(expected.size){FloatArray(3)}
            for(i in topology.indices step 3) {
                val a=expected[topology[i]];val b=expected[topology[i+1]]-a;val c=expected[topology[i+2]]-a
                val normal=floatArrayOf(b.y*c.z-b.z*c.y,b.z*c.x-b.x*c.z,b.x*c.y-b.y*c.x)
                for(j in i..i+2)for(k in 0..2)accum[topology[j]][k]+=normal[k]
            }
            accum.forEachIndexed { i,v ->
                val len=sqrt(v.sumOf{it.toDouble()*it}).toFloat()
                val e=if(len>1e-12f) v.map{it/len} else listOf(0f,0f,1f)
                val actual=p.model.normals!![i]; near(e[0],actual.x);near(e[1],actual.y);near(e[2],actual.z)
            }
        }
        if(previous!=null)check(previous!!.flatMap{listOf(it.x,it.y,it.z)}==previousValues)
        previous=p.model.normals; previousValues=previous?.flatMap{listOf(it.x,it.y,it.z)}
    }
    newSingleThreadContext("fixture-ui").use { ui -> withContext(ui) {
        val geometry=FaceGeometry(FloatArray(478*4),indices)
        val scene=FaceMeshScene(geometry)
        scene.initialize(SpatialViewContent(),null)
        scene.setMeshStyle(0)
        Vector3.workerVectors.set(0)
        scene.update(FaceFrame(1,points))
        check(Vector3.workerVectors.get()>=478)
        check(scene.face.enabled && MeshResource.last!!.model!!.normals==null)
        val timing=scene.uploadTiming!!
        check(timing.getInt("frame")==1 && !timing.getBoolean("normalsIncluded"))
        val keys=listOf("sceneReceivedSeconds","sceneAcquiredSeconds","ownerSnapshotStartSeconds","ownerSnapshotEndSeconds","workerDispatchedSeconds","workerStartedSeconds","preparedSeconds","sdkUploadStartSeconds","sdkUploadEndSeconds","uiResumedSeconds","sceneReadySeconds")
        keys.zipWithNext().forEach { (a,b) -> check(timing.getDouble(b)>=timing.getDouble(a)) }
        scene.setMeshStyle(1);check(!scene.face.enabled)
        scene.update(FaceFrame(2,points));check(scene.face.enabled && MeshResource.last!!.model!!.normals!=null)
        scene.update(FaceFrame(3,points,Auto()));check(scene.uploadedGeometry!!.getDouble("ownerRoundTripMaxMetres")<.0001)
        check(MeshResource.last!!.model!!.normals==null && MeshResource.last!!.model!!.uv0!!.size==6)
        scene.update(FaceFrame(4,points,Auto(board=true)));check(MeshResource.last!!.model!!.positions.size==3)
        scene.update(FaceFrame(5,points,Auto(protocol="markers")));check(MeshResource.last!!.model!!.positions.size==3)
        scene.update(FaceFrame(6,points,hasFace=false));check(!scene.face.enabled && scene.uploadTiming==null)
        scene.setMeshStyle(2);scene.update(FaceFrame(7,points));check(!scene.face.enabled && scene.uploadTiming==null)
        scene.setMeshStyle(0)
        MeshResource.reject=true
        check(runCatching{scene.update(FaceFrame(8,points))}.isFailure && scene.uploadTiming==null)
        MeshResource.reject=false
        // Cancellation does not release ownership of a blocking native replacement early.
        MeshResource.entered=CountDownLatch(1);MeshResource.release=CountDownLatch(1)
        val old=launch { scene.update(FaceFrame(9,points)) }
        withContext(Dispatchers.IO) { check(MeshResource.entered!!.await(5,TimeUnit.SECONDS)) }
        scene.setMeshStyle(1);check(!scene.face.enabled)
        old.cancel()
        val next=launch { scene.update(FaceFrame(10,points)) }
        yield();check(MeshResource.active.get()==1)
        MeshResource.release!!.countDown();old.join();next.join()
        check(MeshResource.peak==1 && scene.uploadTiming!!.getInt("frame")==10)
        check(scene.face.enabled && MeshResource.last!!.model!!.normals!=null)
        // Close during a suspended update must defer resource close, then suppress acknowledgement.
        MeshResource.entered=CountDownLatch(1);MeshResource.release=CountDownLatch(1)
        val closing=launch { scene.update(FaceFrame(11,points)) }
        withContext(Dispatchers.IO) { check(MeshResource.entered!!.await(5,TimeUnit.SECONDS)) }
        scene.close();check(!MeshResource.last!!.closed)
        MeshResource.release!!.countDown();closing.join()
        check(MeshResource.last!!.closed && scene.uploadTiming==null)
        scene.close();check(MeshResource.closes==1)
    } }
    File(args[0]).writeText(JSONObject().put("status","PASS").put("numericalCases",80).put("maximumConcurrentUploads",MeshResource.peak).put("deviceRuntime","NOT_RUN").toString(2)+"\n")
    println("PASS: production coordinate/normal/bounds parity, scratch reuse, UI/worker ownership, style/reference/board/hidden modes, SDK rejection, cancellation serialization and close during upload")
}
''',
    }
    for name, body in files.items():
        (output / name).write_text(body)
    cache = Path.home() / '.gradle/caches/modules-2/files-2.1'
    def jar(group, name, version):
        return next((cache / group / name / version).glob('*/*.jar'))
    stdlib = jar('org.jetbrains.kotlin', 'kotlin-stdlib', '2.0.21')
    coroutines = jar('org.jetbrains.kotlinx', 'kotlinx-coroutines-core-jvm', '1.9.0')
    compiler = [jar('org.jetbrains.kotlin', name, '2.0.21') for name in
                ['kotlin-compiler-embeddable', 'kotlin-script-runtime', 'kotlin-reflect', 'kotlin-daemon-embeddable']]
    compiler += [stdlib, jar('org.jetbrains', 'annotations', '13.0'),
                 jar('org.jetbrains.intellij.deps', 'trove4j', '1.0.20200330'), coroutines]
    java = '/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java'
    cp = os.pathsep.join(map(str, [stdlib, coroutines, json_jar]))
    classes = output / 'classes'
    subprocess.run([java, '-cp', os.pathsep.join(map(str, compiler)),
                    'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler', '-nowarn', '-no-stdlib', '-no-reflect',
                    '-classpath', cp, '-d', str(classes), *map(str, output.glob('*.kt')),
                    *[str(source / name) for name in ['FaceMeshPreparation.kt', 'FaceMeshScene.kt', 'StageRegistration.kt']]], check=True)
    subprocess.run([java, '-cp', str(classes)+os.pathsep+cp,
                    'com.pico.spatial.ml.sample.facelandmarker.FixtureKt', str(output/'validation.json')], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--json-jar', type=Path, required=True)
    args = parser.parse_args()
    validate(args.output, args.json_jar)
