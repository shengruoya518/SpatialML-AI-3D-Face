// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import kotlin.math.*

internal data class FaceEffectMesh(
    val name: String,
    val color: FloatArray,
    val vertices: FloatArray,
    val indices: List<Int>,
    val jaw: Boolean = false,
)

/** Pure geometry in face-local metres. Rendering resources are allocated by the scene owner. */
internal class FaceGeometryBuilder {
    private val positions = mutableListOf<Float>()
    private val indices = mutableListOf<Int>()

    private fun vertex(x: Float, y: Float, z: Float): Int {
        val index = positions.size / 3
        positions.add(x)
        positions.add(y)
        positions.add(z)
        return index
    }

    private fun triangle(a: Int, b: Int, c: Int) {
        indices.add(a)
        indices.add(b)
        indices.add(c)
    }

    fun ellipsoid(
        x: Float,
        y: Float,
        z: Float,
        rx: Float,
        ry: Float,
        rz: Float,
        dome: Boolean = false,
    ) {
        val start = positions.size / 3
        val rows = 14
        val columns = 24
        for (row in 0..rows) for (column in 0..columns) {
            val latitude = PI * row / rows * if (dome) .5 else 1.0
            val longitude = 2 * PI * column / columns
            vertex(
                x + rx * (sin(latitude) * cos(longitude)).toFloat(),
                y + ry * cos(latitude).toFloat(),
                z + rz * (sin(latitude) * sin(longitude)).toFloat(),
            )
        }
        for (row in 0 until rows) for (column in 0 until columns) {
            val a = start + row * (columns + 1) + column
            triangle(a, a + 1, a + columns + 1)
            triangle(a + 1, a + columns + 2, a + columns + 1)
        }
    }

    fun tube(points: List<FloatArray>, radius: Float, endRadius: Float = radius) {
        require(points.size >= 2)
        val start = positions.size / 3
        val sides = 10
        for (i in points.indices) {
            val a = points[(i - 1).coerceAtLeast(0)]
            val b = points[(i + 1).coerceAtMost(points.lastIndex)]
            val tangent = FloatArray(3) { b[it] - a[it] }
            val length = sqrt(tangent.sumOf { (it * it).toDouble() }).toFloat()
            for (axis in 0..2) tangent[axis] /= length
            val reference =
                if (abs(tangent[1]) < .9f) floatArrayOf(0f, 1f, 0f) else floatArrayOf(1f, 0f, 0f)
            fun cross(a: FloatArray, b: FloatArray) =
                floatArrayOf(
                    a[1] * b[2] - a[2] * b[1],
                    a[2] * b[0] - a[0] * b[2],
                    a[0] * b[1] - a[1] * b[0],
                )
            val normal = cross(tangent, reference)
            val norm = sqrt(normal.sumOf { (it * it).toDouble() }).toFloat()
            for (axis in 0..2) normal[axis] /= norm
            val binormal = cross(tangent, normal)
            val r = radius + (endRadius - radius) * i / points.lastIndex
            for (side in 0 until sides) {
                val angle = 2 * PI * side / sides
                val p =
                    FloatArray(3) { axis ->
                        points[i][axis] +
                            r * (normal[axis] * cos(angle) + binormal[axis] * sin(angle)).toFloat()
                    }
                vertex(p[0], p[1], p[2])
            }
        }
        for (i in 0 until points.lastIndex) for (side in 0 until sides) {
            val a = start + i * sides + side
            val b = start + i * sides + (side + 1) % sides
            triangle(a, b, a + sides)
            triangle(b, b + sides, a + sides)
        }
        val first = vertex(points[0][0], points[0][1], points[0][2])
        val last = vertex(points.last()[0], points.last()[1], points.last()[2])
        for (side in 0 until sides) {
            triangle(first, start + (side + 1) % sides, start + side)
            triangle(
                last,
                start + points.lastIndex * sides + side,
                start + points.lastIndex * sides + (side + 1) % sides,
            )
        }
    }

    fun capPeak() {
        val start = positions.size / 3
        val columns = 28
        val rows = 6
        for (layer in 0..1) for (row in 0..rows) for (column in 0..columns) {
            val theta = -PI / 2 + PI * column / columns
            val t = row.toFloat() / rows
            // The inner arc shares the crown hem, joining the visor to the front half only.
            val x = ((.093 + .017 * t) * sin(theta)).toFloat()
            val z = ((.092 + .075 * t) * cos(theta)).toFloat()
            val y = (-.010 * t * sin(theta).pow(2) - .004 * t).toFloat() - layer * .003f
            vertex(x, y, z)
        }
        val layerSize = (columns + 1) * (rows + 1)
        for (layer in 0..1) for (row in 0 until rows) for (column in 0 until columns) {
            val a = start + layer * layerSize + row * (columns + 1) + column
            if (layer == 0) {
                triangle(a, a + columns + 1, a + 1)
                triangle(a + 1, a + columns + 1, a + columns + 2)
            } else {
                triangle(a, a + 1, a + columns + 1)
                triangle(a + 1, a + columns + 2, a + columns + 1)
            }
        }
        val border =
            (0..columns).toList() +
                (1..rows).map { it * (columns + 1) + columns } +
                (columns - 1 downTo 0).map { rows * (columns + 1) + it } +
                (rows - 1 downTo 1).map { it * (columns + 1) }
        for (i in border.indices) {
            val a = start + border[i]
            val b = start + border[(i + 1) % border.size]
            triangle(a, b, a + layerSize)
            triangle(b, b + layerSize, a + layerSize)
        }
    }

    fun mesh(name: String, color: FloatArray, jaw: Boolean = false) =
        FaceEffectMesh(name, color, positions.toFloatArray(), indices.toList(), jaw)
}

internal object FaceBaseballCapGeometry {
    fun parts(): List<FaceEffectMesh> {
        val crown =
            FaceGeometryBuilder().apply { ellipsoid(0f, 0f, 0f, .093f, .065f, .092f, dome = true) }
        val peak = FaceGeometryBuilder().apply { capPeak() }
        val seams =
            FaceGeometryBuilder().apply {
                ellipsoid(0f, .065f, 0f, .006f, .003f, .006f)
                for (panel in 0 until 6) {
                    val angle = panel * PI / 3
                    tube(
                        (0..12).map { i ->
                            val a = PI * i / 24
                            floatArrayOf(
                                (.0935 * cos(a) * cos(angle)).toFloat(),
                                (.0655 * sin(a)).toFloat(),
                                (.0925 * cos(a) * sin(angle)).toFloat(),
                            )
                        },
                        .00065f,
                    )
                }
            }
        return listOf(
            crown.mesh("baseball-cap-crown", floatArrayOf(.04f, .18f, .56f, 1f)),
            peak.mesh("baseball-cap-forward-peak", floatArrayOf(.018f, .06f, .2f, 1f)),
            seams.mesh("baseball-cap-stitching", floatArrayOf(.85f, .9f, 1f, 1f)),
        )
    }
}

internal object FaceDragonGeometry {
    fun parts(): List<FaceEffectMesh> {
        val green =
            FaceGeometryBuilder().apply {
                ellipsoid(0f, .042f, .01f, .093f, .092f, .077f)
                ellipsoid(0f, -.012f, .125f, .075f, .028f, .073f)
                for (side in listOf(-1, 1)) {
                    ellipsoid(side * .075f, .015f, .06f, .029f, .038f, .04f)
                    ellipsoid(side * .055f, .055f, .063f, .038f, .04f, .039f)
                }
            }
        val gold =
            FaceGeometryBuilder().apply {
                for (side in listOf(-1f, 1f)) {
                    tube(
                        listOf(
                            floatArrayOf(side * .056f, .108f, -.005f),
                            floatArrayOf(side * .078f, .15f, -.018f),
                            floatArrayOf(side * .074f, .198f, -.048f),
                            floatArrayOf(side * .106f, .241f, -.054f),
                        ),
                        .012f,
                        .0015f,
                    )
                    tube(
                        listOf(
                            floatArrayOf(side * .075f, .167f, -.029f),
                            floatArrayOf(side * .111f, .184f, -.015f),
                            floatArrayOf(side * .129f, .211f, -.026f),
                        ),
                        .007f,
                        .0008f,
                    )
                    tube(
                        listOf(
                            floatArrayOf(side * .076f, .199f, -.048f),
                            floatArrayOf(side * .046f, .22f, -.071f),
                            floatArrayOf(side * .036f, .243f, -.076f),
                        ),
                        .005f,
                        .0008f,
                    )
                    tube(
                        (0..16).map { i ->
                            val t = i / 16f
                            floatArrayOf(
                                side * (.051f + .125f * sin(t * 2.3f)),
                                -.018f + .10f * t * t,
                                .18f - .065f * t * t,
                            )
                        },
                        .0035f,
                        .0005f,
                    )
                }
            }
        val red =
            FaceGeometryBuilder().apply {
                for (side in listOf(-1f, 1f)) tube(
                    listOf(
                        floatArrayOf(side * .014f, .082f, .086f),
                        floatArrayOf(side * .036f, .092f, .098f),
                        floatArrayOf(side * .076f, .074f, .083f),
                    ),
                    .01f,
                    .004f,
                )
                for (i in 0..5) tube(
                    listOf(
                        floatArrayOf(0f, .095f - i * .012f, -.035f),
                        floatArrayOf(0f, .153f - i * .018f, -.05f - i * .009f),
                    ),
                    .018f,
                    .0007f,
                )
            }
        val eyes =
            FaceGeometryBuilder().apply {
                for (side in listOf(-1f, 1f)) ellipsoid(
                    side * .046f,
                    .052f,
                    .098f,
                    .022f,
                    .023f,
                    .016f,
                )
            }
        val black =
            FaceGeometryBuilder().apply {
                for (side in listOf(-1f, 1f)) {
                    ellipsoid(side * .046f, .052f, .114f, .007f, .016f, .003f)
                    ellipsoid(side * .028f, -.005f, .194f, .012f, .007f, .004f)
                }
                ellipsoid(0f, -.04f, .132f, .066f, .022f, .058f)
            }
        val teeth =
            FaceGeometryBuilder().apply {
                for (side in listOf(-1f, 1f)) tube(
                    listOf(
                        floatArrayOf(side * .049f, -.029f, .157f),
                        floatArrayOf(side * .052f, -.059f, .169f),
                        floatArrayOf(side * .049f, -.071f, .174f),
                    ),
                    .006f,
                    .0005f,
                )
            }
        val lower =
            FaceGeometryBuilder().apply { ellipsoid(0f, -.022f, .091f, .074f, .017f, .076f) }
        val lowerTeeth =
            FaceGeometryBuilder().apply {
                for (side in listOf(-1f, 1f)) tube(
                    listOf(
                        floatArrayOf(side * .052f, -.008f, .129f),
                        floatArrayOf(side * .053f, .008f, .138f),
                    ),
                    .0045f,
                    .0005f,
                )
            }
        val beard =
            FaceGeometryBuilder().apply {
                for (i in -3..3) tube(
                    listOf(
                        floatArrayOf(i * .017f, -.032f, .129f),
                        floatArrayOf(i * .015f, -.059f, .147f),
                        floatArrayOf(i * .014f, -.083f, .116f),
                    ),
                    .012f,
                    .0007f,
                )
            }
        return listOf(
            green.mesh("dragon-emerald-head", floatArrayOf(.08f, .43f, .2f, 1f)),
            gold.mesh("dragon-antlers-and-whiskers", floatArrayOf(.95f, .62f, .12f, 1f)),
            red.mesh("dragon-red-crest-and-brows", floatArrayOf(.72f, .04f, .065f, 1f)),
            eyes.mesh("dragon-golden-eyes", floatArrayOf(1f, .83f, .28f, 1f)),
            black.mesh("dragon-pupils-nostrils-mouth", floatArrayOf(.018f, .012f, .015f, 1f)),
            teeth.mesh("dragon-upper-fangs", floatArrayOf(.96f, .91f, .72f, 1f)),
            lower.mesh("dragon-lower-jaw", floatArrayOf(.09f, .39f, .16f, 1f), true),
            lowerTeeth.mesh("dragon-lower-fangs", floatArrayOf(.96f, .91f, .72f, 1f), true),
            beard.mesh("dragon-red-beard", floatArrayOf(.74f, .045f, .065f, 1f), true),
        )
    }

    fun flame(): FaceEffectMesh {
        val builder = FaceGeometryBuilder()
        builder.tube(
            (0..18).map { i ->
                val t = i / 18f
                floatArrayOf(.09f * sin(t * 7f) * t, .065f * sin(t * 9f) * t, t)
            },
            .10f,
            .0005f,
        )
        return builder.mesh("dragon-flame-tongue", floatArrayOf(1f, .4f, .025f, 1f))
    }
}
