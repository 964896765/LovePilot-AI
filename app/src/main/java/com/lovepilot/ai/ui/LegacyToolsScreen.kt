package com.lovepilot.ai.ui

import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.lovepilot.ai.DeepSeek
import com.lovepilot.ai.Policy
import com.lovepilot.ai.Store
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun LegacyToolsScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var alias by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("") }
    var key by remember { mutableStateOf("") }
    var result by remember { mutableStateOf("保留原有本地工具，供兼容与离线排查使用。") }
    var busy by remember { mutableStateOf(false) }
    var clear by remember { mutableStateOf(false) }
    var consent by remember { mutableStateOf(false) }
    fun run(action: suspend () -> String) {
        scope.launch {
            busy = true
            try { result = withContext(Dispatchers.IO) { action() } }
            catch (error: Exception) { result = error.message ?: "操作失败" }
            finally { busy = false }
        }
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { PageHeading("本地兼容工具", "原有功能保留在独立工具页") }
        item {
            SectionCard {
                Text("本地联系人")
                OutlinedTextField(alias, { alias = it.take(100) }, label = { Text("联系人别名") }, modifier = Modifier.fillMaxWidth().padding(top = 10.dp))
                OutlinedTextField(notes, { notes = it.take(2000) }, label = { Text("已确认资料与偏好") }, modifier = Modifier.fillMaxWidth().padding(top = 10.dp))
                Row { Checkbox(consent, { consent = it }); Text("已确认资料保存授权", color = Muted) }
                Row {
                    TextButton(onClick = {
                        val label = alias; val profile = notes
                        run { Store(context).use { it.addContact(label, profile, true); it.contacts() } }
                    }, enabled = !busy && consent && alias.isNotBlank()) { Text("保存本地档案") }
                    TextButton(onClick = { run { Store(context).use { it.contacts() } } }, enabled = !busy) { Text("查看档案") }
                }
            }
        }
        item {
            SectionCard {
                Text("直接调用 DeepSeek")
                OutlinedTextField(key, { key = it }, label = { Text("API Key，仅在本页内存中使用") }, modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                    visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
                OutlinedTextField(message, { message = it.take(4000) }, label = { Text("粘贴消息") }, minLines = 2, modifier = Modifier.fillMaxWidth().padding(top = 10.dp))
                Button(onClick = {
                    val apiKey = key; val profile = notes; val incoming = message
                    if (Policy.needsHuman(incoming)) result = "这次请由本人处理。"
                    else run { DeepSeek.suggest(apiKey, profile, incoming) }
                }, enabled = !busy && key.isNotBlank() && message.isNotBlank(), modifier = Modifier.padding(top = 12.dp)) { Text("生成回复建议") }
            }
        }
        item {
            SectionCard {
                Text("通知兼容与日志")
                TextButton(onClick = { context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) }) { Text("打开通知使用权设置") }
                TextButton(onClick = { run { Store(context).use { it.history() } } }, enabled = !busy) { Text("查看兼容日志") }
                TextButton(onClick = { clear = true }, enabled = !busy) { Text("清除本地档案与日志", color = MaterialTheme.colorScheme.error) }
            }
        }
        item { SectionCard { Text(result) } }
    }
    if (clear) AlertDialog(onDismissRequest = { clear = false }, title = { Text("清除本地数据？") },
        text = { Text("将清除旧版保存在手机上的档案、消息与日志。") },
        confirmButton = { TextButton(onClick = { run { Store(context).use { it.clearAll() }; "本地数据已清除" }; clear = false }) { Text("确认清除") } },
        dismissButton = { TextButton(onClick = { clear = false }) { Text("取消") } })
}
