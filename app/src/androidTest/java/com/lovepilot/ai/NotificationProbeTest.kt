package com.lovepilot.ai

import android.app.Notification
import android.app.PendingIntent
import android.app.RemoteInput
import android.content.Intent
import android.os.UserHandle
import android.service.notification.StatusBarNotification
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class NotificationProbeTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    @Before fun start() {
        NotificationProbe.start(context)
        NotificationProbe.connection(context, true)
    }

    @After fun clear() { NotificationProbe.clear(context) }

    private fun notification(text: String, packageName: String = "com.tencent.mm",
        summary: Boolean = false, action: Notification.Action? = null): StatusBarNotification {
        val builder = Notification.Builder(context, "probe-test")
            .setContentTitle("Synthetic controlled peer").setContentText(text)
            .setSmallIcon(android.R.drawable.ic_dialog_info).setGroupSummary(summary)
        if (action != null) builder.addAction(action)
        return StatusBarNotification(packageName, packageName, 100, "probe-test", 0, 0, 0,
            builder.build(), UserHandle.getUserHandleForUid(android.os.Process.myUid()), System.currentTimeMillis())
    }

    @Test fun unrelatedPackagesMessagesAndSummariesAreIgnored() {
        val marker = NotificationProbe.state.value.marker
        NotificationProbe.observe(context, notification(marker, packageName = context.packageName))
        NotificationProbe.observe(context, notification("unrelated-message"))
        NotificationProbe.observe(context, notification(marker, summary = true))
        assertEquals(0, NotificationProbe.state.value.seen)
        assertFalse(NotificationProbe.state.value.evidence.optBoolean("notification_seen"))
    }

    @Test fun matchingVisibleTextRecordsCapabilityWithoutClaimingDelivery() {
        val marker = NotificationProbe.state.value.marker
        NotificationProbe.observe(context, notification(marker))
        val state = NotificationProbe.state.value
        assertEquals(1, state.seen)
        assertEquals("Synthetic controlled peer", state.senderLabel)
        assertEquals(64, state.evidence.getString("sender_label_hash").length)
        assertFalse(state.canReply)
        assertFalse(state.evidence.has("dispatch_accepted"))
        assertFalse(state.evidence.toString().contains(state.senderLabel))
    }

    @Test fun foreignPendingIntentCannotBecomeAWeChatReplyAction() {
        val pending = PendingIntent.getBroadcast(context, 17, Intent("com.lovepilot.ai.PROBE_TEST").setPackage(context.packageName),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE)
        try {
            val action = Notification.Action.Builder(null, "reply", pending)
                .addRemoteInput(RemoteInput.Builder("reply").setAllowFreeFormInput(true).build()).build()
            NotificationProbe.observe(context, notification(NotificationProbe.state.value.marker, action = action))
            assertEquals(1, NotificationProbe.state.value.seen)
            assertFalse(NotificationProbe.state.value.canReply)
            assertEquals(0, NotificationProbe.state.value.actionCount)
        } finally { pending.cancel() }
    }
}
