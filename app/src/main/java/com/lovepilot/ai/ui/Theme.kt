package com.lovepilot.ai.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

val Background = Color(0xFF0B1120)
val Panel = Color(0xFF151E31)
val Purple = Color(0xFFB7A8FF)
val Mint = Color(0xFF83E4D0)
val Muted = Color(0xFF9BA9C2)

@Composable
fun LovePilotTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = darkColorScheme(
        primary = Purple, onPrimary = Color(0xFF21153C), secondary = Mint,
        background = Background, surface = Panel, surfaceVariant = Color(0xFF202B40),
        onBackground = Color(0xFFF3F4FF), onSurface = Color(0xFFF3F4FF)
    ), content = content)
}

@Composable
fun SectionCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Card(modifier = modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Panel.copy(alpha = 0.82f)),
        border = BorderStroke(1.dp, Brush.linearGradient(listOf(Color.White.copy(alpha = 0.16f), Purple.copy(alpha = 0.08f), Mint.copy(alpha = 0.06f)))),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)) {
        Column(Modifier.padding(18.dp), content = content)
    }
}

@Composable
fun PageHeading(title: String, subtitle: String) {
    Column(Modifier.padding(vertical = 8.dp)) {
        Text(title, fontSize = 27.sp, fontWeight = FontWeight.Bold)
        Text(subtitle, color = Muted, fontSize = 13.sp, modifier = Modifier.padding(top = 6.dp))
    }
}

@Composable
fun StatusPill(text: String, active: Boolean = false) {
    Box(Modifier.background((if (active) Mint else Muted).copy(alpha = 0.12f), RoundedCornerShape(50))
        .padding(horizontal = 12.dp, vertical = 7.dp)) {
        Text(text, color = if (active) Mint else Muted, fontSize = 11.sp)
    }
}
