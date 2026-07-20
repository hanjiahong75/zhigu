import { useNavigate } from "react-router-dom";
import { Card, Radio, Typography, Divider, Button, App, Select, Input, Space, Spin } from "antd";
import { ArrowLeftOutlined, UserOutlined, BulbOutlined, SaveOutlined, DollarOutlined } from "@ant-design/icons";
import { useTheme } from "../api/ThemeContext";
import { useState, useEffect } from "react";
import { getUserProfile, updateUserProfile } from "../api/client";
import type { UserProfile } from "../types";

const { Title, Text } = Typography;

export default function SettingsPage() {
  const navigate = useNavigate();
  const { mode, setMode } = useTheme();

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);

  useEffect(() => { loadProfile(); }, []);

  const loadProfile = async () => {
    setProfileLoading(true);
    try { const data = await getUserProfile(); setProfile(data); } catch { /* */ }
    setProfileLoading(false);
  };

  const handleProfileSave = async () => {
    if (!profile) return;
    try { await updateUserProfile(profile); } catch { /* */ }
  };

  const styleOptions = [
    { label: '短线交易', value: 'short_term' },
    { label: '中线波段', value: 'medium_term' },
    { label: '长线价值', value: 'long_term' },
  ];
  const riskOptions = [
    { label: '保守型（低风险）', value: 'conservative' },
    { label: '稳健型（中等风险）', value: 'moderate' },
    { label: '积极型（高风险）', value: 'aggressive' },
  ];

  return (
    <App>
      <div style={{
        minHeight: "100vh", background: "var(--bg-primary, #f5f5f5)",
        animation: "fadeIn 0.5s ease",
      }}>
        <div style={{ maxWidth: 600, margin: "0 auto", padding: "40px 24px" }}>
          <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate("/market")}
            style={{ marginBottom: 24 }}>
            返回聊天
          </Button>

          <Card title={<><BulbOutlined style={{ marginRight: 8 }} />主题设置</>}
            style={{ borderRadius: 16, marginBottom: 24, background: "var(--bg-secondary, #fff)" }}>
            <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)}
              optionType="button" buttonStyle="solid" size="large" style={{ width: "100%" }}>
              <Radio.Button value="light" style={{ width: "33.3%", textAlign: "center" }}>
                ☀️ 浅色
              </Radio.Button>
              <Radio.Button value="dark" style={{ width: "33.3%", textAlign: "center" }}>
                🌙 深色
              </Radio.Button>
              <Radio.Button value="system" style={{ width: "33.3%", textAlign: "center" }}>
                💻 跟随系统
              </Radio.Button>
            </Radio.Group>
            <Text type="secondary" style={{ display: "block", marginTop: 12, fontSize: 12 }}>
              {mode === "system" ? "将跟随系统外观自动切换" : mode === "dark" ? "已启用深色模式" : "已启用浅色模式"}
            </Text>
          </Card>

          {profileLoading ? (
            <div style={{ textAlign: 'center', padding: 20 }}><Spin size="small" /></div>
          ) : (
            <Card title={<><DollarOutlined style={{ marginRight: 8 }} />投资偏好</>}
              style={{ borderRadius: 16, marginBottom: 24, background: "var(--bg-secondary, #fff)" }}>
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                <div>
                  <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>投资风格</Text>
                  <Select
                    style={{ width: '100%' }}
                    value={profile?.investment_style || 'medium_term'}
                    onChange={v => setProfile(p => p ? { ...p, investment_style: v } : null)}
                    options={styleOptions}
                  />
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>风险偏好</Text>
                  <Select
                    style={{ width: '100%' }}
                    value={profile?.risk_preference || 'moderate'}
                    onChange={v => setProfile(p => p ? { ...p, risk_preference: v } : null)}
                    options={riskOptions}
                  />
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>关注行业</Text>
                  <Input
                    placeholder="如：白酒、新能源、半导体"
                    value={profile?.focus_industries || ''}
                    onChange={e => setProfile(p => p ? { ...p, focus_industries: e.target.value } : null)}
                  />
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>重点关注股票</Text>
                  <Input
                    placeholder="如：600519, 300750"
                    value={profile?.focus_stocks || ''}
                    onChange={e => setProfile(p => p ? { ...p, focus_stocks: e.target.value } : null)}
                  />
                </div>
                <Button type="primary" icon={<SaveOutlined />} onClick={handleProfileSave} block>
                  保存偏好设置
                </Button>
              </Space>
              <Text type="secondary" style={{ display: "block", marginTop: 8, fontSize: 12 }}>
                AI 将根据你的投资偏好调整分析角度和侧重点
              </Text>
            </Card>
          )}

          <Card title={<><UserOutlined style={{ marginRight: 8 }} />账号管理</>}
            style={{ borderRadius: 16, background: "var(--bg-secondary, #fff)" }}>
            <Button type="primary" icon={<UserOutlined />} block size="large"
              onClick={() => navigate("/user")}>
              个人中心
            </Button>
            <Text type="secondary" style={{ display: "block", marginTop: 8, fontSize: 12 }}>
              修改昵称、密码，管理账号信息
            </Text>
          </Card>

          <Divider />
          <Text type="secondary" style={{ fontSize: 12, textAlign: "center", display: "block" }}>
            知股 AI投研助手 v0.2.0
          </Text>
        </div>
      </div>
    </App>
  );
}
