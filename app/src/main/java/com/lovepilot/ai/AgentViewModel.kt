package com.lovepilot.ai

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class AgentState(
    val busy: Boolean = false,
    val connected: Boolean = false,
    val notice: String = "先连接你的 LovePilot 服务",
    val baseUrl: String = "http://127.0.0.1:8768",
    val token: String = "",
    val contacts: List<JSONObject> = emptyList(),
    val skills: List<JSONObject> = emptyList(),
    val candidates: List<JSONObject> = emptyList(),
    val messages: List<JSONObject> = emptyList(),
    val facts: List<JSONObject> = emptyList(),
    val runs: List<JSONObject> = emptyList(),
    val logs: List<JSONObject> = emptyList(),
    val status: JSONObject = JSONObject(),
    val settings: JSONObject = JSONObject(),
    val bot: JSONObject = JSONObject(),
    val botLogin: JSONObject? = null,
    val selectedContact: String = "",
    val lastResult: JSONObject? = null,
    val pendingBackup: String? = null,
    val pendingRestore: String? = null
)

class AgentViewModel(application: Application) : AndroidViewModel(application) {
    private val prefs = SecurePrefs(application)
    private val mutable = MutableStateFlow(AgentState())
    val state = mutable.asStateFlow()
    private val mutex = Mutex()

    init {
        try {
            mutable.update { it.copy(baseUrl = prefs.read("url", it.baseUrl), token = prefs.read("token")) }
            if (mutable.value.token.isNotBlank()) refresh()
        } catch (_: Exception) {
            mutable.update { it.copy(notice = "设备密钥已变化，请重新输入连接配置") }
        }
    }

    private fun operation(block: suspend (ApiClient) -> Unit) {
        if (mutable.value.busy) return
        viewModelScope.launch {
            mutex.withLock {
                mutable.update { it.copy(busy = true) }
                try {
                    block(ApiClient(mutable.value.baseUrl, mutable.value.token))
                } catch (error: Exception) {
                    if (error is kotlinx.coroutines.CancellationException) throw error
                    mutable.update { it.copy(notice = error.message ?: "操作失败，请检查服务连接") }
                } finally {
                    mutable.update { it.copy(busy = false) }
                }
            }
        }
    }

    private suspend fun snapshot(client: ApiClient) = coroutineScope {
        val contacts = async { client.get("/contacts").optJSONArray("contacts").objects() }
        val skills = async { client.get("/skills").optJSONArray("items").objects() }
        val candidates = async { client.get("/candidates").optJSONArray("candidates").objects() }
        val status = async { client.get("/status") }
        val settings = async { client.get("/settings") }
        val bot = async { client.get("/bot/status") }
        val runs = async { client.get("/runs").optJSONArray("runs").objects() }
        val logs = async { client.get("/logs").optJSONArray("logs").objects() }
        val profiles = contacts.await()
        val current = mutable.value.selectedContact
        val selected = profiles.firstOrNull { it.optString("contact_id") == current }?.optString("contact_id")
            ?: profiles.firstOrNull()?.optString("contact_id").orEmpty()
        val loadedSkills = skills.await()
        val loadedCandidates = candidates.await()
        val loadedStatus = status.await()
        val loadedSettings = settings.await()
        val loadedBot = bot.await()
        val loadedRuns = runs.await()
        val loadedLogs = logs.await()
        mutable.update { it.copy(connected = true, contacts = profiles, skills = loadedSkills,
            candidates = loadedCandidates, status = loadedStatus, settings = loadedSettings,
            bot = loadedBot, runs = loadedRuns, logs = loadedLogs, selectedContact = selected) }
        loadMemory(client, selected)
    }

    private suspend fun loadMemory(client: ApiClient, cid: String) {
        if (cid.isBlank()) {
            mutable.update { it.copy(messages = emptyList(), facts = emptyList()) }
            return
        }
        val memory = client.get("/memory?contact_id=" + encodeQuery(cid))
        mutable.update { it.copy(messages = memory.optJSONArray("history").objects(), facts = memory.optJSONArray("items").objects()) }
    }

    fun refresh(silent: Boolean = false) = operation { client ->
        try {
            snapshot(client)
            if (!silent) mutable.update { it.copy(notice = "已同步最新运行状态") }
        } catch (error: Exception) {
            mutable.update { it.copy(connected = false) }
            throw error
        }
    }

    fun connect(url: String, token: String) {
        if (mutable.value.busy) return
        try {
            val clean = validateApiEndpoint(url, BuildConfig.DEBUG)
            require(token.isNotBlank()) { "请填写访问令牌" }
            prefs.saveConnection(clean, token.trim())
            mutable.update { it.copy(baseUrl = clean, token = token.trim(), connected = false, lastResult = null) }
            refresh()
        } catch (error: Exception) {
            mutable.update { it.copy(notice = error.message ?: "连接配置无效") }
        }
    }

    fun selectContact(cid: String) = operation { client ->
        mutable.update { it.copy(selectedContact = cid, lastResult = null) }
        loadMemory(client, cid)
    }

    fun saveContact(id: String, alias: String, notes: String, consent: Boolean) = operation { client ->
        val cid = id.ifBlank { UUID.randomUUID().toString() }
        client.post("/contacts", JSONObject().put("contact_id", cid).put("alias", alias).put("notes", notes).put("consent", consent))
        mutable.update { it.copy(selectedContact = cid, notice = "联系人已保存") }
        snapshot(client)
    }

    fun revoke(cid: String) = mutate("/revoke", JSONObject().put("contact_id", cid), "授权已撤销")
    fun deleteContact(cid: String) = mutate("/delete", JSONObject().put("contact_id", cid), "联系人及其聊天、记忆已删除")

    fun draft(message: String, skill: String) = operation { client ->
        val cid = mutable.value.selectedContact
        require(cid.isNotBlank()) { "请先创建并选择联系人" }
        val result = client.post("/draft", JSONObject().put("contact_id", cid).put("message", message)
            .put("message_id", UUID.randomUUID().toString()).put("skill", skill))
        mutable.update { it.copy(lastResult = result, notice = if (result.optString("action") == "draft") "建议已生成，请确认后使用" else result.optString("reason")) }
        snapshot(client)
    }

    private fun mutate(path: String, data: JSONObject, notice: String) = operation { client ->
        client.post(path, data)
        mutable.update { it.copy(notice = notice) }
        snapshot(client)
    }

    fun saveSettings(settings: JSONObject) = mutate("/settings", settings, "设置已保存")
    fun testModel() = operation { client ->
        client.post("/model/test", JSONObject())
        mutable.update { it.copy(notice = "模型接口实际调用成功") }
    }
    fun startBotLogin() = operation { client ->
        val login = client.post("/bot/login/start", JSONObject())
        mutable.update { it.copy(botLogin = login, notice = "使用微信扫一扫，并在微信内确认官方 Bot 登录") }
    }
    fun pollBotLogin() {
        val session = mutable.value.botLogin?.optString("session_id") ?: return
        operation { client ->
            val login = client.post("/bot/login/poll", JSONObject().put("session_id", session))
            mutable.update { it.copy(botLogin = JSONObject(it.botLogin?.toString() ?: "{}").apply {
                login.keys().forEach { key -> put(key, login.get(key)) }
            }, notice = when (login.optString("status")) {
                "created" -> "官方微信 Bot 登录已保存，发送 /start 可以授权会话"
                "expired" -> "二维码已过期，请重新获取"
                "denied" -> "微信登录已取消"
                else -> "等待你在微信确认登录"
            }) }
        }
    }
    fun confirmMemory(item: JSONObject, approve: Boolean) = mutate("/candidates/confirm", JSONObject()
        .put("contact_id", item.getString("contact_id")).put("candidate_id", item.getString("id")).put("approve", approve),
        if (approve) "记忆已确认保存" else "候选记忆已忽略")
    fun saveFact(key: String, value: String) = mutate("/facts", JSONObject()
        .put("contact_id", mutable.value.selectedContact).put("key", key).put("value", value), "记忆已保存")
    fun deleteFact(key: String) = mutate("/facts/delete", JSONObject()
        .put("contact_id", mutable.value.selectedContact).put("key", key), "记忆已删除")
    fun setSkill(id: String, enabled: Boolean) {
        val disabled = mutable.value.skills.filter { !it.optBoolean("enabled", true) }.map { it.getString("id") }.toMutableSet()
        if (enabled) disabled.remove(id) else disabled.add(id)
        saveSettings(JSONObject().put("disabled_skills", JSONArray(disabled.toList())))
    }

    fun searchMemory(query: String) = operation { client ->
        val result = client.get("/memory/search?contact_id=" + encodeQuery(mutable.value.selectedContact) + "&q=" + encodeQuery(query))
        val matches = result.optJSONArray("results").objects()
        val description = if (result.optString("method") != "mem0") "语义索引尚未就绪，请检查模型设置与运行日志"
            else matches.joinToString("\n") { it.optString("memory") }.ifBlank { "没有相关的已确认记忆" }
        mutable.update { it.copy(notice = description) }
    }

    fun backup(password: String) = operation { client ->
        val backup = client.post("/backup", JSONObject().put("password", password))
        mutable.update { it.copy(pendingBackup = backup.toString(), notice = "加密备份已生成，请选择保存位置") }
    }

    fun saveBackup(uri: Uri?) {
        val data = mutable.value.pendingBackup ?: return
        mutable.update { it.copy(pendingBackup = null) }
        if (uri == null) return
        operation {
            withContext(Dispatchers.IO) {
                getApplication<Application>().contentResolver.openOutputStream(uri)?.use { it.write(data.toByteArray(Charsets.UTF_8)) }
                    ?: error("备份文件无法写入")
            }
            mutable.update { it.copy(notice = "加密备份已保存") }
        }
    }

    fun openRestore(uri: Uri?) {
        if (uri == null) return
        operation {
            val content = withContext(Dispatchers.IO) {
                getApplication<Application>().contentResolver.openInputStream(uri)?.use { input ->
                    val bytes = input.readBounded(64 * 1024 * 1024)
                    String(bytes, Charsets.UTF_8)
                } ?: error("备份文件无法读取")
            }
            require(JSONObject(content).optString("format") == "lovepilot-backup-v1") { "请选择 LovePilot 加密备份" }
            mutable.update { it.copy(pendingRestore = content) }
        }
    }

    fun restore(password: String) {
        val content = mutable.value.pendingRestore ?: return
        operation { client ->
            client.post("/restore", JSONObject().put("backup", JSONObject(content)).put("password", password).put("confirm", "RESTORE"))
            mutable.update { it.copy(pendingRestore = null, notice = "备份已恢复，联系人需要重新授权") }
            snapshot(client)
        }
    }
    fun cancelRestore() { mutable.update { it.copy(pendingRestore = null) } }
    fun deleteAll() = operation { client ->
        client.post("/data/delete", JSONObject().put("confirm", "DELETE_ALL"))
        withContext(Dispatchers.IO) { Store(getApplication()).use { it.clearAll() } }
        mutable.update { it.copy(lastResult = null, pendingBackup = null, notice = "联系人、记忆、聊天、日志和应用保存的模型密钥已删除") }
        snapshot(client)
    }
}
