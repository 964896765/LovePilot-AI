package com.lovepilot.ai.ui

import android.content.ComponentName
import android.content.Intent
import android.provider.Settings
import android.service.notification.NotificationListenerService
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovepilot.ai.NotificationProbe
import com.lovepilot.ai.WeChatListener

@Composable
fun NotificationProbeScreen() {
    val context = LocalContext.current
    val state by NotificationProbe.state.collectAsStateWithLifecycle()
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { PageHeading("微信接入验证", "P0 · 通知读取与系统快捷回复实测") }
        item {
            SectionCard {
                StatusPill(if (state.connected) "通知监听已连接" else "等待通知使用权", state.connected)
                TextButton(onClick = { context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) }) { Text("打开通知使用权设置") }
                TextButton(onClick = { NotificationListenerService.requestRebind(ComponentName(context, WeChatListener::class.java)) }) { Text("重新连接监听服务") }
            }
        }
        item {
            SectionCard {
                Text("受控测试会话")
                Text("开始后，让测试联系人发送下方测试码。将微信切至后台，保留微信消息通知和通知内容显示。测试码有效期为十分钟。", color = Muted, modifier = Modifier.padding(vertical = 10.dp))
                Button(onClick = { NotificationProbe.start(context) }, modifier = Modifier.fillMaxWidth()) { Text("开始新的通知测试") }
                if (state.marker.isNotEmpty()) {
                    SelectionContainer { Text(state.marker, color = Mint, modifier = Modifier.padding(top = 16.dp)) }
                    InfoLine("已匹配测试通知", state.seen.toString())
                    InfoLine("通知中的联系人称呼", state.senderLabel.ifBlank { "等待通知" })
                    InfoLine("可用快捷回复动作", state.actionCount.toString())
                    Text(state.result, color = Muted, modifier = Modifier.padding(top = 10.dp))
                }
            }
        }
        item {
            SectionCard {
                Text("快捷回复送达验证")
                Text("收到测试通知后，可向同一会话发送固定测试回复。系统接受动作后，还需在测试联系人一侧核对原文送达。", color = Muted, modifier = Modifier.padding(vertical = 10.dp))
                if (state.reply.isNotEmpty()) SelectionContainer { Text(state.reply, color = Mint) }
                Button(onClick = { NotificationProbe.send(context) }, enabled = state.canReply,
                    modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) { Text("发送测试回复") }
                TextButton(onClick = { NotificationProbe.clear(context) }) { Text("清除本轮测试记录") }
            }
        }
    }
}
