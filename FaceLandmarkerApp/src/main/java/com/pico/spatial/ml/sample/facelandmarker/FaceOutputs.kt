// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

/**
 * Immutable per-frame output selection. None suspends submission; tracking state stays owned by
 * SpatialML.
 */
internal data class FaceOutputs(val mask: Int) {
    init {
        require(mask in 0..7)
    }

    val pose
        get() = mask and 1 != 0

    val mesh
        get() = mask and 2 != 0

    val blendshapes
        get() = mask and 4 != 0

    val any
        get() = mask != 0

    val spatial
        get() = pose || mesh

    val packetSize
        get() =
            62 + (if (spatial) 16 else 0) + (if (mesh) 1453 else 0) + (if (blendshapes) 52 else 0)

    fun toggle(bit: Int): FaceOutputs {
        require(bit == 1 || bit == 2 || bit == 4)
        return FaceOutputs(mask xor bit)
    }

    companion object {
        val POSE = FaceOutputs(1)
        val HELMET = FaceOutputs(3)
        val ALL = FaceOutputs(7)
        val NONE = FaceOutputs(0)
    }
}

/** Schema 2 is a final handoff: nothing reconstructed here is uploaded to SpatialML. */
internal object FaceOutputPacket {
    fun decode(packet: FloatArray, outputs: FaceOutputs): FloatArray {
        require(outputs.any && packet.size == outputs.packetSize)
        require(packet[packet.size - 2] == 2f && packet.last() == outputs.mask.toFloat()) {
            "Face output schema or selection does not match the submitted frame"
        }
        require(packet[0].isFinite())
        // Retain the app's established storage/coordinate layout without transferring its unused
        // sections across processes. FaceFrame exposes absent outputs as empty arrays.
        val result = FloatArray(FaceFrame.RESULT_SIZE)
        result[0] = packet[0]
        result[2] = packet[7]
        result[3] = packet[5]
        packet.copyInto(result, FaceFrame.TRACKING_OFFSET, 12, 44)
        packet.copyInto(result, 2978, 44, 60)
        if (packet[4] <= 0 || !packet.all(Float::isFinite)) return result
        var offset = 60
        val world = if (outputs.spatial) packet.copyOfRange(offset, offset + 16) else FloatArray(0)
        if (outputs.spatial) offset += 16
        if (outputs.spatial) world.copyInto(result, FaceFrame.POSE_OFFSET)
        if (outputs.mesh) {
            if (!mesh(packet, offset, world, result)) return result
            offset += 1453
        }
        if (outputs.blendshapes)
            packet.copyInto(result, FaceFrame.BLENDSHAPE_OFFSET, offset, offset + 52)
        if (result.all(Float::isFinite)) result[1] = 1f
        return result
    }

    private fun mesh(
        packet: FloatArray,
        offset: Int,
        world: FloatArray,
        result: FloatArray,
    ): Boolean {
        val width = SpatialMLGraphSession.WIDTH.toDouble()
        val height = SpatialMLGraphSession.HEIGHT.toDouble()
        val cx = packet[8].toDouble()
        val cy = packet[9].toDouble()
        val side = packet[10].toDouble()
        val cosine = kotlin.math.cos(packet[11].toDouble())
        val sine = kotlin.math.sin(packet[11].toDouble())
        val fx = packet[24].toDouble()
        val fy = packet[25].toDouble()
        val principalX = packet[26].toDouble()
        val principalY = packet[27].toDouble()
        val fit = offset + 1434
        val scale = packet[fit + 16].toDouble() * packet[fit + 17]
        val depth = packet[fit + 18].toDouble()
        val squaredScale =
            packet[fit].toDouble() * packet[fit] +
                packet[fit + 4].toDouble() * packet[fit + 4] +
                packet[fit + 8].toDouble() * packet[fit + 8]
        if (fx <= 0 || fy <= 0 || scale <= 0 || squaredScale <= 1e-12) return false
        val metric = DoubleArray(3)
        val local = DoubleArray(3)
        for (i in 0 until 478) {
            val j = i * 3
            val x = packet[offset + j].toDouble() / 256 - .5
            val y = packet[offset + j + 1].toDouble() / 256 - .5
            val lx = ((cx + side * (cosine * x - sine * y)) / width).toFloat()
            val ly = ((cy + side * (sine * x + cosine * y)) / height).toFloat()
            val lz = (packet[offset + j + 2].toDouble() / 256 * side / width).toFloat()
            result[4 + j] = lx
            result[5 + j] = ly
            result[6 + j] = lz
            // Preserve float32 boundaries of the former service tensors for numerical parity.
            val px = ((lx * width - principalX) / fx).toFloat()
            val py = ((principalY - ly * height) / fy).toFloat()
            val pz = (lz * width / fx).toFloat()
            val z = (pz.toDouble() - depth + 1) / scale
            metric[0] = (px * z).toFloat().toDouble()
            metric[1] = (py * z).toFloat().toDouble()
            metric[2] = (-z).toFloat().toDouble()
            for (a in 0..2) {
                var v = 0.0
                for (b in 0..2) v += packet[fit + b * 4 + a] * (metric[b] - packet[fit + b * 4 + 3])
                local[a] = v * (.01 / squaredScale)
            }
            for (r in 0..2) {
                var v = world[r * 4 + 3].toDouble()
                for (c in 0..2) v += world[r * 4 + c] * local[c]
                result[FaceFrame.VERTEX_OFFSET + j + r] = v.toFloat()
            }
        }
        return true
    }
}
