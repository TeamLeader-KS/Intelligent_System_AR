package com.example.intelligent_system_ar.ui.component

import android.graphics.BitmapFactory
import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.example.intelligent_system_ar.ui.MainViewModel

@Composable
fun ServerVisionDialog(viewModel: MainViewModel,onDismiss: () -> Unit,onOpenComponent: () -> Unit) {
    val result=viewModel.lastVisionInspection ?: return
    val jpeg=viewModel.lastVisionImage
    val bitmap=remember(jpeg) { jpeg?.let { BitmapFactory.decodeByteArray(it,0,it.size) } }
    val findings=result.detections.orEmpty()
    Dialog(onDismissRequest=onDismiss) {
        Surface(shape=MaterialTheme.shapes.large) {
            Column(Modifier.fillMaxWidth().heightIn(max=720.dp).verticalScroll(rememberScrollState()).padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                Text("Серверный ИИ · осмотр №${result.inspectionId}",style=MaterialTheme.typography.titleLarge)
                Text("Предварительные гипотезы по одному кадру камеры. Внутренние неисправности, состав масла и механическая исправность этим анализом не подтверждаются.")
                Text("Оборудование №${result.equipmentId} · ${inspectionTitle(result.status)}")
                Text("Модель: ${result.modelVersion ?: "не указана"}",style=MaterialTheme.typography.bodySmall)
                bitmap?.let { image ->
                    Box(Modifier.fillMaxWidth().aspectRatio(image.width.toFloat()/image.height)) {
                        Image(image.asImageBitmap(),contentDescription="Кадр камеры, отправленный на анализ",contentScale=ContentScale.FillBounds,modifier=Modifier.matchParentSize())
                        Canvas(Modifier.matchParentSize()) {
                            val label=Paint(Paint.ANTI_ALIAS_FLAG).apply { color=android.graphics.Color.YELLOW;textSize=18.dp.toPx() }
                            findings.forEachIndexed { index,item ->
                                val b=item.box
                                if(b!=null && b.size==4 && b.all { it.isFinite() && it in 0f..1f } && b[0]<b[2] && b[1]<b[3]) {
                                    drawRect(Color.Yellow,Offset(b[0]*size.width,b[1]*size.height),Size((b[2]-b[0])*size.width,(b[3]-b[1])*size.height),style=Stroke(2.dp.toPx()))
                                    drawContext.canvas.nativeCanvas.drawText("${index+1}",b[0]*size.width+4.dp.toPx(),b[1]*size.height+20.dp.toPx(),label)
                                }
                            }
                        }
                    }
                    Text("Метки относятся к этому сохранённому кадру. На текущий видеопоток они не переносятся.",style=MaterialTheme.typography.bodySmall)
                }
                Text(result.reason)
                Text(result.recommendation)
                if(findings.isEmpty()) Text("Распознавание узлов не дало надёжных находок. Это не подтверждает исправность.")
                findings.forEachIndexed { index,item ->
                    HorizontalDivider()
                    Text("${index+1}. ${item.componentName ?: "Узел не определён"}",style=MaterialTheme.typography.titleMedium)
                    Text(item.description)
                    Text("Уверенность модели не откалибрована; вывод требует проверки.",style=MaterialTheme.typography.bodySmall)
                    result.componentContext?.firstOrNull { it.detectionIndex==index }?.let { facts ->
                        Text("Данные карточки на ${facts.asOf}",style=MaterialTheme.typography.titleSmall)
                        Text("Привязка узла предложена ИИ и не подтверждена.",style=MaterialTheme.typography.bodySmall)
                        facts.resource?.let { resource ->
                            Text("Нормативный ресурс: ${resourceTitle(resource.status)}")
                            resource.estimates["hours"]?.remaining?.let { Text("Остаток по наработке: $it ч") }
                            resource.serviceRemainingHours?.let { Text("До обслуживания: $it ч") }
                        }
                        Text("Наработка: ${facts.operatingHours?.let { "$it ч" } ?: "не указана"}")
                        Text("Последнее обслуживание: ${facts.lastServicedAt ?: "не указано"}")
                        facts.attentionReasons.forEach { Text(it) }
                        Text(facts.limitations,style=MaterialTheme.typography.bodySmall)
                    }
                    val componentId=item.componentId
                    val valid=viewModel.card?.id==result.equipmentId && viewModel.card?.components?.any { it.id==componentId }==true
                    if(componentId!=null && valid) {
                        TextButton(onClick={viewModel.selectComponent(componentId);onOpenComponent()}) { Text("Открыть карточку сопоставленного узла") }
                    } else Text("Точная привязка к компоненту не подтверждена. Выберите узел вручную в карточке оборудования.",style=MaterialTheme.typography.bodySmall)
                }
                TextButton(onClick=onDismiss,modifier=Modifier.fillMaxWidth()) { Text("Вернуться к камере") }
            }
        }
    }
}
