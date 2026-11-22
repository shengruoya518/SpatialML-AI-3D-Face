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
import com.pico.spatial.core.math.Quat
import com.pico.spatial.core.math.Vector3
import kotlin.math.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import org.json.JSONObject

/** Retained dragon mesh assembly. Only the lower jaw and mouth-local flames animate. */
internal class FaceDragonScene(private val names: List<String>) : AutoCloseable {
    private val root =
        Entity().apply {
            setName("chinese-dragon-head")
            enabled = false
        }
    private val jaw =
        Entity().apply {
            setName("DragonJawHinge")
            root.addChild(this)
            checkNotNull(components.get<TransformComponent>()).position = Vector3(0f, -.037f, .037f)
        }
    private val fire =
        Entity().apply {
            setName("DragonFireSocket")
            enabled = false
            root.addChild(this)
            checkNotNull(components.get<TransformComponent>()).position = Vector3(0f, -.043f, .20f)
        }
    private val meshes = mutableListOf<MeshResource>()
    private val materials = mutableListOf<PhysicallyBasedMaterial>()
    private val fireMaterials = mutableListOf<UnlitMaterial>()
    private val flames = mutableListOf<Entity>()
    private val gate = FaceDragonFireGate()
    private var jawTarget = 0f
    private var jawAngle = 0f
    private var lastTime = 0L
    private var closed = false

    suspend fun initialize(parent: Entity, ordering: FaceRenderOrder) {
        parent.addChild(root)
        val preparation = FaceMeshPreparation()
        val definitions = FaceDragonGeometry.parts()
        val created = mutableListOf<MeshResource>()
        var adopted = false
        try {
            withContext(Dispatchers.IO) {
                for (definition in definitions + FaceDragonGeometry.flame()) {
                    val data =
                        preparation.prepare(
                            definition.vertices,
                            IDENTITY,
                            definition.indices,
                            needsNormals = true,
                        )
                    created.add(
                        MeshResource.createWithMeshModel(data.model, data.bounds, definition.name)
                            .apply { toGlobal() }
                    )
                }
            }
            currentCoroutineContext().ensureActive()
            check(!closed)
            meshes.addAll(created)
            adopted = true
        } finally {
            if (!adopted) created.forEach { it.close() }
        }
        for ((index, definition) in definitions.withIndex()) {
            val c = definition.color
            val material =
                PhysicallyBasedMaterial.create()
                    .apply {
                        setBlendingMode(BlendingMode.TRANSPARENT)
                        toGlobal()
                        setBaseColor(Color4(c[0], c[1], c[2], c[3]))
                        setOpacity(1f)
                        setRoughness(
                            if (
                                definition.name.contains("gold") ||
                                    definition.name.contains("antler")
                            )
                                .35f
                            else .62f
                        )
                        setMetallic(if (definition.name.contains("antler")) .65f else 0f)
                        setDepthTest(true)
                        setDepthWrite(true)
                        setCullingMode(MaterialCullingMode.NONE)
                    }
                    .also { materials.add(it) }
            val entity =
                Entity().apply {
                    setName(definition.name)
                    components.set(ModelComponent(meshes[index], material))
                    ordering.model(this)
                }
            (if (definition.jaw) jaw else root).addChild(entity)
        }
        for (layer in 0..1) {
            val material =
                UnlitMaterial.create(BlendingMode.TRANSPARENT)
                    .apply {
                        toGlobal()
                        setBaseColor(
                            if (layer == 0) Color4(1f, .19f, .015f, .48f)
                            else Color4(1f, .88f, .12f, .78f)
                        )
                        setOpacity(if (layer == 0) .65f else .9f)
                        setDepthTest(true)
                        setDepthWrite(false)
                        setCullingMode(MaterialCullingMode.NONE)
                        setApplyToneMapping(false)
                    }
                    .also { fireMaterials.add(it) }
            for (tongue in 0..2) {
                val entity =
                    Entity().apply {
                        setName("dragon-fire-$layer-$tongue")
                        components.set(ModelComponent(meshes.last(), material))
                    }
                fire.addChild(entity)
                flames.add(entity)
            }
        }
    }

    fun select(selected: Boolean) {
        root.enabled = selected && !closed
        if (!selected) {
            hideFire()
            lastTime = 0L
        }
    }

    fun update(face: TrackedFace) {
        if (closed || !root.enabled) return
        val jawIndex = names.indexOf("jawOpen")
        val amount =
            face.expressions.getOrNull(jawIndex)?.takeIf { it.isFinite() }?.coerceIn(0f, 1f) ?: 0f
        jawTarget = .85f * amount.pow(.75f)
        gate.update(
            amount,
            face.frame.tongueConfidence,
            face.frame.captureSeconds,
            checkNotNull(face.frame.readbackSeconds),
            face.generation,
        )
    }

    fun animate(frameTimeNanos: Long) {
        if (closed || !root.enabled) return
        val dt =
            if (lastTime == 0L) 1.0 / 60
            else ((frameTimeNanos - lastTime) * 1e-9).coerceIn(0.0, .06)
        lastTime = frameTimeNanos
        jawAngle += ((jawTarget - jawAngle) * (1 - exp(-18 * dt))).toFloat()
        checkNotNull(jaw.components.get<TransformComponent>()).quaternion =
            Quat(Vector3(1f, 0f, 0f), jawAngle)
        val burning = gate.burning(System.nanoTime() * 1e-9)
        if (fire.enabled != burning) fire.enabled = burning
        if (!burning) return
        val t = (frameTimeNanos * 1e-9).toFloat()
        for ((index, entity) in flames.withIndex()) {
            val layer = index / 3
            val tongue = index % 3
            val transform = checkNotNull(entity.components.get<TransformComponent>())
            val pulse = 1f + .13f * sin(t * 19 + index * 1.7f)
            val radius = if (layer == 0) .52f else .28f
            transform.scaleVector =
                Vector3(
                    radius * pulse,
                    radius * pulse,
                    (.5f + .13f * sin(t * 13 + index)) * if (layer == 0) 1f else .78f,
                )
            transform.position = Vector3((tongue - 1) * .018f, .012f * sin(t * 17 + index), 0f)
            transform.quaternion =
                Quat(Vector3(0f, 1f, 0f), (tongue - 1) * .12f + .035f * sin(t * 11 + index))
        }
    }

    fun hideFire() {
        gate.reset()
        fire.enabled = false
        jawTarget = 0f
    }

    fun evidence(): JSONObject =
        JSONObject()
            .put("jawAngleDegrees", jawAngle * 180 / PI)
            .put("jawTargetDegrees", jawTarget * 180 / PI)
            .put("fireVisible", root.enabled && fire.enabled)

    override fun close() {
        if (closed) return
        closed = true
        root.destroy(true)
        meshes.forEach { it.close() }
        materials.forEach { it.close() }
        fireMaterials.forEach { it.close() }
        meshes.clear()
        materials.clear()
        fireMaterials.clear()
        flames.clear()
    }

    companion object {
        private val IDENTITY = floatArrayOf(0f, 0f, 0f, 1f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 1f)
    }
}
