package com.example.intelligent_system_ar.ui.screen.login

import android.app.Activity
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.intelligent_system_ar.ui.component.PrimaryActionButton
import com.example.intelligent_system_ar.ui.component.SecondaryActionButton
import com.example.intelligent_system_ar.ui.component.menuBackground
import com.example.intelligent_system_ar.ui.theme.ArBackground
import com.example.intelligent_system_ar.ui.theme.ArTextPrimary
import com.example.intelligent_system_ar.ui.theme.ArTextSecondary

@Composable
fun LoginScreen(
    serverUrl: String,
    onLogin: (String, String, String) -> Unit,
    isLoading: Boolean,
    error: String?
) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current

    var login by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }

    // Кнопка "Войти" активна только если заполнены логин и пароль
    val canSubmit = login.isNotBlank() && password.isNotBlank() && !isLoading

    fun submit() {
        if (canSubmit) {
            focus.clearFocus()

            // =========================================================
            // ВНИМАНИЕ! АДРЕС СЕРВЕРА УКАЗАН ЗДЕСЬ!
            // Для ЭМУЛЯТОРА оставь 10.0.2.2
            // Для РЕАЛЬНОГО ТЕЛЕФОНА поменяй на IP твоего ПК (напр. 192.168.3.47)
            // =========================================================
            val hardcodedAddress = "http://10.0.2.2:8001/industrial-vision/api/v1/"

            onLogin(hardcodedAddress, login, password)
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(ArBackground)
            .padding(16.dp),
        contentAlignment = Alignment.Center
    ) {
        Surface(
            shape = RoundedCornerShape(20.dp),
            color = Color.Transparent,
            modifier = Modifier
                .widthIn(max = 400.dp)
                .fillMaxWidth()
                .fillMaxHeight(0.6f) // Уменьшили высоту, так как полей стало меньше
                .menuBackground()
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(38.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "Вход в систему",
                    color = ArTextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                    textAlign = TextAlign.Center
                )

                // Поля "Адрес сервера" больше нет

                CustomField(
                    value = login,
                    onValueChange = { login = it },
                    placeholder = "Логин",
                    keyboardType = KeyboardType.Text,
                    imeAction = ImeAction.Next,
                    onNext = { focus.moveFocus(FocusDirection.Next) }
                )

                CustomField(
                    value = password,
                    onValueChange = { password = it },
                    placeholder = "Пароль",
                    keyboardType = KeyboardType.Password,
                    imeAction = ImeAction.Done,
                    visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                    trailingIcon = {
                        TextButton(
                            onClick = { passwordVisible = !passwordVisible },
                            contentPadding = PaddingValues(0.dp),
                            modifier = Modifier.height(24.dp)
                        ) {
                            Text(
                                text = if (passwordVisible) "Скрыть" else "Показать",
                                color = ArTextPrimary,
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    },
                    onDone = { submit() }
                )

                if (error != null) {
                    Text(error, color = MaterialTheme.colorScheme.error, fontSize = 14.sp, textAlign = TextAlign.Center)
                }

                Spacer(Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    SecondaryActionButton(
                        text = "Отмена",
                        onClick = {
                            (context as? Activity)?.finish() // Закрывает приложение
                        }
                    )

                    Spacer(Modifier.width(8.dp))

                    PrimaryActionButton(
                        text = if (isLoading) "Вход…" else "Войти",
                        onClick = { submit() },
                        enabled = canSubmit
                    )
                }
            }
        }
    }
}

@Composable
private fun CustomField(
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    keyboardType: KeyboardType,
    imeAction: ImeAction,
    visualTransformation: VisualTransformation = VisualTransformation.None,
    trailingIcon: @Composable (() -> Unit)? = null,
    onNext: () -> Unit = {},
    onDone: () -> Unit = {}
) {
    val shape = RoundedCornerShape(16.dp)
    BasicTextField(
        value = value,
        onValueChange = onValueChange,
        singleLine = true,
        textStyle = MaterialTheme.typography.bodyLarge.copy(color = ArTextPrimary),
        cursorBrush = SolidColor(Color.White),
        visualTransformation = visualTransformation,
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType, imeAction = imeAction, autoCorrect = false),
        keyboardActions = KeyboardActions(onNext = { onNext() }, onDone = { onDone() }),
        modifier = Modifier.fillMaxWidth(),
        decorationBox = { inner ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(shape)
                    .background(Color.White.copy(alpha = 0.1f))
                    .border(1.dp, Color.White.copy(alpha = 0.3f), shape)
                    .padding(horizontal = 16.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Box(modifier = Modifier.weight(1f)) {
                    if (value.isEmpty()) {
                        Text(text = placeholder, color = ArTextSecondary, style = MaterialTheme.typography.bodyLarge)
                    }
                    inner()
                }
                if (trailingIcon != null) {
                    trailingIcon()
                }
            }
        }
    )
}