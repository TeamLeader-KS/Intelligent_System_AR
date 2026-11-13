package com.example.intelligent_system_ar.data.ml

import android.content.Context
import android.graphics.Bitmap
import android.graphics.RectF
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.support.common.FileUtil
import java.io.BufferedReader
import java.io.InputStreamReader
import java.nio.ByteBuffer
import java.nio.ByteOrder


class ObjectDetectorHelper(context: Context) {
    private var interpreter: Interpreter
    private val labels: List<String>
    private val inputSize = 640

    init {
        val model = FileUtil.loadMappedFile(context, "best_float16.tflite")
        val options = Interpreter.Options().apply { setNumThreads(4) }
        interpreter = Interpreter(model, options)

        val labelStream = context.assets.open("labels.txt")
        labels = BufferedReader(InputStreamReader(labelStream)).use { reader ->
            reader.readLines()
        }
    }

    fun detect(image: Bitmap): List<Detection> {
        // 1. Масштабируем под 640x640
        val resizedBitmap = Bitmap.createScaledBitmap(image, inputSize, inputSize, true)
        val inputBuffer = convertBitmapToByteBuffer(resizedBitmap)

        // 2. Получаем форму выхода (YOLOv8: [1, 4 + num_classes, 8400])
        val outputShape = interpreter.getOutputTensor(0).shape()
        val outputArray = Array(outputShape[0]) {
            Array(outputShape[1]) {
                FloatArray(outputShape[2])
            }
        }

        interpreter.run(inputBuffer, outputArray)

        // 3. Парсим результаты
        val detections = mutableListOf<Detection>()
        val numClasses = labels.size
        val rows = outputShape[2] // 8400 боксов
        val cols = outputShape[1] // 4 (координаты) + классы

        for (i in 0 until rows) {
            var maxClassScore = 0f
            var classId = -1

            for (c in 0 until numClasses) {
                val score = outputArray[0][4 + c][i]
                if (score > maxClassScore) {
                    maxClassScore = score
                    classId = c
                }
            }

            // Если уверенность > 0.4
            if (maxClassScore > 0.4f && classId != -1) {
                // Координаты YOLO (cx, cy, w, h) в пикселях
                val cx = outputArray[0][0][i]
                val cy = outputArray[0][1][i]
                val w = outputArray[0][2][i]
                val h = outputArray[0][3][i]

                // Переводим в нормализованные (0..1) и RectF(left, top, right, bottom)
                val left = (cx - w / 2) / inputSize
                val top = (cy - h / 2) / inputSize
                val right = (cx + w / 2) / inputSize
                val bottom = (cy + h / 2) / inputSize

                // Проверка на выход за границы
                if (left < 0f || top < 0f || right > 1f || bottom > 1f) continue

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

        // Сортируем по уверенности (сначала самые точные)
        return detections.sortedByDescending { it.confidence }.take(10)
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
                // ВАЖНО: Нормализация 0..1 (а не -1..1!)
                byteBuffer.putFloat((( `val` shr 16 and 0xFF) / 255.0f))
                byteBuffer.putFloat((( `val` shr 8 and 0xFF) / 255.0f))
                byteBuffer.putFloat((( `val` and 0xFF) / 255.0f))
            }
        }
        return byteBuffer
    }
}