package com.lovepilot.ai

import android.app.Notification
import android.app.PendingIntent
import android.app.RemoteInput
import android.content.Context
import android.content.ComponentName
import android.content.Intent
import android.os.Bundle
import android.os.SystemClock
import android.provider.Settings
import android.service.notification.StatusBarNotification
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.UUID

data class NotificationProbeState(
    val connected: Boolean = false,
    val marker: String = "",
    val reply: String = "",
    val senderLabel: String = "",
    val seen: Int = 0,
    val actionCount: Int = 0,
    val canReply: Boolean = false,
    val result: String = "尚未开始测试",
    val evidence: JSONObject = JSONObject()
)

/** P0 captures only a notification containing the current random test marker. */
object NotificationProbe {
    private val mutable = MutableStateFlow(NotificationProbeState())
    val state = mutable.asStateFlow()
    private var startedAt = 0L
    private var target: Notification.Action? = null
    private var targetKey: String? = null
    private const val maxAge = 10 * 60 * 1000L

    @Synchronized fun start(context: Context) {
        val marker = "LP-P0-" + UUID.randomUUID().toString().replace("-", "").take(12)
        target = null
        targetKey = null
        startedAt = SystemClock.elapsedRealtime()
        mutable.value = NotificationProbeState(connected = mutable.value.connected,
            marker = marker, reply = "$marker-REPLY", result = "等待受控测试通知",
            evidence = JSONObject().put("marker", marker).put("reply", "$marker-REPLY")
                .put("started_at", System.currentTimeMillis()).put("notification_seen", false))
        persist(context)
    }

    @Synchronized fun connection(context: Context, connected: Boolean) {
        if (!connected) { target = null; targetKey = null }
        mutable.value = mutable.value.copy(connected = connected,
            canReply = connected && target != null)
        if (mutable.value.marker.isNotEmpty()) persist(context)
    }

    @Suppress("DEPRECATION")
    @Synchronized fun observe(context: Context, sbn: StatusBarNotification) {
        val previous = mutable.value
        if (sbn.packageName != "com.tencent.mm" || previous.marker.isEmpty() ||
            SystemClock.elapsedRealtime() - startedAt > maxAge) return
        val notification = sbn.notification
        if (notification.flags and Notification.FLAG_GROUP_SUMMARY != 0) return
        val extras = notification.extras
        val messages = extras.getParcelableArray(Notification.EXTRA_MESSAGES)
            ?.mapNotNull { (it as? Bundle)?.getCharSequence("text")?.toString() }.orEmpty()
        val bodies = messages + listOfNotNull(extras.getCharSequence(Notification.EXTRA_TEXT)?.toString(),
            extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString()) +
            extras.getCharSequenceArray(Notification.EXTRA_TEXT_LINES)?.map { it.toString() }.orEmpty()
        if (bodies.none { it.contains(previous.marker) }) return
        val actions = notification.actions.orEmpty().filter { action ->
            action.actionIntent?.creatorPackage == "com.tencent.mm" &&
                action.remoteInputs?.any { it.allowFreeFormInput } == true
        }
        val attempted = previous.evidence.optBoolean("dispatch_accepted") || previous.evidence.has("dispatch_error")
        target = if (attempted) null else actions.firstOrNull()
        targetKey = if (target != null) sbn.key else null
        val label = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val evidence = JSONObject(previous.evidence.toString())
            .put("notification_seen", true).put("notification_key_hash", digest(sbn.key))
            .put("sender_label_hash", digest(label)).put("shortcut_id_hash", notification.shortcutId?.let(::digest))
            .put("notification_tag_hash", sbn.tag?.let(::digest))
            .put("notification_id", sbn.id).put("post_time", sbn.postTime)
            .put("remote_input_actions", actions.size).put("seen_count", previous.seen + 1)
            .put("group_conversation", extras.getBoolean(Notification.EXTRA_IS_GROUP_CONVERSATION, false))
        mutable.value = previous.copy(senderLabel = label, seen = previous.seen + 1,
            actionCount = actions.size, canReply = target != null && previous.connected,
            result = when {
                attempted -> previous.result
                target == null -> "已读到测试通知，微信未提供可用的快捷回复动作"
                else -> "已读到测试通知，可发送测试回复"
            },
            evidence = evidence)
        persist(context)
    }

    @Synchronized fun send(context: Context) {
        val previous = mutable.value
        val action = target ?: return
        if (!hasAccess(context) || !previous.connected || !previous.canReply || SystemClock.elapsedRealtime() - startedAt > maxAge) {
            target = null
            targetKey = null
            mutable.value = previous.copy(canReply = false, result = "测试动作已失效，请重新开始")
            persist(context)
            return
        }
        target = null
        targetKey = null
        try {
            val inputs = action.remoteInputs.filter { it.allowFreeFormInput }.toTypedArray()
            val results = Bundle()
            inputs.forEach { results.putCharSequence(it.resultKey, previous.reply) }
            val intent = Intent()
            RemoteInput.addResultsToIntent(inputs, intent, results)
            if (android.os.Build.VERSION.SDK_INT >= 28) RemoteInput.setResultsSource(intent, RemoteInput.SOURCE_FREE_FORM_INPUT)
            action.actionIntent.send(context, 0, intent)
            mutable.value = previous.copy(canReply = false, result = "系统已接受测试回复，等待对端核实送达",
                evidence = JSONObject(previous.evidence.toString()).put("dispatch_accepted", true)
                    .put("dispatch_time", System.currentTimeMillis()))
        } catch (error: PendingIntent.CanceledException) {
            mutable.value = previous.copy(canReply = false, result = "微信快捷回复动作已取消",
                evidence = JSONObject(previous.evidence.toString()).put("dispatch_error", error.javaClass.simpleName))
        } catch (error: SecurityException) {
            mutable.value = previous.copy(canReply = false, result = "系统拒绝此快捷回复动作",
                evidence = JSONObject(previous.evidence.toString()).put("dispatch_error", error.javaClass.simpleName))
        } catch (error: RuntimeException) {
            mutable.value = previous.copy(canReply = false, result = "快捷回复失败，请在微信核对本次消息",
                evidence = JSONObject(previous.evidence.toString()).put("dispatch_error", error.javaClass.simpleName))
        }
        persist(context)
    }

    @Synchronized fun clear(context: Context) {
        target = null
        targetKey = null
        startedAt = 0
        mutable.value = NotificationProbeState(connected = mutable.value.connected)
        File(context.filesDir, "notification-probe.json").delete()
    }

    @Synchronized fun removed(context: Context, sbn: StatusBarNotification) {
        if (sbn.key != targetKey) return
        target = null
        targetKey = null
        mutable.value = mutable.value.copy(canReply = false, result = "测试通知已移除，快捷回复已停止")
        persist(context)
    }

    fun hasAccess(context: Context): Boolean = Settings.Secure.getString(context.contentResolver,
        "enabled_notification_listeners").orEmpty().split(':').any {
            ComponentName.unflattenFromString(it) == ComponentName(context, WeChatListener::class.java)
        }

    private fun persist(context: Context) {
        val value = mutable.value
        val document = JSONObject(value.evidence.toString()).put("listener_connected", value.connected)
            .put("can_reply", value.canReply).put("result", value.result)
        File(context.filesDir, "notification-probe.json").writeText(document.toString())
    }

    private fun digest(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray()).joinToString("") { "%02x".format(it) }
}
