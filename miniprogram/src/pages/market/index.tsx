import { useState, useEffect } from "react";
import { View, Input, ScrollView, Text } from "@tarojs/components";
import Taro from "@tarojs/taro";

var API = "http://localhost:8000";
var periods = ["1m", "5m", "15m", "30m", "60m", "day", "week", "month"];

function get(path: string) {
  return new Promise<any>(function(resolve, reject) {
    Taro.request({ url: API + path, method: "GET", success: function(r) { resolve(r.data); }, fail: reject });
  });
}

export default function MarketPage() {
  var kw = useState(""); var keyword = kw[0]; var setKeyword = kw[1];
  var rs = useState<any[]>([]); var results = rs[0]; var setResults = rs[1];
  var ix = useState<any[]>([]); var indices = ix[0]; var setIndices = ix[1];
  var gi = useState<any[]>([]); var globalIdx = gi[0]; var setGlobalIdx = gi[1];
  var cs = useState<any>(null); var currentStock = cs[0]; var setCurrentStock = cs[1];
  var kl = useState<any[]>([]); var kline = kl[0]; var setKline = kl[1];
  var pr = useState("day"); var period = pr[0]; var setPeriod = pr[1];

  useEffect(function() {
    get("/api/indices").then(function(r: any) { setIndices(r.indices || []); }).catch(function() {});
    get("/api/global-indices").then(function(r: any) { setGlobalIdx(r.indices || []); }).catch(function() {});
  }, []);

  function doSearch() {
    if (!keyword.trim()) return;
    get("/api/search?keyword=" + encodeURIComponent(keyword.trim()))
      .then(function(r: any) { setResults(r.results || []); }).catch(function() {});
  }

  function loadKline(code: string, name: string, market: string, p: string) {
    setCurrentStock({ code: code, name: name, market: market });
    get("/api/kline?code=" + code + "&market=" + market + "&period=" + p)
      .then(function(r: any) { setKline(r.kline || r.data || []); }).catch(function() {});
  }

  return (
    <View className="page-wrap">
      <ScrollView className="page-scroll" scrollY>
        <View className="flex-row" style={{ gap: "8px", marginBottom: "16px" }}>
          <Input className="flex-1" style={{ height: "64px", border: "1px solid #ddd", borderRadius: "8px", padding: "0 12px", fontSize: "28px", background: "#fff" }}
            value={keyword} onInput={function(e: any) { setKeyword(e.detail.value); }}
            placeholder="搜索股票代码或名称" onConfirm={doSearch} />
          <View style={{ width: "100px", height: "64px", background: "#1677ff", borderRadius: "8px", textAlign: "center", lineHeight: "64px", color: "#fff", fontSize: "28px", flexShrink: 0 }}
            onClick={doSearch}>搜索</View>
        </View>
        {results.map(function(r: any, i: number) {
          return (
            <View key={i} className="card" onClick={function() { loadKline(r.code, r.name, r.market, period); }}>
              <View className="flex-row" style={{ justifyContent: "space-between" }}>
                <Text style={{ fontWeight: 600 }}>{r.name}</Text>
                <Text style={{ color: "#999", fontSize: "24px" }}>{r.code}</Text>
              </View>
            </View>
          );
        })}
        <View style={{ fontSize: "32px", fontWeight: 700, margin: "16px 0 8px" }}>全球指数</View>
        <ScrollView scrollX style={{ whiteSpace: "nowrap", marginBottom: "16px" }}>
          {globalIdx.map(function(idx: any, i: number) {
            return (
              <View key={i} style={{ display: "inline-block", width: "200px", marginRight: "12px" }} className="card"
                onClick={function() { loadKline(idx.code, idx.name, idx.market || "us", period); }}>
                <View style={{ fontWeight: 600, marginBottom: "4px" }}>{idx.name}</View>
                <Text className={idx.change_pct >= 0 ? "up" : "down"}>{idx.price} {idx.change_pct >= 0 ? "+" : ""}{idx.change_pct}%</Text>
              </View>
            );
          })}
        </ScrollView>
        {currentStock && (
          <View>
            <View style={{ fontSize: "32px", fontWeight: 700, marginBottom: "12px" }}>{currentStock.name} ({currentStock.code}) - K线</View>
            <ScrollView scrollX style={{ whiteSpace: "nowrap", marginBottom: "12px" }}>
              {periods.map(function(p: string) {
                return (
                  <View key={p} onClick={function() { setPeriod(p); loadKline(currentStock.code, currentStock.name, currentStock.market, p); }}
                    style={{ display: "inline-block", padding: "6px 16px", marginRight: "8px", borderRadius: "16px", fontSize: "24px",
                      background: period === p ? "#1677ff" : "#eee", color: period === p ? "#fff" : "#333" }}>{p}</View>
                );
              })}
            </ScrollView>
            <View style={{ background: "#fff", borderRadius: "8px", padding: "12px", maxHeight: "400px", overflowY: "auto" }}>
              <View className="flex-row" style={{ borderBottom: "1px solid #eee", paddingBottom: "8px", marginBottom: "8px" }}>
                <Text style={{ flex: 1, fontSize: "22px", color: "#999" }}>时间</Text>
                <Text style={{ flex: 1, fontSize: "22px", color: "#999", textAlign: "right" }}>开</Text>
                <Text style={{ flex: 1, fontSize: "22px", color: "#999", textAlign: "right" }}>高</Text>
                <Text style={{ flex: 1, fontSize: "22px", color: "#999", textAlign: "right" }}>低</Text>
                <Text style={{ flex: 1, fontSize: "22px", color: "#999", textAlign: "right" }}>收</Text>
              </View>
              {kline.slice(-30).reverse().map(function(k: any, i: number) {
                return (
                  <View key={i} className="flex-row" style={{ padding: "4px 0" }}>
                    <Text style={{ flex: 1, fontSize: "22px" }}>{k.date || k.time || ""}</Text>
                    <Text style={{ flex: 1, fontSize: "22px", textAlign: "right" }}>{k.open}</Text>
                    <Text style={{ flex: 1, fontSize: "22px", textAlign: "right" }}>{k.high}</Text>
                    <Text style={{ flex: 1, fontSize: "22px", textAlign: "right" }}>{k.low}</Text>
                    <Text style={{ flex: 1, fontSize: "22px", textAlign: "right", color: k.close >= k.open ? "#ff4d4f" : "#52c41a" }}>{k.close}</Text>
                  </View>
                );
              })}
            </View>
          </View>
        )}
      </ScrollView>
    </View>
  );
}