// Copyright 2026 PICO. All rights reserved.
package com.pico.spatial.ml.sample.facelandmarker

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.pico.spatial.ui.design.Button
import com.pico.spatial.ui.design.ButtonDefaults
import com.pico.spatial.ui.design.HorizontalDivider
import com.pico.spatial.ui.design.Icon
import com.pico.spatial.ui.design.PicoTheme
import com.pico.spatial.ui.design.Slider
import com.pico.spatial.ui.design.Text
import com.pico.spatial.ui.design.ToggleButton
import com.pico.spatial.ui.design.ToggleButtonDefaults
import com.pico.spatial.ui.foundation.material.backgroundMaterial
import com.pico.spatial.ui.platform.Material
import kotlin.math.abs
import kotlin.math.roundToInt

internal class FaceSwapChoice(val effect: FaceEffect, val name: String, val icon: ImageVector)

internal val FaceSwapChoices =
    listOf(
        FaceSwapChoice(FaceEffect.HELMET, "钢铁侠头盔", FaceSwapIcons.helmet),
        FaceSwapChoice(FaceEffect.EYES, "大眼咧嘴", FaceSwapIcons.eyes),
        FaceSwapChoice(FaceEffect.HAT, "棒球帽", FaceSwapIcons.cap),
        FaceSwapChoice(FaceEffect.FLAG, "脸颊国旗", FaceSwapIcons.flag),
        FaceSwapChoice(FaceEffect.DRAGON, "中国龙", FaceSwapIcons.dragon),
    )

// Five 108 dp tiles and four 6 dp gaps; the sliders share this width so the glass does not resize.
private val StripWidth = 564.dp
// Spare room above the strip equal to what the sliders need below it. The panel is centred on its
// anchor, so this keeps the strip in place whether or not the sliders are open.
private val SliderRoom = 104.dp

/**
 * The whole face-swap UI: one glass strip of effects, then pause, re-target and fine-tune. [hint]
 * is the only status line and is absent while an effect is on a face. [action] replaces the bottom
 * buttons when the app is blocked on the wearer, e.g. the camera permission. While [adjusting], the
 * same glass grows three sliders and the bottom buttons become reset and done.
 */
@Composable
internal fun FaceSwapStrip(
    selected: FaceEffect,
    enabled: Boolean,
    paused: Boolean,
    adjusting: Boolean,
    adjustment: FaceAdjustment,
    hint: String?,
    action: Pair<String, () -> Unit>?,
    onSelect: (FaceEffect) -> Unit,
    onPause: () -> Unit,
    onSwitchPerson: () -> Unit,
    onAdjusting: (Boolean) -> Unit,
    onAdjust: (FaceAdjustment) -> Unit,
    onAdjustFinished: () -> Unit,
) {
    Column(
        Modifier.size(600.dp, 236.dp + SliderRoom * 2).padding(top = SliderRoom),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // Fixed slot: the strip must not jump when the hint comes and goes.
        Box(Modifier.height(40.dp), contentAlignment = Alignment.Center) {
            if (hint != null)
                Box(
                    Modifier.clip(RoundedCornerShape(20.dp))
                        .backgroundMaterial(enable = true, style = Material.Regular)
                        .padding(horizontal = 16.dp, vertical = 8.dp)
                ) {
                    Text(
                        hint,
                        style = PicoTheme.typography.bodyMedium,
                        color = PicoTheme.colorScheme.labelPrimary,
                    )
                }
        }
        Column(
            Modifier.clip(RoundedCornerShape(32.dp))
                .backgroundMaterial(enable = true, style = Material.Regular)
                .padding(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                for (choice in FaceSwapChoices) ToggleButton(
                    checked = choice.effect == selected,
                    onCheckedChange = { if (it) onSelect(choice.effect) },
                    enabled = enabled,
                    size = ToggleButtonDefaults.toggleButtonSize(width = 108.dp, height = 92.dp),
                    contentPadding = PaddingValues(4.dp),
                    shape = RoundedCornerShape(24.dp),
                ) {
                    Column(
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Icon(
                            choice.icon,
                            contentDescription = null,
                            modifier = Modifier.size(34.dp),
                        )
                        Text(choice.name, style = PicoTheme.typography.bodyMedium, maxLines = 1)
                    }
                }
            }
            if (adjusting) {
                HorizontalDivider(Modifier.width(StripWidth))
                Row(
                    Modifier.width(StripWidth).padding(horizontal = 12.dp),
                    horizontalArrangement = Arrangement.spacedBy(20.dp),
                ) {
                    AdjustSlider(
                        "大小",
                        "${(adjustment.scale * 100).roundToInt()}%",
                        adjustment.scale,
                        FaceAdjustment.SCALE,
                        { onAdjust(adjustment.copy(scale = (it * 100).roundToInt() / 100f)) },
                        onAdjustFinished,
                    )
                    AdjustSlider(
                        "左右",
                        shiftText(adjustment.rightCm, "左", "右"),
                        adjustment.rightCm,
                        FaceAdjustment.SHIFT_CM,
                        { onAdjust(adjustment.copy(rightCm = (it * 2).roundToInt() / 2f)) },
                        onAdjustFinished,
                    )
                    AdjustSlider(
                        "上下",
                        shiftText(adjustment.upCm, "下", "上"),
                        adjustment.upCm,
                        FaceAdjustment.SHIFT_CM,
                        { onAdjust(adjustment.copy(upCm = (it * 2).roundToInt() / 2f)) },
                        onAdjustFinished,
                    )
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            if (action != null) {
                Button(onClick = action.second) { Text(action.first) }
            } else if (adjusting) {
                Button(
                    onClick = {
                        onAdjust(FaceAdjustment())
                        onAdjustFinished()
                    },
                    enabled = adjustment != FaceAdjustment(),
                    leadingIcon = { Icon(FaceSwapIcons.reset, contentDescription = null) },
                ) {
                    Text("重置")
                }
                Button(
                    onClick = { onAdjusting(false) },
                    colors =
                        ButtonDefaults.buttonColors(
                            containerColor = PicoTheme.colorScheme.interaction,
                            contentColor = PicoTheme.colorScheme.labelPrimaryLight,
                        ),
                    leadingIcon = { Icon(FaceSwapIcons.check, contentDescription = null) },
                ) {
                    Text("完成")
                }
            } else {
                Button(
                    onClick = onPause,
                    enabled = enabled,
                    leadingIcon = {
                        Icon(
                            if (paused) FaceSwapIcons.play else FaceSwapIcons.pause,
                            contentDescription = null,
                        )
                    },
                ) {
                    Text(if (paused) "继续" else "暂停")
                }
                Button(
                    onClick = onSwitchPerson,
                    enabled = enabled && !paused,
                    leadingIcon = { Icon(FaceSwapIcons.swap, contentDescription = null) },
                ) {
                    Text("换一个人")
                }
                Button(
                    onClick = { onAdjusting(true) },
                    enabled = enabled && !paused,
                    leadingIcon = { Icon(FaceSwapIcons.tune, contentDescription = null) },
                ) {
                    Text("微调")
                }
            }
        }
    }
}

@Composable
private fun RowScope.AdjustSlider(
    name: String,
    value: String,
    position: Float,
    range: ClosedFloatingPointRange<Float>,
    onChange: (Float) -> Unit,
    onFinished: () -> Unit,
) {
    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(
                name,
                style = PicoTheme.typography.bodyMedium,
                color = PicoTheme.colorScheme.labelPrimary,
            )
            Text(
                value,
                style = PicoTheme.typography.bodyMedium,
                color = PicoTheme.colorScheme.labelSecondary,
            )
        }
        Slider(
            value = position,
            onValueChange = onChange,
            modifier = Modifier.fillMaxWidth(),
            valueRange = range,
            onValueChangeFinished = onFinished,
        )
    }
}

private fun shiftText(cm: Float, negative: String, positive: String): String {
    if (cm == 0f) return "居中"
    val size = abs(cm)
    val amount = if (size % 1f == 0f) size.toInt().toString() else size.toString()
    return "${if (cm < 0) negative else positive} $amount 厘米"
}
