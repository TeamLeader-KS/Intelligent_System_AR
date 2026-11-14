package com.example.intelligent_system_ar.ui.component

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.example.intelligent_system_ar.data.local.Employee
import com.example.intelligent_system_ar.data.model.ScanResult
import com.example.intelligent_system_ar.data.model.UserState
import com.example.intelligent_system_ar.data.model.Workshop
import com.example.intelligent_system_ar.ui.RegistrationUi
import com.example.intelligent_system_ar.ui.theme.ArAccent
import com.example.intelligent_system_ar.ui.theme.ArTextPrimary
import com.example.intelligent_system_ar.ui.theme.ArTextSecondary
import com.example.intelligent_system_ar.ui.theme.StatusCritical

// ТРЕТЬЕ ОКНО

@Composable
fun RegistrationDialog(
    state: RegistrationUi,
    onWorkshopSelected: (Workshop) -> Unit,
    onRoleSelected: (String) -> Unit,
    onEmployeeSelected: (Employee) -> Unit,
    onRetry: () -> Unit,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier // Добавили modifier для единого стиля
) {
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            shape = RoundedCornerShape(20.dp),
            color = Color.Transparent,
            border = null,
            modifier = modifier // Применяем единый фон
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .fillMaxHeight(0.55f)
                    .menuBackground()
                    .padding(38.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(22.dp, Alignment.CenterVertically)
            ) {
                Text(
                    text = "Регистрация сотрудника",
                    color = ArTextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth()
                )

                DropdownField(
                    placeholder = "Выберите цех",
                    value = state.selectedWorkshop?.name,
                    options = state.workshops.map { it.name },
                    enabled = state.workshops.isNotEmpty(),
                    onSelect = { onWorkshopSelected(state.workshops[it]) }
                )
                DropdownField(
                    placeholder = "Выберите должность",
                    value = state.selectedRole,
                    options = state.roles,
                    enabled = state.selectedWorkshop != null && state.roles.isNotEmpty(),
                    onSelect = { onRoleSelected(state.roles[it]) }
                )
                DropdownField(
                    placeholder = "Выберите свое Ф.И.О.",
                    value = state.selectedEmployee?.name,
                    options = state.employees.map { it.name },
                    enabled = state.selectedRole != null && state.employees.isNotEmpty(),
                    onSelect = { onEmployeeSelected(state.employees[it]) }
                )

                if (state.isLoading) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                            color = ArAccent
                        )
                        Spacer(Modifier.width(10.dp))
                        Text("Загрузка…", color = ArTextSecondary, style = MaterialTheme.typography.bodyMedium)
                    }
                }

                state.error?.let {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = it,
                            color = StatusCritical,
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.weight(1f)
                        )
                        TextButton(onClick = onRetry) { Text("Повторить") }
                    }
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    SecondaryActionButton(
                        text = "Отмена",
                        onClick = onDismiss
                    )

                    Spacer(Modifier.width(8.dp))

                    PrimaryActionButton(
                        text = "Подтвердить",
                        onClick = onConfirm,
                        enabled = state.selectedEmployee != null
                    )
                }
            }
        }
    }
}

@Composable
private fun DropdownField(
    placeholder: String,
    value: String?,
    options: List<String>,
    enabled: Boolean,
    onSelect: (Int) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    var widthPx by remember { mutableIntStateOf(0) }
    val density = LocalDensity.current
    val shape = RoundedCornerShape(16.dp)

    Box(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .onSizeChanged { widthPx = it.width }
                .clip(shape)
                .background(Color.White.copy(alpha = 0.1f))
                .border(1.dp, Color.White.copy(alpha = 0.3f), shape)
                .clickable(enabled = enabled) { expanded = true }
                .padding(horizontal = 16.dp, vertical = 14.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = value ?: placeholder,
                color = if (value != null) ArTextPrimary else ArTextSecondary,
                style = MaterialTheme.typography.bodyLarge
            )
            Text("▾", color = ArTextSecondary, style = MaterialTheme.typography.bodyLarge)
        }

        DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
            containerColor = Color.Black,
            modifier = Modifier
                .width(with(density) { widthPx.toDp() })
                .wrapContentWidth(Alignment.CenterHorizontally)
        ) {
            options.forEachIndexed { index, option ->
                DropdownMenuItem(
                    text = { Text(option) },
                    onClick = {
                        expanded = false
                        onSelect(index)
                    }
                )
            }
        }
    }
}

// ВТОРОЕ ОКНО

@Composable
private fun MenuDialog(
    title: String,
    onDismiss: () -> Unit,
    buttons: @Composable RowScope.() -> Unit,
    content: @Composable ColumnScope.() -> Unit
) {
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            shape = RoundedCornerShape(20.dp),
            color = Color.Transparent,
            border = null,
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.55f)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .fillMaxHeight(0.55f)
                    .menuBackground()
                    .padding(38.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(22.dp, Alignment.CenterVertically)
            ) {
                Text(
                    text = title,
                    color = ArTextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth()
                )

                content()

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                    verticalAlignment = Alignment.CenterVertically,
                    content = buttons
                )
            }
        }
    }
}

// Подтверждение «Изменить данные»

@Composable
fun ConfirmChangeDialog(
    user: UserState,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit
) {
    MenuDialog(
        title = "Изменить данные?",
        onDismiss = onDismiss,
        buttons = {
            SecondaryActionButton(
                text = "Отмена",
                onClick = onDismiss
            )

            Spacer(Modifier.width(8.dp))

            PrimaryActionButton(
                text = "Да, изменить",
                onClick = onConfirm
            )
        }
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.Top
        ) {
            Text(
                text = "Сейчас:",
                color = ArTextSecondary,
                style = MaterialTheme.typography.bodyMedium
            )

            Column(
                modifier = Modifier.padding(start = 16.dp),
                verticalArrangement = Arrangement.spacedBy(2.dp)
            ) {
                Text(text = user.workshop, color = ArTextPrimary, style = MaterialTheme.typography.bodyMedium)
                Text(text = user.role, color = ArTextPrimary, style = MaterialTheme.typography.bodyMedium)
                Text(text = user.employeeName, color = ArTextPrimary, style = MaterialTheme.typography.bodyMedium)
            }
        }

        Spacer(Modifier.height(8.dp))

        Text(
            text = "Данные сотрудника будут заменены. Продолжить?",
            color = ArTextSecondary,
            style = MaterialTheme.typography.bodyMedium
        )
    }
}

//  Сообщить

@Composable
fun ReportDialog(
    result: ScanResult,
    user: UserState,
    onSend: (String) -> Unit,
    onDismiss: () -> Unit
) {
    var comment by remember { mutableStateOf("") }

    MenuDialog(
        title = "Сообщить о проблеме",
        onDismiss = onDismiss,
        buttons = {
            SecondaryActionButton(
                text = "Отмена",
                onClick = onDismiss
            )

            Spacer(Modifier.width(8.dp))

            PrimaryActionButton(
                text = "Отправить",
                onClick = { onSend(comment.trim()) }
            )
        }
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            InfoRow("Оборудование", result.equipmentName)
            InfoRow("Состояние", result.summary)
            InfoRow("Цех", user.workshop)
            InfoRow("Автор", "${user.employeeName} (${user.role})")
        }
        OutlinedTextField(
            value = comment,
            onValueChange = { comment = it },
            label = { Text("Комментарий (необязательно)") },
            minLines = 2,
            modifier = Modifier.fillMaxWidth()
        )
        Text(
            text = "Время и автор фиксируются в журнале событий.",
            color = ArTextSecondary,
            style = MaterialTheme.typography.bodyMedium
        )
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
        Text(
            text = label,
            color = ArTextSecondary,
            style = MaterialTheme.typography.bodyMedium
        )
        Text(
            text = value,
            fontWeight = FontWeight.Medium,
            textAlign = TextAlign.End,
            style = MaterialTheme.typography.bodyMedium,
            color = ArTextPrimary,
            modifier = Modifier.weight(1f).padding(start = 16.dp)
        )
    }
}

// Меню Регистрации

// ПЕРВОЕ ОКНО
@Composable
fun SettingsDialog(
    user: UserState,
    onRegisterClick: () -> Unit,
    onChangeDataClick: () -> Unit,
    onDismiss: () -> Unit
) {
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            shape = RoundedCornerShape(20.dp),
            color = Color.Transparent,
            border = null,
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.55f)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .fillMaxHeight(0.55f)
                    .menuBackground()
                    .padding(38.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(50.dp, Alignment.CenterVertically)
            ) {
                // Пункт 1: Регистрация
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(16.dp))
                        .background(
                            // Активна, если НЕ зарегистрирован
                            if (!user.isRegistered) Color.White.copy(alpha = 0.1f)
                            else Color.White.copy(alpha = 0.03f)
                        )
                        .border(
                            width = 1.dp,
                            // Рамка тоже тускнеет
                            color = if (!user.isRegistered) Color.White.copy(alpha = 0.3f)
                            else Color.White.copy(alpha = 0.1f),
                            shape = RoundedCornerShape(16.dp)
                        )
                        .clickable(enabled = !user.isRegistered) {
                            onDismiss()
                            onRegisterClick()
                        }
                        .padding(16.dp), // ВАШ ОТСТУП НА МЕСТЕ
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.Person, contentDescription = null, tint = ArTextPrimary)

                    Column(
                        modifier = Modifier.padding(start = 20.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp) // ВАШ ОТСТУП НА МЕСТЕ
                    ) {
                        Text("Регистрация сотрудника", color = ArTextPrimary, style = MaterialTheme.typography.bodyLarge)
                        Text(
                            text = if (user.isRegistered) "Вы уже зарегистрированы" else "Цех, должность, Ф.И.О.",
                            color = ArTextSecondary,
                            style = MaterialTheme.typography.labelMedium
                        )
                    }
                }

                // Пункт 2: Изменить данные
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(16.dp))
                        .background(
                            // Активна, если ЗАРЕГИСТРИРОВАН
                            if (user.isRegistered) Color.White.copy(alpha = 0.1f)
                            else Color.White.copy(alpha = 0.03f)
                        )
                        .border(
                            width = 1.dp,
                            // Рамка тоже тускнеет
                            color = if (user.isRegistered) Color.White.copy(alpha = 0.3f)
                            else Color.White.copy(alpha = 0.1f),
                            shape = RoundedCornerShape(16.dp)
                        )
                        .clickable(enabled = user.isRegistered) {
                            onDismiss()
                            onChangeDataClick()
                        }
                        .padding(16.dp), // ВАШ ОТСТУП НА МЕСТЕ
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.Edit, contentDescription = null, tint = ArTextPrimary)

                    Column(
                        modifier = Modifier.padding(start = 20.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp) // ВАШ ОТСТУП НА МЕСТЕ
                    ) {
                        Text("Изменить данные", color = ArTextPrimary, style = MaterialTheme.typography.bodyLarge)
                        Text(
                            text = if (user.isRegistered) "Потребуется подтверждение" else "Сначала зарегистрируйтесь",
                            color = ArTextSecondary,
                            style = MaterialTheme.typography.labelMedium
                        )
                    }
                }

                // отмена

                // НОВАЯ КНОПКА ОТМЕНЫ
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center
                ) {
                    SecondaryActionButton(
                        text = "Отмена",
                        onClick = onDismiss
                    )
                }
            }

        }
    }
}