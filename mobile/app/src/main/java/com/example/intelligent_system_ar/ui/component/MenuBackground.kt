package com.example.intelligent_system_ar.ui.component

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import kotlin.math.roundToInt

private const val MENU_BACKGROUND_NAME = "menu_background"

@Composable
fun Modifier.menuBackground(): Modifier {
    val image: ImageBitmap = rememberDrawableBitmap(MENU_BACKGROUND_NAME) ?: return this
    return this
        .clipToBounds() // Чтобы картинка не вылезала за скругленные углы Surface
        .drawBehind {
            drawImageFillBounds(image)
        }
}

/**
 * Аналог JavaFX: fitWidthProperty().bind() + fitHeightProperty().bind() + setPreserveRatio(false).
 * Жестко растягивает картинку под размер контейнера (игнорирует пропорции).
 */
private fun DrawScope.drawImageFillBounds(image: ImageBitmap) {
    drawImage(
        image = image,
        dstOffset = IntOffset(0, 0), // Начинаем с левого верхнего угла
        dstSize = IntSize(size.width.roundToInt(), size.height.roundToInt()) // Растягиваем на 100% ширины и высоты
    )
}