import { useState } from "react";
import { View, Input, ScrollView, Text } from "@tarojs/components";
import Taro from "@tarojs/taro";

var API = "http://localhost:8000";

var msgId = 0;

export default function HomePage() {
  var messagesState = useState<any[]>([]);
  var messages = messagesState[0];
  var setMessages = messagesState[1];

  var inputState = useState("");
  var input = inputState[0];
  var setInput = inputState[1];

  var loadingState = useState(false);
  var loading = loadingState[0];
  var setLoading = loadingState[1];

  var idState = useState<string | null>(null);
  var threadId = idState[0];
  var setThreadId = idState[1];

  var scrollState = useState(0);
  var scrollKey = scrollState[0];
  var setScrollKey = scrollState[1];

  function scrollToBottom() {
    setScrollKey(Date.now());
  }

  function doSend(text?: string) {
    var msg = (text || input).trim();
    if (!msg || loading) return;
    var userMsg = { id: "u" + (++msgId), role: "user", content: msg };
    setMessages(messages.concat([userMsg]));
    setInput("");
    setLoading(true);
    scrollToBottom();
    var aiId = "a" + (++msgId);
    setMessages(messages.concat([userMsg, { id: aiId, role: "assistant", content: "思考中..." }]));
    var token = Taro.getStorageSync("token") || "";
    Taro.request({
      url: API + "/api/chat",
      method: "POST",
      header: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
      data: { message: msg, thread_id: threadId },
      success: function(res: any) {
        var data = res.data;
        setMessages(function(prev: any[]) {
          return prev.map(function(m: any) { return m.id === aiId ? { id: m.id, role: m.role, content: data.reply || "" } : m; });
        });
        if (data.thread_id) setThreadId(data.thread_id);
        setLoading(false);
        scrollToBottom();
      },
      fail: function(err: any) {
        setMessages(function(prev: any[]) {
          return prev.map(function(m: any) { return m.id === aiId ? { id: m.id, role: m.role, content: "请求失败: " + (err.errMsg || "") } : m; });
        });
        setLoading(false);
        scrollToBottom();
      },
    });
  }

  return (
    <View className="chat-page">
      <ScrollView className="chat-list" scrollY scrollTop={scrollKey} scrollWithAnimation>
        {messages.length === 0 && (
          <View style={{ textAlign: "center", padding: "40px 0" }}>
            <View style={{ fontSize: "48px", marginBottom: "16px" }}>🤖</View>
            <View style={{ fontSize: "28px", color: "#999" }}>我是知股，你的AI投研助手</View>
            <View style={{ fontSize: "24px", color: "#bbb", marginTop: "12px" }}>试着问我: 茅台现在怎么样?</View>
          </View>
        )}
        {messages.map(function(msg: any) {
          return (
            <View key={msg.id} className={"chat-item" + (msg.role === "user" ? " chat-item-user" : "")}>
              <View className={"chat-avatar" + (msg.role === "user" ? " chat-avatar-user" : " chat-avatar-ai")}>
                {msg.role === "user" ? "我" : "AI"}
              </View>
              <View className={"chat-bubble" + (msg.role === "user" ? " chat-bubble-user" : " chat-bubble-ai")}>
                <Text selectable>{msg.content}</Text>
              </View>
            </View>
          );
        })}
        <View style={{ height: "20px" }} />
      </ScrollView>
      <View className="input-bar">
        <Input value={input} onInput={function(e: any) { setInput(e.detail.value); }}
          placeholder="输入你的问题" confirmType="send"
          onConfirm={function(e: any) { doSend(e.detail.value); }} />
        <View className="send-btn" style={{ textAlign: "center", lineHeight: "72px", flexShrink: 0 }}
          onClick={function() { doSend(); }}>发送</View>
      </View>
    </View>
  );
}