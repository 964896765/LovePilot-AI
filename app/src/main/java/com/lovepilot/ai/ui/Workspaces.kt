package com.lovepilot.ai.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.lovepilot.ai.AgentState
import com.lovepilot.ai.AgentViewModel
import org.json.JSONObject

@Composable
fun ContactPicker(state: AgentState, select: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    val selected = state.contacts.firstOrNull { it.optString("contact_id") == state.selectedContact }
    Box {
        OutlinedButton(onClick = { expanded = true }, enabled = state.contacts.isNotEmpty() && !state.busy,
            modifier = Modifier.fillMaxWidth()) {
            Text(selected?.optString("alias")?.ifBlank { "未命名联系人" } ?: "请先创建联系人")
            Spacer(Modifier.weight(1f))
            Text("切换 ▾", color = Muted)
        }
        DropdownMenu(expanded, { expanded = false }) {
            state.contacts.forEach { contact ->
                DropdownMenuItem(text = { Text(contact.optString("alias")) }, onClick = {
                    select(contact.getString("contact_id")); expanded = false
                })
            }
        }
    }
}

@Composable
fun HomeScreen(state: AgentState, chat: () -> Unit, configure: () -> Unit, route: (String) -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("LOVE PILOT", color = Purple, fontSize = 11.sp, letterSpacing = 3.sp)
                Text("让交流，自然发生", fontSize = 26.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 8.dp))
            }
            StatusPill(if (state.connected) "服务已连接" else "等待连接", state.connected)
        }
        Box(Modifier.fillMaxWidth().background(Brush.linearGradient(listOf(Color(0xFF27314E), Color(0xFF1B2841), Color(0xFF182E35))), RoundedCornerShape(28.dp)).padding(22.dp)) {
            Column(Modifier.fillMaxWidth()) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("你的 AI\n沟通搭档", fontSize = 28.sp, lineHeight = 38.sp, fontWeight = FontWeight.Bold)
                        Text("理解表达 · 记住共识\n每条建议，由你决定", fontSize = 12.sp, color = Muted, lineHeight = 21.sp, modifier = Modifier.padding(top = 12.dp))
                    }
                    Canvas(Modifier.size(118.dp)) {
                        val radius = size.minDimension * 0.43f
                        val center = Offset(size.width / 2, size.height / 2)
                        drawCircle(Brush.radialGradient(listOf(Mint.copy(alpha = 0.55f), Purple.copy(alpha = 0.08f), Color.Transparent), center, radius * 1.3f), radius * 1.3f, center)
                        drawCircle(Brush.radialGradient(listOf(Color(0xFF8CEADC), Color(0xFF3A668B), Color(0xFF6458B7)), center - Offset(radius * 0.3f, radius * 0.4f), radius * 1.7f), radius, center)
                        drawCircle(Mint.copy(alpha = 0.55f), radius, center, style = Stroke(1.5f))
                        drawCircle(Color.White.copy(alpha = 0.65f), radius * 0.1f, center - Offset(radius * 0.35f, radius * 0.45f))
                    }
                }
                Button(onClick = if (state.connected) chat else configure, modifier = Modifier.fillMaxWidth().padding(top = 20.dp)) {
                    Text(if (state.connected) "开始一次交流  →" else "连接我的 Agent  →")
                }
            }
        }
        val counts = state.status.optJSONObject("counts")
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Metric("联系人", state.contacts.size.toString(), Modifier.weight(1f))
            Metric("已确认记忆", (counts?.optInt("facts") ?: 0).toString(), Modifier.weight(1f))
            Metric("待确认", state.candidates.count { it.optString("status") == "pending" }.toString(), Modifier.weight(1f))
        }
        Text("你的工作空间", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionCard(Modifier.weight(1f)) {
                Text("Agent 工作流", fontWeight = FontWeight.SemiBold)
                Text("查看实际节点与执行轨迹", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(vertical = 10.dp))
                TextButton(onClick = { route("workflow") }, contentPadding = PaddingValues(0.dp)) { Text("查看工作流 →") }
            }
            SectionCard(Modifier.weight(1f)) {
                Text("微信 AI Bot", fontWeight = FontWeight.SemiBold)
                Text(if (state.bot.optString("state") == "recent_event") "近期收到微信事件" else "等待适配器活动", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(vertical = 10.dp))
                TextButton(onClick = { route("bot") }, contentPadding = PaddingValues(0.dp)) { Text("管理 Bot →") }
            }
        }
        SectionCard {
            Text("运行概览", fontWeight = FontWeight.SemiBold)
            InfoLine("聊天模型", if (state.status.optBoolean("model_configured")) "已配置" else "等待配置")
            InfoLine("长期记忆", when (state.status.optString("memory_status")) { "ready" -> "Mem0 索引就绪"; "loading" -> "本地模型加载中"; "unavailable" -> "索引加载失败"; else -> "等待模型配置" })
            InfoLine("自动回复", if (state.bot.optBoolean("auto_reply_enabled")) "已开启" else "已暂停")
        }
        Spacer(Modifier.height(12.dp))
    }
}

@Composable
private fun Metric(label: String, value: String, modifier: Modifier) {
    SectionCard(modifier) {
        Text(value, fontSize = 25.sp, color = Mint, fontWeight = FontWeight.SemiBold)
        Text(label, color = Muted, fontSize = 11.sp, modifier = Modifier.padding(top = 6.dp))
    }
}

@Composable
fun InfoLine(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(label, color = Muted, fontSize = 12.sp, modifier = Modifier.weight(1f))
        Text(value, fontSize = 12.sp)
    }
}

@Composable
fun ChatScreen(state: AgentState, model: AgentViewModel, voice: () -> Unit, addContact: () -> Unit, voiceText: String, consumeVoice: () -> Unit) {
    var message by remember(state.selectedContact) { mutableStateOf("") }
    var selectedSkill by remember { mutableStateOf("romance-reply") }
    val context = LocalContext.current
    LaunchedEffect(voiceText) { if (voiceText.isNotBlank()) { message = voiceText; consumeVoice() } }
    LaunchedEffect(state.lastResult) {
        if (state.lastResult != null && message.trim() == state.lastInput) message = ""
    }
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(horizontal = 20.dp)) {
            PageHeading("聊天工作台", "回复、分析与复盘，始终保留你的选择")
            ContactPicker(state, model::selectContact)
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                state.skills.filter { it.optBoolean("enabled", true) }.forEach { skill ->
                    FilterChip(selectedSkill == skill.optString("id"), onClick = { selectedSkill = skill.optString("id") },
                        label = { Text(skill.optString("name"), fontSize = 12.sp) })
                }
            }
        }
        LazyColumn(Modifier.weight(1f).testTag("chat-history"), contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            if (state.messages.isEmpty()) item {
                SectionCard {
                    Text("从一条消息开始", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
                    Text("选择已授权联系人，输入对方发来的消息。AI 会结合已确认资料给出建议。", color = Muted, modifier = Modifier.padding(top = 12.dp))
                    if (state.contacts.isEmpty()) TextButton(onClick = addContact) { Text("创建联系人") }
                }
            }
            items(state.messages) { item ->
                val assistant = item.optString("role") == "assistant"
                Column(Modifier.fillMaxWidth(), horizontalAlignment = if (assistant) Alignment.Start else Alignment.End) {
                    Text(if (assistant) "LovePilot · AI 建议" else "收到的消息", color = Muted, fontSize = 10.sp, modifier = Modifier.padding(bottom = 6.dp))
                    Box(Modifier.widthIn(max = 320.dp).background(if (assistant) Panel else Color(0xFF3C345D), RoundedCornerShape(20.dp)).padding(16.dp)) {
                        Text(item.optString("content"), lineHeight = 24.sp, fontSize = 15.sp)
                    }
                    if (assistant) TextButton(onClick = { copy(context, item.optString("content")) }) { Text("确认后复制", fontSize = 11.sp) }
                }
            }
            state.lastResult?.let { result ->
                item {
                    SectionCard {
                        if (result.optString("action") != "draft") {
                            Text("需要你亲自处理", color = Purple, fontWeight = FontWeight.SemiBold)
                            Text(result.optString("reason"), modifier = Modifier.padding(top = 8.dp))
                            result.optString("draft").takeIf { it.isNotBlank() }?.let { Text(it, color = Muted, modifier = Modifier.padding(top = 8.dp)) }
                        } else {
                            val analysis = result.optJSONObject("analysis")
                            Text("表达线索", color = Mint, fontSize = 12.sp)
                            if (analysis?.has("facts") == true) {
                                listOf("facts" to "原话与上下文", "inferences" to "可能的解释", "unknowns" to "仍需了解").forEach { (key, label) ->
                                    val values = analysis.optJSONArray(key)
                                    if (values != null && values.length() > 0) {
                                        Text(label, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 12.dp))
                                        Text((0 until values.length()).joinToString("\n") { values.optString(it) }, color = Muted, fontSize = 12.sp)
                                    }
                                }
                            } else Text(analysis?.toString(2)?.take(1500) ?: "请结合原话与实际沟通判断。", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(top = 8.dp))
                        }
                    }
                }
                val options = result.optJSONArray("reply_options")
                if (result.optString("action") == "draft" && options != null) {
                    items(options.length()) { index ->
                        ReplyOptionCard(options.getJSONObject(index), state.selectedContact,
                            flirtingEnabled = state.settings.optJSONObject("personal_style")?.optString("flirting") != "关闭",
                            humorEnabled = state.settings.optJSONObject("personal_style")?.optString("humor") != "关闭")
                    }
                }
                item {
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("shorter" to "简短一些", "longer" to "更详细", "casual" to "更口语", "gentle" to "更温柔").forEach { (key, label) ->
                            SuggestionChip(onClick = { model.draft(state.lastInput, state.lastSkill, regenerate = true, refinement = key) },
                                label = { Text(label) }, enabled = !state.busy && !state.paused && state.lastInput.isNotBlank() && state.connected)
                        }
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        TextButton(onClick = { model.draft(state.lastInput, state.lastSkill, regenerate = true) },
                            enabled = !state.busy && !state.paused && state.lastInput.isNotBlank() && state.connected) { Text("重新生成") }
                        TextButton(onClick = model::cancelReply, enabled = !state.busy) { Text("取消本次回复") }
                    }
                }
            }
        }
        Surface(color = Background) {
            Column(Modifier.padding(horizontal = 20.dp, vertical = 10.dp)) {
                OutlinedTextField(message, { message = it.take(4000) }, modifier = Modifier.fillMaxWidth().testTag("chat-message"),
                    placeholder = { Text("粘贴对方发来的消息…") }, minLines = 2, maxLines = 4, shape = RoundedCornerShape(20.dp))
                Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = voice, enabled = !state.busy) { Text("语音转写") }
                    Spacer(Modifier.weight(1f))
                    Button(onClick = { model.draft(message.trim(), selectedSkill) },
                        modifier = Modifier.testTag("chat-generate"), enabled = message.isNotBlank() && state.selectedContact.isNotBlank() && state.connected && !state.busy && !state.paused) { Text(if (state.paused) "AI 已暂停" else "生成建议  ↑") }
                }
            }
        }
    }
}

@Composable
private fun ReplyOptionCard(option: JSONObject, contactId: String, flirtingEnabled: Boolean, humorEnabled: Boolean) {
    val context = LocalContext.current
    val original = option.optString("text")
    var edited by remember(contactId, original) { mutableStateOf(original) }
    var showReason by remember(contactId, original) { mutableStateOf(false) }
    var notice by remember(contactId, original) { mutableStateOf("") }
    val title = when (option.optString("id")) {
        "gentle" -> "自然温柔"
        "humor" -> if (humorEnabled) "轻松幽默" else "自然表达"
        else -> if (flirtingEnabled) "适度暧昧" else "自然关心"
    }
    SectionCard {
        Text(title, color = Mint, fontWeight = FontWeight.SemiBold)
        OutlinedTextField(edited, { edited = it.take(2000); notice = "" }, modifier = Modifier.fillMaxWidth().padding(top = 12.dp).testTag("reply-edit-${option.optString("id")}"),
            minLines = 2, label = { Text("编辑回复") }, shape = RoundedCornerShape(16.dp))
        Row {
            TextButton(onClick = { copy(context, edited.trim()); notice = "已复制，请在微信核对联系人并发送" }, enabled = edited.isNotBlank(),
                modifier = Modifier.testTag("reply-copy-${option.optString("id")}")) { Text("确认并复制") }
            TextButton(onClick = { showReason = !showReason }) { Text("生成原因") }
        }
        if (showReason) Text(option.optString("reason"), color = Muted, fontSize = 12.sp)
        TextButton(onClick = {
            val intent = context.packageManager.getLaunchIntentForPackage("com.tencent.mm")
            if (intent == null) notice = "请从手机桌面打开微信，核对原会话后发送"
            else runCatching { context.startActivity(intent) }.onFailure { notice = "微信未能打开，请从手机桌面进入" }
        }) { Text("打开微信") }
        if (notice.isNotBlank()) Text(notice, color = Mint, fontSize = 12.sp)
    }
}

private fun copy(context: Context, text: String) {
    (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager)
        .setPrimaryClip(ClipData.newPlainText("LovePilot AI 建议", text))
}

@Composable
fun ContactsScreen(state: AgentState, edit: (JSONObject?) -> Unit, chat: (String) -> Unit, revoke: (String) -> Unit, delete: (JSONObject) -> Unit) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item {
            PageHeading("联系人", "每位联系人，拥有独立的上下文与记忆")
            Button(onClick = { edit(null) }, enabled = state.connected && !state.busy, modifier = Modifier.fillMaxWidth()) { Text("＋ 建立联系人档案") }
        }
        if (state.contacts.isEmpty()) item { SectionCard { Text("还没有联系人"); Text("连接 Agent 后建立档案，微信 Bot 会话也会在这里出现。", color = Muted, modifier = Modifier.padding(top = 10.dp)) } }
        items(state.contacts, key = { it.getString("contact_id") }) { contact ->
            SectionCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(46.dp).background(Purple.copy(alpha = 0.18f), RoundedCornerShape(16.dp)), contentAlignment = Alignment.Center) {
                        Text(contact.optString("alias").take(1), color = Purple, fontSize = 20.sp)
                    }
                    Column(Modifier.weight(1f).padding(start = 12.dp)) {
                        Text(contact.optString("alias"), fontWeight = FontWeight.SemiBold)
                        Text(contact.optString("contact_id"), color = Muted, fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                    StatusPill(if (contact.optBoolean("consent")) "已授权" else "待授权", contact.optBoolean("consent"))
                }
                Text(contact.optString("notes").ifBlank { "尚未添加已确认资料" }, color = Muted, fontSize = 13.sp, modifier = Modifier.padding(top = 14.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    TextButton(onClick = { chat(contact.getString("contact_id")) }, enabled = !state.busy) { Text("聊天") }
                    TextButton(onClick = { edit(contact) }, enabled = !state.busy) { Text("编辑") }
                    if (contact.optBoolean("consent")) TextButton(onClick = { revoke(contact.getString("contact_id")) }, enabled = !state.busy) { Text("撤销") }
                    TextButton(onClick = { delete(contact) }, enabled = !state.busy) { Text("删除", color = MaterialTheme.colorScheme.error) }
                }
            }
        }
    }
}

@Composable
fun MemoryScreen(state: AgentState, model: AgentViewModel, edit: (JSONObject?) -> Unit, delete: (JSONObject) -> Unit) {
    var query by remember { mutableStateOf("") }
    val pending = state.candidates.filter { it.optString("contact_id") == state.selectedContact && it.optString("status") == "pending" }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item {
            PageHeading("记忆空间", "原话有来源，重要记忆由你确认")
            ContactPicker(state, model::selectContact)
            Row(Modifier.padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(query, { query = it.take(500) }, modifier = Modifier.weight(1f), label = { Text("检索已确认的话题") }, singleLine = true)
                TextButton(onClick = { model.searchMemory(query) }, enabled = query.isNotBlank() && state.selectedContact.isNotBlank() && !state.busy) { Text("检索") }
            }
        }
        if (pending.isNotEmpty()) item { Text("待确认 · ${pending.size}", color = Mint, fontWeight = FontWeight.SemiBold) }
        items(pending, key = { it.getString("id") }) { candidate ->
            SectionCard {
                Text(candidate.optString("category"), color = Purple, fontSize = 11.sp)
                Text(candidate.optString("value"), fontSize = 16.sp, modifier = Modifier.padding(vertical = 8.dp))
                Text("对方原话\n“${candidate.optString("source")}”", color = Muted, fontSize = 12.sp)
                Row {
                    TextButton(onClick = { model.confirmMemory(candidate, true) }, enabled = !state.busy) { Text("确认保存") }
                    TextButton(onClick = { model.confirmMemory(candidate, false) }, enabled = !state.busy) { Text("忽略") }
                }
            }
        }
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("已确认记忆", fontSize = 18.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                TextButton(onClick = { edit(null) }, enabled = state.selectedContact.isNotBlank() && !state.busy) { Text("＋ 添加") }
            }
        }
        if (state.facts.isEmpty()) item { SectionCard { Text("确认后的资料会保存在这里", color = Muted) } }
        items(state.facts, key = { it.getString("key") }) { fact ->
            SectionCard {
                Text(fact.optString("key"), color = Purple, fontSize = 11.sp)
                Text(fact.optString("value"), modifier = Modifier.padding(vertical = 10.dp))
                Text("当前权重 ${fact.optDouble("weight", 1.0)}", color = Muted, fontSize = 10.sp)
                Row {
                    TextButton(onClick = { edit(fact) }, enabled = !state.busy) { Text("编辑") }
                    TextButton(onClick = { delete(fact) }, enabled = !state.busy) { Text("删除", color = MaterialTheme.colorScheme.error) }
                }
            }
        }
    }
}
