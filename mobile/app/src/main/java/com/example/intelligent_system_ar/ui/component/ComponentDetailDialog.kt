package com.example.intelligent_system_ar.ui.component

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.example.intelligent_system_ar.ui.MainViewModel

private val workActions=linkedMapOf("INSPECTED" to "Проверено", "SERVICED" to "Обслужено",
    "REPLACED" to "Заменено", "READINGS" to "Показания", "STARTED" to "Запустить учёт", "STOPPED" to "Остановить учёт")

@Composable
fun ComponentDetailDialog(viewModel: MainViewModel,onDismiss: () -> Unit) {
    val component=viewModel.selectedComponent ?: return
    var action by remember(component.id) { mutableStateOf("INSPECTED") }
    var comment by remember(component.id) { mutableStateOf("") }
    var hours by remember(component.id) { mutableStateOf("") }
    var cycles by remember(component.id) { mutableStateOf("") }
    var validation by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(component.id) { viewModel.loadWorkHistory() }
    Dialog(onDismissRequest=onDismiss) {
        Surface(shape=MaterialTheme.shapes.large) {
            Column(Modifier.fillMaxWidth().heightIn(max=680.dp).verticalScroll(rememberScrollState()).padding(16.dp),
                verticalArrangement=Arrangement.spacedBy(8.dp)) {
                Text(component.name,style=MaterialTheme.typography.titleLarge)
                Text(component.model)
                Text("Привязка находок к этому узлу выбрана инженером вручную.",style=MaterialTheme.typography.bodySmall)
                Text("Состояние: ${if(component.runtimeState == "RUNNING") "в работе — моточасы считаются" else "остановлен — моточасы не считаются"}")
                Text("Наработка: ${component.operatingHours?.let { "%.2f ч".format(it) } ?: "не указана"}")
                Text("Установлен: ${component.installedOn ?: "нет данных"}")
                Text("Последнее ТО: ${component.lastServicedAt ?: "нет данных"}")
                component.specifications.forEach { spec ->
                    val outside=(spec.minimum != null && spec.value < spec.minimum) || (spec.maximum != null && spec.value > spec.maximum)
                    Text("${if(outside) "⚠ " else ""}${parameterTitle(spec.name)}: ${spec.value} ${parameterUnit(spec.unit)}")
                    if(spec.minimum != null || spec.maximum != null) Text("Уставки: ${spec.minimum ?: "—"} … ${spec.maximum ?: "—"}",style=MaterialTheme.typography.bodySmall)
                }
                Text("Нормативный ресурс: ${resourceTitle(component.resource.status)}",style=MaterialTheme.typography.titleSmall)
                component.resource.estimates.forEach { (unit,value) ->
                    val label=when(unit) { "hours"->"ч"; "days"->"дней";else->"циклов" }
                    Text("Норма: ${value.norm ?: "нет данных"}; остаток: ${value.remaining ?: "нет данных"} $label")
                }
                component.resource.serviceRemainingHours?.let { Text("До обслуживания: $it ч") }
                TextButton(onClick={viewModel.card?.id?.let { viewModel.selectEquipment(it) }},enabled=!viewModel.isLoadingCard) { Text("Обновить наработку и ресурс") }
                Text(component.resource.limitations,style=MaterialTheme.typography.bodySmall)
                Text("При визуальных признаках коррозии: проверить поверхность и состояние покрытия; решение принимает специалист. Уверенность модели не определяет ресурс.",style=MaterialTheme.typography.bodySmall)
                if(viewModel.canRecordWork) {
                    HorizontalDivider()
                    Text("Записать выполненную работу",style=MaterialTheme.typography.titleMedium)
                    workActions.forEach { (code,label) ->
                        if(code != "STARTED" || component.runtimeState != "RUNNING") {
                            if(code != "STOPPED" || component.runtimeState == "RUNNING") {
                                Row { RadioButton(selected=action == code,onClick={action=code}); TextButton(onClick={action=code}) { Text(label) } }
                            }
                        }
                    }
                    OutlinedTextField(value=comment,onValueChange={comment=it.take(2000)},label={Text("Что проверено / сделано")},modifier=Modifier.fillMaxWidth())
                    if(action == "READINGS") {
                        OutlinedTextField(value=hours,onValueChange={hours=it},label={Text("Наработка, ч (необязательно)")},keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.Decimal))
                        OutlinedTextField(value=cycles,onValueChange={cycles=it},label={Text("Циклы (необязательно)")},keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.Number))
                    }
                    if(action == "REPLACED") Text("Замена обнулит наработку нового компонента и задаст сегодняшнюю дату установки. Сначала остановите учёт работы.",color=MaterialTheme.colorScheme.error)
                    validation?.let { Text(it,color=MaterialTheme.colorScheme.error) }
                    Button(onClick={
                        val h=hours.replace(',','.').toDoubleOrNull()
                        val c=cycles.toIntOrNull()
                        validation=when {
                            comment.isBlank() -> "Добавьте комментарий"
                            action == "READINGS" && hours.isNotBlank() && (h == null || !h.isFinite() || h<0) -> "Неверная наработка"
                            action == "READINGS" && cycles.isNotBlank() && (c == null || c<0) -> "Неверное число циклов"
                            else -> null
                        }
                        if(validation == null) viewModel.recordWork(action,comment,if(action == "READINGS") h else null,if(action == "READINGS") c else null)
                    },enabled=!viewModel.isSaving) { Text("Сохранить работу") }
                } else Text("Работы и замены фиксирует инженер или мастер. Оператор может сохранить осмотр и замечание с камеры.",style=MaterialTheme.typography.bodySmall)
                viewModel.saveMessage?.let { Text(it) }
                Text("История работ",style=MaterialTheme.typography.titleMedium)
                TextButton(onClick={viewModel.loadWorkHistory()},enabled=!viewModel.isLoadingWork) { Text("Обновить историю") }
                viewModel.workHistory?.let { history ->
                    if(history.items.isEmpty()) Text("Работы ещё не зарегистрированы")
                    history.items.forEach { Text("${it.recordedAt} · ${workActions[it.action] ?: it.action}\n${it.comment}") }
                    Row {
                        TextButton(onClick={viewModel.loadWorkHistory(history.offset-history.limit)},enabled=history.offset>0 && !viewModel.isLoadingWork) { Text("Ранее") }
                        TextButton(onClick={viewModel.loadWorkHistory(history.offset+history.limit)},enabled=history.offset+history.items.size<history.total && !viewModel.isLoadingWork) { Text("Далее") }
                    }
                }
                TextButton(onClick=onDismiss,modifier=Modifier.fillMaxWidth()) { Text("Вернуться к камере") }
            }
        }
    }
}
