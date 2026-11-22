// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.Manifest
import android.content.pm.PackageManager
import android.util.Log
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pico.spatial.ui.design.Button
import com.pico.spatial.ui.design.PicoTheme
import com.pico.spatial.ui.design.Slider
import com.pico.spatial.ui.design.Text
import com.pico.spatial.ui.foundation.content.SpatialView
import com.pico.spatial.ui.platform.containers.closeStage
import java.util.Locale
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

@Composable
fun FaceLandmarkerSample() {
    val context = LocalContext.current
    val appContext = context.applicationContext
    val lab = remember {
        if (appContext.packageName.endsWith(".registrationlab")) FaceRegistrationLab(appContext)
        else null
    }
    DisposableEffect(lab) { onDispose { lab?.close() } }
    val uiScope = rememberCoroutineScope()
    val exit: () -> Unit = {
        uiScope.launch { closeStage() }
        Unit
    }
    BackHandler(onBack = exit)
    var permission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED
        )
    }
    val permissionLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
            permission = it
        }
    var revision by remember { mutableIntStateOf(0) }
    var size by remember { mutableFloatStateOf(1f) }
    var paused by remember { mutableStateOf(false) }
    val geometry = remember { FaceGeometry.load(appContext) }
    val scene = remember { FaceMeshScene(geometry) }
    val runner =
        remember(permission, revision) {
            FaceLandmarkerRunner(appContext, backend = 2, poses = scene.poses, lab = lab)
        }
    var initialized by remember { mutableStateOf(false) }
    var sceneError by remember { mutableStateOf<String?>(null) }
    val frame by runner.frame.collectAsStateWithLifecycle()
    val status by runner.status.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) { if (!permission) permissionLauncher.launch(Manifest.permission.CAMERA) }
    DisposableEffect(runner) { onDispose { runner.close() } }
    LaunchedEffect(runner, permission, initialized) {
        if (permission && initialized) runner.start()
    }
    DisposableEffect(scene) { onDispose { scene.close() } }
    LaunchedEffect(runner, scene, initialized) {
        if (initialized) {
            // Complete each resource replacement. StateFlow supplies the newest frame afterward;
            // fast inference must not repeatedly cancel a slower native mesh update.
            runner.frame.collect { next ->
                try {
                    scene.update(next)
                    lab?.sceneApplied(
                        next,
                        scene.face.enabled,
                        scene.uploadedGeometry,
                        scene.stabilization,
                        scene.uploadTiming,
                    )
                } catch (cancel: CancellationException) {
                    throw cancel
                } catch (error: Exception) {
                    scene.face.enabled = false
                    lab?.sceneApplied(null, false)
                    sceneError = "Mesh error: ${error.message}"
                    Log.e(FaceLandmarkerRunner.TAG, sceneError, error)
                }
            }
        }
    }

    PicoTheme {
        SpatialView(
            modifier = Modifier.fillMaxSize(),
            initial = { content, attachments ->
                try {
                    scene.initialize(content, attachments.entity("controls"))
                    initialized = true
                } catch (cancel: CancellationException) {
                    throw cancel
                } catch (error: Exception) {
                    sceneError = "Mesh error: ${error.message}"
                    Log.e(FaceLandmarkerRunner.TAG, sceneError, error)
                }
            },
            attachments = {
                AttachmentPanel(id = "controls") {
                    if (lab != null) {
                        Column(Modifier.size(740.dp, 580.dp).padding(12.dp)) {
                            LabTimelineBadge(lab, scene, runner, geometry)
                        }
                    } else {
                        Column(
                            Modifier.size(640.dp, 720.dp).padding(24.dp),
                            verticalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            Text(
                                "SpatialML Face Landmarker",
                                style = PicoTheme.typography.titleMedium,
                                color = PicoTheme.colorScheme.labelPrimary,
                            )
                            Button(onClick = exit) { Text("Close sample") }
                            Text(
                                sceneError
                                    ?: if (permission) status else "Camera permission is required",
                                style = PicoTheme.typography.bodyMedium,
                                color = PicoTheme.colorScheme.labelPrimary,
                            )
                            Text(
                                "Point the headset camera toward a face.",
                                style = PicoTheme.typography.bodySmall,
                                color = PicoTheme.colorScheme.labelPrimary,
                            )
                            if (!permission) {
                                Button(
                                    onClick = {
                                        permissionLauncher.launch(Manifest.permission.CAMERA)
                                    }
                                ) {
                                    Text("Grant camera access")
                                }
                            } else {
                                FaceOutputControls(runner)
                                Text(
                                    String.format(Locale.US, "Face size / depth: %.2f×", size),
                                    color = PicoTheme.colorScheme.labelPrimary,
                                )
                                Slider(
                                    value = size,
                                    onValueChange = {
                                        size = it
                                        runner.sizeScale = it
                                    },
                                    valueRange = .5f..1.5f,
                                )
                                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                    Button(
                                        onClick = {
                                            size = 1f
                                            runner.sizeScale = 1f
                                        }
                                    ) {
                                        Text("Reset size / depth")
                                    }
                                    Button(
                                        onClick = {
                                            paused = !paused
                                            runner.paused = paused
                                        }
                                    ) {
                                        Text(if (paused) "Resume" else "Pause")
                                    }
                                    if (status.startsWith("SpatialML error")) {
                                        Button(
                                            onClick = {
                                                revision += 1
                                                paused = false
                                                size = 1f
                                            }
                                        ) {
                                            Text("Retry")
                                        }
                                    }
                                }
                                FaceOutputSummary(frame, geometry)
                            }
                        }
                    }
                }
            },
        )
    }
}
