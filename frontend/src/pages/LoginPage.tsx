import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Form, Input, Button, message, App } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import AuthShell from "../components/AuthShell";
import { useAuth, apiAuth } from "../api/auth";

export default function LoginPage() {
  const { user, loading: authLoading, login } = useAuth();
  const navigate = useNavigate();
  const [loginLoading, setLoginLoading] = useState(false);

  // Auto-redirect if already logged in
  useEffect(() => {
    if (!authLoading && user) navigate("/home", { replace: true });
  }, [authLoading, user, navigate]);

  if (authLoading) return <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }} />;
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
      navigate("/home");
    } catch {
      message.error("网络错误");
    } finally {
      setLoginLoading(false);
    }
  };

  return (
    <App>
      <AuthShell overline="AI 智能投研助手" title="欢迎回来" subtitle="登录知股，让 AI 陪你做投研">
        <Form onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 12 }}>
            <Button type="primary" htmlType="submit" loading={loginLoading} block>
              登录
            </Button>
          </Form.Item>
        </Form>
        <div style={{ textAlign: "center", fontSize: 13 }}>
          <span style={{ color: "var(--text-muted)" }}>还没有账号？</span>
          <Link to="/register" className="auth-link" style={{ marginLeft: 8 }}>
            立即注册
          </Link>
        </div>
      </AuthShell>
    </App>
  );
}
