package com.lovepilot.ai.ui

import android.content.Intent
import android.net.Uri
import android.provider.Settings
import android.graphics.BitmapFactory
import android.util.Base64
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.background
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.lovepilot.ai.AgentState
import com.lovepilot.ai.AgentViewModel
import com.lovepilot.ai.BuildConfig
import com.lovepilot.ai.objects
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.coroutineScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner

@Composable
fun MeScreen(state: AgentState, route: (String) -> Unit, backup: () -> Unit, restore: () -> Unit, erase: () -> Unit) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item {
            PageHeading("我的", "管理你的 AI、数据与连接")
            SectionCard {
                Text("LovePilot AI", fontSize = 22.sp, fontWeight = FontWeight.SemiBold)
                Text("个人沟通助手 · V${BuildConfig.VERSION_NAME}", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(top = 8.dp))
                InfoLine("服务连接", if (state.connected) "已连接" else "等待配置")
                InfoLine("本机凭据", if (state.token.isBlank()) "尚未保存" else "Android Keystore 加密")
            }
        }
        item { MenuCard("连接与权限", "服务地址、令牌与系统权限", { route("connection") }) }
        item { MenuCard("安全中心", "人工确认、暂停与通知权限", { route("safety") }) }
        item { MenuCard("微信接入验证", "P0 通知读取与快捷回复实测", { route("notification-probe") }) }
        item { MenuCard("模型设置", "DeepSeek / OpenAI 兼容供应商", { route("models") }) }
        item { MenuCard("个人表达风格", "长度、语气、幽默和提问偏好", { route("style") }) }
        item { MenuCard("Skills 管理", "查看与启用独立技能", { route("skills") }) }
        item { MenuCard("Agent 工作流", "实际节点和最近执行记录", { route("workflow") }) }
        item { MenuCard("微信 Bot", "全局开关、适配器活动与官方控制台", { route("bot") }) }
        item { MenuCard("运行日志", "查看最近 100 条审计事件", { route("logs") }) }
        item {
            SectionCard {
                Text("数据与隐私", fontWeight = FontWeight.SemiBold)
                Text("备份使用独立密码加密，恢复后需要重新授权联系人。", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(top = 10.dp))
                TextButton(onClick = backup, enabled = state.connected && !state.busy) { Text("导出加密备份") }
                TextButton(onClick = restore, enabled = state.connected && !state.busy) { Text("恢复加密备份") }
                TextButton(onClick = erase, enabled = state.connected && !state.busy) { Text("删除应用保存的数据", color = MaterialTheme.colorScheme.error) }
            }
        }
        item { MenuCard("本地兼容工具", "原有联系人、通知兼容检查与直接模型调用", { route("legacy") }) }
    }
}

@Composable
private fun MenuCard(title: String, detail: String, action: () -> Unit) {
    SectionCard(Modifier.clickable(onClick = action)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.SemiBold)
                Text(detail, color = Muted, fontSize = 11.sp, modifier = Modifier.padding(top = 6.dp))
            }
            Text("›", color = Purple, fontSize = 24.sp)
        }
    }
}

@Composable
fun ConnectionScreen(state: AgentState, model: AgentViewModel) {
    var url by remember(state.baseUrl) { mutableStateOf(state.baseUrl) }
    var token by remember(state.token) { mutableStateOf(state.token) }
    val context = LocalContext.current
    val enabled = Settings.Secure.getString(context.contentResolver, "enabled_notification_listeners").orEmpty().contains(context.packageName)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { PageHeading("连接与权限", "安全连接到你自己的 Windows Agent") }
        item {
            SectionCard {
                OutlinedTextField(url, { url = it }, label = { Text("Agent 服务地址") }, modifier = Modifier.fillMaxWidth().testTag("connection-url"), singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri))
                OutlinedTextField(token, { token = it }, label = { Text("访问令牌") }, modifier = Modifier.fillMaxWidth().padding(top = 12.dp).testTag("connection-token"), singleLine = true,
                    visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
                Text("本机 USB 联调使用 http://127.0.0.1:8768，并执行 adb reverse。远程服务使用 HTTPS。", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(vertical = 12.dp))
                Button(onClick = { model.connect(url, token) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth().testTag("connection-save")) { Text("保存并连接") }
            }
        }
        item {
            SectionCard {
                Text("系统权限", fontWeight = FontWeight.SemiBold)
                InfoLine("网络访问", "用于连接 Agent")
                InfoLine("语音转写", "使用系统识别服务")
                InfoLine("兼容通知监听", if (enabled) "系统已启用" else "按需授权")
                TextButton(onClick = { context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) }) { Text("打开通知权限设置") }
                Text("在「微信接入验证」查看通知内容与系统快捷回复实测结果。", color = Muted, fontSize = 12.sp)
            }
        }
    }
}

@Composable
fun ModelsScreen(state: AgentState, model: AgentViewModel) {
    var base by remember(state.settings.optString("model_base_url")) { mutableStateOf(state.settings.optString("model_base_url", "https://api.deepseek.com")) }
    var name by remember(state.settings.optString("model_name")) { mutableStateOf(state.settings.optString("model_name", "deepseek-chat")) }
    var key by remember { mutableStateOf("") }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { PageHeading("模型设置", "使用真实模型服务生成回复与分析") }
        item {
            SectionCard {
                StatusPill(if (state.settings.optBoolean("model_key_configured")) "密钥已配置" else "等待密钥", state.settings.optBoolean("model_key_configured"))
                OutlinedTextField(base, { base = it }, label = { Text("供应商 API 基础地址") }, modifier = Modifier.fillMaxWidth().padding(top = 16.dp), singleLine = true)
                OutlinedTextField(name, { name = it }, label = { Text("模型名称") }, modifier = Modifier.fillMaxWidth().padding(top = 12.dp), singleLine = true)
                OutlinedTextField(key, { key = it }, label = { Text("新 API Key，留空保留已有配置") }, modifier = Modifier.fillMaxWidth().padding(top = 12.dp), singleLine = true,
                    visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
                Text("模型密钥保存在服务端加密存储。语义记忆使用本地中文向量模型，首次加载需要下载模型。", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(vertical = 12.dp))
                Button(onClick = {
                    val values = JSONObject().put("model_base_url", base.trim()).put("model_name", name.trim())
                    if (key.isNotBlank()) values.put("model_api_key", key.trim())
                    model.saveSettings(values); key = ""
                }, enabled = state.connected && !state.busy && base.isNotBlank() && name.isNotBlank(), modifier = Modifier.fillMaxWidth()) { Text("保存模型配置") }
                TextButton(onClick = model::testModel, enabled = state.connected && !state.busy && state.settings.optBoolean("model_key_configured")) { Text("实际测试模型连接") }
            }
        }
    }
}

@Composable
fun StyleScreen(state: AgentState, model: AgentViewModel) {
    val fields = linkedMapOf(
        "length" to ("回复长度" to listOf("简短", "适中")),
        "tone" to ("表达语气" to listOf("口语", "温和", "正式")),
        "humor" to ("幽默表达" to listOf("少量", "关闭")),
        "flirting" to ("暧昧表达" to listOf("克制", "关闭")),
        "questions" to ("提问习惯" to listOf("最多一个", "避免追问"))
    )
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { PageHeading("个人表达风格", "仅使用你亲自确认的偏好") }
        fields.forEach { (key, definition) ->
            item {
                SectionCard {
                    Text(definition.first, fontWeight = FontWeight.SemiBold)
                    val current = state.settings.optJSONObject("personal_style")?.optString(key).orEmpty()
                    Row(Modifier.horizontalScroll(rememberScrollState()).padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        definition.second.forEach { value ->
                            FilterChip(current == value, onClick = {
                                val style = JSONObject(state.settings.optJSONObject("personal_style")?.toString() ?: "{}")
                                style.put(key, value)
                                model.saveSettings(JSONObject().put("personal_style", style))
                            }, enabled = state.connected && !state.busy, label = { Text(value) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun SkillsScreen(state: AgentState, model: AgentViewModel) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { PageHeading("Skills 管理", "独立技能，共同尊重沟通边界") }
        items(state.skills, key = { it.getString("id") }) { skill ->
            val locked = skill.optString("id") in setOf("boundary-guardian", "human-handoff", "reply-quality-checker")
            SectionCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(skill.optString("name"), fontWeight = FontWeight.SemiBold)
                        Text("v${skill.optString("version")} · ${if (locked) "必需守卫" else "可独立启用"}", color = Muted, fontSize = 10.sp)
                    }
                    Switch(skill.optBoolean("enabled", true), onCheckedChange = { model.setSkill(skill.getString("id"), it) }, enabled = !locked && !state.busy)
                }
                Text(skill.optString("instructions"), color = Muted, fontSize = 12.sp, modifier = Modifier.padding(top = 12.dp))
            }
        }
    }
}

@Composable
fun WorkflowScreen(state: AgentState) {
    val names = mapOf("message_receive" to "接收消息", "contact_identify" to "识别联系人", "memory_retrieve" to "检索记忆",
        "emotion_analysis" to "表达线索分析", "intent_analysis" to "识别意图", "skill_route" to "选择 Skill",
        "reply_generate" to "生成回复", "reply_review" to "审核回复", "human_handoff" to "人工接管", "memory_update" to "记忆更新")
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item {
            PageHeading("Agent 工作流", "LangGraph 实际节点与最近 100 次执行")
            SectionCard {
                val nodes = state.status.optJSONArray("workflow")
                if (nodes == null) Text("连接服务后查看实际工作流", color = Muted)
                else (0 until nodes.length()).forEach { index ->
                    val node = nodes.optString(index)
                    Text("${index + 1}  ${names[node] ?: node}", color = if (node == "human_handoff") Purple else Mint, modifier = Modifier.padding(vertical = 7.dp))
                }
            }
        }
        items(state.runs, key = { it.getString("id") }) { run ->
            SectionCard {
                Text(if (run.optString("action") == "draft") "草稿已生成" else "人工接管", fontWeight = FontWeight.SemiBold)
                Text(timestamp(run.optLong("created_at")), color = Muted, fontSize = 11.sp, modifier = Modifier.padding(vertical = 8.dp))
                run.optJSONArray("trace").objects().forEach { node ->
                    Text("${names[node.optString("node")] ?: node.optString("node")}  ${node.optDouble("duration_ms", 0.0)} ms", color = Muted, fontSize = 11.sp)
                }
            }
        }
    }
}

@Composable
fun LogsScreen(state: AgentState) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { PageHeading("运行日志", "最近 100 条事件，正文与密钥不写入审计日志") }
        if (state.logs.isEmpty()) item { SectionCard { Text("暂无审计事件", color = Muted) } }
        items(state.logs, key = { it.optLong("id") }) { log ->
            SectionCard {
                Text(log.optString("decision"), color = Mint)
                Text(timestamp(log.optLong("created_at")), color = Muted, fontSize = 11.sp, modifier = Modifier.padding(top = 8.dp))
                Text(log.optString("contact_id"), color = Muted, fontSize = 10.sp, modifier = Modifier.padding(top = 4.dp))
            }
        }
    }
}

@Composable
fun BotScreen(state: AgentState, model: AgentViewModel) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    var url by remember(state.settings.optString("astrbot_url")) { mutableStateOf(state.settings.optString("astrbot_url", "http://127.0.0.1:6185")) }
    val login = state.botLogin
    val loginStatus = login?.optString("status")
    val image = remember(login?.optString("qr_image_base64")) {
        runCatching {
            val bytes = Base64.decode(login?.optString("qr_image_base64").orEmpty(), Base64.DEFAULT)
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()
        }.getOrNull()
    }
    DisposableEffect(lifecycle, login?.optString("session_id"), loginStatus) {
        val monitor = lifecycle.coroutineScope.launch {
            lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
                if (loginStatus == "pending") repeat(120) { delay(2000); model.pollBotLogin() }
            }
        }
        onDispose { monitor.cancel() }
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { PageHeading("微信 AI Bot", "独立 AI 身份 · AstrBot + 腾讯 iLink") }
        item {
            SectionCard {
                Text("微信官方扫码登录", fontWeight = FontWeight.SemiBold)
                if (image != null && loginStatus == "pending") {
                    Image(image, contentDescription = "微信官方登录二维码", modifier = Modifier.fillMaxWidth().height(240.dp).padding(vertical = 12.dp).background(Color.White))
                    Text("使用微信扫一扫，在微信内确认登录。", color = Muted, fontSize = 12.sp)
                }
                if (loginStatus == "created") Text("登录已保存，可向 AI Bot 发送 /start", color = Mint, modifier = Modifier.padding(top = 12.dp))
                if (loginStatus == "expired" || loginStatus == "denied") Text("二维码已过期或登录已取消，请重新获取。", color = Muted, modifier = Modifier.padding(top = 12.dp))
                Button(onClick = model::startBotLogin, enabled = state.connected && !state.busy, modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) {
                    Text(if (image == null) "获取官方登录二维码" else "重新获取二维码")
                }
            }
        }
        item {
            SectionCard {
                StatusPill(if (state.bot.optString("state") == "recent_event") "近期收到适配器事件" else "等待微信事件", state.bot.optString("state") == "recent_event")
                InfoLine("最近事件", if (state.bot.optLong("last_seen") == 0L) "尚无记录" else timestamp(state.bot.optLong("last_seen")))
                Row(Modifier.padding(top = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("自动回复总开关", fontWeight = FontWeight.SemiBold)
                        Text("仅对已通过 /start 授权的会话生效", color = Muted, fontSize = 11.sp)
                    }
                    Switch(state.bot.optBoolean("auto_reply_enabled"), onCheckedChange = { model.saveSettings(JSONObject().put("auto_reply_enabled", it)) }, enabled = state.connected && !state.busy)
                }
                Text("插件端 LOVEPILOT_AUTO_REPLY 也需启用。/pause 可撤销会话授权，/forget 删除该会话数据。", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(top = 12.dp))
            }
        }
        item {
            SectionCard {
                Text("扫码与登录管理", fontWeight = FontWeight.SemiBold)
                Text("登录二维码、账号与掉线状态由 AstrBot 官方适配器提供。打开控制台后选择「个人微信」并完成扫码。", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(vertical = 12.dp))
                OutlinedTextField(url, { url = it }, label = { Text("AstrBot 控制台地址") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Row {
                    TextButton(onClick = { model.saveSettings(JSONObject().put("astrbot_url", url.trim())) }, enabled = state.connected && !state.busy) { Text("保存地址") }
                    TextButton(onClick = {
                        runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
                    }, enabled = url.startsWith("http://127.0.0.1") || url.startsWith("https://")) { Text("打开官方控制台 ↗") }
                }
                Text("USB 访问本机控制台还需反向转发 6185 端口。图片理解与语音发送的能力按实际适配器逐项验收。", color = Muted, fontSize = 11.sp)
            }
        }
    }
}

private fun timestamp(seconds: Long): String =
    SimpleDateFormat("MM-dd HH:mm:ss", Locale.getDefault()).format(Date(seconds * 1000))
