package com.example.intelligent_system_ar.ui.screen.camera

import android.Manifest
import android.content.Intent
import android.content.ClipData
import android.content.ActivityNotFoundException
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
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.example.intelligent_system_ar.ui.MainViewModel
import com.example.intelligent_system_ar.data.model.componentAttention
import com.example.intelligent_system_ar.ui.component.EquipmentDialog
import com.example.intelligent_system_ar.ui.component.MainTopBar
import com.example.intelligent_system_ar.ui.component.ComponentDetailDialog
import com.example.intelligent_system_ar.ui.component.ServerVisionDialog
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
    LaunchedEffect(viewModel.reportToShare) {
        viewModel.reportToShare?.let { (file,mime) ->
            val uri=FileProvider.getUriForFile(context,"${context.packageName}.reports",file)
            val intent=Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM,uri)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION).apply { clipData=ClipData.newRawUri("Отчёт осмотра",uri) }
            try { context.startActivity(Intent.createChooser(intent,"Сохранить или отправить отчёт")) }
            catch (_: ActivityNotFoundException) { viewModel.reportShareFailed() }
            viewModel.consumeReport()
        }
    }
    var permissionGranted by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { permissionGranted=it }
    LaunchedEffect(Unit) { if (!permissionGranted) permission.launch(Manifest.permission.CAMERA) }
    var showEquipment by remember { mutableStateOf(false) }
    var analyzing by remember { mutableStateOf(true) }
    var status by remember { mutableStateOf(LiveCameraStatus()) }
    var cameraView by remember { mutableStateOf<LiveCameraPreview?>(null) }
    var capturing by remember { mutableStateOf(false) }
    var showComponent by remember { mutableStateOf(false) }
    var qrCandidate by remember { mutableStateOf<String?>(null) }
    var nameplateCandidates by remember { mutableStateOf<List<String>?>(null) }
    var nameplateError by remember { mutableStateOf<String?>(null) }
    var readingNameplate by remember { mutableStateOf(false) }
    var confirmedNumber by remember { mutableStateOf("") }
    var showManualChecks by remember { mutableStateOf(false) }
    var confirmDiscardWork by remember { mutableStateOf(false) }
    var showServerVision by remember { mutableStateOf(false) }
    var showAttention by remember { mutableStateOf(false) }
    val attention = componentAttention(viewModel.card?.components.orEmpty())
    val panelHeight=(LocalConfiguration.current.screenHeightDp*0.52f).dp
    LaunchedEffect(status.error) { if(status.error) capturing=false }
    LaunchedEffect(viewModel.lastVisionInspection?.inspectionId) { if(viewModel.lastVisionInspection!=null) showServerVision=true }

    Box(Modifier.fillMaxSize().background(ArBackground)) {
        if (permissionGranted) {
            val camera = remember { LiveCameraPreview(context,onStatus={status=it},onFindingTap={
                if(viewModel.selectedComponent != null) showComponent=true else showEquipment=true
            },onInventoryCode={qrCandidate=it},onNameplate={candidates,error ->
                readingNameplate=false;nameplateCandidates=candidates;nameplateError=error;confirmedNumber=candidates.firstOrNull().orEmpty()
            }) }
            DisposableEffect(camera,lifecycleOwner) {
                cameraView=camera
                camera.bind(lifecycleOwner)
                onDispose { cameraView=null; camera.release() }
            }
            AndroidView(factory={camera}, update={it.setAnalyzing(analyzing && !showEquipment && !showComponent && !showAttention && !showManualChecks && !showServerVision && !confirmDiscardWork && qrCandidate==null && nameplateCandidates==null)},
                modifier=Modifier.fillMaxSize())
        } else {
            Column(Modifier.align(Alignment.Center).padding(24.dp), horizontalAlignment=Alignment.CenterHorizontally) {
                Text("Для живого распознавания нужен доступ к камере",color=ArTextPrimary)
                Button(onClick={permission.launch(Manifest.permission.CAMERA)}) { Text("Разрешить камеру") }
            }
        }
        MainTopBar(user=viewModel.userState, onRegisterClick={},
            onChangeDataClick={viewModel.logout()}, modifier=Modifier.align(Alignment.TopCenter))
        Surface(modifier=Modifier.align(Alignment.BottomCenter).fillMaxWidth(),
            color=ArSurface.copy(alpha=0.95f)) {
            Column(Modifier.heightIn(max=panelHeight).verticalScroll(rememberScrollState()).navigationBarsPadding().padding(16.dp), verticalArrangement=Arrangement.spacedBy(8.dp)) {
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
                Row {
                    TextButton(onClick={cameraView?.startQrScan();analyzing=true},enabled=permissionGranted) { Text("Найти по QR") }
                    TextButton(onClick={readingNameplate=cameraView?.readNameplate()==true},enabled=permissionGranted && analyzing && !readingNameplate) {
                        Text(if(readingNameplate) "Читаем шильдик…" else "Считать шильдик")
                    }
                }
                viewModel.card?.let { equipment ->
                    Text(equipment.name,color=ArTextPrimary,style=MaterialTheme.typography.bodySmall)
                    OutlinedButton(onClick={showAttention=true},modifier=Modifier.fillMaxWidth()) {
                        Text("Требуют внимания: ${attention.size}")
                    }
                    OutlinedButton(onClick={
                        val componentId=viewModel.selectedComponentId
                        capturing=cameraView?.captureNextFrame { snapshot ->
                            capturing=false
                            analyzing=false
                            viewModel.saveVisionSnapshot(snapshot,equipment.id,componentId)
                        } == true
                    },enabled=analyzing && !viewModel.isSaving && !capturing && status.ready && !status.error,modifier=Modifier.fillMaxWidth()) {
                        Text("ИИ-анализ узлов на сервере")
                    }
                    Text("Один кадр отправится только на локальный сервер. Анализ может занять до двух минут; выводы предварительные.",color=ArTextSecondary,style=MaterialTheme.typography.bodySmall)
                }
                if(viewModel.isVisionAnalyzing) {
                    LinearProgressIndicator(modifier=Modifier.fillMaxWidth())
                    Text("Локальный сервер анализирует кадр…",color=ArTextPrimary)
                }
                viewModel.selectedComponent?.let { component ->
                    Text("Узел выбран вручную: ${component.name}",color=ArTextPrimary,style=MaterialTheme.typography.bodySmall)
                    Text("Модель распознаёт признаки поверхности; тип узла она не определяет.",color=ArTextSecondary,style=MaterialTheme.typography.bodySmall)
                    Text("Наведите камеру на выбранный узел. Нажмите рамку для его карточки.",color=ArTextSecondary,style=MaterialTheme.typography.bodySmall)
                    OutlinedTextField(value=viewModel.inspectionComment,onValueChange={viewModel.inspectionComment=it.take(2000)},
                        label={Text("Замечание к осмотру")},maxLines=2,modifier=Modifier.fillMaxWidth())
                    TextButton(onClick={showManualChecks=true}) { Text("Ручные признаки (${viewModel.visualChecks.size})") }
                    Button(onClick={
                        val equipmentId=viewModel.card?.id ?: return@Button
                        val componentId=component.id
                        val comment=viewModel.inspectionComment
                        val checks=viewModel.visualChecks
                        capturing=cameraView?.captureNextFrame { snapshot ->
                            capturing=false
                            viewModel.saveSnapshot(snapshot,equipmentId,componentId,comment,checks)
                        } == true
                    },enabled=analyzing && !viewModel.isSaving && !capturing && status.ready && !status.error,
                        modifier=Modifier.fillMaxWidth()) {
                        Text(if(capturing) "Снимаем кадр…" else if(viewModel.isSaving) "Сохранение…" else "Сохранить осмотр с кадром")
                    }
                    TextButton(onClick={showComponent=true}) { Text("Карточка узла и выполненные работы") }
                } ?: Text("Выберите оборудование и узел для сохранения осмотра",color=ArTextSecondary)
                viewModel.saveMessage?.let { Text(it,color=ArTextPrimary,style=MaterialTheme.typography.bodySmall) }
                viewModel.lastInspection?.let { result ->
                    Text("Осмотр №${result.inspectionId}: ${result.defect}",color=ArTextPrimary)
                    Text(result.recommendation,color=ArTextPrimary,style=MaterialTheme.typography.bodySmall)
                    result.componentResource?.serviceRemainingHours?.let { Text("Расчётно до ТО: $it ч",color=ArTextSecondary) }
                    result.diagnostics.orEmpty().forEach { Text("${it.title}. ${it.recommendation}",color=ArTextPrimary,style=MaterialTheme.typography.bodySmall) }
                }
                viewModel.lastVisionInspection?.let { TextButton(onClick={showServerVision=true}) { Text("Результат серверного ИИ №${it.inspectionId}") } }
                if(viewModel.pendingVisionCount>0) Text("Серверных запросов в очереди: ${viewModel.pendingVisionCount}. Для повтора нажмите «Отправить очередь».",color=ArTextSecondary,style=MaterialTheme.typography.bodySmall)
                if(viewModel.pendingCount>0) OutlinedButton(onClick={viewModel.flushPending()},
                    enabled=!viewModel.isSaving,modifier=Modifier.fillMaxWidth()) { Text("Отправить очередь (${viewModel.pendingCount})") }
                if(viewModel.pendingCount>0) TextButton(onClick={confirmDiscardWork=true},enabled=!viewModel.isSaving) { Text("Отменить запросы работ при конфликте") }
            }
        }
    }
    if (showEquipment) EquipmentDialog(viewModel,onDismiss={showEquipment=false},onComponentOpen={showEquipment=false;showComponent=true})
    if (showComponent) ComponentDetailDialog(viewModel,onDismiss={showComponent=false})
    if (showAttention) AlertDialog(onDismissRequest={showAttention=false},title={Text("Узлы требуют внимания")},text={
        Column(Modifier.heightIn(max=400.dp).verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(8.dp)) {
            Text("Причины по цифровой карточке, не диагноз ИИ. Отсутствие узла в списке не подтверждает исправность.")
            if(attention.isEmpty()) Text("По имеющимся нормативам причин внимания нет. Можно выбрать любой узел для осмотра.")
            attention.forEach { item ->
                Text(item.name,style=MaterialTheme.typography.titleSmall)
                item.reasons.forEach { Text("• $it") }
                Button(onClick={viewModel.selectComponent(item.componentId);showAttention=false;analyzing=true},modifier=Modifier.fillMaxWidth()) {
                    Text("Навести камеру на узел")
                }
            }
        }
    },confirmButton={TextButton(onClick={showAttention=false}) { Text("Закрыть") }})
    if(showServerVision) ServerVisionDialog(viewModel,onDismiss={showServerVision=false},onOpenComponent={showServerVision=false;showComponent=true})
    if(showManualChecks) {
        val checks=linkedMapOf("SEAL_LEAK" to "Утечка у уплотнения", "FRAME_CORROSION" to "Коррозия фундаментной рамы",
            "LOOSE_ANCHOR" to "Ослаблен анкерный болт", "OIL_DARK" to "Масло тёмное или мутное", "OIL_LOW" to "Масло ниже MIN",
            "TERMINAL_OXIDATION" to "Окисление / перегрев контактов", "COUPLING_GUARD_MISSING" to "Кожух муфты отсутствует или повреждён")
        AlertDialog(onDismissRequest={showManualChecks=false},title={Text("Отметки инженера")},text={
            Column(Modifier.heightIn(max=400.dp).verticalScroll(rememberScrollState())) {
                Text("Это ручные наблюдения. Нейросеть эти признаки не распознавала. Отмечайте только то, что проверили лично.")
                checks.forEach { (code,label) -> Row {
                    Checkbox(checked=code in viewModel.visualChecks,onCheckedChange={checked ->
                        viewModel.visualChecks=if(checked) viewModel.visualChecks+code else viewModel.visualChecks-code
                    }); Text(label,modifier=Modifier.padding(top=12.dp))
                } }
            }
        },confirmButton={TextButton(onClick={showManualChecks=false}) { Text("Готово") }})
    }
    if(confirmDiscardWork) AlertDialog(onDismissRequest={confirmDiscardWork=false},title={Text("Отменить локальные запросы работ?")},
        text={Text("Осмотры и фотографии в очереди останутся. Уже принятые сервером работы не удаляются. После отмены обновите карточку и заново введите только неподтверждённую работу.")},
        confirmButton={TextButton(onClick={confirmDiscardWork=false;viewModel.discardPendingWork()}) { Text("Отменить запросы работ") }},
        dismissButton={TextButton(onClick={confirmDiscardWork=false}) { Text("Назад") }})
    qrCandidate?.let { code ->
        AlertDialog(onDismissRequest={qrCandidate=null},title={Text("QR оборудования")},
            text={Text("Найден инвентарный номер: $code. Загрузить карточку из локальной базы?")},
            confirmButton={TextButton(onClick={viewModel.resolveEquipment(code);qrCandidate=null;showEquipment=true}) { Text("Открыть карточку") }},
            dismissButton={TextButton(onClick={qrCandidate=null}) { Text("Отмена") }})
    }
    nameplateCandidates?.let { candidates ->
        AlertDialog(onDismissRequest={nameplateCandidates=null},title={Text("Проверьте номер на шильдике")},
            text={Column(Modifier.heightIn(max=360.dp).verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                Text("OCR работает на телефоне. Выберите точный инвентарный/серийный номер, при необходимости исправьте. Частичный номер не считается идентификацией.")
                nameplateError?.let { Text(it,color=MaterialTheme.colorScheme.error) }
                if(candidates.isEmpty()) Text("Номер не распознан. Введите его вручную или повторите с лучшим освещением.")
                candidates.forEach { number -> TextButton(onClick={confirmedNumber=number}) { Text(number) } }
                OutlinedTextField(value=confirmedNumber,onValueChange={confirmedNumber=it.take(120)},label={Text("Подтверждённый номер")},singleLine=true)
            }},
            confirmButton={TextButton(onClick={viewModel.resolveEquipment(confirmedNumber);nameplateCandidates=null;showEquipment=true},enabled=confirmedNumber.isNotBlank()) { Text("Найти карточку") }},
            dismissButton={TextButton(onClick={nameplateCandidates=null}) { Text("Отмена") }})
    }
}
