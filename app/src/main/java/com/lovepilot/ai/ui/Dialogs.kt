package com.lovepilot.ai.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import org.json.JSONObject

@Composable
fun ContactDialog(contact: JSONObject?, dismiss: () -> Unit, save: (String, String, String, Boolean) -> Unit) {
    var alias by remember { mutableStateOf(contact?.optString("alias").orEmpty()) }
    var notes by remember { mutableStateOf(contact?.optString("notes").orEmpty()) }
    var consent by remember { mutableStateOf(contact?.optBoolean("consent") ?: false) }
    val id = contact?.optString("contact_id").orEmpty()
    AlertDialog(onDismissRequest = dismiss, title = { Text(if (id.isBlank()) "建立联系人档案" else "编辑联系人") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(alias, { alias = it.take(100) }, label = { Text("联系人称呼") }, singleLine = true, modifier = Modifier.testTag("contact-alias"))
                OutlinedTextField(notes, { notes = it.take(2000) }, label = { Text("双方确认的资料与沟通偏好") }, minLines = 3)
                Row {
                    Checkbox(consent, { consent = it }, modifier = Modifier.testTag("contact-consent"))
                    Text("对方知情并同意使用 AI 辅助及保存必要资料", color = Muted)
                }
                if (id.isNotBlank()) Text("会话 ID\n$id", color = Muted)
            }
        },
        confirmButton = { TextButton(onClick = { save(id, alias.trim(), notes, consent); dismiss() }, enabled = alias.isNotBlank()) { Text("保存档案") } },
        dismissButton = { TextButton(onClick = dismiss) { Text("取消") } })
}

@Composable
fun FactDialog(existing: JSONObject?, dismiss: () -> Unit, save: (String, String) -> Unit) {
    var key by remember { mutableStateOf(existing?.optString("key").orEmpty()) }
    var value by remember { mutableStateOf(existing?.optString("value").orEmpty()) }
    AlertDialog(onDismissRequest = dismiss, title = { Text(if (existing == null) "确认一条记忆" else "编辑已确认记忆") },
        text = { Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("请根据对方明确分享的事实保存。", color = Muted)
            OutlinedTextField(key, { key = it.take(60) }, enabled = existing == null, label = { Text("类别或标题") })
            OutlinedTextField(value, { value = it.take(500) }, label = { Text("事实内容") }, minLines = 2)
        } },
        confirmButton = { TextButton(onClick = { save(key, value); dismiss() }, enabled = key.isNotBlank() && value.isNotBlank()) { Text("确认保存") } },
        dismissButton = { TextButton(onClick = dismiss) { Text("取消") } })
}

@Composable
fun PasswordDialog(title: String, detail: String, dismiss: () -> Unit, confirm: (String) -> Unit) {
    var password by remember { mutableStateOf("") }
    AlertDialog(onDismissRequest = dismiss, title = { Text(title) }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(detail, color = Muted)
            OutlinedTextField(password, { password = it }, label = { Text("备份密码，至少 12 位") },
                visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
        }
    }, confirmButton = { TextButton(onClick = { confirm(password); dismiss() }, enabled = password.length >= 12) { Text("继续") } },
        dismissButton = { TextButton(onClick = dismiss) { Text("取消") } })
}
