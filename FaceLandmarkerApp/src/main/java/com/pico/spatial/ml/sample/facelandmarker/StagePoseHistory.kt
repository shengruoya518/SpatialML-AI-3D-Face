// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import android.util.Log
import com.pico.spatial.core.math.Quat
import com.pico.spatial.core.math.Vector3
import com.pico.spatial.tracking.DataProvider
import com.pico.spatial.tracking.hmd.HMDTrackingData
import com.pico.spatial.tracking.hmd.HMDTrackingProvider

/** Stage HMD poses sampled on the tracking callback, indexed by the same monotonic clock as VST. */
internal class StagePoseHistory : AutoCloseable {
    private class Sample(val time: Double, val position: Vector3, val rotation: Quat)

    private val provider = HMDTrackingProvider()
    private val samples = ArrayDeque<Sample>()
    private var started = false
    private val listener =
        object : DataProvider.DataListener<HMDTrackingData> {
            override fun onProvideData(data: HMDTrackingData) {
                val pose = data.hmdPose
                if (!pose.position.isFinite()) return
                synchronized(samples) {
                    // SDK 6.1.9 does not expose the tracking timestamp in Kotlin. Timestamp the
                    // direct
                    // callback before any UI dispatch; reject stale/gapped history instead of
                    // substituting
                    // a render-time pose. This follows the Unity sample's capture-time pose
                    // history.
                    samples.addLast(Sample(System.nanoTime() * 1e-9, pose.position, pose.rotation))
                    while (samples.size > 2048) samples.removeFirst()
                }
            }
        }

    fun start() {
        if (started) return
        started = true
        provider.addListener(listener)
        val result = provider.start()
        Log.i(
            FaceLandmarkerRunner.TAG,
            "stage_pose_history start=$result support=${provider.supportState}",
        )
    }

    val ready: Boolean
        get() =
            provider.supportState == DataProvider.SupportState.SUPPORTED &&
                atCapture(System.nanoTime() * 1e-9) != null

    fun atCapture(seconds: Double): FloatArray? =
        synchronized(samples) {
            if (samples.isEmpty()) return@synchronized null
            if (!seconds.isFinite() || seconds < samples.first().time) return@synchronized null
            val latest = samples.last()
            if (seconds >= latest.time) {
                return@synchronized if (seconds - latest.time <= .05)
                    pose(latest.position, latest.rotation)
                else null
            }
            var previous: Sample? = null
            for (next in samples) {
                val older = previous
                if (next.time >= seconds && older != null) {
                    val gap = next.time - older.time
                    if (gap <= 0 || gap > .1) return@synchronized null
                    val alpha = ((seconds - older.time) / gap).toFloat().coerceIn(0f, 1f)
                    return@synchronized pose(
                        older.position + (next.position - older.position) * alpha,
                        Quat.slerp(older.rotation, next.rotation, alpha),
                    )
                }
                previous = next
            }
            null
        }

    /** Export callback-arrival times explicitly; these are not hardware sensor timestamps. */
    fun snapshot(from: Double, until: Double): List<Pair<Double, FloatArray>> =
        synchronized(samples) {
            val before = samples.lastOrNull { it.time <= from }
            val window = samples.filter { it.time > from && it.time <= until }
            (listOfNotNull(before) + window).map { it.time to pose(it.position, it.rotation) }
        }

    private fun pose(position: Vector3, rotation: Quat): FloatArray {
        val matrix = rotation.toMatrix()
        return FloatArray(16) { index ->
            when (index) {
                3 -> position.x
                7 -> position.y
                11 -> position.z
                else -> matrix[index / 4, index % 4]
            }
        }
    }

    override fun close() {
        if (!started) return
        started = false
        provider.removeListener(listener)
        provider.stop()
        synchronized(samples) { samples.clear() }
    }
}
