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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
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
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject

/** Selectable face effects consume retained tracking; surface uploads never pace rendering. */
@Composable
fun FaceHelmetSample() {
    val context = LocalContext.current.applicationContext
    val lab = remember {
        if (context.packageName.endsWith(".registrationlab"))
            FaceRegistrationLab(context, helmetMode = true)
        else null
    }
    val scope = rememberCoroutineScope()
    val exit: () -> Unit = {
        scope.launch { closeStage() }
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
    val geometry = remember { FaceGeometry.load(context) }
    val poses = remember { StagePoseHistory() }
    val tracking = remember { FaceTrackingState() }
    val surfaces = remember { Channel<TrackedFace>(Channel.CONFLATED) }
    val scene = remember { FaceHelmetScene(geometry) }
    val runner = remember {
        FaceLandmarkerRunner(context, backend = 2, poses = poses, lab = lab, helmetMode = true)
    }
    var initialized by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var paused by remember { mutableStateOf(false) }
    var fit by remember { mutableFloatStateOf(1f) }
    var effect by remember { mutableStateOf(FaceEffect.MESH) }
    var visible by remember { mutableStateOf(false) }
    val status by runner.status.collectAsStateWithLifecycle()
    DisposableEffect(runner, scene, lab) {
        onDispose {
            runner.close()
            surfaces.close()
            poses.close()
            scene.close()
            lab?.close()
        }
    }
    LaunchedEffect(Unit) { if (!permission) permissionLauncher.launch(Manifest.permission.CAMERA) }
    LaunchedEffect(permission, initialized) { if (permission && initialized) runner.start() }
    LaunchedEffect(initialized) {
        if (initialized)
            lab?.occlusionProbe?.collect { mode ->
                try {
                    scene.setOcclusionProbe(mode)
                } catch (cancel: CancellationException) {
                    throw cancel
                } catch (failure: Exception) {
                    Log.e(FaceLandmarkerRunner.TAG, "face_occlusion_probe_error", failure)
                }
            }
    }
    LaunchedEffect(runner) {
        runner.outputs.collect { outputs ->
            if (!outputs.any) {
                tracking.clear()
                scene.hide()
                visible = false
            }
        }
    }
    LaunchedEffect(initialized) {
        if (initialized)
            runner.frame.collect { frame ->
                try {
                    if (paused) {
                        return@collect
                    }
                    tracking.offer(frame, System.nanoTime() * 1e-9)?.let { surfaces.trySend(it) }
                } catch (cancel: CancellationException) {
                    throw cancel
                } catch (failure: Exception) {
                    Log.e(FaceLandmarkerRunner.TAG, "face_measurement_rejected", failure)
                }
            }
    }
    LaunchedEffect(initialized) {
        if (initialized)
            for (face in surfaces) {
                if (
                    paused ||
                        tracking.current(System.nanoTime() * 1e-9)?.generation != face.generation
                )
                    continue
                try {
                    val timing = scene.updateSurface(face)
                    lab?.timeline?.event("face_effect_surface_upload", timing)
                } catch (cancel: CancellationException) {
                    throw cancel
                } catch (failure: Exception) {
                    // An already measured surface remains usable; do not blink on a shape-upload
                    // miss.
                    error = "Face surface update failed: ${failure.message}"
                    Log.e(FaceLandmarkerRunner.TAG, "face_surface_error", failure)
                }
            }
    }
    LaunchedEffect(initialized) {
        if (initialized)
            while (isActive) withFrameNanos { nanos ->
                val wasVisible = visible
                val current = if (paused) null else tracking.current(System.nanoTime() * 1e-9)
                val applied =
                    try {
                        scene.render(current, nanos)
                    } catch (cancel: CancellationException) {
                        throw cancel
                    } catch (failure: Exception) {
                        scene.hide()
                        error = "Face effect could not render: ${failure.message}"
                        Log.e(FaceLandmarkerRunner.TAG, "face_effect_render_error", failure)
                        null
                    }
                visible = scene.visible
                if (visible) error = null
                if (applied != null) lab?.helmetApplied(applied)
                if (wasVisible && !visible)
                    lab?.helmetApplied(
                        JSONObject()
                            .put("visible", false)
                            .put("reason", if (paused) "paused" else "tracking_expired_or_changed")
                    )
            }
    }
    LaunchedEffect(initialized) {
        if (initialized)
            while (isActive) {
                lab?.timeline?.tick()
                delay(100)
            }
    }
    PicoTheme {
        SpatialView(
            modifier = Modifier.fillMaxSize(),
            initial = { content, attachments ->
                try {
                    scene.initialize(content, attachments.entity("helmet_controls"))
                    poses.start()
                    initialized = true
                } catch (cancel: CancellationException) {
                    throw cancel
                } catch (failure: Exception) {
                    error = "Face effects could not load: ${failure.message}"
                    Log.e(FaceLandmarkerRunner.TAG, "helmet_initialization_error", failure)
                }
            },
            attachments = {
                AttachmentPanel(id = "helmet_controls") {
                    Column(
                        Modifier.size(660.dp, 640.dp).padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text(
                            "Face effects · ${effect.label}",
                            style = PicoTheme.typography.titleMedium,
                        )
                        Text(
                            error
                                ?: when {
                                    !permission -> "Camera access is needed to find a face."
                                    paused -> "Paused"
                                    !initialized -> "Loading face effects…"
                                    visible -> effect.description
                                    status.startsWith("SpatialML error") ||
                                        status.startsWith("Error") -> status
                                    else -> "Look toward another person to place the effect."
                                }
                        )
                        if (!permission)
                            Button(
                                onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) }
                            ) {
                                Text("Allow camera")
                            }
                        FaceEffectChoices(effect, initialized) { chosen ->
                            effect = chosen
                            scene.select(chosen)
                            runner.tongueRequested = chosen == FaceEffect.DRAGON
                            runner.setOutputs(chosen.outputs)
                        }
                        Text("Accessory / mask fit")
                        Slider(
                            value = fit,
                            onValueChange = {
                                fit = it
                                scene.fitScale = it
                            },
                            valueRange = .8f..1.2f,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Button(
                                onClick = {
                                    paused = !paused
                                    runner.paused = paused
                                    if (paused) {
                                        tracking.clear()
                                        scene.hide()
                                        visible = false
                                    }
                                },
                                enabled = initialized,
                            ) {
                                Text(if (paused) "Resume" else "Pause")
                            }
                            Button(
                                onClick = {
                                    fit = 1f
                                    scene.fitScale = 1f
                                }
                            ) {
                                Text("Reset fit")
                            }
                            Button(onClick = exit) { Text("Close") }
                        }
                    }
                }
            },
        )
    }
}
