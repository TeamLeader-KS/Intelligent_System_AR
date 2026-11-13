package com.example.intelligent_system_ar.ui.component

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.imageResource

/**
 * Загружает картинку из res/drawable по имени файла (без расширения, строчными буквами).
 * Возвращает null, если файла нет или он не декодировался — тогда кнопка рисует запасной вариант.
 * Проект собирается и без картинки: ресурс ищется по имени, а не через R.drawable.
 */
@Composable
fun rememberDrawableBitmap(name: String): ImageBitmap? {
    val context = LocalContext.current
    return remember(name) {
        runCatching {
            val id = context.resources.getIdentifier(name, "drawable", context.packageName)
            if (id != 0) ImageBitmap.imageResource(context.resources, id) else null
        }.getOrNull()
    }
}
