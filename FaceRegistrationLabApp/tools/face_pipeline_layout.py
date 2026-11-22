"""Record the actual Kotlin graph construction with host tensor/native adapters.

This executes construction only, to map operator indices to names and tensor sizes.
It measures no operator runtime and never contacts a headset.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def record(output, json_jar):
    root = Path(__file__).resolve().parents[2]
    source = root / 'FaceLandmarkerApp/src/main/java/com/pico/spatial/ml/sample/facelandmarker'
    output.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='face-pipeline-layout-'))
    session_source = (source / 'SpatialMLGraphSession.kt').read_text()
    preprocess = session_source[session_source.index('        fun preprocess('):session_source.index('        fun submit(')]
    stubs = {
        'Context.kt': '''package android.content
class Context(val assets: android.content.res.AssetManager)
''',
        'Assets.kt': '''package android.content.res
class AssetManager(private val root: java.io.File) {
    fun open(path: String) = java.io.File(root, path).inputStream()
}
''',
        'Encoding.kt': '''package com.bytedance.pico.openmr.spatial.pack.utils
class ModelEncoding { enum class EncodingType { FLOATING_POINT32, UNSIGNED_FIXED_POINT8, SIGNED_FIXED_POINT8, UNSIGNED_FIXED_POINT16, INT32 } }
''',
        'Build.kt': '''package android.os
object Build { const val FINGERPRINT = "Pico/swan/swan:16/BQ2A.260122.002-BP2A.250705.008/20261014024400:userdebug/test-keys" }
''',
        'Log.kt': '''package android.util
object Log { fun i(tag: String, text: String) = 0 }
''',
    }
    for name, text in stubs.items():
        (staging / name).write_text(text)
    adapter = r'''package com.pico.spatial.ml.sample.facelandmarker
import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import com.bytedance.pico.openmr.spatial.pack.utils.ModelEncoding

internal object FaceFrame { const val RESULT_SIZE = 2994; const val TRACKING_OFFSET = 2946; const val VERTEX_OFFSET = 1438; const val BLENDSHAPE_OFFSET = 2872; const val POSE_OFFSET = 2924 }
internal object BuildConfig {
    var FACE_GPU_PREPROCESSING = true
    var FACE_GPU_SAMPLE_BYTES = false
    var FACE_FUSED_GEOMETRY = false
    var FACE_INLINE_GEOMETRY = false
    var FACE_RETAINED_VST_PIPELINE = false
    var FACE_COMPACT_VST_PIPELINE = false
    var FACE_FUSED_CONTROL_MODELS = false
}
internal object FaceLandmarkerRunner { const val TAG = "FaceLandmarker" }
internal class LabCapture(vararg values: Any)
internal class SpatialMLGraphSession : AutoCloseable {
    val pipelines = mutableListOf<GraphPipeline>()
    val submitted = mutableListOf<GraphPipeline>()
    var resetCount = 0
    var readValues: FloatArray? = null
    private var nextId = 1L
    fun global(rows: Int, columns: Int, values: FloatArray? = null) = GraphTensor(nextId++, intArrayOf(rows, columns))
    fun globalImage(width: Int = WIDTH, height: Int = HEIGHT, float: Boolean = false) = GraphTensor(nextId++, intArrayOf(height, width))
    fun globalTimestamp() = GraphTensor(nextId++, intArrayOf(1))
    fun pipeline(context: Context) = GraphPipeline { pipeline, waitFor ->
        check(waitFor == if(submitted.isEmpty()) 0L else submitted.size.toLong())
        submitted.add(pipeline); submitted.size.toLong()
    }.also { pipelines.add(it) }
    fun reset(tensor: GraphTensor, values: FloatArray) { resetCount++ }
    fun read(tensor: GraphTensor, size: Int) = readValues?.copyOf(size) ?: FloatArray(size)
    fun readBytes(tensor: GraphTensor, size: Int) = ByteArray(size)
    override fun close() {}
    class GraphTensor(val id: Long, val shape: IntArray)
    class GraphPipeline(val onSubmit: (GraphPipeline, Long) -> Long) {
        private var nextId = 1000L
        val operators = mutableListOf<JSONObject>()
        fun floats(rows: Int, columns: Int, values: FloatArray? = null) = GraphTensor(nextId++, intArrayOf(rows, columns))
        fun image(size: Int, float: Boolean = false) = GraphTensor(nextId++, intArrayOf(size, size))
        fun timestamp() = GraphTensor(nextId++, intArrayOf(1))
        private fun tensors(values: Map<String, GraphTensor>) = JSONObject().apply {
            values.forEach { (name, tensor) -> put(name, JSONArray(tensor.shape.toList())) }
        }
        private fun add(kind: String, name: String, inputs: Map<String, GraphTensor>, outputs: Map<String, GraphTensor>) {
            operators.add(JSONObject().put("index", operators.size).put("kind", kind).put("name", name)
                .put("inputs", tensors(inputs)).put("outputs", tensors(outputs))
                .put("inputTensorIds", JSONObject(inputs.mapValues { it.value.id }))
                .put("outputTensorIds", JSONObject(outputs.mapValues { it.value.id })))
        }
        fun op(type: Int, inputs: List<GraphTensor>, outputs: List<GraphTensor>, config: String? = null) {
            val name = when(type) { 1 -> "Arithmetic"; 15 -> "ApplyAffine"; 18 -> "Assignment"; 34 -> "SVD"; else -> type.toString() }
            add("native", name, inputs.mapIndexed { i, t -> i.toString() to t }.toMap(), outputs.mapIndexed { i, t -> i.toString() to t }.toMap())
        }
        fun namedOp(type: Int, inputs: Map<String, GraphTensor>, outputs: Map<String, GraphTensor>, config: String? = null) {
            add("native", when(type) { 22 -> "CameraSpaceToWorld"; 23 -> "RectifiedVSTAccess"; 43 -> "RetainedVSTAccess"; 44 -> "RetainedVSTRoi"; 45 -> "RetainedVSTAffine"; else -> type.toString() }, inputs, outputs)
        }
        fun script(name: String, inputs: Map<String, GraphTensor>, outputs: Map<String, GraphTensor>) { add("javascript", name, inputs, outputs) }
        fun model(name: String, inputs: Map<String, GraphTensor>, outputs: Map<String, GraphTensor>, backend: Int, inputEncodings: Map<String, ModelEncoding.EncodingType> = emptyMap()) { add("model", name, inputs, outputs); operators.last().put("backend", backend) }
        fun submit(waitFor: Long = 0) = onSubmit(this, waitFor)
PREPROCESS
    }
    companion object {
        const val WIDTH = 3248; const val HEIGHT = 2464; const val LANDMARK_TILE_SIZE = 768
        const val ASSETS = "SpatialML/face-landmarker"
        const val PREPROCESSING_BACKEND = 1
        const val ARITHMETIC = 1; const val APPLY_AFFINE = 15; const val ASSIGNMENT = 18
        const val CAMERA_TO_WORLD = 22; const val VST = 23; const val SVD = 34
        const val RETAINED_VST_ACCESS = 43; const val RETAINED_VST_ROI = 44; const val RETAINED_VST_AFFINE = 45
    }
}
fun main(args: Array<String>) {
    val context = Context(android.content.res.AssetManager(java.io.File(args[0])))
    BuildConfig.FACE_GPU_PREPROCESSING = args.getOrNull(1) != "native"
    BuildConfig.FACE_GPU_SAMPLE_BYTES = args.getOrNull(1) == "rgb_first"
    BuildConfig.FACE_FUSED_GEOMETRY = args.getOrNull(2) in listOf("fused", "inline_fused")
    BuildConfig.FACE_INLINE_GEOMETRY = args.getOrNull(2) in listOf("inline", "inline_fused")
    BuildConfig.FACE_RETAINED_VST_PIPELINE = args.getOrNull(3) == "retained"
    BuildConfig.FACE_COMPACT_VST_PIPELINE = args.getOrNull(3) == "compact"
    BuildConfig.FACE_FUSED_CONTROL_MODELS = args.getOrNull(4) == "fused_controls"
    val result = JSONObject()
    for (lab in listOf(true, false)) {
        val session = SpatialMLGraphSession()
        // Use the production factory with only the session constructor replaced in its host copy.
        val graph = FaceLandmarkerGraph.createRecorded(context, 2, lab, session)
        val names = listOf("detector", "tracking", "landmark_fit") +
            (if(lab) listOf("mesh") else emptyList()) + listOf("expressions", "tongue") +
            (1..7).map { "output_$it" } + (if(lab) listOf("capture") else emptyList())
        val fitOps = session.pipelines[2].operators
        val fitNames = fitOps.map { it.getString("name") }
        val tongueOp = session.pipelines[names.indexOf("tongue")].operators.single()
        check(tongueOp.getString("name") == "tongue_visibility" && tongueOp.getInt("backend") == 0)
        val tongueImageId = tongueOp.getJSONObject("inputTensorIds").getLong("mouth_image")
        val landmarkInputs = fitOps.single { it.getString("name") == "face_landmarks_detector" }.getJSONObject("inputTensorIds")
        check(landmarkInputs.length() == 1 && landmarkInputs.getLong(landmarkInputs.keys().next()) == tongueImageId)
        if (BuildConfig.FACE_FUSED_CONTROL_MODELS) {
            check(fitNames.count { it == "SVD" } == 0)
            check(fitNames.count { it == if (lab) "face_landmark_control_lab" else "face_landmark_control" } == 1)
            check(fitOps.none { it.getString("kind") == "javascript" })
        } else if (BuildConfig.FACE_INLINE_GEOMETRY) {
            check(fitNames.count { it == "SVD" } == 0)
            check(fitNames.count { it == "face_fit_inline" } == 1)
            check(fitNames.none { it in listOf("geometry_covariance", "geometry_solve", "geometry_unproject", "face_fit_prepare", "face_fit_bridge", "face_fit_finish") })
            check(fitNames.indexOf("face_fit_inline") + 1 == fitNames.indexOf("face_pose"))
            check(fitOps.single { it.getString("name") == "face_fit_inline" }.getInt("backend") == 0)
        } else if (BuildConfig.FACE_FUSED_GEOMETRY) {
            val first = fitNames.indexOf("face_fit_prepare")
            check(first >= 0)
            check(fitNames.subList(first, first + 7) == listOf(
                "face_fit_prepare", "SVD", "face_fit_bridge", "SVD", "face_fit_bridge", "SVD", "face_fit_finish"))
            check(fitNames.none { it in listOf("geometry_covariance", "geometry_solve", "geometry_unproject") })
            check(fitOps.filter { it.getString("name").startsWith("face_fit_") }.all { it.getInt("backend") == 0 })
        } else {
            check(fitNames.count { it == "geometry_covariance" } == 3)
            check(fitNames.count { it == "geometry_solve" } == 3)
            check(fitNames.count { it == "geometry_unproject" } == 2)
        }
        val paths = JSONArray()
        for (mask in listOf(1, 2, 3, 4, 5, 6, 7, 4, 1, 7)) {
            for (acquire in listOf(true, false)) {
                session.submitted.clear()
                val resets = session.resetCount
                val outputs = FaceOutputs(mask)
                graph.submit(100 + mask, 1f, 1f, acquire, outputs, evidence = false)
                check(session.resetCount == resets + 1) // command only; switching preserves tracker
                check(graph.readResult().size == outputs.packetSize)
                check(graph.readTongue(100 + mask) == null)
                try { graph.submitCapture(); error("Compact frame authorized capture") }
                catch (_: IllegalStateException) { }
                val path = session.submitted.map { names[session.pipelines.indexOf(it)] }
                check(path == listOf(if(acquire) "detector" else "tracking", "landmark_fit") +
                    (if(outputs.blendshapes) listOf("expressions") else emptyList()) + listOf("output_$mask"))
                paths.put(JSONObject().put("mask",mask).put("acquire",acquire).put("path",JSONArray(path)))
            }
        }
        val tonguePaths = JSONArray()
        for (acquire in listOf(true, false)) {
            session.submitted.clear()
            graph.submit(17001, 1f, 1f, acquire, FaceOutputs.ALL, evidence = false, tongueRequested = true)
            val path = session.submitted.map { names[session.pipelines.indexOf(it)] }
            check(path == listOf(if(acquire) "detector" else "tracking", "landmark_fit", "expressions", "tongue", "output_7"))
            session.readValues = floatArrayOf(17001f, .8f)
            check(graph.readTongue(17001) == .8f)
            for(values in listOf(floatArrayOf(17000f,.8f),floatArrayOf(17001f,Float.NaN),floatArrayOf(17001f,1.1f))) {
                session.readValues = values
                check(runCatching { graph.readTongue(17001) }.exceptionOrNull() is IllegalStateException)
            }
            session.readValues = null
            tonguePaths.put(JSONArray(path))
        }
        session.submitted.clear()
        try { graph.submit(199, 1f, 1f, true, FaceOutputs(3), evidence = false, tongueRequested = true); error("Tongue without blendshapes submitted") }
        catch (_: IllegalArgumentException) { }
        check(session.submitted.isEmpty())
        try { graph.submit(199, 1f, 1f, true, FaceOutputs.NONE, evidence = false); error("Empty outputs submitted") }
        catch (_: IllegalArgumentException) { }
        check(session.submitted.isEmpty())
        if(lab) {
            try { graph.submit(199, 1f, 1f, true, FaceOutputs.ALL, evidence = true, tongueRequested = true); error("Tongue during evidence capture submitted") }
            catch (_: IllegalArgumentException) { }
            check(session.submitted.isEmpty())
            try { graph.submit(199, 1f, 1f, true, FaceOutputs(1), evidence = true); error("Partial evidence submitted") }
            catch (_: IllegalArgumentException) { }
            check(session.submitted.isEmpty())
            session.submitted.clear()
            graph.submit(200, 1f, 1f, true, FaceOutputs.ALL, evidence = true)
            check(graph.readResult().size == 2994)
            check(session.submitted.map { names[session.pipelines.indexOf(it)] } == listOf("detector","landmark_fit","mesh"))
            graph.submitCapture()
            check(names[session.pipelines.indexOf(session.submitted.last())] == "capture")
        }
        result.put(if(lab) "labOutputSubmissions" else "normalOutputSubmissions", paths)
        result.put(if(lab) "labTongueSubmissions" else "normalTongueSubmissions", tonguePaths)
        result.put(if(lab) "lab" else "normal", JSONArray().apply {
            session.pipelines.forEachIndexed { i, pipeline ->
                put(JSONObject().put("pipeline", names[i]).put("operators", JSONArray(pipeline.operators)))
            }
        })
    }
    println(result.toString(2))
}
'''.replace('\nPREPROCESS\n', '\n' + preprocess + '\n')
    (staging / 'SessionAdapter.kt').write_text(adapter)
    graph = (source / 'FaceLandmarkerGraph.kt').read_text()
    host_graph = graph.replace('fun create(context: Context, backend: Int, lab: Boolean = false): FaceLandmarkerGraph {\n            val session = SpatialMLGraphSession()',
                              'fun createRecorded(context: Context, backend: Int, lab: Boolean, session: SpatialMLGraphSession): FaceLandmarkerGraph {')
    assert host_graph != graph
    (staging / 'FaceLandmarkerGraph.kt').write_text(host_graph)
    cache = Path.home() / '.gradle/caches/modules-2/files-2.1'
    def jar(group, artifact, version):
        return next((cache / group / artifact / version).glob('*/*.jar'))
    stdlib = jar('org.jetbrains.kotlin', 'kotlin-stdlib', '2.0.21')
    compiler = [jar('org.jetbrains.kotlin', name, '2.0.21') for name in
                ('kotlin-compiler-embeddable', 'kotlin-script-runtime', 'kotlin-reflect', 'kotlin-daemon-embeddable')]
    compiler += [stdlib, jar('org.jetbrains', 'annotations', '13.0'), jar('org.jetbrains.intellij.deps', 'trove4j', '1.0.20200330'),
                 jar('org.jetbrains.kotlinx', 'kotlinx-coroutines-core-jvm', '1.6.4')]
    java = Path(os.environ.get('JAVA_HOME', '/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home')) / 'bin/java'
    classes = staging / 'classes'
    cp = os.pathsep.join(map(str, [stdlib, json_jar]))
    subprocess.run([str(java), '-cp', os.pathsep.join(map(str, compiler)), 'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler',
                    '-no-stdlib', '-no-reflect', '-classpath', cp, '-d', str(classes), *map(str, staging.glob('*.kt')),
                    *[str(source/name) for name in ('LabGeometryProbe.kt', 'LabIntrinsics.kt', 'LabCameraProfile.kt', 'LabStereoCalibration.kt', 'CompactFaceDetector.kt', 'FaceOutputs.kt')]], check=True)
    binding_count = 0
    configurations = [
        (variant, fitting, capture, 'legacy_controls')
        for fitting in ('legacy', 'fused', 'inline', 'inline_fused')
        for variant in ('gpu', 'native', 'rgb_first')
        for capture in ('full', 'retained')
    ]
    configurations.append(('rgb_first', 'legacy', 'compact', 'fused_controls'))
    import tflite as fb
    control_models = {
        'detector_compact_preprocess_gpu',
        'face_detector_control',
        'face_roi_control',
        'face_landmark_control',
        'face_landmark_control_lab',
        'face_completion_marker',
        'tongue_visibility',
    }
    for variant, fitting, capture, controls in configurations:
        result = subprocess.run([str(java), '-cp', str(classes)+os.pathsep+cp,
                                 'com.pico.spatial.ml.sample.facelandmarker.SessionAdapterKt',
                                 str(root/'FaceLandmarkerApp/src/main/assets'), variant, fitting, capture,
                                 controls], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        data['boundary'] = 'Actual graph construction with host adapters; operator order and tensor sizes only, no native runtime timings.'
        data['sourceSha256'] = hashlib.sha256(graph.encode()).hexdigest()
        data['preprocessing'] = variant
        data['fusedGeometry'] = fitting in ('fused', 'inline_fused')
        data['inlineGeometry'] = fitting in ('inline', 'inline_fused')
        data['retainedVstPipeline'] = capture == 'retained'
        data['compactVstPipeline'] = capture == 'compact'
        data['fusedControlModels'] = controls == 'fused_controls'
        if controls == 'fused_controls':
            filename = 'operator-layout-compact-fused-controls.json'
        else:
            filename={'gpu':'operator-layout.json','native':'operator-layout-native.json','rgb_first':'operator-layout-rgb-first.json'}[variant]
            if fitting != 'legacy': filename=filename.replace('.json','-'+fitting.replace('_','-')+'-geometry.json')
            if capture == 'retained': filename=filename.replace('.json','-retained-vst.json')
        (output/filename).write_text(json.dumps(data, indent=2)+'\n')
        for mode in ('lab', 'normal'):
            print(variant, fitting, capture, controls, mode, [(p['pipeline'], len(p['operators'])) for p in data[mode]])
            if controls == 'fused_controls':
                pipelines = {p['pipeline']: p['operators'] for p in data[mode]}
                names = lambda pipeline: [op['name'] for op in pipelines[pipeline]]
                assert names('detector') == [
                    'RectifiedVSTAccess', 'RectifiedVSTAccess', 'CameraSpaceToWorld',
                    'detector_compact_preprocess_gpu', 'face_detector', 'face_detector_control',
                ]
                assert names('tracking') == [
                    'RectifiedVSTAccess', 'CameraSpaceToWorld', 'face_roi_control',
                ]
                assert names('landmark_fit') == [
                    'landmark_preprocess_rgb_gpu', 'face_landmarks_detector',
                    'face_landmark_control_lab' if mode == 'lab' else 'face_landmark_control',
                ]
                ordinary = ['detector', 'tracking', 'landmark_fit', 'expressions'] + [f'output_{i}' for i in range(1, 8)]
                assert not [op for pipeline in ordinary for op in pipelines[pipeline] if op['kind'] == 'javascript']
            # Inspect the actual FlatBuffer ABI, not just a handwritten manifest.
            for pipeline in data[mode]:
                for op in pipeline['operators']:
                    if op['kind'] != 'model' or not (op['name'].startswith('face_fit_') or op['name'] in control_models): continue
                    asset=root/'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker/model'/(op['name']+'.tflite')
                    model=fb.Model.GetRootAsModel(asset.read_bytes(),0);sub=model.Subgraphs(0)
                    for side in ('inputs','outputs'):
                        length=getattr(sub,side.capitalize()+'Length')()
                        indices=[getattr(sub,side.capitalize())(i) for i in range(length)]
                        actual={sub.Tensors(i).Name().decode():sub.Tensors(i).ShapeAsNumpy().tolist() for i in indices}
                        assert actual.keys()==op[side].keys(),(variant,fitting,capture,mode,op['name'],side,actual,op[side])
                        for name, shape in op[side].items():
                            # TIMESTAMP is declared as one native value but exposes the existing
                            # four-word timespec payload to scripts and model inference.
                            expected = [[1, 1, 1, 4]] if name == 'timestamp' else [[1, 1, *shape]]
                            if len(shape) == 2:
                                expected.append([1, *shape, 3])
                            assert actual[name] in expected,(variant,fitting,capture,mode,op['name'],side,name,actual[name],expected)
                            if name == 'timestamp':
                                assert sub.Tensors(indices[list(actual).index(name)]).Type() == fb.TensorType.INT32
                    expected_backend = 1 if op['name'] == 'detector_compact_preprocess_gpu' else 0
                    assert op['backend']==expected_backend
                    binding_count += 1
    print('Validated serialized weightless model call bindings:',binding_count)
    shutil.rmtree(staging)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--json-jar', type=Path, required=True)
    args = parser.parse_args()
    record(args.output, args.json_jar)
