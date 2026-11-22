// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

internal enum class FaceEffect(val label: String, val description: String) {
    MESH("Face mesh", "Transparent mesh follows the face. Check its alignment first."),
    HELMET("Opening helmet", "A hinged faceplate opens to reveal your face."),
    CLOSED_HELMET("Closed helmet", "A solid face cover follows your head, with no moving visor."),
    EYES("Buggy eyes + grin", "Big blinking eyes and an oversized toothy grin follow your face."),
    HAT("Baseball cap", "A fitted baseball cap with a forward peak follows your head."),
    PIGTAILS("Red pigtails", "Red hair and blue bows follow the filtered head pose."),
    FLAG("USA cheek flags", "A USA flag on each cheek follows your face."),
    TEAM("Team colors", "Blue and gold face paint follows the measured face mesh."),
    DRAGON(
        "Chinese dragon",
        "Open your mouth to move its jaw. Stick out your tongue to breathe fire.",
    );

    val outputs: FaceOutputs
        get() = if (this == DRAGON || this == EYES) FaceOutputs.ALL else FaceOutputs.HELMET
}
