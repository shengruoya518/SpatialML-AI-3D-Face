// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pico.spatial.ui.design.Button
import com.pico.spatial.ui.design.PicoTheme
import com.pico.spatial.ui.design.Text
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive

@Composable
internal fun LabTimelineBadge(
    lab: FaceRegistrationLab,
    scene: FaceMeshScene,
    runner: FaceLandmarkerRunner,
    geometry: FaceGeometry,
) {
    val frame by runner.frame.collectAsStateWithLifecycle()
    val time by lab.timeline.ui.collectAsStateWithLifecycle()
    val state by lab.ui.collectAsStateWithLifecycle()
    val preview by lab.preview.collectAsStateWithLifecycle()
    val automatic by lab.automaticUi.collectAsStateWithLifecycle()
    var showFaceTests by remember(lab) { mutableStateOf(true) }
    var startError by remember(lab) { mutableStateOf<String?>(null) }
    LaunchedEffect(lab) {
        while (isActive) {
            lab.timeline.tick()
            delay(100)
        }
    }
    // Desktop/adb mesh commands remain active without the former headset controls.
    LaunchedEffect(state.meshStyle) {
        scene.setMeshStyle(state.meshStyle)
        lab.timeline.visibilityChanged(scene.face.enabled)
    }
    Column(
        Modifier.verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        val hint =
            startError
                ?: when {
                    state.stopped -> "Reopen this app to restart the camera."
                    !automatic.active && state.count + 12 > 100 ->
                        "Reopen this app to begin another roll trial."
                    automatic.active -> "Keep the target fixed and follow the capture prompt."
                    state.poseCorrection.stereo -> "Stereo calibration active."
                    else -> "Previous camera mode. Select stereo calibration to restore it."
                }
        Text(
            listOfNotNull(
                    time.text(),
                    automatic.text().takeUnless { automatic.phase == "IDLE" },
                    hint,
                )
                .joinToString("\n"),
            // Bounded diagnostic content surface for OCR against passthrough, not a root fill.
            Modifier.fillMaxWidth().background(PicoTheme.colorScheme.fillPrimary).padding(12.dp),
            style = PicoTheme.typography.bodyMedium.copy(fontFamily = FontFamily.Monospace),
            color = PicoTheme.colorScheme.labelPrimaryLight,
        )
        FaceOutputControls(runner, state.locked || state.showCaptureTools || automatic.active)
        if (!automatic.active && showFaceTests) FaceOutputSummary(frame, geometry)
        if (!automatic.active) {
            Button(onClick = { lab.toggleDiagnosticPreview() }, enabled = !state.locked) {
                Text(if (state.showCaptureTools) "Hide source preview" else "Show source preview")
            }
            if (state.showCaptureTools) {
                preview?.let { image ->
                    Text(
                        "Captured source · frame ${image.sequence} · mode ${image.mode}. Green dots are source-image landmarks."
                    )
                    Row(Modifier.fillMaxWidth()) {
                        Image(
                            image.source.asImageBitmap(),
                            contentDescription = "Exact captured source image",
                            modifier = Modifier.weight(1f).height(180.dp),
                        )
                        Image(
                            image.model.asImageBitmap(),
                            contentDescription =
                                "Captured model crop; landmarks valid only with a detected face",
                            modifier = Modifier.weight(1f).height(180.dp),
                        )
                    }
                } ?: Text("Waiting for a captured source image…")
            }
        }
        if (automatic.active) {
            Button(onClick = { lab.cancelAutomatic() }) { Text("Cancel capture") }
        }
        val canStart =
            lab.trialsAvailable &&
                !state.locked &&
                !automatic.active &&
                !state.stopped &&
                time.logging
        if (!automatic.active) {
            if (!showFaceTests) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    for ((kind, label) in
                        listOf(
                            LabBoardCapture.CHECK to "Board check",
                            LabBoardCapture.VIEWS to "Board views · 16",
                        )) {
                        Button(
                            onClick = {
                                startError =
                                    runCatching {
                                            lab.startAutomatic(single = true, boardKind = kind)
                                        }
                                        .exceptionOrNull()
                                        ?.message
                            },
                            modifier = Modifier.weight(1f),
                            enabled = canStart && state.count + LabBoardCapture.count(kind) <= 100,
                        ) {
                            Text(label)
                        }
                    }
                }
                Button(
                    onClick = {
                        startError =
                            runCatching {
                                    lab.startAutomatic(
                                        single = false,
                                        boardKind = LabBoardCapture.TRIAL,
                                    )
                                }
                                .exceptionOrNull()
                                ?.message
                    },
                    enabled =
                        canStart &&
                            state.count + LabBoardCapture.count(LabBoardCapture.TRIAL) <= 100,
                ) {
                    Text("Board trial · 8 holds")
                }
            }
            Button(onClick = { showFaceTests = !showFaceTests }) {
                Text(if (showFaceTests) "Show board tests" else "Show face tests")
            }
        }
        if (!automatic.active && showFaceTests) {
            Button(onClick = { lab.toggleMeshStabilization() }, enabled = !state.locked) {
                Text(if (state.stabilizeMesh) "Mesh smoothing: On" else "Mesh smoothing: Off")
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(
                    onClick = { lab.toggleStereoCalibration() },
                    modifier = Modifier.weight(1f),
                    enabled = !state.locked && lab.trialsAvailable && time.logging,
                ) {
                    Text(
                        if (state.poseCorrection.stereo) "Use previous camera"
                        else "Use stereo calibration"
                    )
                }
                Button(
                    onClick = {
                        startError =
                            runCatching {
                                    lab.startAutomatic(
                                        single = false,
                                        geometry = true,
                                        rollOnly = true,
                                    )
                                }
                                .exceptionOrNull()
                                ?.message
                    },
                    modifier = Modifier.weight(1f),
                    enabled = canStart && state.count + 12 <= 100,
                ) {
                    Text("Roll trial · 4 holds")
                }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(
                    onClick = {
                        startError =
                            runCatching { lab.startAutomatic(single = true, geometry = true) }
                                .exceptionOrNull()
                                ?.message
                    },
                    modifier = Modifier.weight(1f),
                    enabled = canStart && state.count + 3 <= 100,
                ) {
                    Text("Geometry check")
                }
                Button(
                    onClick = {
                        startError =
                            runCatching { lab.startAutomatic(single = false, geometry = true) }
                                .exceptionOrNull()
                                ?.message
                    },
                    modifier = Modifier.weight(1f),
                    enabled =
                        canStart && state.count + LabProjectionReference.prompts.size * 3 <= 100,
                ) {
                    Text("Geometry trial")
                }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(
                    onClick = {
                        startError =
                            runCatching { lab.startAutomatic(single = true) }
                                .exceptionOrNull()
                                ?.message
                    },
                    modifier = Modifier.weight(1f),
                    enabled = canStart && state.count + 3 <= 100,
                ) {
                    Text("One check")
                }
                Button(
                    onClick = {
                        startError =
                            runCatching { lab.startAutomatic(single = false) }
                                .exceptionOrNull()
                                ?.message
                    },
                    modifier = Modifier.weight(1f),
                    enabled = canStart && state.count + 84 <= 100,
                ) {
                    Text("Full trial")
                }
            }
        }
    }
}
