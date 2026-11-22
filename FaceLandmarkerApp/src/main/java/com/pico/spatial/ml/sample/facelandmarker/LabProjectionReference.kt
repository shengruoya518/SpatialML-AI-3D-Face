// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import org.json.JSONArray
import org.json.JSONObject

/** Independent renderer references, in metres in the capture-HMD frame. No face fit is used. */
internal object LabProjectionReference {
    const val PROTOCOL = "binocular-geometry-v1"
    const val ATLAS_SIZE = 512
    private const val TILE = 128
    // OpenCV DICT_4X4_50, ids 0..11, row-major MSB first (1 = white).
    private val codes =
        listOf(
            0xb532,
            0x0f9a,
            0x332d,
            0x9946,
            0x549e,
            0x79cd,
            0x9e2e,
            0xc4f2,
            0xfeda,
            0xcf56,
            0xf991,
            0x11a7,
        )
    private val locations =
        listOf(
            -.34f to -.25f,
            -.34f to -.08f,
            -.34f to .09f,
            -.34f to .26f,
            -.16f to .26f,
            .16f to .26f,
            .34f to .26f,
            .34f to .09f,
            .34f to -.08f,
            .34f to -.25f,
            -.50f to .02f,
            .50f to .02f,
        )
    // Full white panels leave |x / depth| < .408 clear in the capture-head frame.
    // The roll gate reserves a smaller whole-face region for stereo/parallax margin.
    private val rollLocations =
        listOf(-.44f, .44f).flatMap { x ->
            listOf(-.25f, -.15f, -.05f, .05f, .15f, .25f).map { y -> x to y }
        }
    private val depths = listOf(.65f, 1.15f, 2.05f)
    val prompts =
        listOf(
            "Subject faces you at about 0.7 m. Keep your headset level.",
            "Subject faces you at about 1.2 m. Keep your headset level.",
            "Subject faces you at about 2 m. Keep your headset level.",
            "At 1.2 m, subject turns left about 25 degrees. Keep your headset level.",
            "At 1.2 m, subject turns right about 25 degrees. Keep your headset level.",
            "Subject faces you at 1.2 m. Tilt YOUR headset left about 15 degrees, then hold.",
            "Subject faces you at 1.2 m. Tilt YOUR headset right about 15 degrees, then hold.",
            "Subject stays still at 1.2 m. Turn YOUR headset left 15 degrees; keep face visible.",
            "Subject stays still at 1.2 m. Turn YOUR headset right 15 degrees; keep face visible.",
            "Repeat: subject faces you at 1.2 m. Return your headset to level.",
        )

    data class Mesh(val positions: FloatArray, val uv: FloatArray, val triangles: List<Int>)

    /** TL, TR, BR, BL; image top is +Y, forward is -Z. */
    private fun quad(x: Float, y: Float, z: Float, width: Float, height: Float = width) =
        floatArrayOf(
            x - width / 2,
            y + height / 2,
            z,
            x + width / 2,
            y + height / 2,
            z,
            x + width / 2,
            y - height / 2,
            z,
            x - width / 2,
            y - height / 2,
            z,
        )

    fun corners(id: Int, rollOnly: Boolean = false): FloatArray {
        val depth = depths[id % depths.size]
        val (x, y) = (if (rollOnly) rollLocations else locations)[id]
        return quad(x * depth, y * depth, -depth, .048f * depth)
    }

    // CRC-8/ATM protects the full 32-bit sequence drawn into the SAME mesh upload as the face.
    fun checksum(sequence: Int): Int {
        var crc = 0
        for (shift in listOf(24, 16, 8, 0)) {
            crc = crc xor ((sequence ushr shift) and 255)
            repeat(8) {
                crc = if (crc and 128 != 0) ((crc shl 1) xor 7) and 255 else (crc shl 1) and 255
            }
        }
        return crc
    }

    fun codeCell(row: Int, column: Int, sequence: Int): Boolean {
        if (row == 0 || row == 8 || column == 0 || column == 11) return true
        if (row == 1 || row == 7 || column == 1 || column == 10) return false
        val index = (row - 2) * 8 + column - 2
        return if (index < 32) (sequence ushr (31 - index)) and 1 != 0
        else (checksum(sequence) ushr (39 - index)) and 1 != 0
    }

    fun codeCentre(row: Int, column: Int): FloatArray =
        floatArrayOf((column - 5.5f) * .013f * 1.1f, (.33f + (4 - row) * .013f) * 1.1f, -1.1f)

    fun mesh(sequence: Int, rollOnly: Boolean = false): Mesh {
        val positions = ArrayList<Float>()
        val uv = ArrayList<Float>()
        val triangles = ArrayList<Int>()
        fun add(points: FloatArray, tex: FloatArray) {
            val first = positions.size / 3
            positions.addAll(points.toList())
            uv.addAll(tex.toList())
            triangles.addAll(listOf(0, 2, 1, 0, 3, 2).map { first + it })
        }
        for (id in locations.indices) {
            val depth = depths[id % depths.size]
            val (x, y) = (if (rollOnly) rollLocations else locations)[id]
            val u = (id % 4) * .25f
            val v = (id / 4) * .25f
            add(
                quad(x * depth, y * depth, -depth, .064f * depth),
                floatArrayOf(u, v, u + .25f, v, u + .25f, v + .25f, u, v + .25f),
            )
        }
        for (r in 0..8) for (c in 0..11) {
            val p = codeCentre(r, c)
            val u = if (codeCell(r, c, sequence)) .375f else .625f
            add(
                quad(p[0], p[1], p[2], .013f * 1.1f),
                floatArrayOf(u, .875f, u, .875f, u, .875f, u, .875f),
            )
        }
        return Mesh(positions.toFloatArray(), uv.toFloatArray(), triangles)
    }

    const val FACE_MARKER_U = .125f
    const val FACE_MARKER_V = .875f

    // Bitmap rows run downward; TextureResource's mesh V runs upward on this renderer.
    // Reverse the full bitmap once, preserving the logical tile/cell UVs used by every quad.
    // The recorded 7271d44e check exposed the former row swap: slots 0..3 sampled palette
    // tiles, face markers sampled white, and both frame-code values sampled white.
    fun atlas(): IntArray =
        IntArray(ATLAS_SIZE * ATLAS_SIZE) { i ->
            val x = i % ATLAS_SIZE
            val y = ATLAS_SIZE - 1 - i / ATLAS_SIZE
            val id = (y / TILE) * 4 + x / TILE
            val column = (x % TILE) / 16
            val row = (y % TILE) / 16
            when {
                id == 12 -> 0xff00ff00.toInt()
                id == 14 -> 0xff000000.toInt()
                id >= 12 || row == 0 || row == 7 || column == 0 || column == 7 -> -1
                row == 1 || row == 6 || column == 1 || column == 6 -> 0xff000000.toInt()
                (codes[id] ushr (15 - (row - 2) * 4 - column + 2)) and 1 != 0 -> -1
                else -> 0xff000000.toInt()
            }
        }

    fun json(headToStage: FloatArray, rollOnly: Boolean = false): JSONObject =
        JSONObject()
            .put("protocol", PROTOCOL)
            .put("dictionary", "DICT_4X4_50")
            .put("referenceLayout", if (rollOnly) LabRollCapture.LAYOUT else "original-v1")
            .put(
                "clearFaceRegion",
                if (rollOnly)
                    JSONObject()
                        .put("owner", "capture-head")
                        .put("coordinates", "x/depth,y/depth; depth=-z metres")
                        .put("xMin", -.25)
                        .put("xMax", .25)
                        .put("yMin", -.30)
                        .put("yMax", .24)
                        .put("minimumDepthMetres", .45)
                else JSONObject.NULL,
            )
            .put("textureMapping", "bitmap-rows-reversed-for-bottom-origin-mesh-v")
            .put("faceMarkerUv", JSONArray(listOf(FACE_MARKER_U, FACE_MARKER_V)))
            .put("cornerOrder", "TL,TR,BR,BL at outer black border; quiet zone excluded")
            .put("rigToStage", JSONArray(headToStage.toList()))
            .put(
                "frameCode",
                "32-bit sequence MSB first + CRC-8/ATM; 5x8 payload, black border, white quiet zone",
            )
            .put(
                "markers",
                JSONArray().apply {
                    for (id in locations.indices) put(
                        JSONObject()
                            .put("id", id)
                            .put("rigCorners", JSONArray(corners(id, rollOnly).toList()))
                            .put(
                                "stageCorners",
                                JSONArray(
                                    StageRegistration.transformVertices(
                                            headToStage,
                                            corners(id, rollOnly),
                                        )
                                        .toList()
                                ),
                            )
                    )
                },
            )
}

/** Immutable per-packet metadata, preserved across presentation tags and Stage conversion. */
internal class LabRegistrationEvidence(
    head: FloatArray,
    optical: FloatArray,
    transform: FloatArray,
    private val exposure: LabMotion = LabMotion(false, 0.0, 0.0),
    val poseCorrection: LabPoseCorrection = LabPoseCorrection(),
    rawTransform: FloatArray = transform,
) {
    val headToStage = head.copyOf()
    val cameraToHead = optical.copyOf()
    val serviceToStage = transform.copyOf()
    val rawServiceToStage = rawTransform.copyOf()

    fun json(rollOnly: Boolean = false): JSONObject =
        LabProjectionReference.json(headToStage, rollOnly)
            .put("cameraToHead", JSONArray(cameraToHead.toList()))
            .put("serviceToStage", JSONArray(serviceToStage.toList()))
            .put("rawServiceToStage", JSONArray(rawServiceToStage.toList()))
            .put("poseCorrection", poseCorrection.json())
            .put("headStableAtExposure", exposure.stable)
            .put("exposureHistoryCovered", exposure.covered)
            .put("headMovementAtExposureMetres", exposure.metres)
            .put("headMovementAtExposureDegrees", exposure.degrees)
            .put(
                "trackingClock",
                "callback arrival; physical origin and prediction horizon unverified",
            )
}
