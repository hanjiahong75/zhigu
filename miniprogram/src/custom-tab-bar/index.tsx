import { View, Text } from "@tarojs/components";
import Taro, { useDidShow } from "@tarojs/taro";
import { useState } from "react";

const tabs = [
  { key: "news", label: "新闻", icon: "📰", path: "/pages/news/index" },
  { key: "market", label: "行情", icon: "📈", path: "/pages/market/index" },
  { key: "home", label: "投研", icon: "🤖", path: "/pages/home/index" },
  { key: "watchlist", label: "自选", icon: "⭐", path: "/pages/watchlist/index" },
  { key: "holdings", label: "持有", icon: "💰", path: "/pages/holdings/index" },
];

export default function CustomTabBar() {
  const [current, setCurrent] = useState("home");

  useDidShow(() => {
    try {
      const pages = Taro.getCurrentPages();
      if (pages && pages.length > 0) {
        const route = pages[pages.length - 1].route || "";
        const matched = tabs.find(function(t) { return route.indexOf(t.key) !== -1; });
        if (matched) setCurrent(matched.key);
      }
    } catch (e) {
      // ignore
    }
  });

  const switchTab = function(path: string) {
    Taro.switchTab({ url: path }).catch(function() {});
  };

  return (
    <View style={{
      display: "flex", height: "100px", borderTop: "1px solid #eee",
      background: "#fff", paddingBottom: "env(safe-area-inset-bottom)",
    }}>
      {tabs.map(function(tab) {
        var active = current === tab.key;
        return (
          <View key={tab.key} onClick={function() { switchTab(tab.path); }}
            style={{
              flex: 1, display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center",
              gap: "4px",
              color: active ? "#1677ff" : "#999",
              borderTop: active ? "2px solid #1677ff" : "2px solid transparent",
            }}>
            <Text style={{ fontSize: "36px" }}>{tab.icon}</Text>
            <Text style={{ fontSize: "20px", fontWeight: active ? 600 : 400 }}>{tab.label}</Text>
          </View>
        );
      })}
    </View>
  );
}