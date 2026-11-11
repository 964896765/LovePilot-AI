package com.lovepilot.ai.ui

import android.app.Activity
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.coroutineScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.lovepilot.ai.AgentViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.util.Locale

@Composable
fun LovePilotApp(model: AgentViewModel = viewModel()) {
    val state by model.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var route by rememberSaveable { mutableStateOf("") }
    var contactEditor by remember { mutableStateOf(false) }
    var editContact by remember { mutableStateOf<JSONObject?>(null) }
    var factEditor by remember { mutableStateOf(false) }
    var editFact by remember { mutableStateOf<JSONObject?>(null) }
    var danger by remember { mutableStateOf<Pair<String, () -> Unit>?>(null) }
    var backupPassword by remember { mutableStateOf(false) }
    var voiceText by remember { mutableStateOf("") }
    var localNotice by remember { mutableStateOf<String?>(null) }
    var fullNotice by remember { mutableStateOf(false) }
    val createBackup = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream"), model::saveBackup)
    val openBackup = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument(), model::openRestore)
    val voice = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            voiceText = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull().orEmpty()
        }
    }
    LaunchedEffect(state.pendingBackup) {
        if (state.pendingBackup != null) createBackup.launch("LovePilot-backup-${System.currentTimeMillis()}.lpbackup")
    }
    DisposableEffect(lifecycle, state.token, state.baseUrl) {
        val monitor = lifecycle.coroutineScope.launch {
            lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
                while (true) {
                    delay(15000)
                    if (state.token.isNotBlank()) model.refresh(silent = true)
                }
            }
        }
        onDispose { monitor.cancel() }
    }
    BackHandler(route.isNotBlank() || tab != 0) { if (route.isNotBlank()) route = "" else tab = 0 }
    val navigate: (String) -> Unit = { route = it }
    val addContact = { editContact = null; contactEditor = true }
    Scaffold(modifier = Modifier.background(Brush.linearGradient(listOf(Background, Color(0xFF1C2039), Color(0xFF122831)))),
        containerColor = Color.Transparent, bottomBar = {
        NavigationBar(containerColor = Panel, tonalElevation = 0.dp) {
            val titles = listOf("首页", "聊天", "联系人", "记忆", "我的")
            val icons = listOf(Icons.Default.Home, Icons.Default.Email, Icons.Default.Person, Icons.Default.Favorite, Icons.Default.Settings)
            titles.forEachIndexed { index, title ->
                NavigationBarItem(selected = tab == index && route.isBlank(), onClick = { tab = index; route = "" },
                    modifier = Modifier.testTag("nav-$index"),
                    icon = { Icon(icons[index], contentDescription = title) }, label = { Text(title, fontSize = 11.sp) })
            }
        }
    }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            if (route.isNotBlank()) TextButton(onClick = { route = "" }, modifier = Modifier.padding(start = 10.dp)) { Text("‹  返回") }
            if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            val notice = localNotice ?: state.notice
            if (notice.isNotBlank()) Text(notice, color = Muted, fontSize = 11.sp, maxLines = 2,
                modifier = Modifier.fillMaxWidth().clickable { fullNotice = true }.padding(horizontal = 20.dp, vertical = 8.dp))
            Box(Modifier.weight(1f)) {
                when (route) {
                    "connection" -> ConnectionScreen(state, model)
                    "notification-probe" -> NotificationProbeScreen()
                    "safety" -> SafetyScreen(state, model) { route = "notification-probe" }
                    "models" -> ModelsScreen(state, model)
                    "style" -> StyleScreen(state, model)
                    "skills" -> SkillsScreen(state, model)
                    "workflow" -> WorkflowScreen(state)
                    "logs" -> LogsScreen(state)
                    "bot" -> BotScreen(state, model)
                    "legacy" -> LegacyToolsScreen()
                    else -> when (tab) {
                        0 -> HomeScreen(state, { tab = 1 }, { tab = 4; route = "connection" }, navigate)
                        1 -> ChatScreen(state, model, voice = {
                            try {
                                voice.launch(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                                    .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                                    .putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
                                    .putExtra(RecognizerIntent.EXTRA_PROMPT, "确认转写后再提交给 AI"))
                            } catch (_: Exception) { localNotice = "系统语音识别服务暂不可用，可以使用输入法语音转写" }
                        }, addContact, voiceText, { voiceText = "" })
                        2 -> ContactsScreen(state, { editContact = it; contactEditor = true }, { model.selectContact(it); tab = 1 }, model::revoke,
                            { contact -> danger = "删除「${contact.optString("alias")}」及其聊天和记忆？" to { model.deleteContact(contact.getString("contact_id")) } })
                        3 -> MemoryScreen(state, model, { editFact = it; factEditor = true }, { fact -> danger = "删除这条已确认记忆？" to { model.deleteFact(fact.getString("key")) } })
                        else -> MeScreen(state, navigate, { backupPassword = true }, { openBackup.launch(arrayOf("application/octet-stream", "application/json", "*/*")) },
                            { danger = "删除服务端和本机联系人、聊天、记忆、日志以及应用保存的模型密钥？外部备份文件由你自行管理。" to model::deleteAll })
                    }
                }
            }
        }
    }
    if (contactEditor) ContactDialog(editContact, { contactEditor = false }, model::saveContact)
    if (factEditor) FactDialog(editFact, { factEditor = false }, model::saveFact)
    if (backupPassword) PasswordDialog("导出加密备份", "请保存好密码，恢复备份时需要再次输入。", { backupPassword = false }, model::backup)
    if (state.pendingRestore != null) PasswordDialog("确认恢复备份", "现有联系人会受到冲突保护。恢复的联系人需要重新授权。", model::cancelRestore, model::restore)
    danger?.let { action -> AlertDialog(onDismissRequest = { danger = null }, title = { Text("确认敏感操作") },
        text = { Text(action.first) }, confirmButton = { TextButton(onClick = { action.second(); danger = null }) { Text("确认继续", color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton(onClick = { danger = null }) { Text("取消") } }) }
    if (fullNotice) AlertDialog(onDismissRequest = { fullNotice = false; localNotice = null }, title = { Text("运行提示") },
        text = { Text(localNotice ?: state.notice, modifier = Modifier.verticalScroll(rememberScrollState())) },
        confirmButton = { TextButton(onClick = { fullNotice = false; localNotice = null }) { Text("知道了") } })
}
