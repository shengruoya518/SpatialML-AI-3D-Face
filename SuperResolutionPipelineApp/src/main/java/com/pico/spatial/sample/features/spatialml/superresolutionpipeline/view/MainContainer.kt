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

package com.pico.spatial.sample.features.spatialml.superresolutionpipeline.view

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pico.spatial.sample.features.spatialml.superresolutionpipeline.vm.SrViewModel
import com.pico.spatial.sample.features.spatialml.superresolutionpipeline.vm.SrViewModel.AppMode
import com.pico.spatial.ui.design.Button
import com.pico.spatial.ui.design.ButtonDefaults.buttonColors
import com.pico.spatial.ui.design.PicoTheme
import com.pico.spatial.ui.design.Text
import com.pico.spatial.ui.design.defaultColorScheme
import com.pico.spatial.ui.foundation.material.backgroundMaterial
import com.pico.spatial.ui.foundation.vibrant.Vibrant
import com.pico.spatial.ui.foundation.vibrant.withVibrant
import com.pico.spatial.ui.graphics.Vibrant

/**
 * The first and backbone UI in the super-resolution window container after launched. It gives users
 * a selection between SpatialML and RelaxMR mode, and calling SpatialML functionalities according
 * to the user choices.
 *
 * @param srViewModel the viewmodel, maintaining SpatialML session (as well as resources) and
 *   connection to the VQA RESTFul API.
 */
@Preview
@Composable
fun MainContainer(srViewModel: SrViewModel = viewModel()) {
    DisposableEffect(srViewModel) { onDispose { srViewModel.stop() } }

    val appMode by srViewModel.appMode.collectAsStateWithLifecycle()

    when (appMode) {
        AppMode.NO_SELECTION ->
            PicoTheme(
                colorScheme =
                    defaultColorScheme(
                        fillPrimary = Color.Vibrant.withVibrant(Vibrant.Light),
                        labelPrimaryLight = Color.Vibrant.withVibrant(Vibrant.Darkest),
                    )
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.backgroundMaterial(true),
                ) {
                    Text(
                        "Super Resolution — Pipeline",
                        textAlign = TextAlign.Center,
                        fontSize = 8.em,
                        softWrap = false,
                        modifier =
                            Modifier.padding(start = 10.dp, end = 10.dp, top = 20.dp, bottom = 8.dp),
                    )
                    Text(
                        "The app can be run in SpatialML mode or RelaxMR mode. In SpatialML mode, the" +
                            " zoomed camera image will be handled securely by the system, and rendered" +
                            " in a separated window, isolated from the app to fully protect users privacy." +
                            " In RelaxMR mode, the zoomed camera image will be returned to the app," +
                            " allowing for better user interfaces, but will request the user to explicitly" +
                            " allow the app to access the camera data.",
                        textAlign = TextAlign.Justify,
                        fontSize = 4.em,
                        softWrap = true,
                        modifier =
                            Modifier.padding(start = 40.dp, end = 40.dp, top = 35.dp, bottom = 8.dp),
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceAround,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Button(
                            onClick = { srViewModel.updateAppMode(AppMode.SECURE_MR) },
                            modifier = Modifier.padding(12.dp),
                            colors = buttonColors(Color.White),
                        ) {
                            Text("SpatialML mode", color = Color.Black)
                        }

                        Button(
                            onClick = { srViewModel.updateAppMode(AppMode.RELAX_MR) },
                            modifier = Modifier.padding(12.dp),
                            colors = buttonColors(Color.Black),
                        ) {
                            Text("RelaxMR mode", color = Color.White)
                        }
                    }
                }
            }

        AppMode.RELAX_MR -> CameraConfirm(srViewModel)
        AppMode.SECURE_MR -> SpatialMLConfirm(srViewModel)
        else -> SuperResolutionSpatialView(srViewModel)
    }
}
