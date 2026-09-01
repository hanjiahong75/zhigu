import { useState, useEffect } from "react";
import { View, ScrollView, Text } from "@tarojs/components";
import Taro from "@tarojs/taro";

var API = "http://localhost:8000";

export default function WatchlistPage() {
  var items = useState<any[]>([]);
  var quotes = useState<Record<string, any>>({});

  function load() {
    Taro.request({
      url: API + "/api/watchlist", method: "GET",
      success: function(res: any) {
        var list = res.data.items || [];
        items[1](list);
        if (list.length > 0) {
          var p = list.map(function(i: any) { return "codes=" + i.code; }).join("&");
          Taro.request({
            url: API + "/api/watchlist/quotes?" + p, method: "GET",
            success: function(r: any) {
              var m: Record<string, any> = {};
              (r.data || []).forEach(function(x: any) { m[x.code] = x; });
              quotes[1](m);
            },
          });
        }
      },
    });
  }

  useEffect(function() { load(); }, []);

  function del(code: string) {
    Taro.request({ url: API + "/api/watchlist/" + code, method: "DELETE", success: function() { load(); } });
  }

  return (
    <View className="page-wrap">
      <ScrollView className="page-scroll" scrollY>
        {items[0].length === 0 && (
          <View className="text-center text-muted" style={{ padding: "60px 0" }}>暂无自选股票</View>
        )}
        {items[0].map(function(item: any, i: number) {
          var q = quotes[0][item.code];
          return (
            <View key={i} className="card">
              <View className="flex-row" style={{ justifyContent: "space-between" }}>
                <View><Text style={{ fontWeight: 600, fontSize: "30px" }}>{item.name}</Text>
                  <Text style={{ color: "#999", fontSize: "24px", marginLeft: "12px" }}>{item.code}</Text></View>
                <View onClick={function() { del(item.code); }} style={{ color: "#ff4d4f", fontSize: "24px", padding: "4px 12px" }}>删除</View>
              </View>
              {q && (
                <View className="flex-row" style={{ marginTop: "8px", gap: "16px" }}>
                  <Text style={{ fontSize: "36px", fontWeight: 700, color: q.change_pct >= 0 ? "#ff4d4f" : "#52c41a" }}>{q.price}</Text>
                  <Text style={{ fontSize: "28px", color: q.change_pct >= 0 ? "#ff4d4f" : "#52c41a" }}>{q.change_pct >= 0 ? "+" : ""}{q.change_pct}%</Text>
                </View>
              )}
            </View>
          );
        })}
      </ScrollView>
    </View>
  );
}