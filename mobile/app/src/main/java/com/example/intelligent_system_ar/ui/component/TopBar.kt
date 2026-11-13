package com.example.intelligent_system_ar.ui.component

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.intelligent_system_ar.data.model.UserState
import com.example.intelligent_system_ar.ui.theme.ArScrim
import com.example.intelligent_system_ar.ui.theme.ArTextPrimary
import com.example.intelligent_system_ar.ui.theme.ArTextSecondary
import com.example.intelligent_system_ar.ui.theme.StatusWarning

@Composable
fun MainTopBar(
    user: UserState,
    onRegisterClick: () -> Unit,
    onChangeDataClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    // Состояние для открытия меню
    var menuOpen by remember { mutableStateOf(false) }

    // Сама шапка
    Row(
        modifier = modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Top
    ) {
        // Кнопка-шестеренка
        IconButton(
            onClick = { menuOpen = true },
            modifier = Modifier.background(ArScrim.copy(alpha = 0.65f), CircleShape)
        ) {
            Icon(
                imageVector = Icons.Default.Settings,
                contentDescription = "Настройки",
                tint = ArTextPrimary
            )
        }

        // Плашка с информацией (Цех / Должность / ФИО)
        Column(
            horizontalAlignment = Alignment.End,
            modifier = Modifier
                .clip(RoundedCornerShape(16.dp))
                .background(ArScrim.copy(alpha = 0.65f))
                .padding(horizontal = 16.dp, vertical = 8.dp)
        ) {
            if (user.isRegistered) {
                Text(
                    text = user.workshop,
                    color = ArTextPrimary,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.bodyLarge
                )
                Text(
                    text = user.role,
                    color = ArTextPrimary,
                    style = MaterialTheme.typography.bodyMedium
                )
                Text(
                    text = user.employeeName,
                    color = ArTextSecondary,
                    style = MaterialTheme.typography.bodyMedium
                )
            } else {
                Text(
                    text = "Не зарегистрирован",
                    color = StatusWarning,
                    style = MaterialTheme.typography.bodyMedium
                )
            }
        }
    }

    // Вызов диалога, если он открыт
    if (menuOpen) {
        SettingsDialog(
            user = user,
            onRegisterClick = onRegisterClick,
            onChangeDataClick = onChangeDataClick,
            onDismiss = { menuOpen = false }
        )
    }
}