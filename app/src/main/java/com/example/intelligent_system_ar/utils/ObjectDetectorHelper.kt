package com.example.intelligent_system_ar.utils

import android.content.Context
import android.graphics.Bitmap
import android.graphics.RectF
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.support.common.FileUtil
import java.io.BufferedReader
import java.io.InputStreamReader
import java.nio.ByteBuffer
import java.nio.ByteOrder

data class Detection(
    val boundingBox: RectF, // Координаты [0..1] относительно картинки
    val label: String,
    val confidence: Float
)

class ObjectDetectorHelper(context: Context) {
    private var interpreter: Interpreter
    private val labels: List<String>
    private val inputSize = 640

    init {
        // Загружаем модель из assets
        val model = FileUtil.loadMappedFile(context, "best_float16.tflite")
        val options = Interpreter.Options().apply {
            setNumThreads(4)
        }
        interpreter = Interpreter(model, options)

        // Загружаем классы из labels.txt
        val labelStream = context.assets.open("labels.txt")
        labels = BufferedReader(InputStreamReader(labelStream)).use { reader ->
            reader.readLines()
        }
    }

    fun detect(image: Bitmap): List<Detection> {
        // 1. Подготавливаем картинку (640x640)
        val resizedBitmap = Bitmap.createScaledBitmap(image, inputSize, inputSize, true)
        val inputBuffer = convertBitmapToByteBuffer(resizedBitmap)

        // 2. Формат вывода YOLOv8: [1, 4 + num_classes, 8400]
        val outputShape = interpreter.getOutputTensor(0).shape()
        val outputArray = Array(outputShape[0]) { Array(outputShape[1]) { FloatArray(outputShape[2]) } }

        // 3. Запускаем модель
        interpreter.run(inputBuffer, outputArray)

        // 4. Парсим результаты (Упрощенный парсер для YOLOv8)
        val detections = mutableListOf<Detection>()
        val numClasses = labels.size
        val rows = outputShape[2] // 8400 боксов
        val cols = outputShape[1] // 4 (координаты) + классы

        for (i in 0 until rows) {
            var maxClassScore = 0f
            var classId = -1

            // Ищем класс с максимальной уверенностью
            for (c in 0 until numClasses) {
                val score = outputArray[0][4 + c][i]
                if (score > maxClassScore) {
                    maxClassScore = score
                    classId = c
                }
            }

            // Если уверенность > 0.4
            if (maxClassScore > 0.4f && classId != -1) {
                // Координаты YOLOv8 (cx, cy, w, h) нормализованы от 0 до 1
                val cx = outputArray[0][0][i]
                val cy = outputArray[0][1][i]
                val w = outputArray[0][2][i]
                val h = outputArray[0][3][i]

                // Переводим в формат (left, top, right, bottom)
                val left = cx - w / 2
                val top = cy - h / 2
                val right = cx + w / 2
                val bottom = cy + h / 2

                // Если это "Без коррозии" (ID=5), можем не рисовать рамку или рисовать зеленую
                val labelName = labels.getOrElse(classId) { "Дефект поверхности" }

                detections.add(
                    Detection(
                        boundingBox = RectF(left, top, right, bottom),
                        label = labelName,
                        confidence = maxClassScore
                    )
                )
            }
        }
        return detections
    }

    private fun convertBitmapToByteBuffer(bitmap: Bitmap): ByteBuffer {
        val byteBuffer = ByteBuffer.allocateDirect(1 * inputSize * inputSize * 3 * 4)
        byteBuffer.order(ByteOrder.nativeOrder())
        val intValues = IntArray(inputSize * inputSize)
        bitmap.getPixels(intValues, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)

        var pixel = 0
        for (i in 0 until inputSize) {
            for (j in 0 until inputSize) {
                val `val` = intValues[pixel++]
                // Нормализация (0..255) -> (0..1)
                byteBuffer.putFloat(((`val` shr 16 and 0xFF) - 127.5f) / 127.5f)
                byteBuffer.putFloat(((`val` shr 8 and 0xFF) - 127.5f) / 127.5f)
                byteBuffer.putFloat(((`val` and 0xFF) - 127.5f) / 127.5f)
            }
        }
        return byteBuffer
    }
}