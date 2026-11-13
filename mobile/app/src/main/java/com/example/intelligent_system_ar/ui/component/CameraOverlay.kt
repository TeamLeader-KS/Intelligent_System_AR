package com.example.intelligent_system_ar.ui.component

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.intelligent_system_ar.data.model.ScanResult
import com.example.intelligent_system_ar.data.model.ScanStatus
import com.example.intelligent_system_ar.ui.theme.ArOutline
import com.example.intelligent_system_ar.ui.theme.ArScrim
import com.example.intelligent_system_ar.ui.theme.ArSurfaceHigh
import com.example.intelligent_system_ar.ui.theme.ArTextPrimary
import com.example.intelligent_system_ar.ui.theme.statusColor
import kotlin.math.roundToInt

/**
 * AR-слой поверх камеры (по макету):
 *  - контур всего оборудования + подпись («Компрессор»);
 *  - маркер проблемного узла + линия к подписи дефекта («Поломка двигателя»);
 *  - плашка «Сообщить!» рядом с объектом;
 *  - тап по рамке оборудования открывает/закрывает карточку.
 * Все bbox нормализованы (0..1).
 */
@Composable
fun CameraOverlay(
    result: ScanResult?,
    canReport: Boolean,
    onEquipmentClick: () -> Unit,
    onReportClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    if (result == null) return

    val density = LocalDensity.current
    val px: (Float) -> Float = { it * density.density }

    val transition = rememberInfiniteTransition(label = "pulse")
    val pulse by transition.animateFloat(
        initialValue = 1f,
        targetValue = 0.55f,
        animationSpec = infiniteRepeatable(tween(700), RepeatMode.Reverse),
        label = "pulseAlpha"
    )

    val paint = remember {
        android.graphics.Paint().apply {
            isAntiAlias = true
            isFakeBoldText = true
        }
    }

    val baseColor = result.status.statusColor()
    val frameColor = if (result.status == ScanStatus.CRITICAL) baseColor.copy(alpha = pulse) else baseColor

    BoxWithConstraints(modifier = modifier) {
        val wPx = constraints.maxWidth.toFloat()
        val hPx = constraints.maxHeight.toFloat()

        // ---- геометрия оборудования
        val eq = result.equipmentBox
        val left = eq.x1 * wPx
        val top = eq.y1 * hPx
        val right = eq.x2 * wPx
        val bottom = eq.y2 * hPx

        // ---- размеры подписей
        val margin = px(8f)
        val gap = px(8f)
        val padH = px(12f)
        val padV = px(7f)
        paint.textSize = with(density) { 15.sp.toPx() }
        val fm = paint.fontMetrics
        val chipH = fm.descent - fm.ascent + 2 * padV

        // Подпись оборудования: над рамкой, если не хватает места — под рамкой
        val eqLabel = if (result.status == ScanStatus.OK || result.status == ScanStatus.UNKNOWN) {
            "${result.equipmentName}: ${result.status.titleRu}"
        } else {
            result.equipmentName
        }
        val eqChipW = paint.measureText(eqLabel) + 2 * padH
        val eqChipLeft = left.coerceIn(margin, maxOf(margin, wPx - eqChipW - margin))
        val eqAbove = top - gap - chipH >= px(96f)
        val eqChipTop = if (eqAbove) top - gap - chipH else bottom + gap

        // Дефект: подпись под оборудованием, линия к узлу
        val defect = result.primaryDefect.takeIf {
            result.status == ScanStatus.WARNING || result.status == ScanStatus.CRITICAL
        }
        val dText = defect?.title.orEmpty()
        val dChipW = if (defect != null) paint.measureText(dText) + 2 * padH else 0f
        val dMin = margin + dChipW / 2
        val dChipCx = ((left + right) / 2).coerceIn(dMin, maxOf(dMin, wPx - margin - dChipW / 2))
        var belowY = bottom + gap
        if (!eqAbove) belowY += chipH + gap
        val dChipTop = belowY + px(20f)

        // Кнопка «Сообщить!» под подписью дефекта
        val btnW = px(124f)
        val btnY = dChipTop + chipH + px(10f)
        val btnX = (dChipCx - btnW / 2).coerceIn(margin, maxOf(margin, wPx - btnW - margin))

        // ---- рисование
        Canvas(Modifier.fillMaxSize()) {
            val corner = CornerRadius(px(14f))
            val eqTopLeft = Offset(left, top)
            val eqSize = Size(right - left, bottom - top)

            drawRoundRect(frameColor.copy(alpha = 0.10f), eqTopLeft, eqSize, corner)
            drawRoundRect(frameColor.copy(alpha = frameColor.alpha * 0.30f), eqTopLeft, eqSize, corner, style = Stroke(px(10f)))
            drawRoundRect(frameColor, eqTopLeft, eqSize, corner, style = Stroke(px(4f)))

            drawChip(eqLabel, paint, eqChipLeft, eqChipTop, eqChipW, chipH, baseColor)

            if (defect != null) {
                val dl = defect.box.x1 * wPx
                val dt = defect.box.y1 * hPx
                val dr = defect.box.x2 * wPx
                val db = defect.box.y2 * hPx

                drawRoundRect(
                    color = frameColor,
                    topLeft = Offset(dl, dt),
                    size = Size(dr - dl, db - dt),
                    cornerRadius = CornerRadius(px(8f)),
                    style = Stroke(px(3f))
                )
                val start = Offset((dl + dr) / 2, db)
                val end = Offset(dChipCx, dChipTop)
                drawLine(baseColor, start, end, strokeWidth = px(2f), cap = StrokeCap.Round)
                drawCircle(baseColor, radius = px(4f), center = start)

                drawChip(dText, paint, dChipCx - dChipW / 2, dChipTop, dChipW, chipH, baseColor)
            }
        }

        // ---- тап по оборудованию -> карточка
        Box(
            Modifier
                .offset { IntOffset(left.roundToInt(), top.roundToInt()) }
                .size(
                    with(density) { (right - left).toDp() },
                    with(density) { (bottom - top).toDp() }
                )
                .clickable(
                    interactionSource = remember { MutableInteractionSource() },
                    indication = null,
                    onClick = onEquipmentClick
                )
        )

        // ---- «Сообщить!» прямо в AR-сцене
        if (canReport && defect != null) {
            Button(
                onClick = onReportClick,
                shape = RoundedCornerShape(12.dp),
                border = BorderStroke(1.dp, ArOutline),
                contentPadding = PaddingValues(horizontal = 8.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = ArSurfaceHigh.copy(alpha = 0.92f),
                    contentColor = ArTextPrimary
                ),
                modifier = Modifier
                    .offset { IntOffset(btnX.roundToInt(), btnY.roundToInt()) }
                    .width(124.dp)
                    .height(40.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Warning,
                    contentDescription = null,
                    tint = baseColor,
                    modifier = Modifier.size(16.dp)
                )
                Spacer(Modifier.width(6.dp))
                Text("Сообщить!", style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}

/** Тёмная «таблетка» с цветной рамкой и цветным текстом: читается на любом фоне. */
private fun DrawScope.drawChip(
    text: String,
    paint: android.graphics.Paint,
    left: Float,
    top: Float,
    width: Float,
    height: Float,
    color: Color
) {
    val radius = CornerRadius(height / 2)
    drawRoundRect(ArScrim.copy(alpha = 0.78f), Offset(left, top), Size(width, height), radius)
    drawRoundRect(color, Offset(left, top), Size(width, height), radius, style = Stroke(2.dp.toPx()))

    paint.color = color.toArgb()
    val fm = paint.fontMetrics
    val baseline = top + height / 2 - (fm.ascent + fm.descent) / 2
    drawContext.canvas.nativeCanvas.drawText(
        text,
        left + (width - paint.measureText(text)) / 2,
        baseline,
        paint
    )
}
