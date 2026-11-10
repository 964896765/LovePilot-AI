package com.lovepilot.ai

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.SystemBarStyle
import com.lovepilot.ai.ui.LovePilotApp
import com.lovepilot.ai.ui.LovePilotTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.rgb(11, 17, 32))
        )
        setContent {
            LovePilotTheme {
                LovePilotApp()
            }
        }
    }
}
