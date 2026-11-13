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
                val viewModel: MainViewModel = viewModel()
                CameraScreen(viewModel = viewModel)
            }
        }
    }
}
