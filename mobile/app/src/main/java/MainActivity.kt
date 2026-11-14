//package com.example.intelligent_system_ar
//
//import android.graphics.Color
//import android.os.Bundle
//import android.os.Build
//import android.content.pm.PackageManager
//import androidx.activity.compose.rememberLauncherForActivityResult
//import androidx.activity.result.contract.ActivityResultContracts
//import androidx.compose.foundation.layout.*
//import androidx.compose.material3.Button
//import androidx.compose.material3.Text
//import androidx.compose.runtime.*
//import androidx.compose.ui.Modifier
//import androidx.compose.ui.unit.dp
//import androidx.core.content.ContextCompat
//import androidx.activity.ComponentActivity
//import androidx.activity.SystemBarStyle
//import androidx.activity.compose.setContent
//import androidx.activity.enableEdgeToEdge
//import androidx.lifecycle.viewmodel.compose.viewModel
//import com.example.intelligent_system_ar.ui.MainViewModel
//import com.example.intelligent_system_ar.ui.screen.camera.CameraScreen
//import com.example.intelligent_system_ar.ui.theme.Intelligent_System_ARTheme
//
//class MainActivity : ComponentActivity() {
//    override fun onCreate(savedInstanceState: Bundle?) {
//        super.onCreate(savedInstanceState)
//        enableEdgeToEdge(
//            statusBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
//            navigationBarStyle = SystemBarStyle.dark(Color.TRANSPARENT)
//        )
//        setContent {
//            Intelligent_System_ARTheme {
//                var networkAllowed by remember {
//                    mutableStateOf(Build.VERSION.SDK_INT < 37 || ContextCompat.checkSelfPermission(
//                        this, "android.permission.ACCESS_LOCAL_NETWORK") == PackageManager.PERMISSION_GRANTED)
//                }
//                val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
//                    networkAllowed = it
//                }
//                LaunchedEffect(Unit) {
//                    if (!networkAllowed) permission.launch("android.permission.ACCESS_LOCAL_NETWORK")
//                }
//                if (networkAllowed) {
//                    val viewModel: MainViewModel = viewModel()
//                    CameraScreen(viewModel = viewModel)
//                } else {
//                    Column(Modifier.fillMaxSize().padding(32.dp), verticalArrangement = Arrangement.Center) {
//                        Text("Для подключения к серверу предприятия нужен доступ к локальной сети.")
//                        Button(onClick = { permission.launch("android.permission.ACCESS_LOCAL_NETWORK") }) {
//                            Text("Разрешить доступ")
//                        }
//                    }
//                }
//            }
//        }
//    }
//}

package com.example.intelligent_system_ar

import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.intelligent_system_ar.ui.MainViewModel
import com.example.intelligent_system_ar.ui.screen.camera.CameraScreen
import com.example.intelligent_system_ar.ui.theme.Intelligent_System_ARTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(Color.TRANSPARENT)
        )
        setContent {
            Intelligent_System_ARTheme {
                // Доступ к локальной сети (Android 17+) запрашивается только на экране входа,
                // когда пользователь сам нажимает «Найти сервер в Wi-Fi». Приложение им больше не блокируется.
                val viewModel: MainViewModel = viewModel()
                CameraScreen(viewModel = viewModel)
            }
        }
    }
}