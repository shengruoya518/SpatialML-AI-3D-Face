// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pico.spatial.ui.design.PicoTheme
import com.pico.spatial.ui.design.Switch
import com.pico.spatial.ui.design.Text
import java.util.Locale

@Composable
internal fun FaceOutputControls(runner: FaceLandmarkerRunner, calibration: Boolean = false) {
    val requested by runner.outputs.collectAsStateWithLifecycle()
    val outputs = if (calibration) FaceOutputs.ALL else requested
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            if (calibration) "Calibration uses all face outputs" else "Face outputs",
            style = PicoTheme.typography.bodyMedium,
        )
        if (!outputs.any) Text("Outputs paused", style = PicoTheme.typography.bodySmall)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            for ((bit, label) in
                listOf(1 to "Face pose", 2 to "Face mesh", 4 to "Face blendshapes")) {
                Column {
                    Text(label, style = PicoTheme.typography.bodySmall)
                    Switch(
                        checked = outputs.mask and bit != 0,
                        onCheckedChange = { runner.setOutputs(requested.toggle(bit)) },
                        enabled = !calibration,
                        modifier = Modifier.semantics { contentDescription = label },
                    )
                }
            }
        }
    }
}

@Composable
internal fun FaceOutputSummary(frame: FaceFrame?, geometry: FaceGeometry) {
    if (frame == null || !frame.hasFace) return
    if (frame.outputs.pose) {
        val pose = frame.pose
        Text(
            String.format(
                Locale.US,
                "Face position: %.2f, %.2f, %.2f m",
                pose[3],
                pose[7],
                pose[11],
            ),
            style = PicoTheme.typography.bodySmall,
        )
    }
    if (frame.outputs.blendshapes) {
        val scores = frame.blendshapes
        val top = scores.indices.sortedByDescending { scores[it] }.take(3)
        Text(
            top.joinToString(" · ") {
                String.format(
                    Locale.US,
                    "%s %.0f%%",
                    geometry.blendshapeNames[it],
                    scores[it] * 100,
                )
            },
            style = PicoTheme.typography.bodySmall,
        )
    }
}
