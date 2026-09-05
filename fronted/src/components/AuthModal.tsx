import { Alert, Button, Input, Modal, Tabs } from "antd";
import { useState } from "react";
import {
  type CurrentUser,
  ApiError,
  login,
  register,
} from "../api/client";

interface AuthModalProps {
  open: boolean;
  onClose: () => void;
  onAuthenticated: (user: CurrentUser) => void;
}

export function AuthModal({ open, onClose, onAuthenticated }: AuthModalProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    setError(undefined);
    if (!email.trim() || password.length < 8) {
      setError("请输入邮箱和至少 8 位的密码");
      return;
    }
    setSubmitting(true);
    try {
      const user = mode === "login"
        ? await login(email, password)
        : await register(email, password);
      setPassword("");
      onAuthenticated(user);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "操作失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="登录以同步你的资料与对话"
      open={open}
      onCancel={onClose}
      footer={null}
      destroyOnClose
    >
      <Tabs
        activeKey={mode}
        onChange={(key) => {
          setMode(key as "login" | "register");
          setError(undefined);
        }}
        items={[
          { key: "login", label: "登录" },
          { key: "register", label: "注册" },
        ]}
      />
      <div style={{ display: "grid", gap: 12, marginTop: 8 }}>
        {error && <Alert type="error" showIcon message={error} />}
        <Input
          autoFocus
          autoComplete="email"
          placeholder="邮箱"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Input.Password
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          placeholder="密码（至少 8 位）"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          onPressEnter={() => void submit()}
        />
        <Button type="primary" loading={submitting} onClick={() => void submit()}>
          {mode === "login" ? "登录" : "创建账号"}
        </Button>
      </div>
    </Modal>
  );
}
