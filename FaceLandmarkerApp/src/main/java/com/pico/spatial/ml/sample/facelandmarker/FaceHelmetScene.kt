// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.util.Log
import com.pico.spatial.core.container.SpatialViewContent
import com.pico.spatial.core.ecs.AnchorComponent
import com.pico.spatial.core.ecs.AnchorEntity
import com.pico.spatial.core.ecs.DirectionalLightComponent
import com.pico.spatial.core.ecs.Entity
import com.pico.spatial.core.ecs.TransformComponent
import com.pico.spatial.core.ecs.anchor.AnchorTarget
import com.pico.spatial.core.math.Color4
import com.pico.spatial.core.math.Quat
import com.pico.spatial.core.math.Transform
import com.pico.spatial.core.math.Vector3
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import org.json.JSONArray
import org.json.JSONObject

/** One retained model with independent owners for tracked head pose, fitting and visor motion. */
internal class FaceHelmetScene(geometry: FaceGeometry) : AutoCloseable {
    private val owner = Entity().apply { setName("helmet-placement-owner") }
    private val head =
        Entity().apply {
            setName("tracked-face-pose")
            enabled = false
        }
    private val fitting = Entity().apply { setName("helmet-face-local-fit") }
    private val occlusion = FaceOcclusionScene(geometry)
    private val augmentation = FaceAugmentationScene(geometry)
    private var surfaceGeneration = -1L
    private var surfaceSequence = -1
    private var renderedSequence = -1
    private var renderedGeneration = -1L
    private var selected = FaceEffect.MESH
    private var appliedEffect: FaceEffect? = null
    private val controls = AnchorEntity(AnchorTarget.createCameraTarget())
    private var panel: Entity? = null
    private var asset: Entity? = null
    private var faceplate: TransformComponent? = null
    private var closedFaceplateRotation: Quat? = null
    private var animationStartedNanos: Long? = null
    private var animationElapsedSeconds = 0.0
    private var faceplateAngleRadians = 0f
    private var loggedAnimationPhase = -1L
    private var lastReadback = Double.NEGATIVE_INFINITY
    private var visibilityRevision = 0L
    private var closed = false
    private var applied = 0
    private var appliedFitScale = Float.NaN
    var fitScale = 1f
    val visible
        get() = !closed && head.enabled

    suspend fun initialize(content: SpatialViewContent, attachment: Entity?) {
        content.addEntity(owner)
        owner.addChild(head)
        head.addChild(fitting)
        controls.components.get<AnchorComponent>()?.positionOffset = Vector3(0f, -.28f, -1f)
        panel = attachment
        attachment?.let { controls.addChild(it) }
        controls.addChild(light("helmet-key", .55f, -.35f, 1500f, Color4(1f, .95f, .9f, 1f)))
        controls.addChild(light("helmet-fill", -.8f, .1f, 350f, Color4(.8f, .9f, 1f, 1f)))
        content.addEntity(controls)
        var loaded: Entity? = null
        try {
            loaded = Entity.loadSuspend("asset://helmet/sentinel-helmet.glb")
            currentCoroutineContext().ensureActive()
            check(!closed)
            fitting.addChild(loaded)
            // Preserve the GLB's intrinsic 0.125 scale and physical head cavity. Its wide crest
            // must not be fitted to the previous helmet's 24 cm outer width.
            val bounds = loaded.getVisualBounds(fitting, recursive = true, enabledOnly = false)
            check(!bounds.isEmpty() && matchesSentinelSize(bounds.size, 1f)) {
                "Sentinel physical bounds disagree with the supplied model: ${bounds.size}"
            }
            val model = checkNotNull(loaded.findEntity("SentinelHelmet"))
            val hinge = checkNotNull(model.findEntity("FaceplateHinge"))
            check(hinge.getParent()?.id == model.id) { "Sentinel hinge hierarchy changed" }
            faceplate = checkNotNull(hinge.components.get<TransformComponent>())
            closedFaceplateRotation = checkNotNull(faceplate).quaternion
            applyFit()
            val fitted = loaded.getVisualBounds(head, recursive = true, enabledOnly = false)
            check(!fitted.isEmpty() && matchesSentinelSize(fitted.size, fitScale)) {
                "Sentinel fit bounds disagree"
            }
            occlusion.initialize(head, loaded)
            augmentation.initialize(head, occlusion.ordering)
            asset = loaded
            Log.i(
                FaceLandmarkerRunner.TAG,
                "helmet_loaded asset=sentinel-helmet.glb source_size=${bounds.size} fitted_size=${fitted.size} head_center=(0,0.26875,0.00625) forward=+Z hinge=FaceplateHinge face_occlusion=true",
            )
        } finally {
            if (asset !== loaded) loaded?.destroy(true)
        }
    }

    suspend fun setOcclusionProbe(mode: String) {
        occlusion.setProbe(mode, controls)
    }

    fun select(effect: FaceEffect) {
        selected = effect
        augmentation.select(effect)
    }

    /** Uploads only surface shape. This coroutine never owns the head transform or visibility. */
    suspend fun updateSurface(face: TrackedFace): JSONObject {
        val revision = visibilityRevision
        check(!closed && asset != null)
        val timing = occlusion.update(face.frame, face.localVertices)
        currentCoroutineContext().ensureActive()
        if (closed || revision != visibilityRevision) return timing.put("discarded", true)
        surfaceGeneration = face.generation
        surfaceSequence = face.frame.sequence
        return timing.put("generation", face.generation)
    }

    /** Called on the display frame clock, even between inference completions and during uploads. */
    fun render(face: TrackedFace?, frameTimeNanos: Long): JSONObject? {
        if (closed) return null
        if (selected == FaceEffect.HELMET) animateFaceplate(frameTimeNanos)
        if (
            face == null ||
                System.nanoTime() * 1e-9 - checkNotNull(face.frame.readbackSeconds) !in
                    0.0..FaceTrackingState.HOLD_SECONDS
        ) {
            if (visible || surfaceGeneration != -1L) hide()
            return null
        }
        val frame = face.frame
        val started = System.nanoTime() * 1e-9
        // The first appearance/new identity needs its own measured depth surface. A shape update
        // on this same track retains the previous local surface beneath the latest rigid pose.
        if (surfaceGeneration != face.generation) {
            head.enabled = false
            return null
        }
        val changed =
            renderedSequence != frame.sequence ||
                renderedGeneration != face.generation ||
                appliedFitScale != fitScale ||
                appliedEffect != selected
        if (changed) {
            val pose = FaceHelmetPose.decompose(frame.pose)
            val q = pose.quaternion
            val stage =
                Transform(
                    Vector3(pose.position[0], pose.position[1], pose.position[2]),
                    Quat(q[0], q[1], q[2], q[3]),
                    Vector3(pose.scale, pose.scale, pose.scale),
                )
            val local = owner.convertTransformFrom(stage, null)
            val transform = checkNotNull(head.components.get<TransformComponent>())
            transform.position = local.position
            transform.quaternion = local.quaternion
            transform.scaleVector = local.scale
            applyFit()
            if (appliedEffect != selected) {
                occlusion.setEffect(selected)
                fitting.enabled = selected == FaceEffect.HELMET
                appliedEffect = selected
            }
            augmentation.render(face, fitScale)
            renderedSequence = frame.sequence
            renderedGeneration = face.generation
            lastReadback = checkNotNull(frame.readbackSeconds)
            head.enabled = true
            val done = System.nanoTime() * 1e-9
            augmentation.animate(frameTimeNanos)
            applied++
            if (applied == 1 || applied % 120 == 0)
                Log.i(
                    FaceLandmarkerRunner.TAG,
                    "face_effect_pose_applied frame=${frame.sequence} effect=$selected generation=${face.generation}",
                )
            return JSONObject()
                .put("frame", frame.sequence)
                .put("visible", true)
                .put("effect", selected.name)
                .put("generation", face.generation)
                .put("surfaceGeneration", surfaceGeneration)
                .put("captureSeconds", frame.captureSeconds)
                .put("readbackSeconds", frame.readbackSeconds)
                .put("appliedSeconds", done)
                .put("readbackToPoseApplyMs", (done - lastReadback) * 1000)
                .put("poseApplyMs", (done - started) * 1000)
                .put("poseBeforeOcclusion", surfaceSequence < frame.sequence)
                .put("surfaceFrame", surfaceSequence)
                .put("presentationTiming", frame.presentationTiming ?: JSONObject.NULL)
                .put("stagePose", JSONArray(frame.pose))
                .put("parentTransform", JSONArray(local.toFloatArray()))
                .put("fitScale", fitScale)
                .put(
                    "asset",
                    if (selected == FaceEffect.HELMET) "sentinel-helmet.glb" else selected.name,
                )
                .put("faceplateAngleDegrees", faceplateAngleRadians * 180 / kotlin.math.PI)
                .put("faceplateElapsedSeconds", animationElapsedSeconds)
                .put("outputMask", frame.outputs.mask)
                .put("meshVertices", face.localVertices.size / 3)
                .put("blendshapes", face.expressions.size)
                .put("tongueAppearanceConfidence", frame.tongueConfidence ?: JSONObject.NULL)
                .put(
                    "dragon",
                    if (selected == FaceEffect.DRAGON) augmentation.dragonEvidence()
                    else JSONObject.NULL,
                )
                .put("stabilization", frame.presentationStabilization ?: JSONObject.NULL)
                .put("boundary", "entity transform setters returned; not screen presentation")
        }
        head.enabled = true
        // Jaw and flames continue on display frames while acquisition runs independently.
        augmentation.animate(frameTimeNanos)
        return null
    }

    fun hide() {
        if (!closed) {
            augmentation.hide()
            visibilityRevision++
            head.enabled = false
            surfaceGeneration = -1L
            surfaceSequence = -1
            renderedSequence = -1
            renderedGeneration = -1L
        }
    }

    // Called on the Compose frame clock/main thread. Absolute time avoids accumulated delay
    // and never replaces the tracked root pose, hinge translation or shell transform.
    fun animateFaceplate(frameTimeNanos: Long) {
        if (closed) return
        val transform = faceplate ?: return
        val started = animationStartedNanos ?: frameTimeNanos.also { animationStartedNanos = it }
        animationElapsedSeconds = (frameTimeNanos - started) * 1e-9
        faceplateAngleRadians = FaceHelmetMotion.angleRadians(animationElapsedSeconds)
        transform.quaternion =
            checkNotNull(closedFaceplateRotation) * Quat(Vector3(1f, 0f, 0f), faceplateAngleRadians)
        val phase = (animationElapsedSeconds / FaceHelmetMotion.PHASE_SECONDS).toLong()
        if (phase != loggedAnimationPhase) {
            loggedAnimationPhase = phase
            Log.i(
                FaceLandmarkerRunner.TAG,
                "helmet_faceplate_phase phase=$phase target=${if (phase % 2 == 0L) "closed" else "open"} elapsed=$animationElapsedSeconds",
            )
        }
    }

    private fun applyFit() {
        if (appliedFitScale == fitScale) return
        val transform = checkNotNull(fitting.components.get<TransformComponent>())
        val scale = fitScale
        transform.scaleVector = Vector3(scale, scale, scale)
        // extras.arAttachment.headCenterGltfMeters is expressed after the intrinsic GLB scale.
        // Align that reference head center to the canonical face-pose origin, scaling the offset
        // with the model so the fit slider always scales around the head rather than its feet.
        transform.position = Vector3(0f, -.26875f * scale, -.00625f * scale)
        appliedFitScale = fitScale
    }

    private fun matchesSentinelSize(size: Vector3, scale: Float): Boolean =
        kotlin.math.abs(size.x - .40050924f * scale) < .005f &&
            kotlin.math.abs(size.y - .41965294f * scale) < .005f &&
            kotlin.math.abs(size.z - .32719553f * scale) < .005f

    private fun light(name: String, yaw: Float, pitch: Float, lux: Float, color: Color4) =
        Entity().apply {
            setName(name)
            checkNotNull(components.get<TransformComponent>()).quaternion =
                Quat(Vector3(0f, 1f, 0f), yaw) * Quat(Vector3(1f, 0f, 0f), pitch)
            components.set(DirectionalLightComponent(color, lux, false))
        }

    override fun close() {
        if (closed) return
        closed = true
        augmentation.close()
        occlusion.close()
        panel?.removeFromParent()
        panel = null
        controls.destroy(true)
        owner.destroy(true)
        asset = null
        faceplate = null
        closedFaceplateRotation = null
    }

    companion object {
        const val MAX_POSE_AGE_SECONDS = FaceTrackingState.HOLD_SECONDS
    }
}
