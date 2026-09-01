import { useState } from "react";
import { View, Input, ScrollView, Text } from "@tarojs/components";
import Taro from "@tarojs/taro";
var API = "http://localhost:8000";

export default function FundPage() {
  var kw = useState(""); var keyword = kw[0]; var setKeyword = kw[1];
  var rs = useState<any[]>([]); var results = rs[0]; var setResults = rs[1];

  function doSearch() {
    if (!keyword.trim()) return;
    Taro.request({ url: API + "/api/search?keyword=" + encodeURIComponent(keyword.trim()), method: "GET",
      success: function(r: any) {
        setResults((r.data.results || []).filter(function(x: any) { return x.code && (x.code[0] === "1" || x.code[0] === "5"); }));
      }});
  }

  return (
    <View className="page-wrap">
      <ScrollView className="page-scroll" scrollY>
        <View className="flex-row" style={{ gap: "8px", marginBottom: "16px" }}>
          <Input className="flex-1" style={{ height: "64px", border: "1px solid #ddd", borderRadius: "8px", padding: "0 12px", fontSize: "28px", background: "#fff" }}
            value={keyword} onInput={function(e: any) { setKeyword(e.detail.value); }} placeholder="搜索基金" onConfirm={doSearch} />
          <View style={{ width: "100px", height: "64px", background: "#1677ff", borderRadius: "8px", textAlign: "center", lineHeight: "64px", color: "#fff", fontSize: "28px", flexShrink: 0 }}
            onClick={doSearch}>搜索</View>
        </View>
        {results.map(function(r: any, i: number) {
          return (<View key={i} className="card"><Text style={{ fontWeight: 600 }}>{r.name}</Text><Text style={{ color: "#999", fontSize: "24px", marginLeft: "12px" }}>{r.code}</Text></View>);
        })}
      </ScrollView>
    </View>
  );
}