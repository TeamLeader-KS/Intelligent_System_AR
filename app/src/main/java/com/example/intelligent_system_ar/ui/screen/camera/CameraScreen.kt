package com.example.intelligent_system_ar.ui.screen.camera

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Paint
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.example.intelligent_system_ar.data.model.ScanStatus
import com.example.intelligent_system_ar.ui.MainViewModel
import com.example.intelligent_system_ar.ui.component.*
import com.example.intelligent_system_ar.ui.theme.*
import com.example.intelligent_system_ar.data.ml.Detection
import com.example.intelligent_system_ar.data.ml.ObjectDetectorHelper
import com.example.intelligent_system_ar.data.ml.*
import java.util.concurrent.Executors

@Composable
fun CameraScreen(viewModel: MainViewModel) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val snackbarHostState = remember { SnackbarHostState() }
    val executor = remember { Executors.newSingleThreadExecutor() }

    // 1. Инициализация нейросети
    var detector by remember { mutableStateOf<ObjectDetectorHelper?>(null) }
    var detections by remember { mutableStateOf<List<Detection>>(emptyList()) }

    LaunchedEffect(Unit) {
        try {
            detector = ObjectDetectorHelper(context)
        } catch (e: Exception) {
            e.printStackTrace()
            // ИСПОЛЬЗУЕМ БЕЗОПАСНЫЙ МЕТОД
            viewModel.showEvent("Ошибка ИИ: ${e.message}")
        }
    }

    // 2. Разрешения камеры
    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                    PackageManager.PERMISSION_GRANTED
        )
    }
    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
        onResult = { granted -> hasCameraPermission = granted }
    )
    LaunchedEffect(Unit) {
        if (!hasCameraPermission) launcher.launch(Manifest.permission.CAMERA)
    }

    val user = viewModel.userState
    var showReportDialog by remember { mutableStateOf(false) }
    var showConfirmChange by remember { mutableStateOf(false) }
    var showLogin by remember { mutableStateOf(!user.isRegistered) }

    // Обработка Snackbar событий
    val event = viewModel.event
    LaunchedEffect(event) {
        if (event != null) {
            snackbarHostState.showSnackbar(event)
            viewModel.consumeEvent()
        }
    }

    val result = viewModel.scanResult
    var showCard by remember(result) { mutableStateOf(false) }
    val canReport = result != null && result.status != ScanStatus.OK

    Box(Modifier.fillMaxSize()) {
        // --- КАМЕРА И ИИ ---
        if (hasCameraPermission && !showReportDialog && !showLogin) {
            CameraPreview(
                lifecycleOwner = lifecycleOwner,
                executor = executor,
                onImageAnalyzed = { imageProxy ->
                    val bitmap = imageProxy.toBitmap()
                    val currentDetector = detector // Безопасная проверка на null
                    if (currentDetector != null) {
                        val newDetections = currentDetector.detect(bitmap)
                        imageProxy.close()
                        if (newDetections.isNotEmpty()) {
                            detections = newDetections
                        } else {
                            detections = emptyList()
                        }
                    } else {
                        imageProxy.close()
                    }
                }
            )
        }

        // --- ОТРИСОВКА РАМОК ---
        if (!showReportDialog && !showLogin) {
            Box(
                Modifier.align(Alignment.TopCenter).fillMaxWidth().height(140.dp)
                    .background(Brush.verticalGradient(listOf(ArScrim.copy(alpha = 0.7f), Color.Transparent)))
            )
            Box(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(220.dp)
                    .background(Brush.verticalGradient(listOf(Color.Transparent, ArScrim.copy(alpha = 0.8f))))
            )

            DetectionCanvas(detections = detections, modifier = Modifier.fillMaxSize())
        }

        // --- ВЕРХНЯЯ ПАНЕЛЬ ---
        MainTopBar(
            user = user,
            onRegisterClick = { showLogin = true },
            onChangeDataClick = { showConfirmChange = true },
            modifier = Modifier.align(Alignment.TopCenter)
        )

        // --- НИЖНИЕ КНОПКИ ---
        if (!showReportDialog && !showLogin) {
            Column(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .navigationBarsPadding()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                if (result != null && showCard) {
                    ResultCard(result)
                } else {
                    StatusHint(isScanning = viewModel.isScanning, hasResult = result != null)
                }

                Row(
                    modifier = Modifier.fillMaxWidth().height(56.dp),
                    horizontalArrangement = Arrangement.spacedBy(20.dp)
                ) {
                    ScanButton(
                        isScanning = viewModel.isScanning,
                        enabled = !viewModel.isScanning && hasCameraPermission,
                        onClick = { viewModel.startScan() },
                        modifier = Modifier.weight(3f).fillMaxHeight()
                    )

                    ClearScreenButton(
                        enabled = result != null || viewModel.isScanning || detections.isNotEmpty(),
                        onClick = {
                            viewModel.clearScreen()
                            detections = emptyList()
                        },
                        modifier = Modifier.weight(1f).fillMaxHeight()
                    )
                }
            }
        }

        // --- SNACKBAR ---
        SnackbarHost(
            hostState = snackbarHostState,
            modifier = Modifier
                .align(Alignment.TopCenter)
                .statusBarsPadding()
                .padding(top = 76.dp, start = 16.dp, end = 16.dp)
        ) { data ->
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = ArSurface.copy(alpha = 0.95f),
                border = BorderStroke(1.dp, ArOutline),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = data.visuals.message,
                    color = ArTextPrimary,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(16.dp)
                )
            }
        }
    }

    // --- ДИАЛОГИ ---
    if (showLogin) {
        LoginDialog(
            state = viewModel.loginUi,
            onLogin = { login, password ->
                viewModel.login(login, password) { showLogin = false }
            },
            onDismiss = { showLogin = false }
        )
    }
    if (showConfirmChange) {
        ConfirmChangeDialog(
            user = user,
            onConfirm = {
                showConfirmChange = false
                showLogin = true
            },
            onDismiss = { showConfirmChange = false }
        )
    }
    if (showReportDialog && result != null) {
        ReportDialog(
            result = result,
            user = viewModel.userState,
            onSend = {
                viewModel.sendReport(it)
                showReportDialog = false
                viewModel.clearScreen()
            },
            onDismiss = { showReportDialog = false }
        )
    }
}

@Composable
fun DetectionCanvas(detections: List<Detection>, modifier: Modifier = Modifier) {
    val paint = remember {
        Paint().apply {
            isAntiAlias = true
            textSize = 36f
            isFakeBoldText = true
        }
    }

    Canvas(modifier = modifier) {
        val scaleX = size.width
        val scaleY = size.height

        detections.forEach { detection ->
            val box = detection.boundingBox
            val left = box.left * scaleX
            val top = box.top * scaleY
            val right = box.right * scaleX
            val bottom = box.bottom * scaleY

            val color = if (detection.confidence > 0.6f) Color.Red else Color.Yellow

            drawRoundRect(
                color = color,
                topLeft = Offset(left, top),
                size = Size(right - left, bottom - top),
                cornerRadius = CornerRadius(16f),
                style = Stroke(width = 6f)
            )

            paint.color = color.toArgb()
            drawContext.canvas.nativeCanvas.drawText(
                "${detection.label} (${(detection.confidence * 100).toInt()}%)",
                left,
                top - 10f,
                paint
            )
        }
    }
}

@Composable
private fun CameraPreview(
    lifecycleOwner: LifecycleOwner,
    executor: java.util.concurrent.ExecutorService,
    onImageAnalyzed: (ImageProxy) -> Unit
) {
    AndroidView(
        modifier = Modifier.fillMaxSize(),
        factory = { ctx ->
            val previewView = PreviewView(ctx).apply {
                implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            }
            val providerFuture = ProcessCameraProvider.getInstance(ctx)
            providerFuture.addListener({
                val provider = providerFuture.get()
                val preview = Preview.Builder().build().also {
                    it.setSurfaceProvider(previewView.surfaceProvider)
                }

                val imageAnalysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build().also {
                        it.setAnalyzer(executor) { imageProxy ->
                            onImageAnalyzed(imageProxy)
                        }
                    }

                try {
                    provider.unbindAll()
                    provider.bindToLifecycle(
                        lifecycleOwner,
                        CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        imageAnalysis
                    )
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }, ContextCompat.getMainExecutor(ctx))
            previewView
        }
    )
}

@Composable
private fun StatusHint(isScanning: Boolean, hasResult: Boolean) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(ArScrim.copy(alpha = 0.7f), RoundedCornerShape(16.dp))
            .padding(horizontal = 16.dp, vertical = 14.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (isScanning) {
            CircularProgressIndicator(
                modifier = Modifier.size(18.dp),
                strokeWidth = 2.dp,
                color = ArAccent
            )
            Spacer(Modifier.width(10.dp))
        }
        Text(
            text = when {
                isScanning -> "Анализ кадра…"
                hasResult -> "Нажмите на рамку, чтобы открыть карточку"
                else -> "Наведите камеру на оборудование для поиска дефектов"
            },
            color = ArTextPrimary,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyMedium
        )
    }
}