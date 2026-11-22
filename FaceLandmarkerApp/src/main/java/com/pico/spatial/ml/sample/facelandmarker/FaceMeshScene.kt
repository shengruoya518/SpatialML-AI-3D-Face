// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.graphics.Bitmap
import android.util.Log
import com.pico.spatial.core.container.SpatialViewContent
import com.pico.spatial.core.ecs.AnchorComponent
import com.pico.spatial.core.ecs.AnchorEntity
import com.pico.spatial.core.ecs.DirectionalLightComponent
import com.pico.spatial.core.ecs.Entity
import com.pico.spatial.core.ecs.ModelComponent
import com.pico.spatial.core.ecs.TransformComponent
import com.pico.spatial.core.ecs.anchor.AnchorTarget
import com.pico.spatial.core.ecs.resource.MaterialCullingMode
import com.pico.spatial.core.ecs.resource.MeshResource
import com.pico.spatial.core.ecs.resource.PhysicallyBasedMaterial
import com.pico.spatial.core.ecs.resource.PolygonFillMode
import com.pico.spatial.core.ecs.resource.TextureResource
import com.pico.spatial.core.ecs.resource.UnlitMaterial
import com.pico.spatial.core.math.Color4
import com.pico.spatial.core.math.Quat
import com.pico.spatial.core.math.Vector2
import com.pico.spatial.core.math.Vector3
import kotlin.math.sqrt
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/** A Stage-owned, identity-transform face. The control panel alone follows the headset. */
internal class FaceMeshScene(private val geometry: FaceGeometry) : AutoCloseable {
    val poses = StagePoseHistory()
    private val triangles = geometry.triangles
    val face =
        Entity().apply {
            setName("face-landmarker-stage-mesh")
            enabled = false
        }
    private val controls = AnchorEntity(AnchorTarget.createCameraTarget())
    private var controlPanel: Entity? = null
    private var mesh: MeshResource? = null
    private val updateMutex = Mutex()
    private val preparation = FaceMeshPreparation()
    private var uploadingResource: MeshResource? = null
    private var uploadingStyle: Int? = null
    private var uploadedHasNormals = true
    var uploadTiming: JSONObject? = null
        private set

    private var material: PhysicallyBasedMaterial? = null
    private var wireMaterial: UnlitMaterial? = null
    private var markerMaterial: UnlitMaterial? = null
    private var referenceMaterial: UnlitMaterial? = null
    private var referenceTexture: TextureResource? = null
    var uploadedGeometry: JSONObject? = null
        private set

    var stabilization: JSONObject? = null
        private set

    private var effectiveStyle = 1
    private var appliedStyle = -1
    private var meshStyle = 1
    private var measuredFace = false
    private var closed = false
    private var appliedFirstFrame = false

    suspend fun initialize(content: SpatialViewContent, panel: Entity?) {
        content.addEntity(face)
        controls.components.get<AnchorComponent>()?.positionOffset = Vector3(0f, -.25f, -1f)
        if (panel != null) {
            controlPanel = panel
            controls.addChild(panel)
        }
        // Directional lights inherit headset orientation; their position does not affect lux.
        // Keep an oblique key and weaker fill so the nose/cheeks retain visible relief in VST.
        controls.addChild(createLight("face-key", .55f, -.35f, 1500f, Color4(1f, .95f, .9f, 1f)))
        controls.addChild(createLight("face-fill", -.8f, .1f, 350f, Color4(.8f, .9f, 1f, 1f)))
        content.addEntity(controls)
        Log.i(
            FaceLandmarkerRunner.TAG,
            "scene_ready stage=full_space passthrough=mixed mesh_owner=stage camera_anchor=controls_only",
        )
        poses.start()
        Log.i(FaceLandmarkerRunner.TAG, "controls_position x=0 y=-0.25 z=-1 camera_relative=true")
        Log.i(
            FaceLandmarkerRunner.TAG,
            "face_lighting material=pbr roughness=0.7 metallic=0 key_lux=1500 fill_lux=350 normals=solid_only",
        )
        // Match Unity's initial canonical topology. Keep it hidden until a measured frame arrives.
        val canonical =
            FloatArray(478 * 3) { i ->
                if (i / 3 < 468) geometry.canonical[i / 3 * 4 + i % 3] * .01f else 0f
            }
        var created: MeshResource? = null
        var adopted = false
        try {
            withContext(Dispatchers.IO) {
                val prepared =
                    preparation.prepare(
                        canonical,
                        floatArrayOf(0f, 0f, 0f, 1f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 1f),
                        triangles,
                        needsNormals = true,
                    )
                created =
                    MeshResource.createWithMeshModel(
                            prepared.model,
                            prepared.bounds,
                            "FaceLandmarkerDynamicMesh",
                        )
                        .apply { toGlobal() }
            }
            currentCoroutineContext().ensureActive()
            if (closed) return
            val nextMaterial = createMaterial()
            material = nextMaterial
            face.components.set(ModelComponent(checkNotNull(created), nextMaterial))
            mesh = created
            adopted = true
            Log.i(
                FaceLandmarkerRunner.TAG,
                "dynamic_mesh_initialized vertices=478 triangles=${triangles.size / 3} hidden=true",
            )
        } finally {
            if (!adopted) created?.close()
        }
    }

    suspend fun update(frame: FaceFrame?) {
        val received = System.nanoTime() * 1e-9
        updateMutex.withLock { updateSerialized(frame, received) }
    }

    private suspend fun updateSerialized(frame: FaceFrame?, received: Double) {
        uploadTiming = null
        val acquired = System.nanoTime() * 1e-9
        uploadedGeometry = null
        stabilization = frame?.presentationStabilization
        if (closed) return
        val board = frame?.automatic?.board == true
        if (frame == null || (!frame.hasFace && !board) || !frame.outputs.mesh) {
            measuredFace = false
            face.enabled = false
            return
        }
        val reference =
            frame.registrationEvidence?.takeIf {
                frame.automatic?.protocol == LabProjectionReference.PROTOCOL &&
                    frame.automatic.markers
            }
        effectiveStyle =
            frame.automatic?.let {
                if (it.board) if (it.markers && reference != null) 4 else 2
                else if (it.markers) if (reference != null) 4 else 3 else 2
            } ?: meshStyle
        if (effectiveStyle == 2) {
            measuredFace = true
            face.enabled = false
            return
        }
        val style = effectiveStyle
        val ownerStart = System.nanoTime() * 1e-9
        val owner = snapshotMeshOwner()
        val ownerEnd = System.nanoTime() * 1e-9
        val current = mesh
        var sceneMesh: SceneMesh? = null
        var workerStarted = 0.0
        var preparedAt = 0.0
        var sdkStarted = 0.0
        var sdkCompleted = 0.0
        val dispatched = System.nanoTime() * 1e-9
        // close() defers this resource's destruction until the noncancellable SDK call returns.
        uploadingResource = current
        uploadingStyle = style
        var created: MeshResource? = null
        var adopted = false
        try {
            withContext(Dispatchers.IO) {
                workerStarted = System.nanoTime() * 1e-9
                val data = prepareMesh(frame, style, reference, owner)
                sceneMesh = data
                preparedAt = System.nanoTime() * 1e-9
                currentCoroutineContext().ensureActive()
                sdkStarted = System.nanoTime() * 1e-9
                if (current == null) {
                    created =
                        MeshResource.createWithMeshModel(
                                data.prepared.model,
                                data.prepared.bounds,
                                "FaceLandmarkerDynamicMesh",
                            )
                            .apply { toGlobal() }
                } else {
                    check(current.replaceWithMeshModel(data.prepared.model, data.prepared.bounds)) {
                        "Stage mesh replacement was rejected"
                    }
                }
                sdkCompleted = System.nanoTime() * 1e-9
            }
            val resumed = System.nanoTime() * 1e-9
            currentCoroutineContext().ensureActive()
            if (closed) return
            val data = checkNotNull(sceneMesh)
            val vertices = data.prepared.model.positions
            val bounds = data.prepared.bounds
            val stageVertices = data.stageVertices
            uploadedHasNormals = data.prepared.model.normals != null
            created?.let { next ->
                val nextMaterial = createMaterial()
                material = nextMaterial
                face.components.set(ModelComponent(next, nextMaterial))
                mesh = next
                adopted = true
            }
            measuredFace = true
            applyStyle()
            if (reference != null) {
                val origin = face.convertPositionTo(Vector3(0f, 0f, 0f), null)
                val axes =
                    listOf(Vector3(1f, 0f, 0f), Vector3(0f, 1f, 0f), Vector3(0f, 0f, 1f)).map {
                        face.convertPositionTo(it, null) - origin
                    }
                val returned =
                    vertices.map { origin + axes[0] * it.x + axes[1] * it.y + axes[2] * it.z }
                val maxError =
                    returned.indices.maxOf { i ->
                        val p = returned[i]
                        sqrt(
                            (p.x - stageVertices[i * 3]) * (p.x - stageVertices[i * 3]) +
                                (p.y - stageVertices[i * 3 + 1]) *
                                    (p.y - stageVertices[i * 3 + 1]) +
                                (p.z - stageVertices[i * 3 + 2]) * (p.z - stageVertices[i * 3 + 2])
                        )
                    }
                val now = System.nanoTime() * 1e-9
                uploadedGeometry =
                    reference
                        .json(frame.automatic?.sideReferences == true)
                        .put("ownerRoundTripMaxMetres", maxError.toDouble())
                        .put(
                            "headToStageAtUpload",
                            poses.atCapture(now)?.let { JSONArray(it.toList()) } ?: JSONObject.NULL,
                        )
                        .put("uploadSeconds", now)
                        .put("cameraToService", JSONArray(frame.captureCameraPose.toList()))
                        .put("facePoseStage", JSONArray(frame.pose.toList()))
                check(maxError < .0001f) { "Reference mesh owner conversion disagrees with Stage" }
            }
            val ready = System.nanoTime() * 1e-9
            uploadTiming =
                JSONObject()
                    .put("schema", 1)
                    .put("frame", frame.sequence)
                    .put("captureSeconds", frame.captureSeconds)
                    .put("readbackSeconds", frame.readbackSeconds)
                    .put("publication", frame.presentationTiming ?: JSONObject.NULL)
                    .put("sceneReceivedSeconds", received)
                    .put("sceneAcquiredSeconds", acquired)
                    .put("ownerSnapshotStartSeconds", ownerStart)
                    .put("ownerSnapshotEndSeconds", ownerEnd)
                    .put("workerDispatchedSeconds", dispatched)
                    .put("workerStartedSeconds", workerStarted)
                    .put("preparedSeconds", preparedAt)
                    .put("sdkUploadStartSeconds", sdkStarted)
                    .put("sdkUploadEndSeconds", sdkCompleted)
                    .put("uiResumedSeconds", resumed)
                    .put("sceneReadySeconds", ready)
                    .put("coordinateSeconds", data.prepared.coordinateSeconds)
                    .put("normalSeconds", data.prepared.normalSeconds)
                    .put("boundsSeconds", data.prepared.boundsSeconds)
                    .put("normalsIncluded", uploadedHasNormals)
                    .put("preparedStyle", style)
                    .put("appliedStyle", effectiveStyle)
                    .put("vertexCount", vertices.size)
                    .put("triangleCount", data.prepared.model.triangleIndices.size / 3)
                    .put("operation", if (current == null) "create" else "replace")
                    .put("boundary", "SDK call return; not compositor presentation")
            if (!appliedFirstFrame) {
                appliedFirstFrame = true
                Log.i(
                    FaceLandmarkerRunner.TAG,
                    "first_mesh_ready seq=${frame.sequence} vertices=${vertices.size} triangles=${triangles.size / 3} stage_position=(${bounds.center.x},${bounds.center.y},${bounds.center.z})",
                )
            }
        } finally {
            uploadingResource = null
            uploadingStyle = null
            if (closed) current?.close()
            if (!adopted) created?.close()
        }
    }

    private data class SceneMesh(
        val stageVertices: FloatArray,
        val prepared: FaceMeshPreparation.Prepared,
    )

    private fun prepareMesh(
        frame: FaceFrame,
        style: Int,
        reference: LabRegistrationEvidence?,
        owner: FloatArray,
    ): SceneMesh {
        val board = frame.automatic?.board == true
        val referenceMesh =
            reference?.let {
                LabProjectionReference.mesh(frame.sequence, frame.automatic?.sideReferences == true)
            }
        val faceVertices =
            if (board) FloatArray(0)
            else if (style >= 3) LabAutoCapture.markerVertices(frame.vertices) else frame.vertices
        val indices =
            if (referenceMesh != null)
                (if (board) emptyList() else LabAutoCapture.markerTriangles) +
                    referenceMesh.triangles.map { it + faceVertices.size / 3 }
            else if (style == 3) LabAutoCapture.markerTriangles else triangles
        val stageVertices =
            if (referenceMesh != null)
                faceVertices +
                    StageRegistration.transformVertices(
                        checkNotNull(reference).headToStage,
                        referenceMesh.positions,
                    )
            else faceVertices
        val uv =
            referenceMesh?.let {
                List(faceVertices.size / 3) {
                    Vector2(
                        LabProjectionReference.FACE_MARKER_U,
                        LabProjectionReference.FACE_MARKER_V,
                    )
                } + List(it.uv.size / 2) { i -> Vector2(it.uv[2 * i], it.uv[2 * i + 1]) }
            }
        val prepared = preparation.prepare(stageVertices, owner, indices, style == 1, uv)
        return SceneMesh(stageVertices, prepared)
    }

    fun setMeshStyle(style: Int) {
        require(style in 0..2)
        if (meshStyle == style) return
        meshStyle = style
        effectiveStyle = style
        applyStyle()
    }

    private fun applyStyle() {
        val current = mesh ?: return
        val solid = material ?: return
        // A wireframe upload has no normals. Wait for a solid upload before enabling lighting.
        face.enabled =
            measuredFace &&
                effectiveStyle != 2 &&
                (effectiveStyle != 1 ||
                    (uploadedHasNormals && (uploadingStyle == null || uploadingStyle == 1)))
        if (appliedStyle == effectiveStyle) return
        appliedStyle = effectiveStyle
        if (effectiveStyle == 4) {
            val reference =
                referenceMaterial
                    ?: run {
                        val bitmap =
                            Bitmap.createBitmap(
                                LabProjectionReference.atlas(),
                                LabProjectionReference.ATLAS_SIZE,
                                LabProjectionReference.ATLAS_SIZE,
                                Bitmap.Config.ARGB_8888,
                            )
                        val texture =
                            try {
                                TextureResource.create(bitmap).apply { toGlobal() }
                            } finally {
                                bitmap.recycle()
                            }
                        referenceTexture = texture
                        UnlitMaterial.create()
                            .apply {
                                setBaseColor(Color4(1f, 1f, 1f, 1f))
                                setBaseColorTexture(texture)
                                setCullingMode(MaterialCullingMode.NONE)
                                toGlobal()
                            }
                            .also { referenceMaterial = it }
                    }
            face.components.set(ModelComponent(current, reference))
        } else if (effectiveStyle == 3) {
            val markers =
                markerMaterial
                    ?: UnlitMaterial.create()
                        .apply {
                            setBaseColor(Color4(0f, 1f, 0f, 1f))
                            setCullingMode(MaterialCullingMode.NONE)
                            toGlobal()
                        }
                        .also { markerMaterial = it }
            face.components.set(ModelComponent(current, markers))
        } else if (effectiveStyle == 0) {
            val wire =
                wireMaterial
                    ?: UnlitMaterial.create()
                        .apply {
                            setBaseColor(Color4(0f, 1f, 0f, 1f))
                            setCullingMode(MaterialCullingMode.NONE)
                            setPolygonFillMode(PolygonFillMode.LINE)
                            toGlobal()
                        }
                        .also { wireMaterial = it }
            face.components.set(ModelComponent(current, wire))
        } else face.components.set(ModelComponent(current, solid))
        face.enabled =
            measuredFace &&
                effectiveStyle != 2 &&
                (effectiveStyle != 1 ||
                    (uploadedHasNormals && (uploadingStyle == null || uploadingStyle == 1)))
    }

    private fun createMaterial(): PhysicallyBasedMaterial =
        PhysicallyBasedMaterial.create().apply {
            setBaseColor(Color4(.12f, .75f, .85f, 1f))
            setRoughness(.7f)
            setMetallic(0f)
            setCullingMode(MaterialCullingMode.NONE)
            toGlobal()
        }

    private fun createLight(
        name: String,
        yaw: Float,
        pitch: Float,
        lux: Float,
        color: Color4,
    ): Entity =
        Entity().apply {
            setName(name)
            components.get<TransformComponent>()?.quaternion =
                Quat(Vector3(0f, 1f, 0f), yaw) * Quat(Vector3(1f, 0f, 0f), pitch)
            components.set(DirectionalLightComponent(color, lux, false))
        }

    private fun snapshotMeshOwner(): FloatArray {
        // Entity access stays on the UI thread. Do not cache across frames without a verified
        // parent/Stage/recenter invalidation signal; only the copied numeric basis crosses threads.
        val origin = face.convertPositionFrom(Vector3(0f, 0f, 0f), null)
        val x = face.convertPositionFrom(Vector3(1f, 0f, 0f), null) - origin
        val y = face.convertPositionFrom(Vector3(0f, 1f, 0f), null) - origin
        val z = face.convertPositionFrom(Vector3(0f, 0f, 1f), null) - origin
        return floatArrayOf(
            origin.x,
            origin.y,
            origin.z,
            x.x,
            x.y,
            x.z,
            y.x,
            y.y,
            y.z,
            z.x,
            z.y,
            z.z,
        )
    }

    override fun close() {
        if (closed) return
        closed = true
        poses.close()
        // Attachment panels belong to SpatialView; detach before destroying the app-owned anchor.
        controlPanel?.removeFromParent()
        controlPanel = null
        controls.destroy(true)
        face.destroy(true)
        mesh?.takeUnless { it === uploadingResource }?.close()
        material?.close()
        wireMaterial?.close()
        markerMaterial?.close()
        referenceMaterial?.close()
        referenceTexture?.close()
        referenceMaterial = null
        referenceTexture = null
        markerMaterial = null
        wireMaterial = null
        mesh = null
        material = null
    }
}
