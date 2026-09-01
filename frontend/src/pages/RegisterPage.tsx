import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Form, Input, Button, message, App } from "antd";
import { UserOutlined, LockOutlined, SmileOutlined } from "@ant-design/icons";
import AuthShell from "../components/AuthShell";
import { useAuth, apiAuth } from "../api/auth";

export default function RegisterPage() {
  const { user, loading: authLoading, login } = useAuth();
  const navigate = useNavigate();
  const [regLoading, setRegLoading] = useState(false);

  useEffect(() => {
    if (!authLoading && user) navigate("/home", { replace: true });
  }, [authLoading, user, navigate]);

  if (authLoading) return <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }} />;
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
      navigate("/home");
    } catch {
      message.error("网络错误");
    } finally {
      setRegLoading(false);
    }
  };

  return (
    <App>
      <AuthShell overline="AI 智能投研助手" title="创建你的账号" subtitle="注册知股，开启你的 AI 投研之旅">
        <Form onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="nickname">
            <Input prefix={<SmileOutlined />} placeholder="昵称（选填）" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 12 }}>
            <Button type="primary" htmlType="submit" loading={regLoading} block>
              注册
            </Button>
          </Form.Item>
        </Form>
        <div style={{ textAlign: "center", fontSize: 13 }}>
          <span style={{ color: "var(--text-muted)" }}>已有账号？</span>
          <Link to="/login" className="auth-link" style={{ marginLeft: 8 }}>
            去登录
          </Link>
        </div>
      </AuthShell>
    </App>
  );
}
