package com.example.intelligent_system_ar.ui.component

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.example.intelligent_system_ar.ui.MainViewModel

@Composable
fun EquipmentDialog(viewModel: MainViewModel, onDismiss: () -> Unit) {
    var code by remember { mutableStateOf("") }
    Dialog(onDismissRequest = onDismiss) {
        Surface(shape = MaterialTheme.shapes.large) {
            Column(Modifier.fillMaxWidth().heightIn(max = 640.dp)
                .verticalScroll(rememberScrollState()).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Оборудование", style = MaterialTheme.typography.titleLarge)
                OutlinedTextField(value = code, onValueChange = { code = it },
                    label = { Text("Инвентарный номер") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth())
                Row {
                    TextButton(onClick = { viewModel.resolveEquipment(code) },
                        enabled = code.isNotBlank() && !viewModel.isLoadingCard) { Text("Найти") }
                    TextButton(onClick = { viewModel.refreshEquipment() },
                        enabled = !viewModel.isLoadingEquipment) { Text("Обновить список") }
                }
                if (viewModel.isLoadingEquipment || viewModel.isLoadingCard) {
                    CircularProgressIndicator()
                }
                viewModel.equipmentError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                viewModel.cardError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                if (viewModel.equipment.isEmpty() && !viewModel.isLoadingEquipment && viewModel.equipmentError == null) {
                    Text("В вашем цехе пока нет оборудования")
                }
                viewModel.equipment.forEach { equipment ->
                    OutlinedButton(onClick = { viewModel.selectEquipment(equipment.id) },
                        modifier = Modifier.fillMaxWidth()) {
                        Text("${equipment.name} · ${equipment.inventoryNumber}")
                    }
                }
                viewModel.card?.let { card ->
                    HorizontalDivider()
                    Text(card.name, style = MaterialTheme.typography.titleMedium)
                    Text("Инвентарный номер: ${card.inventoryNumber}")
                    if (card.passport.isNotBlank()) Text(card.passport)
                    if (card.components.isEmpty()) Text("Компоненты ещё не добавлены")
                    card.components.forEach { component ->
                        Text(component.name, style = MaterialTheme.typography.titleSmall)
                        if (component.model.isNotBlank()) Text(component.model)
                        component.specifications.forEach { spec ->
                            val bounds = if (spec.minimum != null || spec.maximum != null)
                                " (норма: ${spec.minimum ?: "—"}…${spec.maximum ?: "—"})" else ""
                            Text("${spec.name}: ${spec.value} ${spec.unit}$bounds")
                        }
                        val resource = component.resource
                        val state = when (resource.status) {
                            "DUE" -> "Норматив достигнут"
                            "APPROACHING" -> "Приближается норматив"
                            "WITHIN_NORM" -> "В пределах норматива"
                            else -> "Недостаточно данных для ресурса"
                        }
                        Text("Ресурс: $state")
                        resource.estimates.forEach { (unit, measure) ->
                            val label = when (unit) {
                                "hours" -> "ч"
                                "days" -> "дней"
                                "cycles" -> "циклов"
                                else -> unit
                            }
                            measure.remaining?.let { Text("Остаток: $it $label") }
                        }
                        resource.serviceRemainingHours?.let { Text("До ТО: $it ч") }
                        Text(resource.limitations, style = MaterialTheme.typography.bodySmall)
                    }
                    TextButton(onClick = { viewModel.loadHistory() },
                        enabled = !viewModel.isLoadingHistory) { Text("История осмотров") }
                    if (viewModel.isLoadingHistory) CircularProgressIndicator()
                    viewModel.historyError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                    viewModel.history?.let { history ->
                        Text("Последние ${history.items.size} из ${history.total} осмотров")
                        history.items.forEach { item ->
                            Text("№${item.inspectionId} · ${item.createdAt}")
                            item.result?.let {
                                Text("${it.status}: ${it.defect}")
                                Text(it.recommendation)
                                Text(if (it.analysisSource == "MOCK") "ДЕМО: синтетический осмотр" else "Источник: ${it.analysisSource}",
                                    style = MaterialTheme.typography.bodySmall)
                            } ?: Text(item.processingStatus)
                        }
                    }
                }
                TextButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) { Text("Закрыть") }
            }
        }
    }
}
