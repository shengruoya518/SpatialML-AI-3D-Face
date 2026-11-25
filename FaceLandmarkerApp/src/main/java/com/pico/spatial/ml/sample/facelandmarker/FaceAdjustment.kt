// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.content.Context

/**
 * The wearer's manual trim of where effects land. It corrects this headset, not a face, so it is
 * stored on the device and set once. Shifts are in the headset's own left/right and up/down.
 */
internal data class FaceAdjustment(
    val scale: Float = 1f,
    val rightCm: Float = 0f,
    val upCm: Float = 0f,
) {
    /** Capture-head metres, +X right and +Y up. */
    val headShift
        get() = rightCm / 100f to upCm / 100f

    fun save(context: Context) {
        context
            .getSharedPreferences(STORE, Context.MODE_PRIVATE)
            .edit()
            .putFloat("scale", scale)
            .putFloat("rightCm", rightCm)
            .putFloat("upCm", upCm)
            .apply()
    }

    companion object {
        private const val STORE = "face_adjustment"
        val SCALE = .8f..1.2f
        val SHIFT_CM = -8f..8f

        fun load(context: Context): FaceAdjustment {
            val store = context.getSharedPreferences(STORE, Context.MODE_PRIVATE)
            return FaceAdjustment(
                store.getFloat("scale", 1f).coerceIn(SCALE),
                store.getFloat("rightCm", 0f).coerceIn(SHIFT_CM),
                store.getFloat("upCm", 0f).coerceIn(SHIFT_CM),
            )
        }
    }
}
