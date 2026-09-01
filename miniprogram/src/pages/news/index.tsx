import { useState, useEffect } from "react";
import { View, ScrollView, Text } from "@tarojs/components";
import Taro from "@tarojs/taro";
var API = "http://localhost:8000";

export default function NewsPage() {
  var art = useState<any[]>([]); var articles = art[0]; var setArticles = art[1];
  var pg = useState(1); var page = pg[0]; var setPage = pg[1];

  function load(p: number) {
    Taro.request({ url: API + "/api/news?page=" + p, method: "GET", success: function(r: any) { setArticles(r.data.articles || []); } });
  }
  useEffect(function() { load(1); }, []);

  return (
    <View className="page-wrap">
      <ScrollView className="page-scroll" scrollY>
        {articles.map(function(a: any, i: number) {
          return (
            <View key={i} className="card">
              <Text style={{ fontWeight: 600, fontSize: "30px", lineHeight: 1.5 }}>{a.title}</Text>
              <View className="flex-row" style={{ justifyContent: "space-between", marginTop: "8px" }}>
                <Text style={{ color: "#999", fontSize: "22px" }}>{a.source || ""}</Text>
                <Text style={{ color: "#bbb", fontSize: "22px" }}>{a.time || ""}</Text>
              </View>
            </View>
          );
        })}
        <View style={{ textAlign: "center", padding: "16px" }}>
          <View style={{ display: "inline-block", padding: "8px 24px", background: "#1677ff", color: "#fff", borderRadius: "8px", fontSize: "28px" }}
            onClick={function() { var np = page + 1; setPage(np); load(np); }}>加载更多</View>
        </View>
      </ScrollView>
    </View>
  );
}