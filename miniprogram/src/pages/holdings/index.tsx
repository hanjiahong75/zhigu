import { useState, useEffect } from "react";
import { View, ScrollView, Text, Button } from "@tarojs/components";
import Taro from "@tarojs/taro";
var API = "http://localhost:8000";

export default function HoldingsPage() {
  var it = useState<any[]>([]); var items = it[0]; var setItems = it[1];
  var ld = useState(false); var loading = ld[0]; var setLoading = ld[1];

  function load() {
    Taro.request({ url: API + "/api/portfolio", method: "GET", success: function(r: any) { setItems(r.data.items || []); } });
  }
  useEffect(function() { load(); }, []);

  function chooseImage() {
    Taro.chooseImage({ count: 1, sizeType: ["compressed"], sourceType: ["album"],
      success: function(res: any) {
        setLoading(true);
        Taro.uploadFile({ url: API + "/api/portfolio/upload", filePath: res.tempFilePaths[0], name: "file",
          success: function() { Taro.showToast({ title: "导入成功", icon: "success" }); load(); setLoading(false); },
          fail: function() { Taro.showToast({ title: "导入失败", icon: "none" }); setLoading(false); } });
      }});
  }

  return (
    <View className="page-wrap">
      <ScrollView className="page-scroll" scrollY>
        <View style={{ display: "flex", gap: "12px", marginBottom: "16px" }}>
          <Button style={{ flex: 1, fontSize: "28px" }} onClick={chooseImage} loading={loading}>从相册选择</Button>
          <Button style={{ flex: 1, fontSize: "28px" }} onClick={load}>刷新</Button>
        </View>
        {items.map(function(item: any, i: number) {
          return (
            <View key={i} className="card">
              <View style={{ fontWeight: 600, fontSize: "30px", marginBottom: "8px" }}>{item.name}</View>
              <View className="flex-row" style={{ justifyContent: "space-between" }}>
                <View><Text style={{ color: "#999", fontSize: "24px" }}>持有金额</Text>
                  <View style={{ fontSize: "32px", fontWeight: 700, marginTop: "4px" }}>{item.amount ? "¥" + Number(item.amount).toLocaleString() : "-"}</View></View>
                <View><Text style={{ color: "#999", fontSize: "24px" }}>持有收益</Text>
                  <View style={{ fontSize: "32px", fontWeight: 700, marginTop: "4px", color: (item.profit || 0) >= 0 ? "#ff4d4f" : "#52c41a" }}>
                    {(item.profit || 0) >= 0 ? "+" : ""}{item.profit || "-"}</View></View>
              </View>
            </View>
          );
        })}
      </ScrollView>
    </View>
  );
}