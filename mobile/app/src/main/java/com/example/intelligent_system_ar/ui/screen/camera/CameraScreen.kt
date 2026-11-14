package com.example.intelligent_system_ar.ui.screen.camera

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.example.intelligent_system_ar.ui.MainViewModel
import com.example.intelligent_system_ar.ui.component.ConfirmChangeDialog
import com.example.intelligent_system_ar.ui.component.EquipmentDialog
import com.example.intelligent_system_ar.ui.component.RegistrationDialog
import com.example.intelligent_system_ar.ui.component.MainTopBar
import com.example.intelligent_system_ar.ui.screen.login.LoginScreen
import com.example.intelligent_system_ar.ui.theme.*

@Composable
fun CameraScreen(viewModel: MainViewModel) {
    if (viewModel.accessToken == null) {
        LoginScreen(viewModel.serverUrl, viewModel::login, viewModel.isLoggingIn, viewModel.loginError)
        return
    }
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var permissionGranted by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { permissionGranted=it }
    LaunchedEffect(Unit) { if (!permissionGranted) permission.launch(Manifest.permission.CAMERA) }
    var showEquipment by remember { mutableStateOf(false) }
    var showConfirmChange by remember { mutableStateOf(false) }
    var showRegistration by remember { mutableStateOf(false) }
    var analyzing by remember { mutableStateOf(true) }
    var status by remember { mutableStateOf(LiveCameraStatus()) }

    Box(Modifier.fillMaxSize().background(ArBackground)) {
        if (permissionGranted) {
            val camera = remember { LiveCameraPreview(context) { status=it } }
            DisposableEffect(camera,lifecycleOwner) {
                camera.bind(lifecycleOwner)
                onDispose { camera.release() }
            }
            AndroidView(factory={camera}, update={it.setAnalyzing(analyzing && !showEquipment)},
                modifier=Modifier.fillMaxSize())
        } else {
            Column(Modifier.align(Alignment.Center).padding(24.dp), horizontalAlignment=Alignment.CenterHorizontally) {
                Text("Для живого распознавания нужен доступ к камере",color=ArTextPrimary)
                Button(onClick={permission.launch(Manifest.permission.CAMERA)}) { Text("Разрешить камеру") }
            }
        }
        MainTopBar(user=viewModel.userState,
            onRegisterClick={ viewModel.openRegistration(); showRegistration=true },
            onChangeDataClick={ showConfirmChange=true },
            modifier=Modifier.align(Alignment.TopCenter))
        Surface(modifier=Modifier.align(Alignment.BottomCenter).fillMaxWidth(),
            color=ArSurface.copy(alpha=0.95f)) {
            Column(Modifier.navigationBarsPadding().padding(16.dp), verticalArrangement=Arrangement.spacedBy(8.dp)) {
                Text(if (!analyzing && !status.error) "Анализ приостановлен" else status.message,
                    color=if(status.error) MaterialTheme.colorScheme.error else ArTextPrimary,
                    style=MaterialTheme.typography.bodyMedium)
                if (status.ready) Text("ИИ на телефоне · ${status.latencyMs} мс · порог > 0,4",
                    color=ArTextSecondary,style=MaterialTheme.typography.bodySmall)
                Text("Цвет рамки показывает уверенность, а не тяжесть дефекта.",
                    color=ArTextSecondary,style=MaterialTheme.typography.bodySmall)
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                    Button(onClick={analyzing=!analyzing},enabled=permissionGranted && status.ready && !status.error,
                        modifier=Modifier.weight(1f)) { Text(if(analyzing) "Пауза" else "Начать анализ") }
                    OutlinedButton(onClick={showEquipment=true},modifier=Modifier.weight(1f)) { Text("Оборудование") }
                }
                viewModel.card?.let { Text(it.name,color=ArTextPrimary,style=MaterialTheme.typography.bodySmall) }
                // Выход из аккаунта (смена логина). Не нужна — удалите эту строку.
                TextButton(onClick={ viewModel.logout() }) { Text("Выйти из аккаунта", color=ArTextSecondary) }
            }
        }
    }
    if (showEquipment) EquipmentDialog(viewModel,onDismiss={showEquipment=false})
    if (showConfirmChange) {
        ConfirmChangeDialog(
            user = viewModel.userState,
            onConfirm = {
                showConfirmChange = false
                viewModel.openRegistration()
                showRegistration = true
            },
            onDismiss = { showConfirmChange = false }
        )
    }
    if (showRegistration) {
        RegistrationDialog(
            state = viewModel.registration,
            onWorkshopSelected = viewModel::onWorkshopSelected,
            onRoleSelected = viewModel::onRoleSelected,
            onEmployeeSelected = viewModel::onEmployeeSelected,
            onRetry = viewModel::retryLoad,
            onConfirm = {
                viewModel.confirmRegistration()
                showRegistration = false
            },
            onDismiss = { showRegistration = false },
            // ЕДИНЫЙ СТИЛЬ (РАМКУ И РАЗМЕР)
            modifier = Modifier.fillMaxWidth().fillMaxHeight(0.55f)
        )
    }
}
