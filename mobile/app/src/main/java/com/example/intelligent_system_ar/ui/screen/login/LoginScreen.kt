package com.example.intelligent_system_ar.ui.screen.login

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.example.intelligent_system_ar.data.remote.ServerDiscovery
import com.example.intelligent_system_ar.ui.theme.ArBackground
import com.example.intelligent_system_ar.ui.theme.ArTextPrimary
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
    var address by remember { mutableStateOf<String?>(null) }
    var searching by remember { mutableStateOf(false) }
    var searchMessage by remember { mutableStateOf("Ищем сервер в Wi-Fi…") }
    var searchedAutomatically by remember { mutableStateOf(false) }
    var login by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }
    val canSubmit = address != null && login.isNotBlank() && password.isNotBlank() && !isLoading && !searching

    fun submit() {
        if (canSubmit) {
            focus.clearFocus()
            onLogin(address!!, login, password)
        }
    }

    suspend fun search() {
        if (searching) return
        searching = true
        address = null
        searchMessage = "Ищем сервер в Wi-Fi…"
        try {
            address = ServerDiscovery.find(context, serverUrl)
            searchMessage = if (address != null) "Сервер найден"
                else "Сервер не найден. Проверьте Wi-Fi и запуск проекта на ноутбуке, затем повторите поиск."
        } catch (_: IOException) {
            searchMessage = "Нет доступа к Wi-Fi. Подключитесь к сети ноутбука."
        } catch (_: SecurityException) {
            searchMessage = "Разрешите приложению доступ к локальной сети в настройках Android."
        } finally {
            searching = false
        }
    }

    LaunchedEffect(isLoading) {
        if (!isLoading && !searchedAutomatically) {
            searchedAutomatically = true
            search()
        }
    }

    Box(Modifier.fillMaxSize().background(ArBackground).safeDrawingPadding().imePadding()
        .verticalScroll(rememberScrollState()), contentAlignment = Alignment.TopCenter) {
        Column(
            modifier = Modifier.widthIn(max = 480.dp).fillMaxWidth().padding(horizontal = 24.dp, vertical = 24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text("Вход в систему", style = MaterialTheme.typography.headlineSmall, color = ArTextPrimary)
            Surface(shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceVariant) {
                Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(searchMessage, color = ArTextPrimary)
                    if (searching) LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    address?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                    TextButton(onClick = { scope.launch { search() } }, enabled = !searching && !isLoading) {
                        Text(if (searching) "Поиск…" else "Найти сервер в Wi-Fi")
                    }
                }
            }
            OutlinedTextField(
                value = login, onValueChange = { login = it }, label = { Text("Логин") },
                enabled = !isLoading, singleLine = true, modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(autoCorrectEnabled = false, imeAction = ImeAction.Next),
                keyboardActions = KeyboardActions(onNext = { focus.moveFocus(FocusDirection.Next) })
            )
            OutlinedTextField(
                value = password, onValueChange = { password = it }, label = { Text("Пароль") },
                enabled = !isLoading, singleLine = true, modifier = Modifier.fillMaxWidth(),
                visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    TextButton(onClick = { passwordVisible = !passwordVisible }) {
                        Text(if (passwordVisible) "Скрыть" else "Показать")
                    }
                },
                keyboardOptions = KeyboardOptions(autoCorrectEnabled = false, keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { submit() })
            )
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(onClick = { submit() }, enabled = canSubmit,
                modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) {
                if (isLoading) CircularProgressIndicator(modifier = Modifier.size(20.dp))
                else Text("Войти")
            }
        }
    }
}
