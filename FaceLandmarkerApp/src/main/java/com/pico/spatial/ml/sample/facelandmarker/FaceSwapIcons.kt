// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.unit.dp

/** 24-unit line icons. Icon tints them, so the brush color here only acts as an alpha mask. */
internal object FaceSwapIcons {
    private val mask = SolidColor(Color.Black) // design-style: fixed-figma-color icon alpha mask

    private fun icon(name: String, strokes: List<String>, fills: List<String> = emptyList()) =
        ImageVector.Builder(name, 24.dp, 24.dp, 24f, 24f)
            .apply {
                for (path in strokes) addPath(
                    pathData = addPathNodes(path),
                    stroke = mask,
                    strokeLineWidth = 1.6f,
                    strokeLineCap = StrokeCap.Round,
                    strokeLineJoin = StrokeJoin.Round,
                )
                for (path in fills) addPath(pathData = addPathNodes(path), fill = mask)
            }
            .build()

    private fun circle(x: Float, y: Float, r: Float) =
        "M${x - r} ${y}a$r $r 0 1 0 ${2 * r} 0a$r $r 0 1 0 ${-2 * r} 0z"

    val helmet =
        icon(
            "helmet",
            listOf(
                "M6 9.5a6 7 0 0 1 12 0V15l-3 5H9l-3-5z",
                "M8.3 11.8h2.9M12.8 11.8h2.9",
                "M10 17h4",
                "M12 3.2v3",
            ),
        )
    val eyes =
        icon(
            "eyes",
            listOf(circle(8.5f, 9f, 3.2f), circle(15.5f, 9f, 3.2f), "M6 15c2.2 3.8 9.8 3.8 12 0z"),
            listOf(circle(9.2f, 9.6f, .9f), circle(16.2f, 9.6f, .9f)),
        )
    val cap =
        icon("cap", listOf("M4 16a8 8 0 0 1 16 0z", "M12 16h9.5"), listOf(circle(12f, 7f, .9f)))
    val flag =
        icon(
            "flag",
            listOf(
                "M5 12a7 9 0 1 0 14 0a7 9 0 1 0 -14 0z",
                "M6.8 13h3.6v2.6h-3.6z",
                "M13.6 13h3.6v2.6h-3.6z",
            ),
        )
    val dragon =
        icon(
            "dragon",
            listOf(
                "M3 15c2.5-5.5 7.5-8.5 13.5-7.5l3.5 3-3 1.2 1 3.3-4.2.8-2 3.2H6z",
                "M9 7.5L7.5 4M12 7l.2-3.5",
            ),
            listOf(circle(14.6f, 10f, .9f)),
        )
    val pause = icon("pause", emptyList(), listOf("M6 5h4v14H6z", "M14 5h4v14h-4z"))
    val play = icon("play", emptyList(), listOf("M7 5v14l12-7z"))
    val swap =
        icon(
            "swap",
            listOf(
                "M20 11a8 8 0 0 0-14.5-4.5L4 8",
                "M4 3v5h5",
                "M4 13a8 8 0 0 0 14.5 4.5L20 16",
                "M20 21v-5h-5",
            ),
        )
}
