// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.Manifest
import android.content.pm.PackageManager
import android.util.Log
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pico.spatial.ui.design.PicoTheme
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
    var adjustment by remember { mutableStateOf(FaceAdjustment.load(context)) }
    var adjusting by remember { mutableStateOf(false) }
    val scene = remember { FaceHelmetScene(geometry).also { it.fitScale = adjustment.scale } }
    val runner = remember {
        FaceLandmarkerRunner(context, backend = 2, poses = poses, lab = lab, helmetMode = true)
            .also { it.headShift = adjustment.headShift }
    }
    val adjust: (FaceAdjustment) -> Unit = { next ->
        adjustment = next
        scene.fitScale = next.scale
        runner.headShift = next.headShift
    }
    var initialized by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var paused by remember { mutableStateOf(false) }
    var effect by remember { mutableStateOf(FaceEffect.HELMET) }
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
                    error = "特效更新失败，请重新打开应用"
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
                        error = "特效显示失败，请重新打开应用"
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
                    scene.select(effect)
                    poses.start()
                    initialized = true
                } catch (cancel: CancellationException) {
                    throw cancel
                } catch (failure: Exception) {
                    error = "特效加载失败，请重新打开应用"
                    Log.e(FaceLandmarkerRunner.TAG, "helmet_initialization_error", failure)
                }
            },
            attachments = {
                AttachmentPanel(id = "helmet_controls") {
                    FaceSwapStrip(
                        selected = effect,
                        enabled = initialized,
                        paused = paused,
                        adjusting = adjusting,
                        adjustment = adjustment,
                        hint =
                            error
                                ?: when {
                                    !permission -> "需要相机权限才能识别人脸"
                                    paused -> "已暂停"
                                    !initialized -> "正在加载特效…"
                                    adjusting && visible -> "拖动滑块，让特效对准对方的脸"
                                    adjusting -> "先看向一个人，再拖动滑块"
                                    visible -> null
                                    status.startsWith("SpatialML error") ||
                                        status.startsWith("Error") -> "识别中断了，请重新打开应用"
                                    else -> "把头转向想换脸的人"
                                },
                        action =
                            if (permission) null
                            else
                                "允许使用相机" to
                                    {
                                        permissionLauncher.launch(Manifest.permission.CAMERA)
                                    },
                        onSelect = { chosen ->
                            effect = chosen
                            scene.select(chosen)
                            runner.tongueRequested = chosen == FaceEffect.DRAGON
                            runner.setOutputs(chosen.outputs)
                        },
                        onPause = {
                            paused = !paused
                            runner.paused = paused
                            if (paused) {
                                tracking.clear()
                                scene.hide()
                                visible = false
                            }
                        },
                        onSwitchPerson = {
                            runner.reacquire()
                            tracking.clear()
                            scene.hide()
                            visible = false
                        },
                        onAdjusting = { open ->
                            adjusting = open
                            if (!open) adjustment.save(context)
                        },
                        onAdjust = adjust,
                        onAdjustFinished = { adjustment.save(context) },
                    )
                }
            },
        )
    }
}
