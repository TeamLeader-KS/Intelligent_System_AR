//package com.example.intelligent_system_ar.ui.screen.camera
//
//import android.Manifest
//import android.content.pm.PackageManager
//import androidx.activity.compose.rememberLauncherForActivityResult
//import androidx.activity.result.contract.ActivityResultContracts
//import androidx.camera.core.CameraSelector
//import androidx.camera.core.Preview
//import androidx.camera.lifecycle.ProcessCameraProvider
//import androidx.camera.view.PreviewView
//import androidx.compose.foundation.BorderStroke
//import androidx.compose.foundation.background
//import androidx.compose.foundation.layout.Arrangement
//import androidx.compose.foundation.layout.Box
//import androidx.compose.foundation.layout.Column
//import androidx.compose.foundation.layout.Row
//import androidx.compose.foundation.layout.Spacer
//import androidx.compose.foundation.layout.fillMaxHeight
//import androidx.compose.foundation.layout.fillMaxSize
//import androidx.compose.foundation.layout.fillMaxWidth
//import androidx.compose.foundation.layout.height
//import androidx.compose.foundation.layout.navigationBarsPadding
//import androidx.compose.foundation.layout.padding
//import androidx.compose.foundation.layout.size
//import androidx.compose.foundation.layout.statusBarsPadding
//import androidx.compose.foundation.layout.width
//import androidx.compose.foundation.shape.RoundedCornerShape
//import androidx.compose.material3.Button
//import androidx.compose.material3.CircularProgressIndicator
//import androidx.compose.material3.MaterialTheme
//import androidx.compose.material3.SnackbarHost
//import androidx.compose.material3.SnackbarHostState
//import androidx.compose.material3.Surface
//import androidx.compose.material3.Text
//import androidx.compose.runtime.Composable
//import androidx.compose.runtime.LaunchedEffect
//import androidx.compose.runtime.getValue
//import androidx.compose.runtime.mutableStateOf
//import androidx.compose.runtime.remember
//import androidx.compose.runtime.setValue
//import androidx.compose.ui.Alignment
//import androidx.compose.ui.Modifier
//import androidx.compose.ui.graphics.Brush
//import androidx.compose.ui.graphics.Color
//import androidx.compose.ui.platform.LocalContext
//import androidx.compose.ui.platform.LocalLifecycleOwner
//import androidx.compose.ui.text.style.TextAlign
//import androidx.compose.ui.unit.dp
//import androidx.compose.ui.viewinterop.AndroidView
//import androidx.core.content.ContextCompat
//import androidx.lifecycle.LifecycleOwner
//import com.example.intelligent_system_ar.data.model.ScanStatus
//import com.example.intelligent_system_ar.ui.MainViewModel
//import com.example.intelligent_system_ar.ui.component.CameraOverlay
//import com.example.intelligent_system_ar.ui.component.ClearScreenButton
//import com.example.intelligent_system_ar.ui.component.ConfirmChangeDialog
//import com.example.intelligent_system_ar.ui.component.MainTopBar
//import com.example.intelligent_system_ar.ui.component.RegistrationDialog
//import com.example.intelligent_system_ar.ui.component.ReportDialog
//import com.example.intelligent_system_ar.ui.component.ResultCard
//import com.example.intelligent_system_ar.ui.component.ScanButton
//import com.example.intelligent_system_ar.ui.theme.ArAccent
//import com.example.intelligent_system_ar.ui.theme.ArBackground
//import com.example.intelligent_system_ar.ui.theme.ArOutline
//import com.example.intelligent_system_ar.ui.theme.ArScrim
//import com.example.intelligent_system_ar.ui.theme.ArSurface
//import com.example.intelligent_system_ar.ui.theme.ArTextPrimary
//import com.example.intelligent_system_ar.ui.theme.ArTextSecondary
//
//@Composable
//fun CameraScreen(viewModel: MainViewModel) {
//    val context = LocalContext.current
//    val lifecycleOwner = LocalLifecycleOwner.current
//    val snackbarHostState = remember { SnackbarHostState() }
//
//    var hasCameraPermission by remember {
//        mutableStateOf(
//            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
//                    PackageManager.PERMISSION_GRANTED
//        )
//    }
//    val launcher = rememberLauncherForActivityResult(
//        contract = ActivityResultContracts.RequestPermission(),
//        onResult = { granted -> hasCameraPermission = granted }
//    )
//    LaunchedEffect(Unit) {
//        if (!hasCameraPermission) launcher.launch(Manifest.permission.CAMERA)
//    }
//
//    val user = viewModel.userState
//    var showReportDialog by remember { mutableStateOf(false) }
//    var showConfirmChange by remember { mutableStateOf(false) }
//    // При первом запуске сразу предлагаем зарегистрироваться
//    var showRegistration by remember { mutableStateOf(!user.isRegistered) }
//    // Каждый раз при открытии окна регистрации заново грузим цеха с сервера
//    LaunchedEffect(showRegistration) {
//        if (showRegistration) viewModel.openRegistration()
//    }
//
//    val event = viewModel.event
//    LaunchedEffect(event) {
//        if (event != null) {
//            snackbarHostState.showSnackbar(event)
//            viewModel.consumeEvent()
//        }
//    }
//
//    val result = viewModel.scanResult
//    var showCard by remember(result) { mutableStateOf(false) }
//    val canReport = result != null &&
//            (result.status == ScanStatus.WARNING || result.status == ScanStatus.CRITICAL)
//
//    Box(Modifier.fillMaxSize()) {
//
//    // 1. Камера (всегда включена)
//        if (hasCameraPermission) {
//            CameraPreview(lifecycleOwner)
//        } else {
//            PermissionPlaceholder(onRequest = { launcher.launch(Manifest.permission.CAMERA) })
//        }
//
//        // 2. Затемнение сверху/снизу для читаемости интерфейса (тоже скрываем)
//        if (!showReportDialog) {
//            Box(
//                Modifier.align(Alignment.TopCenter).fillMaxWidth().height(140.dp)
//                    .background(Brush.verticalGradient(listOf(ArScrim.copy(alpha = 0.7f), Color.Transparent)))
//            )
//            Box(
//                Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(220.dp)
//                    .background(Brush.verticalGradient(listOf(Color.Transparent, ArScrim.copy(alpha = 0.8f))))
//            )
//        }
//
//        // 3. AR-слой: рамка, подписи, «Сообщить!» (Скрываем, если открыто окно "Сообщить")
//        if (!showReportDialog) {
//            CameraOverlay(
//                result = result,
//                canReport = canReport,
//                onEquipmentClick = { showCard = !showCard },
//                onReportClick = {
//                    if (user.isRegistered) showReportDialog = true else showRegistration = true
//                },
//                modifier = Modifier.fillMaxSize()
//            )
//        }
//
//        // 4. Верхняя панель (Оставляем видимой всегда, она нужна для настроек)
//        MainTopBar(
//            user = user,
//            onRegisterClick = { showRegistration = true },
//            onChangeDataClick = { showConfirmChange = true },
//            modifier = Modifier.align(Alignment.TopCenter)
//        )
//
//        // 5. Низ: карточка и кнопки (Скрываем, если открыто окно "Сообщить")
////        if (!showReportDialog && !showRegistration) {
//        if (!showReportDialog) {
//            Column(
//                modifier = Modifier
//                    .align(Alignment.BottomCenter)
//                    .fillMaxWidth()
//                    .navigationBarsPadding()
//                    .padding(16.dp),
//                verticalArrangement = Arrangement.spacedBy(12.dp)
//            ) {
//                if (result != null && showCard) {
//                    ResultCard(result)
//                } else {
//                    StatusHint(isScanning = viewModel.isScanning, hasResult = result != null)
//                }
//
//                Row(
//                    modifier = Modifier.fillMaxWidth().height(56.dp),
//                    horizontalArrangement = Arrangement.spacedBy(20.dp)
//                ) {
//                    ScanButton(
//                        isScanning = viewModel.isScanning,
//                        enabled = !viewModel.isScanning && hasCameraPermission,
//                        onClick = { viewModel.startScan() },
//                        modifier = Modifier.weight(3f).fillMaxHeight()
//                    )
//
//                    ClearScreenButton(
//                        enabled = result != null || viewModel.isScanning,
//                        onClick = { viewModel.clearScreen() },
//                        modifier = Modifier.weight(1f).fillMaxHeight()
//                    )
//                }
//            }
//        }
//
//        // 6. Сообщения (отправлено и т.п.)
//        SnackbarHost(
//            hostState = snackbarHostState,
//            modifier = Modifier
//                .align(Alignment.TopCenter)
//                .statusBarsPadding()
//                .padding(top = 76.dp, start = 16.dp, end = 16.dp)
//        ) { data ->
//            Surface(
//                shape = RoundedCornerShape(16.dp),
//                color = ArSurface.copy(alpha = 0.95f),
//                border = BorderStroke(1.dp, ArOutline),
//                modifier = Modifier.fillMaxWidth()
//            ) {
//                Text(
//                    text = data.visuals.message,
//                    color = ArTextPrimary,
//                    style = MaterialTheme.typography.bodyMedium,
//                    modifier = Modifier.padding(16.dp)
//                )
//            }
//        }
//    }
//
//    // Диалоги
//    if (showRegistration) {
//        RegistrationDialog(
//            state = viewModel.registration,
//            onWorkshopSelected = viewModel::onWorkshopSelected,
//            onRoleSelected = viewModel::onRoleSelected,
//            onEmployeeSelected = viewModel::onEmployeeSelected,
//            onRetry = viewModel::retryLoad,
//            onConfirm = {
//                viewModel.confirmRegistration()
//                showRegistration = false
//            },
//            onDismiss = { showRegistration = false }
//        )
//    }
//    if (showConfirmChange) {
//        ConfirmChangeDialog(
//            user = user,
//            onConfirm = {
//                showConfirmChange = false
//                showRegistration = true
//            },
//            onDismiss = { showConfirmChange = false }
//        )
//    }
//    if (showReportDialog && result != null) {
//        ReportDialog(
//            result = result,
//            user = viewModel.userState,
//            onSend = {
//                viewModel.sendReport(it)
//                showReportDialog = false
//                viewModel.clearScreen() // Очищаем экран после успешной отправки!
//            },
//            onDismiss = { showReportDialog = false }
//        )
//    }
//}
//
//@Composable
//private fun CameraPreview(lifecycleOwner: LifecycleOwner) {
//    AndroidView(
//        modifier = Modifier.fillMaxSize(),
//        factory = { ctx ->
//
//            val previewView = PreviewView(ctx).apply {
//                implementationMode = PreviewView.ImplementationMode.COMPATIBLE
//            }
//            val providerFuture = ProcessCameraProvider.getInstance(ctx)
//            providerFuture.addListener({
//                val provider = providerFuture.get()
//                val preview = Preview.Builder().build().also {
//                    it.setSurfaceProvider(previewView.surfaceProvider)
//                }
//                try {
//                    provider.unbindAll()
//                    provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview)
//                } catch (e: Exception) {
//                    e.printStackTrace()
//                }
//            }, ContextCompat.getMainExecutor(ctx))
//            previewView
//        }
//    )
//}
//
//@Composable
//private fun PermissionPlaceholder(onRequest: () -> Unit) {
//    Column(
//        modifier = Modifier.fillMaxSize().padding(32.dp),
//        verticalArrangement = Arrangement.Center,
//        horizontalAlignment = Alignment.CenterHorizontally
//    ) {
//        Text(
//            text = "Для работы нужен доступ к камере",
//            color = ArTextPrimary,
//            textAlign = TextAlign.Center,
//            style = MaterialTheme.typography.bodyLarge
//        )
//        Spacer(Modifier.height(16.dp))
//        Button(onClick = onRequest) { Text("Разрешить доступ") }
//    }
//}
//
//@Composable
//private fun StatusHint(isScanning: Boolean, hasResult: Boolean) {
//    Row(
//        modifier = Modifier
//            .fillMaxWidth()
//            .background(ArScrim.copy(alpha = 0.7f), RoundedCornerShape(16.dp))
//            .padding(horizontal = 16.dp, vertical = 14.dp),
//        horizontalArrangement = Arrangement.Center,
//        verticalAlignment = Alignment.CenterVertically
//    ) {
//        if (isScanning) {
//            CircularProgressIndicator(
//                modifier = Modifier.size(18.dp),
//                strokeWidth = 2.dp,
//                color = ArAccent
//            )
//            Spacer(Modifier.width(10.dp))
//        }
//        Text(
//            text = when {
//                isScanning -> "Анализ кадра…"
//                hasResult -> "Нажмите на рамку, чтобы открыть карточку"
//                else -> "Наведите камеру на оборудование и нажмите «Сканировать»"
//            },
//            color = ArTextPrimary,
//            textAlign = TextAlign.Center,
//            style = MaterialTheme.typography.bodyMedium
//        )
//    }
//}
package com.example.intelligent_system_ar.ui.screen.camera

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.example.intelligent_system_ar.data.model.ScanStatus
import com.example.intelligent_system_ar.ui.MainViewModel
import com.example.intelligent_system_ar.ui.component.CameraOverlay
import com.example.intelligent_system_ar.ui.component.ClearScreenButton
import com.example.intelligent_system_ar.ui.component.MainTopBar
import com.example.intelligent_system_ar.ui.component.ReportDialog
import com.example.intelligent_system_ar.ui.component.ResultCard
import com.example.intelligent_system_ar.ui.component.ScanButton
import com.example.intelligent_system_ar.ui.screen.login.LoginScreen // Импорт нового экрана
import com.example.intelligent_system_ar.ui.theme.ArAccent
import com.example.intelligent_system_ar.ui.theme.ArBackground
import com.example.intelligent_system_ar.ui.theme.ArOutline
import com.example.intelligent_system_ar.ui.theme.ArScrim
import com.example.intelligent_system_ar.ui.theme.ArSurface
import com.example.intelligent_system_ar.ui.theme.ArTextPrimary

@Composable
fun CameraScreen(viewModel: MainViewModel) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    // --- ПРОВЕРКА АВТОРИЗАЦИИ ---
    // Если токена нет, показываем экран входа
    if (viewModel.accessToken == null) {
        LoginScreen(
            onLogin = { login, password -> viewModel.login(login, password) },
            isLoading = viewModel.isLoggingIn,
            error = viewModel.loginError
        )
        return // Выходим из функции, чтобы не рисовать камеру
    }

    // --- ЛОГИКА КАМЕРЫ И СКАНИРОВАНИЯ ---
    val snackbarHostState = remember { SnackbarHostState() }
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

    val event = viewModel.event
    LaunchedEffect(event) {
        if (event != null) {
            snackbarHostState.showSnackbar(event)
            viewModel.consumeEvent()
        }
    }

    val result = viewModel.scanResult
    var showCard by remember(result) { mutableStateOf(false) }
    val canReport = result != null &&
            (result.status == ScanStatus.WARNING || result.status == ScanStatus.CRITICAL)

    Box(Modifier.fillMaxSize()) {
        // 1. Камера
        if (hasCameraPermission) {
            CameraPreview(lifecycleOwner)
        } else {
            PermissionPlaceholder(onRequest = { launcher.launch(Manifest.permission.CAMERA) })
        }

        // 2. Затемнение сверху/снизу
        if (!showReportDialog) {
            Box(
                Modifier.align(Alignment.TopCenter).fillMaxWidth().height(140.dp)
                    .background(Brush.verticalGradient(listOf(ArScrim.copy(alpha = 0.7f), Color.Transparent)))
            )
            Box(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(220.dp)
                    .background(Brush.verticalGradient(listOf(Color.Transparent, ArScrim.copy(alpha = 0.8f))))
            )
        }

        // 3. AR-слой: рамка
        if (!showReportDialog) {
            CameraOverlay(
                result = result,
                canReport = canReport,
                onEquipmentClick = { showCard = !showCard },
                onReportClick = { showReportDialog = true },
                modifier = Modifier.fillMaxSize()
            )
        }

        // 4. Верхняя панель
        MainTopBar(
            user = user,
            onRegisterClick = { /* Вход уже выполнен, можно показать профиль */ },
            onChangeDataClick = { viewModel.logout() }, // Теперь это кнопка "Выйти"
            modifier = Modifier.align(Alignment.TopCenter)
        )

        // 5. Низ: карточка и кнопки
        if (!showReportDialog) {
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
                        enabled = result != null || viewModel.isScanning,
                        onClick = { viewModel.clearScreen() },
                        modifier = Modifier.weight(1f).fillMaxHeight()
                    )
                }
            }
        }

        // 6. Snackbar (Сообщения)
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

    // Диалог отправки сообщения
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
private fun CameraPreview(lifecycleOwner: LifecycleOwner) {
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
                try {
                    provider.unbindAll()
                    provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview)
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }, ContextCompat.getMainExecutor(ctx))
            previewView
        }
    )
}

@Composable
private fun PermissionPlaceholder(onRequest: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "Для работы нужен доступ к камере",
            color = ArTextPrimary,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyLarge
        )
        Spacer(Modifier.height(16.dp))
        Button(onClick = onRequest) { Text("Разрешить доступ") }
    }
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
                else -> "Наведите камеру на оборудование и нажмите «Сканировать»"
            },
            color = ArTextPrimary,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyMedium
        )
    }
}
