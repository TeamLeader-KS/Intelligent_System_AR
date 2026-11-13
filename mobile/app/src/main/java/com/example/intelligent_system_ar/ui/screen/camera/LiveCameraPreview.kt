package com.example.intelligent_system_ar.ui.screen.camera

import android.content.Context
import android.graphics.*
import android.os.SystemClock
import android.view.View
import android.widget.FrameLayout
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.camera.view.transform.CoordinateTransform
import androidx.camera.view.transform.ImageProxyTransformFactory
import androidx.core.content.ContextCompat
import androidx.core.view.doOnLayout
import androidx.lifecycle.LifecycleOwner
import com.example.intelligent_system_ar.data.ml.*
import java.io.IOException
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

data class LiveCameraStatus(
    val ready: Boolean = false,
    val latencyMs: Long = 0,
    val findings: Int = 0,
    val message: String = "Загрузка модели…",
    val error: Boolean = false
)

class LiveCameraPreview(context: Context, private val onStatus: (LiveCameraStatus) -> Unit) : FrameLayout(context) {
    private val previewView = PreviewView(context).apply {
        implementationMode = PreviewView.ImplementationMode.COMPATIBLE
        scaleType = PreviewView.ScaleType.FIT_CENTER
    }
    private val overlay = DetectionOverlay(context)
    private val worker = Executors.newSingleThreadExecutor()
    private val active = AtomicBoolean(true)
    private val enabled = AtomicBoolean(true)
    private val failed = AtomicBoolean(false)
    private var detector: ObjectDetectorHelper? = null // worker only
    private var provider: ProcessCameraProvider? = null
    private var preview: Preview? = null
    private var analysis: ImageAnalysis? = null
    private var lastFrame = 0L

    init {
        addView(previewView, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT))
        addView(overlay, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT))
        worker.execute {
            try {
                detector = ObjectDetectorHelper(context)
                publish(LiveCameraStatus(ready=true, message="Модель загружена. Наведите камеру на поверхность."))
            } catch (e: IOException) {
                publish(LiveCameraStatus(message="Не удалось прочитать модель в APK", error=true))
            } catch (e: RuntimeException) {
                publish(LiveCameraStatus(message="Не удалось запустить модель: ${e.message?.take(140)}", error=true))
            }
        }
    }

    fun bind(owner: LifecycleOwner) {
        previewView.doOnLayout {
            val future = ProcessCameraProvider.getInstance(context)
            future.addListener({
                if (!active.get()) return@addListener
                try {
                    provider = future.get()
                    val rotation = previewView.display?.rotation ?: 0
                    val cameraPreview = Preview.Builder().setTargetRotation(rotation).build()
                    cameraPreview.setSurfaceProvider(previewView.surfaceProvider)
                    val cameraAnalysis = ImageAnalysis.Builder()
                        .setTargetResolution(android.util.Size(640,480))
                        .setTargetRotation(rotation)
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                        .build()
                    cameraAnalysis.setAnalyzer(worker) { frame -> analyze(frame) }
                    preview = cameraPreview
                    analysis = cameraAnalysis
                    val group = UseCaseGroup.Builder().addUseCase(cameraPreview).addUseCase(cameraAnalysis)
                    previewView.viewPort?.let { group.setViewPort(it) }
                    provider!!.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, group.build())
                } catch (e: Exception) {
                    onStatus(LiveCameraStatus(message="Не удалось открыть камеру", error=true))
                }
            }, ContextCompat.getMainExecutor(context))
        }
    }

    fun setAnalyzing(value: Boolean) {
        enabled.set(value && !failed.get())
        if (!value) overlay.show(emptyList())
    }

    fun clear() { overlay.show(emptyList()) }

    private fun analyze(frame: ImageProxy) {
        val model = detector
        if (!active.get() || !enabled.get() || model == null || SystemClock.elapsedRealtime()-lastFrame < 300) {
            frame.close()
            return
        }
        lastFrame = SystemClock.elapsedRealtime()
        val started = SystemClock.elapsedRealtime()
        var closed = false
        var raw: Bitmap? = null
        var upright: Bitmap? = null
        try {
            val rotation = frame.imageInfo.rotationDegrees
            val source = ImageProxyTransformFactory().getOutputTransform(frame)
            val rawWidth = frame.width
            val rawHeight = frame.height
            val rawImage = frame.toBitmap()
            raw = rawImage
            frame.close()
            closed = true
            val image = if (rotation == 0) rawImage else Bitmap.createBitmap(rawImage,0,0,rawImage.width,rawImage.height,
                Matrix().apply { postRotate(rotation.toFloat()) },true)
            upright = image
            val findings = model.detect(image)
            val boxes = findings.map { detection ->
                val box = YoloPostprocessor.toBuffer(detection.box,rotation)
                detection to RectF(box.left*rawWidth,box.top*rawHeight,box.right*rawWidth,box.bottom*rawHeight)
            }
            val elapsed = SystemClock.elapsedRealtime()-started
            post {
                if (!active.get() || !enabled.get()) return@post
                val target = previewView.outputTransform
                if (target != null) {
                    val transform = CoordinateTransform(source,target)
                    val mapped = boxes.mapNotNull { (finding, rect) ->
                        transform.mapRect(rect)
                        if (rect.intersect(0f,0f,width.toFloat(),height.toFloat())) finding to rect else null
                    }
                    overlay.show(mapped)
                }
                onStatus(LiveCameraStatus(true,elapsed,findings.size,
                    if (findings.isEmpty()) "Находок выше 0,4 нет. Это не подтверждает исправность."
                    else "Находок: ${findings.size}. Требуется проверка инженером."))
            }
        } catch (e: RuntimeException) {
            enabled.set(false)
            failed.set(true)
            publish(LiveCameraStatus(message="Ошибка анализа кадра: ${e.message?.take(140)}",error=true))
        } finally {
            if (!closed) frame.close()
            if (upright !== raw) upright?.recycle()
            raw?.recycle()
        }
    }

    private fun publish(status: LiveCameraStatus) { post { if (active.get()) onStatus(status) } }

    fun release() {
        if (!active.getAndSet(false)) return
        analysis?.clearAnalyzer()
        val useCases = listOfNotNull(preview,analysis).toTypedArray()
        if (useCases.isNotEmpty()) provider?.unbind(*useCases)
        worker.execute { detector?.close(); detector = null }
        worker.shutdown()
        overlay.show(emptyList())
    }
}

private class DetectionOverlay(context: Context) : View(context) {
    private var findings: List<Pair<Detection,RectF>> = emptyList()
    private val line = Paint(Paint.ANTI_ALIAS_FLAG).apply { style=Paint.Style.STROKE; strokeWidth=3*resources.displayMetrics.density }
    private val text = Paint(Paint.ANTI_ALIAS_FLAG).apply { textSize=14*resources.displayMetrics.scaledDensity; color=Color.WHITE }
    private val background = Paint().apply { color=Color.argb(210,15,20,25) }
    fun show(value: List<Pair<Detection,RectF>>) { findings=value; invalidate() }
    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        findings.forEach { (finding,box) ->
            line.color = when {
                finding.kind == FindingKind.UNKNOWN -> Color.LTGRAY
                finding.confidence > 0.6f -> Color.RED
                else -> Color.YELLOW
            }
            canvas.drawRect(box,line)
            val label = "${finding.label} · ${(finding.confidence*100).toInt()}%"
            val padding=6*resources.displayMetrics.density
            val labelWidth=(text.measureText(label)+padding*2).coerceAtMost(width.toFloat())
            val left=box.left.coerceIn(0f,(width-labelWidth).coerceAtLeast(0f))
            val baseline=box.top.coerceAtLeast(text.textSize+padding*2)-padding
            canvas.drawRect(left,baseline-text.textSize-padding,left+labelWidth,baseline+padding,background)
            canvas.drawText(label,left+padding,baseline,text)
        }
    }
}
