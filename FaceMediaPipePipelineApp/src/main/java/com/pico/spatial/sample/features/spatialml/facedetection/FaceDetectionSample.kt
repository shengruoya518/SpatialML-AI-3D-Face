/*
 * Copyright 2025 - 2026 PICO. All rights reserved.
 *
 * NOTICE: All information contained herein is, and remains the property of PICO.
 * The intellectual and technical concepts contained herein are proprietary to PICO
 * and may be covered by patents, patents in process, and are protected by trade
 * secret or copyright law. Dissemination of this information or reproduction of
 * this material is strictly forbidden unless prior written permission is obtained
 * from PICO.
 */

package com.pico.spatial.sample.features.spatialml.facedetection

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.pico.spatial.ui.design.PicoTheme
import com.pico.spatial.ui.design.Text

@Composable
fun FaceDetectionSample() {
    val context = LocalContext.current.applicationContext
    val pipeline = remember { FaceDetectionPipeline(context) }

    DisposableEffect(pipeline) {
        pipeline.start()
        onDispose { pipeline.close() }
    }

    PicoTheme {
        Column(
            modifier = Modifier.fillMaxSize().background(Color(color = 0xFF22262E)).padding(32.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = "SpatialML Face Detection",
                textAlign = TextAlign.Center,
                style = PicoTheme.typography.titleLarge,
                color = Color.White,
            )
            Text(
                modifier = Modifier.padding(top = 16.dp),
                text =
                    "Move the SpatialML portal near a face. " +
                        "The face frame appears when detection succeeds.",
                textAlign = TextAlign.Center,
                style = PicoTheme.typography.bodyMedium,
                color = Color.White,
            )
        }
    }
}
