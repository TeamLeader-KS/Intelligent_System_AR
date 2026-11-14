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

/** Accessed only by the camera's single analysis executor. */
class ObjectDetectorHelper(context: Context) : AutoCloseable {
    private val labels = context.assets.open("labels.txt").bufferedReader().use { it.readLines() }
    private val interpreter: Interpreter
    private val bitmap = Bitmap.createBitmap(640, 640, Bitmap.Config.ARGB_8888)
    private val canvas = Canvas(bitmap)
    private val paint = Paint(Paint.FILTER_BITMAP_FLAG)
    private val pixels = IntArray(640 * 640)
    private val input = ByteBuffer.allocateDirect(640 * 640 * 3 * 4).order(ByteOrder.nativeOrder())
    private val output = arrayOf(Array(17) { FloatArray(8400) })

    init {
        // Читаем файл модели целиком. Так работает и со сжатым ассетом (FileUtil.loadMappedFile в этом
        // случае падает с «file is probably compressed»), и не нужна библиотека tensorflow-lite-support.
        val modelBytes = context.assets.open("best_float16.tflite").use { it.readBytes() }
        val actual = MessageDigest.getInstance("SHA-256").digest(modelBytes)
            .joinToString("") { "%02x".format(it.toInt() and 255) }
        require(actual == MODEL_SHA256) { "Файл модели не соответствует проверенному контракту" }
        require(labels.size == 12 && labels[5] == "Без коррозии") { "Неверный список меток" }
        val model = ByteBuffer.allocateDirect(modelBytes.size).order(ByteOrder.nativeOrder()).apply {
            put(modelBytes)
            rewind()
        }
        interpreter = Interpreter(model, Interpreter.Options().apply {
            setNumThreads(minOf(4, Runtime.getRuntime().availableProcessors()))
        })
        try {
            require(interpreter.getInputTensor(0).shape().contentEquals(intArrayOf(1,640,640,3)) &&
                    interpreter.getInputTensor(0).dataType() == DataType.FLOAT32)
            require(interpreter.getOutputTensor(0).shape().contentEquals(intArrayOf(1,17,8400)) &&
                    interpreter.getOutputTensor(0).dataType() == DataType.FLOAT32)
        } catch (error: RuntimeException) { interpreter.close(); throw error }
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

    // SSH МОДЕЛИ
    companion object {
        const val MODEL_SHA256 = "fbbdb8b77278c5d64eeedd80a43e85637f476f438f352861a622863a709de65b"
    }
}