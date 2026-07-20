import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Form, Input, Button, Typography, message, Divider, App, Modal } from "antd";
import { UserOutlined, LockOutlined, SmileOutlined, LogoutOutlined, ArrowLeftOutlined } from "@ant-design/icons";
import { useAuth, apiAuth } from "../api/auth";

const { Title, Text } = Typography;

export default function UserCenterPage() {
  const { user, logout, updateUser, token } = useAuth();
  const navigate = useNavigate();
  const [nickLoading, setNickLoading] = useState(false);
  const [pwLoading, setPwLoading] = useState(false);
  const [pwModal, setPwModal] = useState(false);

  if (!user) {
    navigate("/login");
    return null;
  }

  const handleUpdateNick = async (values: { nickname: string }) => {
    setNickLoading(true);
    try {
      const resp = await apiAuth(`/auth/profile?user_id=${user.id}&nickname=${encodeURIComponent(values.nickname)}`, { method: "PUT" });
      if (!resp.ok) throw new Error();
      updateUser({ nickname: values.nickname });
      message.success("昵称已更新");
    } catch {
      message.error("更新失败");
    } finally {
      setNickLoading(false);
    }
  };

  const handleChangePw = async (values: { old_password: string; new_password: string }) => {
    setPwLoading(true);
    try {
      const resp = await apiAuth(`/auth/change-password?user_id=${user.id}`, {
        method: "POST",
        body: JSON.stringify(values),
      });
      const data = await resp.json();
      if (!resp.ok) { message.error(data.detail || "修改失败"); return; }
      message.success(data.message);
      setPwModal(false);
    } catch {
      message.error("网络错误");
    } finally {
      setPwLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <App>
      <div style={{
        minHeight: "100vh", background: "#f5f5f5",
        animation: "fadeIn 0.5s ease",
      }}>
        <div style={{ maxWidth: 600, margin: "0 auto", padding: "40px 24px" }}>
          <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate("/chat")}
            style={{ marginBottom: 24, animation: "slideInLeft 0.4s ease" }}>
            返回聊天
          </Button>

          <Card style={{ borderRadius: 16, marginBottom: 24, animation: "slideInUp 0.5s ease" }}>
            <div style={{ textAlign: "center", padding: "20px 0" }}>
              <div style={{
                width: 80, height: 80, borderRadius: "50%", background: "linear-gradient(135deg, #667eea, #764ba2)",
                display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px",
                fontSize: 32, color: "#fff", fontWeight: "bold",
              }}>
                {user.nickname?.[0] || user.username[0]}
              </div>
              <Title level={4} style={{ margin: 0 }}>{user.nickname || user.username}</Title>
              <Text type="secondary">@{user.username}</Text>
              <br />
              <Text type="secondary" style={{ fontSize: 12 }}>ID: {user.id}</Text>
            </div>
          </Card>

          <Card title="修改昵称" style={{ borderRadius: 16, marginBottom: 24, animation: "slideInUp 0.6s ease" }}>
            <Form onFinish={handleUpdateNick} layout="inline" style={{ flexWrap: "wrap", gap: 8 }}>
              <Form.Item name="nickname" rules={[{ required: true, message: "请输入新昵称" }]}
                initialValue={user.nickname} style={{ flex: 1 }}>
                <Input prefix={<SmileOutlined />} placeholder="新昵称" />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit" loading={nickLoading}>保存</Button>
              </Form.Item>
            </Form>
          </Card>

          <Card title="修改密码" style={{ borderRadius: 16, marginBottom: 24, animation: "slideInUp 0.7s ease" }}>
            <Button icon={<LockOutlined />} onClick={() => setPwModal(true)}>修改密码</Button>
          </Card>

          <Divider />
          <Button danger icon={<LogoutOutlined />} block size="large" onClick={handleLogout}
            style={{ borderRadius: 12, animation: "slideInUp 0.8s ease" }}>
            退出登录
          </Button>
        </div>
      </div>

      <Modal title="修改密码" open={pwModal} onCancel={() => setPwModal(false)} footer={null} destroyOnClose>
        <Form onFinish={handleChangePw} layout="vertical">
          <Form.Item name="old_password" label="原密码" rules={[{ required: true, message: "请输入原密码" }]}>
            <Input.Password prefix={<LockOutlined />} />
          </Form.Item>
          <Form.Item name="new_password" label="新密码" rules={[
            { required: true, message: "请输入新密码" },
            { min: 6, message: "至少6位" },
          ]}>
            <Input.Password prefix={<LockOutlined />} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={pwLoading} block>确认修改</Button>
        </Form>
      </Modal>
    </App>
  );
}
