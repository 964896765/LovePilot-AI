package com.lovepilot.ai

import android.app.RemoteInput
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification

class WeChatListener: NotificationListenerService() {
 override fun onNotificationPosted(sbn: StatusBarNotification) {
  if(sbn.packageName != "com.tencent.mm") return
  val available = sbn.notification.actions?.any { a -> a.remoteInputs?.any { it.allowFreeFormInput } == true } ?: false
  // Privacy first: never collect notification bodies or attempt to send automatically.
  Store(applicationContext).use { it.log("微信通知", "快捷回复能力=${available}; 通知键=${sbn.key.hashCode()}") }
 }
}
