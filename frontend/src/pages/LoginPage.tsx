import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Form, Input, Button, Card, Typography, message, App } from "antd";
import { UserOutlined, LockOutlined, StockOutlined } from "@ant-design/icons";
import { useAuth, apiAuth } from "../api/auth";

const { Title, Text } = Typography;

export default function LoginPage() {
  const { user, loading: authLoading, login } = useAuth();
  const navigate = useNavigate();
  const [loginLoading, setLoginLoading] = useState(false);

  // Auto-redirect if already logged in
  useEffect(() => {
    if (!authLoading && user) navigate("/market", { replace: true });
  }, [authLoading, user, navigate]);

  if (authLoading) return <div style={{ minHeight: "100vh", background: "#667eea" }} />;
  if (user) return null;

  const onFinish = async (values: { username: string; password: string }) => {
    setLoginLoading(true);
    try {
      const resp = await apiAuth("/auth/login", {
        method: "POST",
        body: JSON.stringify(values),
      });
      if (!resp.ok) {
        const err = await resp.json();
        message.error(err.detail || "登录失败");
        return;
      }
      const data = await resp.json();
      login(data.token, data.user);
      message.success("登录成功");
      navigate("/market");
    } catch {
      message.error("网络错误");
    } finally {
      setLoginLoading(false);
    }
  };

  return (
    <App>
      <div style={{
        minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        animation: "fadeIn 0.6s ease",
      }}>
        <Card
          style={{ width: 400, borderRadius: 16, boxShadow: "0 20px 60px rgba(0,0,0,0.3)" }}
          styles={{ body: { padding: "40px 32px" } }}
        >
          <div style={{ textAlign: "center", marginBottom: 32 }}>
            <StockOutlined style={{ fontSize: 48, color: "#1677ff" }} />
            <Title level={3} style={{ margin: "12px 0 4px" }}>知股</Title>
            <Text type="secondary">AI 智能投研助手</Text>
          </div>

          <Form onFinish={onFinish} size="large">
            <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
              <Input prefix={<UserOutlined />} placeholder="用户名" />
            </Form.Item>
            <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
              <Input.Password prefix={<LockOutlined />} placeholder="密码" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={loginLoading} block>
                登录
              </Button>
            </Form.Item>
          </Form>

          <div style={{ textAlign: "center" }}>
            <Text type="secondary">还没有账号？</Text>
            <Link to="/register" style={{ marginLeft: 8 }}>立即注册</Link>
          </div>
        </Card>
      </div>
    </App>
  );
}
