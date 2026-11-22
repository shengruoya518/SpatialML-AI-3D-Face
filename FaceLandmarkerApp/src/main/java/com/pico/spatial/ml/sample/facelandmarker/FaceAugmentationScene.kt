// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import com.pico.spatial.core.ecs.Entity
import com.pico.spatial.core.ecs.ModelComponent
import com.pico.spatial.core.ecs.TransformComponent
import com.pico.spatial.core.ecs.resource.BlendingMode
import com.pico.spatial.core.ecs.resource.MaterialCullingMode
import com.pico.spatial.core.ecs.resource.MeshResource
import com.pico.spatial.core.ecs.resource.PhysicallyBasedMaterial
import com.pico.spatial.core.ecs.resource.UnlitMaterial
import com.pico.spatial.core.math.Color4
import com.pico.spatial.core.math.Vector3
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext

/** Scene-lifetime geometry; head pose, expression animation and uploads have separate owners. */
internal class FaceAugmentationScene(private val geometry: FaceGeometry) : AutoCloseable {
    private val root = Entity().apply { setName("face-effect-fit") }
    private val hatMount =
        Entity().apply {
            setName("crown-hat-mount")
            root.addChild(this)
        }
    private val hairMount =
        Entity().apply {
            setName("crown-hair-mount")
            root.addChild(this)
        }

    private data class Part(
        val effect: FaceEffect,
        val entity: Entity,
        val position: Vector3,
        val scale: Vector3,
        val eye: Int = -1,
        val pupil: Boolean = false,
    )

    private val parts = mutableListOf<Part>()
    private val materials = mutableListOf<UnlitMaterial>()
    private var sphere: MeshResource? = null
    private val capMeshes = mutableListOf<MeshResource>()
    private val capMaterials = mutableListOf<PhysicallyBasedMaterial>()
    private val closedHelmet = FaceClosedHelmetScene()
    private val dragon = FaceDragonScene(geometry.blendshapeNames)
    private val maskGeometry = FaceMaskGeometry(geometry.canonical, geometry.blendshapeNames)
    private var closed = false
    private var selected = FaceEffect.MESH
    private var appliedSelection: FaceEffect? = null
    private var appliedFit = Float.NaN
    private val preparation = FaceMeshPreparation()

    suspend fun initialize(head: Entity, order: FaceRenderOrder) {
        head.addChild(root)
        val positions = FloatArray(17 * 25 * 3)
        val triangles = mutableListOf<Int>()
        for (y in 0..16) for (x in 0..24) {
            val latitude = PI * y / 16
            val longitude = 2 * PI * x / 24
            val j = (y * 25 + x) * 3
            positions[j] = (sin(latitude) * cos(longitude)).toFloat()
            positions[j + 1] = cos(latitude).toFloat()
            positions[j + 2] = (sin(latitude) * sin(longitude)).toFloat()
            if (y < 16 && x < 24) {
                val a = y * 25 + x
                triangles.addAll(listOf(a, a + 1, a + 25, a + 1, a + 26, a + 25))
            }
        }
        var createdSphere: MeshResource? = null
        val capDefinitions = FaceBaseballCapGeometry.parts()
        val createdCaps = mutableListOf<MeshResource>()
        var adopted = false
        try {
            withContext(Dispatchers.IO) {
                val data = preparation.prepare(positions, IDENTITY, triangles, false)
                createdSphere =
                    MeshResource.createWithMeshModel(data.model, data.bounds, "FaceEffectSphere")
                        .apply { toGlobal() }
                for (definition in capDefinitions) {
                    val data =
                        preparation.prepare(
                            definition.vertices,
                            IDENTITY,
                            definition.indices,
                            needsNormals = true,
                        )
                    createdCaps.add(
                        MeshResource.createWithMeshModel(data.model, data.bounds, definition.name)
                            .apply { toGlobal() }
                    )
                }
            }
            currentCoroutineContext().ensureActive()
            check(!closed)
            sphere = checkNotNull(createdSphere)
            capMeshes.addAll(createdCaps)
            adopted = true
        } finally {
            if (!adopted) {
                createdSphere?.close()
                createdCaps.forEach { it.close() }
            }
        }
        fun material(color: Color4) =
            UnlitMaterial.create(BlendingMode.TRANSPARENT)
                .apply {
                    toGlobal()
                    setBaseColor(color)
                    setCullingMode(MaterialCullingMode.NONE)
                    setDepthTest(true)
                    setDepthWrite(true)
                    setOpacity(1f)
                }
                .also { materials.add(it) }
        val white = material(Color4(1f, .98f, .94f, 1f))
        val black = material(Color4(.025f, .015f, .04f, 1f))
        val blue = material(Color4(.08f, .22f, .78f, 1f))
        val red = material(Color4(.8f, .09f, .025f, 1f))
        fun part(
            effect: FaceEffect,
            name: String,
            position: Vector3,
            scale: Vector3,
            appearance: UnlitMaterial,
            eye: Int = -1,
            pupil: Boolean = false,
        ) {
            val entity =
                Entity().apply {
                    setName(name)
                    components.set(ModelComponent(checkNotNull(sphere), appearance))
                    order.model(this)
                    if (eye < 0) {
                        val transform = checkNotNull(components.get<TransformComponent>())
                        transform.position = position
                        transform.scaleVector = scale
                    }
                    enabled = false
                }
            when (effect) {
                FaceEffect.HAT -> hatMount.addChild(entity)
                FaceEffect.PIGTAILS -> hairMount.addChild(entity)
                else -> root.addChild(entity)
            }
            parts.add(Part(effect, entity, position, scale, eye, pupil))
        }
        for (eye in 0..1) {
            part(
                FaceEffect.EYES,
                "bug-eye-$eye",
                Vector3(0f, 0f, .018f),
                Vector3(.027f, .027f, .022f),
                white,
                eye,
            )
            part(
                FaceEffect.EYES,
                "bug-pupil-$eye",
                Vector3(0f, 0f, .038f),
                Vector3(.012f, .014f, .006f),
                black,
                eye,
                true,
            )
        }
        part(
            FaceEffect.PIGTAILS,
            "red-hair-cap",
            Vector3(0f, .065f, -.016f),
            Vector3(.09f, .045f, .075f),
            red,
        )
        for (side in listOf(-1, 1)) {
            for (i in 0..4) part(
                FaceEffect.PIGTAILS,
                "pigtail-$side-$i",
                Vector3(side * (.09f + .006f * sin(i.toFloat())), .055f - i * .023f, -.02f),
                Vector3(.025f, .027f, .027f),
                red,
            )
            for (lobe in listOf(-1, 1)) part(
                FaceEffect.PIGTAILS,
                "bow-$side-$lobe",
                Vector3(side * .093f + lobe * .013f, .05f, .011f),
                Vector3(.018f, .01f, .008f),
                blue,
            )
        }
        for ((index, definition) in capDefinitions.withIndex()) {
            val c = definition.color
            val appearance =
                PhysicallyBasedMaterial.create()
                    .apply {
                        toGlobal()
                        setBlendingMode(BlendingMode.TRANSPARENT)
                        setBaseColor(Color4(c[0], c[1], c[2], 1f))
                        setOpacity(1f)
                        setRoughness(.85f)
                        setMetallic(0f)
                        setDepthTest(true)
                        setDepthWrite(true)
                        setCullingMode(MaterialCullingMode.NONE)
                    }
                    .also { capMaterials.add(it) }
            val entity =
                Entity().apply {
                    setName(definition.name)
                    components.set(ModelComponent(capMeshes[index], appearance))
                    order.model(this)
                }
            hatMount.addChild(entity)
        }
        closedHelmet.initialize(root, order)
        dragon.initialize(root, order)
    }

    fun select(effect: FaceEffect) {
        selected = effect
    }

    fun render(face: TrackedFace, fit: Float) {
        if (closed) return
        if (selected == FaceEffect.HAT || selected == FaceEffect.PIGTAILS) {
            val anchors = FaceHeadPlacement.anchors(face.localVertices)
            if (selected == FaceEffect.HAT) {
                checkNotNull(hatMount.components.get<TransformComponent>()).position =
                    Vector3(anchors.centerX, anchors.crownY - .055f, anchors.centerZ)
            } else {
                checkNotNull(hairMount.components.get<TransformComponent>()).position =
                    Vector3(anchors.centerX, anchors.crownY - .110f, anchors.centerZ)
            }
        }
        if (appliedFit != fit) {
            checkNotNull(root.components.get<TransformComponent>()).scaleVector =
                Vector3(fit, fit, fit)
            appliedFit = fit
        }
        if (appliedSelection != selected) {
            for (part in parts) {
                val enabled = part.effect == selected
                if (part.entity.enabled != enabled) part.entity.enabled = enabled
            }
            hatMount.enabled = selected == FaceEffect.HAT
            hairMount.enabled = selected == FaceEffect.PIGTAILS
            closedHelmet.select(selected == FaceEffect.CLOSED_HELMET)
            dragon.select(selected == FaceEffect.DRAGON)
            appliedSelection = selected
        }
        for (part in parts) {
            if (part.effect != selected || part.eye < 0) continue
            val transform = checkNotNull(part.entity.components.get<TransformComponent>())
            run {
                val vertices = face.localVertices
                val a = if (part.eye == 0) 33 else 263
                val b = if (part.eye == 0) 133 else 362
                val side = if (part.eye == 0) "Right" else "Left"
                val blink = maskGeometry.coefficient(face.expressions, "eyeBlink$side")
                val wide = maskGeometry.coefficient(face.expressions, "eyeWide$side")
                val lookX =
                    maskGeometry.coefficient(face.expressions, "eyeLookOut$side") -
                        maskGeometry.coefficient(face.expressions, "eyeLookIn$side")
                val lookY =
                    maskGeometry.coefficient(face.expressions, "eyeLookUp$side") -
                        maskGeometry.coefficient(face.expressions, "eyeLookDown$side")
                val opening = (1f - .92f * blink + .2f * wide).coerceIn(.08f, 1.2f)
                transform.position =
                    Vector3(
                        (vertices[a * 3] + vertices[b * 3]) * .5f +
                            if (part.pupil) lookX * .009f * (if (part.eye == 0) -1 else 1) else 0f,
                        (vertices[a * 3 + 1] + vertices[b * 3 + 1]) * .5f +
                            if (part.pupil) lookY * .008f else 0f,
                        (vertices[a * 3 + 2] + vertices[b * 3 + 2]) * .5f + part.position.z,
                    )
                transform.scaleVector = Vector3(part.scale.x, part.scale.y * opening, part.scale.z)
            }
        }
        if (selected == FaceEffect.DRAGON) dragon.update(face)
    }

    fun animate(frameTimeNanos: Long) {
        if (selected == FaceEffect.DRAGON) dragon.animate(frameTimeNanos)
    }

    fun hide() {
        dragon.hideFire()
    }

    fun dragonEvidence() = dragon.evidence()

    override fun close() {
        if (closed) return
        closed = true
        dragon.close()
        closedHelmet.close()
        root.destroy(true)
        sphere?.close()
        capMeshes.forEach { it.close() }
        capMaterials.forEach { it.close() }
        capMeshes.clear()
        capMaterials.clear()
        materials.forEach { it.close() }
        materials.clear()
        parts.clear()
    }

    companion object {
        private val IDENTITY = floatArrayOf(0f, 0f, 0f, 1f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 1f)
    }
}
