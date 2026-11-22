// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

/** Paired source camera and effective stereo registration from the existing measured board. */
internal object LabStereoCalibration {
    const val ID = "stereo-face-existing-data-2026-11-06"

    // Native 3248 x 2464 source pixels, before the preserved C image affine.
    val sourceIntrinsics: FloatArray
        get() =
            floatArrayOf(
                2358.870351068085f,
                0f,
                1561.261136055872f,
                0f,
                1815.389847770632f,
                1222.179704991295f,
                0f,
                0f,
                1f,
            )

    val workingIntrinsics =
        LabIntrinsics(
            1810.079487608682f,
            1815.389847770632f,
            1575.740978260169f,
            1222.179704991295f,
        )

    // Row-major D, multiplying column vectors in metres, before capture-head-to-Stage.
    // Q_stage = H_capture * D * E_camera_to_head * Q_camera_metres. Ray scale is 1.
    val headCorrection: FloatArray
        get() =
            floatArrayOf(
                0.9997588246273411f,
                -0.0011340528732299644f,
                0.02193186047371193f,
                -0.004310512859900328f,
                0.0012597332461165298f,
                0.9999828613348418f,
                -0.005717526452179058f,
                -0.04409491847453374f,
                -0.021925000613598113f,
                0.00574377581939419f,
                0.999743118699714f,
                0.04219700998229438f,
                0f,
                0f,
                0f,
                1f,
            )
}
