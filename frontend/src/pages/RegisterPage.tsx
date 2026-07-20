import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Form, Input, Button, Card, Typography, message, App } from "antd";
import { UserOutlined, LockOutlined, SmileOutlined, StockOutlined } from "@ant-design/icons";
import { useAuth, apiAuth } from "../api/auth";

const { Title, Text } = Typography;

export default function RegisterPage() {
  const { user, loading: authLoading, login } = useAuth();
  const navigate = useNavigate();
  const [regLoading, setRegLoading] = useState(false);

  useEffect(() => {
    if (!authLoading && user) navigate("/market", { replace: true });
  }, [authLoading, user, navigate]);

  if (authLoading) return <div style={{ minHeight: "100vh", background: "#667eea" }} />;
  if (user) return null;

  const onFinish = async (values: { username: string; password: string; nickname?: string }) => {
    setRegLoading(true);
    try {
      const resp = await apiAuth("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          username: values.username,
          password: values.password,
          nickname: values.nickname || values.username,
        }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        message.error(err.detail || "注册失败");
        return;
      }
      const data = await resp.json();
      login(data.token, data.user);
      message.success("注册成功");
      navigate("/market");
    } catch {
      message.error("网络错误");
    } finally {
      setRegLoading(false);
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
            <Text type="secondary">创建你的账号</Text>
          </div>

          <Form onFinish={onFinish} size="large">
            <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
              <Input prefix={<UserOutlined />} placeholder="用户名" />
            </Form.Item>
            <Form.Item name="nickname">
              <Input prefix={<SmileOutlined />} placeholder="昵称（选填）" />
            </Form.Item>
            <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }, { min: 6, message: "至少6位" }]}>
              <Input.Password prefix={<LockOutlined />} placeholder="密码" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={regLoading} block>
                注册
              </Button>
            </Form.Item>
          </Form>

          <div style={{ textAlign: "center" }}>
            <Text type="secondary">已有账号？</Text>
            <Link to="/login" style={{ marginLeft: 8 }}>立即登录</Link>
          </div>
        </Card>
      </div>
    </App>
  );
}
