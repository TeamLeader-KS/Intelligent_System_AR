package com.example.intelligent_system_ar.ui.screen.login

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.layout.Arrangement
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
import com.example.intelligent_system_ar.data.remote.ServerConfig
import com.example.intelligent_system_ar.data.remote.ServerDiscovery
import com.example.intelligent_system_ar.ui.component.PrimaryActionButton
import com.example.intelligent_system_ar.ui.component.SecondaryActionButton
import com.example.intelligent_system_ar.ui.component.menuBackground
import com.example.intelligent_system_ar.ui.theme.ArBackground
import com.example.intelligent_system_ar.ui.theme.ArTextPrimary
import com.example.intelligent_system_ar.ui.theme.ArTextSecondary
import kotlinx.coroutines.launch
import java.io.IOException

@Composable
fun LoginScreen(
    serverUrl: String,
    onLogin: (String, String, String) -> Unit,
    isLoading: Boolean,
    error: String?
) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val scope = rememberCoroutineScope()

    var address by remember { mutableStateOf(serverUrl.takeUnless { it == ServerConfig.DEFAULT_URL }.orEmpty()) }
    var login by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }

    var searching by remember { mutableStateOf(false) }
    var searchMessage by remember { mutableStateOf("Поиск сервера в Wi-Fi...") }

    val canSubmit = address.isNotBlank() && login.isNotBlank() && password.isNotBlank() && !isLoading && !searching

    fun submit() {
        if (canSubmit) {
            focus.clearFocus()
            try {
                val normalized = ServerConfig.normalize(address)
                onLogin(normalized, login, password)
            } catch (e: IllegalArgumentException) {
                // Ошибка адреса
            }
        }
    }

    suspend fun search() {
        if (searching) return
        searching = true
        try {
            val found = ServerDiscovery.find(context, address.ifBlank { serverUrl })
            if (found != null) {
                address = found
                searchMessage = "Сервер найден"
            } else {
                searchMessage = "Сервер не найден"
            }
        } catch (e: Exception) {
            searchMessage = "Ошибка сети"
        } finally {
            searching = false
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
                .fillMaxHeight(0.7f) // Увеличили высоту окна до 70%
                .menuBackground()
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(38.dp) // Отступы как в диалогах
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

                CustomField(
                    value = address,
                    onValueChange = { address = it },
                    placeholder = "Адрес сервера",
                    keyboardType = KeyboardType.Uri,
                    imeAction = ImeAction.Next,
                    onNext = { focus.moveFocus(FocusDirection.Next) }
                )

                // Строка с поиском: кнопка + текст в одну линию
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    TextButton(
                        onClick = { scope.launch { search() } },
                        enabled = !searching && !isLoading,
                        contentPadding = PaddingValues(0.dp)
                    ) {
                        Text("Поиск", color = ArTextPrimary, style = MaterialTheme.typography.labelLarge)
                    }

                    Text(
                        text = searchMessage,
                        color = ArTextSecondary,
                        fontSize = 12.sp,
                        modifier = Modifier.weight(1f)
                    )
                }

                if (searching) {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = ArTextPrimary)
                }

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
                            // Убираем стандартные отступы кнопки, чтобы она не растягивала поле
                            contentPadding = PaddingValues(0.dp),
                            modifier = Modifier.height(24.dp)
                        ) {
                            Text(
                                text = if (passwordVisible) "Скрыть" else "Показать",
                                color = ArTextPrimary,
                                style = MaterialTheme.typography.bodyMedium // Чуть уменьшили шрифт для аккуратности
                            )
                        }
                    },
                    onDone = { submit() }
                )

                if (error != null) {
                    Text(error, color = MaterialTheme.colorScheme.error, fontSize = 14.sp, textAlign = TextAlign.Center)
                }

                Spacer(Modifier.height(16.dp))

                // Кнопки "Отмена" и "Войти" в один ряд, прижаты к правому краю (как в диалогах)
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    SecondaryActionButton(
                        text = "Отмена",
                        onClick = {
                            login = ""
                            password = ""
                            focus.clearFocus()
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