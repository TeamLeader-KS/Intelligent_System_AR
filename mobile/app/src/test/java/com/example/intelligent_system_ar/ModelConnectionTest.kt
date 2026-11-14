package com.example.intelligent_system_ar

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.security.MessageDigest

class ModelConnectionTest {

    // Путь к папке с моделями относительно корня модуля 'app'
    private val modelsDir = File("../../ai/models")

    @Test
    fun testLabelsFileIsCorrect() {
        val labelsFile = File(modelsDir, "labels.txt")

        assertTrue("Файл labels.txt не найден по пути: ${labelsFile.absolutePath}", labelsFile.exists())

        val labels = labelsFile.readLines().filter { it.isNotBlank() }

        // Проверяем количество классов
        assertEquals("В файле labels.txt должно быть ровно 12 строк", 12, labels.size)

        // Проверяем, что 6-я строка (индекс 5) правильная
        assertEquals("6-я строка должна быть 'Без коррозии'", "Без коррозии", labels[5])
    }

    @Test
    fun testModelFileExistsAndHashMatches() {
        val modelFile = File(modelsDir, "best_float16.tflite")

        assertTrue("Файл модели не найден по пути: ${modelFile.absolutePath}", modelFile.exists())
        assertTrue("Файл модели слишком маленький (возможно, не докачался)", modelFile.length() > 1_000_000)

        // Считаем хэш
        val hash = MessageDigest.getInstance("SHA-256")
        modelFile.inputStream().use { stream ->
            val buffer = ByteArray(8192)
            while (true) {
                val count = stream.read(buffer)
                if (count < 0) break
                hash.update(buffer, 0, count)
            }
        }
        val actualHash = hash.digest().joinToString("") { "%02x".format(it.toInt() and 255) }

        // ВСТАВЬ СЮДА ТОТ ХЭШ, КОТОРЫЙ У ТЕБЯ СЕЙЧАС В ObjectDetectorHelper.kt
        val expectedHash = "0c6ce9b3990dcfd9607a3bab073c66a42d4db882ae111676960dd59e6cf7b774"

        assertEquals("Хэш модели не совпадает с тем, что прописан в коде!", expectedHash, actualHash)
    }
}