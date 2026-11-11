package com.lovepilot.ai.ui

import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovepilot.ai.AgentState
import com.lovepilot.ai.AgentViewModel
import com.lovepilot.ai.NotificationProbe

@Composable
fun SafetyScreen(state: AgentState, model: AgentViewModel, diagnostics: () -> Unit) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val probe by NotificationProbe.state.collectAsStateWithLifecycle()
    var permission by remember { mutableStateOf(NotificationProbe.hasAccess(context)) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) permission = NotificationProbe.hasAccess(context)
        }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { PageHeading("安全中心", "确认每一次表达，随时暂停 AI 处理") }
        item {
            SectionCard {
                StatusPill(if (state.paused) "AI 处理已暂停" else "人工确认模式", !state.paused)
                Text("生成建议后，可以编辑、复制，再到微信核对原会话并发送。", color = Muted, modifier = Modifier.padding(vertical = 12.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("暂停 AI 处理", modifier = Modifier.weight(1f))
                    Switch(state.paused, onCheckedChange = model::setPaused)
                }
                Text("暂停会取消本机进行中的生成、清除待选建议，并同步服务端暂停状态。", color = Muted)
            }
        }
        item {
            SectionCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("受限自动回复", modifier = Modifier.weight(1f))
                    Switch(false, onCheckedChange = null, enabled = false)
                }
                Text("等待验收", color = Purple)
                Text("需要可靠的联系人识别、双方许可、平台允许的发送方式与可验证的送达结果。验收记录齐备后才开放测试会话。", color = Muted, modifier = Modifier.padding(top = 10.dp))
            }
        }
        item {
            SectionCard {
                InfoLine("系统通知使用权", if (permission) "已授权" else "尚未授权")
                InfoLine("通知监听连接", if (probe.connected) "已连接" else "尚未连接")
                InfoLine("Agent 连接", if (state.connected) "已连接" else "尚未连接")
                TextButton(onClick = { context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) }) { Text("管理通知使用权") }
                TextButton(onClick = diagnostics) { Text("微信接入验证") }
            }
        }
        item {
            SectionCard {
                Text("重要话题由你处理")
                Text("关系决定、争吵、金钱、隐私、健康和安全求助会进入人工处理。建议中的推测与未知信息会单独展示。", color = Muted, modifier = Modifier.padding(top = 10.dp))
            }
        }
    }
}
