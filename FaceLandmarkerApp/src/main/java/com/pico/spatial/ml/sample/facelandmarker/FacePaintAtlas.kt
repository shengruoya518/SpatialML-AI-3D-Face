// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/** Face-local UVs keep paint attached to the same anatomical vertices while the mesh deforms. */
internal class FacePaintAtlas(canonical: FloatArray) {
    private val xs = FloatArray(468) { canonical[it * 4] }
    private val ys = FloatArray(468) { canonical[it * 4 + 1] }
    private val minX = xs.min()
    private val minY = ys.min()
    private val width = xs.max() - minX
    private val height = ys.max() - minY
    private val flagWidth = width * .235f
    private val flagHeight = flagWidth / 1.9f
    private val mouthX = (xs[61] + xs[291]) * .5f
    private val mouthY = (ys[0] + ys[17]) * .5f
    private val grinHalfWidth = abs(xs[291] - xs[61]) * .78f
    private val mouthHeight = abs(ys[0] - ys[17])
    private val star =
        List(10) { i ->
            val angle = -PI * .5 + i * PI / 5
            val radius = if (i % 2 == 0) 1.0 else .382
            Pair((cos(angle) * radius).toFloat(), (sin(angle) * radius).toFloat())
        }

    private data class ClearArea(val x: Float, val y: Float, val rx: Float, val ry: Float)

    private val clearAreas =
        listOf(
            ClearArea(
                (xs[33] + xs[133]) * .5f,
                (ys[159] + ys[145]) * .5f,
                abs(xs[33] - xs[133]) * .5f + 1.0f,
                abs(ys[159] - ys[145]) * .5f + .9f,
            ),
            ClearArea(
                (xs[263] + xs[362]) * .5f,
                (ys[386] + ys[374]) * .5f,
                abs(xs[263] - xs[362]) * .5f + 1.0f,
                abs(ys[386] - ys[374]) * .5f + .9f,
            ),
            ClearArea(
                (xs[61] + xs[291]) * .5f,
                (ys[0] + ys[17]) * .5f,
                abs(xs[61] - xs[291]) * .5f + .9f,
                abs(ys[0] - ys[17]) * .5f + 1.0f,
            ),
        )
    val uv =
        FloatArray(478 * 2) { i ->
            val point = (i / 2).coerceAtMost(467)
            if (i % 2 == 0) (xs[point] - minX) / width else (ys[point] - minY) / height
        }

    fun pixels(effect: FaceEffect): IntArray =
        IntArray(SIZE * SIZE) { i ->
            val u = (i % SIZE + .5f) / SIZE
            // Bitmap row zero is the top; mesh V increases up the canonical face.
            val v = 1f - (i / SIZE + .5f) / SIZE
            val color =
                when (effect) {
                    FaceEffect.FLAG -> cheekFlags(minX + u * width, minY + v * height)
                    FaceEffect.TEAM -> if (u < .5f) 0xBF2354D8.toInt() else 0xBFFFCE32.toInt()
                    FaceEffect.EYES -> grin(minX + u * width, minY + v * height)
                    else -> error("No paint atlas for $effect")
                }
            if (effect == FaceEffect.FLAG || effect == FaceEffect.TEAM) {
                val alpha = (((color ushr 24) and 255) * paintCoverage(u, v)).toInt()
                (color and 0x00FFFFFF) or (alpha shl 24)
            } else color
        }

    /** Exact transparent eye/lip neighborhoods, with a soft edge outside each clear area. */
    fun paintCoverage(u: Float, v: Float): Float {
        val x = minX + u * width
        val y = minY + v * height
        var coverage = 1f
        for (area in clearAreas) {
            val dx = (x - area.x) / area.rx
            val dy = (y - area.y) / area.ry
            val radius = sqrt(dx * dx + dy * dy)
            val edge = ((radius - 1f) / .18f).coerceIn(0f, 1f)
            coverage = minOf(coverage, edge * edge * (3f - 2f * edge))
        }
        return coverage
    }

    /** Two independent, upright flags; the rest of the face is completely transparent. */
    private fun cheekFlags(x: Float, y: Float): Int {
        for (cheek in intArrayOf(50, 280)) {
            val u = (x - xs[cheek]) / flagWidth + .5f
            val v = .5f - (y - ys[cheek]) / flagHeight
            if (u !in 0f..1f || v !in 0f..1f) continue
            val color =
                if (u < .4f && v < 7f / 13f) {
                    val cantonX = u / .4f
                    val cantonY = v / (7f / 13f)
                    if (isFlagStar(cantonX, cantonY)) 0xFFFFFFFF.toInt() else 0xFF23406F.toInt()
                } else if ((v * 13).toInt().coerceAtMost(12) % 2 == 0) 0xFFBF2441.toInt()
                else 0xFFFFFFFF.toInt()
            val edge = minOf(u, 1 - u, v * flagHeight / flagWidth, (1 - v) * flagHeight / flagWidth)
            val alpha = (255 * (edge * flagWidth / .035f).coerceIn(0f, 1f)).toInt()
            return (color and 0xFFFFFF) or (alpha shl 24)
        }
        return 0
    }

    /** Nine alternating rows of six/five five-pointed stars, fifty in total. */
    private fun isFlagStar(u: Float, v: Float): Boolean {
        for (row in 0..8) {
            val y = (row + 1) / 10f
            val dy = (v - y) * (7f / 13f) * flagHeight
            val radius = flagHeight * .0308f
            if (abs(dy) > radius) continue
            val count = if (row % 2 == 0) 6 else 5
            val offset = if (count == 6) 1f / 12f else 1f / 6f
            val column = kotlin.math.round((u - offset) * 6).toInt()
            if (column !in 0 until count) continue
            val dx = (u - (offset + column / 6f)) * .4f * flagWidth
            if (abs(dx) > radius) continue
            val px = dx / radius
            val py = dy / radius
            var inside = false
            var previous = star.last()
            for (next in star) {
                if (
                    (next.second > py) != (previous.second > py) &&
                        px <
                            (previous.first - next.first) * (py - next.second) /
                                (previous.second - next.second) + next.first
                )
                    inside = !inside
                previous = next
            }
            if (inside) return true
        }
        return false
    }

    /** Opaque teeth and mouth replace the real lips, with extra coverage around the mouth. */
    private fun grin(px: Float, py: Float): Int {
        val x = (px - mouthX) / grinHalfWidth
        if (abs(x) >= 1f) return 0
        val top = mouthY + mouthHeight * (.64f + .31f * x * x)
        val bottom = mouthY + mouthHeight * (-.92f + 1.87f * x * x)
        val t = (top - py) / (top - bottom)
        if (t !in 0f..1f) return 0
        val alpha = (255 * minOf((1 - abs(x)) * 60, t * 45, (1 - t) * 45, 1f)).toInt()
        val upperTeeth = t in 0.13f..0.51f
        val lowerTeeth = t in 0.66f..0.88f
        val teeth = upperTeeth || lowerTeeth
        val cell = (x + 1f) * (if (upperTeeth) 5f else 6f)
        val seam = abs(cell - kotlin.math.round(cell)) < .024f
        val color =
            when {
                t < .07f || t > .94f -> 0x00392B3B
                teeth && seam -> 0x00978C80
                teeth && (t < .18f || t > .83f) -> 0x00E9DABD
                teeth -> 0x00FFF9E8
                else -> 0x00201829
            }
        return color or (alpha shl 24)
    }

    companion object {
        const val SIZE = 512

        // Stitch the existing inner-lip landmarks. The tracked mesh has an oral aperture;
        // a texture alone cannot cover it. These triangles deform with the measured lips.
        val MOUTH_FILL: List<Int> = buildList {
            val upper = intArrayOf(78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308)
            val lower = intArrayOf(78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308)
            for (i in 0 until upper.lastIndex) {
                if (upper[i] != lower[i]) addAll(listOf(upper[i], lower[i], upper[i + 1]))
                if (upper[i + 1] != lower[i + 1])
                    addAll(listOf(upper[i + 1], lower[i], lower[i + 1]))
            }
        }
    }
}
