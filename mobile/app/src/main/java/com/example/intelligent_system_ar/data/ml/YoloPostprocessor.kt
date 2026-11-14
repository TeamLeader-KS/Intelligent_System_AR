package com.example.intelligent_system_ar.data.ml

import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

data class LetterboxGeometry(val width: Int, val height: Int, val size: Int = 640) {
    init { require(width > 0 && height > 0 && size > 0) }
    private val scale = min(size.toFloat() / width, size.toFloat() / height)
    val scaledWidth = max(1, (width * scale).roundToInt())
    val scaledHeight = max(1, (height * scale).roundToInt())
    val left = (size - scaledWidth) / 2
    val top = (size - scaledHeight) / 2

    fun restore(cx: Float, cy: Float, w: Float, h: Float): DetectionBox? {
        if (!listOf(cx, cy, w, h).all { it.isFinite() } || w <= 0 || h <= 0) return null
        val l = ((cx - w / 2 - left) / scaledWidth).coerceIn(0f, 1f)
        val t = ((cy - h / 2 - top) / scaledHeight).coerceIn(0f, 1f)
        val r = ((cx + w / 2 - left) / scaledWidth).coerceIn(0f, 1f)
        val b = ((cy + h / 2 - top) / scaledHeight).coerceIn(0f, 1f)
        return if (l < r && t < b) DetectionBox(l, t, r, b) else null
    }
}

object YoloPostprocessor {
    const val THRESHOLD = 0.4f
    fun decode(output: Array<FloatArray>, labels: List<String>, geometry: LetterboxGeometry): List<Detection> {
        // ИЗМЕНЕНИЕ 1: Проверяем, что тензор теперь имеет размер 20 (4 координаты + 16 классов),
        // а меток ровно 16.
        require(output.size == 20 && labels.size == 16) { "Неподдерживаемый контракт модели" }

        val count = output[0].size
        require(output.all { it.size == count })
        val candidates = mutableListOf<Detection>()

        for (i in 0 until count) {
            var classId = -1
            var confidence = 0f

            // ИЗМЕНЕНИЕ 2: Перебираем 16 классов вместо 13.
            for (c in 0 until 16) {
                val score = output[4 + c][i]
                if (score.isFinite() && score > confidence) {
                    confidence = score
                    classId = c
                }
            }

            // Класс 5 — это "Без коррозии", его не выводим как дефект
            if (confidence <= THRESHOLD || confidence > 1f || classId == 5 || classId < 0) continue

            val box = geometry.restore(output[0][i], output[1][i], output[2][i], output[3][i]) ?: continue
            val known = classId < labels.size
            candidates += Detection(classId, labels.getOrElse(classId) { "Неизвестный класс $classId" },
                confidence, if (known) FindingKind.DEFECT else FindingKind.UNKNOWN, box)
        }

        val kept = mutableListOf<Detection>()
        for (candidate in candidates.sortedByDescending { it.confidence }) {
            if (kept.none { it.classId == candidate.classId && iou(it.box, candidate.box) > 0.45f }) kept += candidate
            if (kept.size == 20) break
        }
        return kept
    }

    private fun iou(a: DetectionBox, b: DetectionBox): Float {
        val intersection = max(0f, min(a.right, b.right) - max(a.left, b.left)) *
                max(0f, min(a.bottom, b.bottom) - max(a.top, b.top))
        val union = (a.right-a.left)*(a.bottom-a.top) + (b.right-b.left)*(b.bottom-b.top) - intersection
        return if (union > 0) intersection / union else 0f
    }

    fun toBuffer(box: DetectionBox, rotation: Int): DetectionBox = when ((rotation % 360 + 360) % 360) {
        0 -> box
        90 -> DetectionBox(box.top, 1f-box.right, box.bottom, 1f-box.left)
        180 -> DetectionBox(1f-box.right, 1f-box.bottom, 1f-box.left, 1f-box.top)
        270 -> DetectionBox(1f-box.bottom, box.left, 1f-box.top, box.right)
        else -> throw IllegalArgumentException("Поворот камеры должен быть кратен 90")
    }
}