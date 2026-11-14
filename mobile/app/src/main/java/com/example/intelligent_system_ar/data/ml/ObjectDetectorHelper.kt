package com.example.intelligent_system_ar.data.ml

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

class ObjectDetectorHelper(context: Context) : AutoCloseable {
    private val labels = context.assets.open("labels.txt").bufferedReader().use { it.readLines() }
    private val interpreter: Interpreter
    private val bitmap = Bitmap.createBitmap(640, 640, Bitmap.Config.ARGB_8888)
    private val canvas = Canvas(bitmap)
    private val paint = Paint(Paint.FILTER_BITMAP_FLAG)
    private val pixels = IntArray(640 * 640)
    private val input = ByteBuffer.allocateDirect(640 * 640 * 3 * 4).order(ByteOrder.nativeOrder())

    // ИЗМЕНЕНИЕ 1: Массив теперь на 20 элементов (4 координаты + 16 классов)
    private val output = arrayOf(Array(20) { FloatArray(8400) })

    init {
        val modelBytes = context.assets.open("best_float16.tflite").use { it.readBytes() }

        // Проверки, которые не зависят от interpreter
        require(labels.size == 16 && labels[5] == "Без коррозии") { "Неверный список меток" }

        val model = ByteBuffer.allocateDirect(modelBytes.size).order(ByteOrder.nativeOrder()).apply {
            put(modelBytes)
            rewind()
        }

        interpreter = Interpreter(model, Interpreter.Options().apply {
            setNumThreads(minOf(4, Runtime.getRuntime().availableProcessors()))
        })

        // Проверки тензоров ПОСЛЕ создания интерпретатора
        try {
            require(interpreter.getInputTensor(0).shape().contentEquals(intArrayOf(1, 640, 640, 3)) &&
                    interpreter.getInputTensor(0).dataType() == DataType.FLOAT32) { "Неверная форма входного тензора" }

            // ИЗМЕНЕНИЕ 2: Проверяем 20 элементов на выходе
            require(interpreter.getOutputTensor(0).shape().contentEquals(intArrayOf(1, 20, 8400)) &&
                    interpreter.getOutputTensor(0).dataType() == DataType.FLOAT32) { "Неверная форма выходного тензора. Ожидалось 1x20x8400" }
        } catch (error: RuntimeException) {
            interpreter.close();
            throw error
        }
    }

    fun detect(image: Bitmap): List<Detection> {
        val geometry = LetterboxGeometry(image.width, image.height)
        canvas.drawColor(Color.rgb(114,114,114))
        canvas.drawBitmap(image, null, Rect(geometry.left, geometry.top,
            geometry.left + geometry.scaledWidth, geometry.top + geometry.scaledHeight), paint)
        bitmap.getPixels(pixels,0,640,0,0,640,640)
        input.rewind()
        for (pixel in pixels) {
            input.putFloat((pixel shr 16 and 255) / 255f)
            input.putFloat((pixel shr 8 and 255) / 255f)
            input.putFloat((pixel and 255) / 255f)
        }
        input.rewind()
        interpreter.run(input, output)
        return YoloPostprocessor.decode(output[0], labels, geometry)
    }

    override fun close() { interpreter.close(); bitmap.recycle() }

    companion object {
        const val MODEL_SHA256 = "fbbdb8b77278c5d64eeedd80a43e85637f476f438f352861a622863a709de65b"
    }
}