import { FormEvent, useState } from "react";

import { LeafMark } from "./icons";

type Props = {
  pending: boolean;
  error: string | null;
  onRegister: (displayName: string, email: string, password: string) => Promise<void>;
  onLogin: (email: string, password: string) => Promise<void>;
};

export function Onboarding({ pending, error, onRegister, onLogin }: Props) {
  const [mode, setMode] = useState<"register" | "login">("register");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (mode === "register") await onRegister(displayName.trim(), email.trim(), password);
    else await onLogin(email.trim(), password);
  }

  return (
    <main className="onboarding">
      <div className="onboarding-photo" aria-hidden="true" />
      <section className="onboarding-panel">
        <a className="brand brand-large" href="/" aria-label="PlantGuard">
          <LeafMark />
          <span>PlantGuard</span>
        </a>
        <div className="onboarding-copy">
          <h1>{mode === "register" ? "Понимайте свои растения" : "С возвращением"}</h1>
          <p>
            {mode === "register"
              ? "Сохраняйте наблюдения, распознавайте вид и получайте проверяемую оценку состояния по фотографии и описанию."
              : "Войдите, чтобы продолжить вести историю растений и сравнивать снимки."}
          </p>
        </div>
        <div className="auth-switch" role="group" aria-label="Режим авторизации">
          <button className={mode === "register" ? "active" : ""} type="button" onClick={() => setMode("register")}>Создать профиль</button>
          <button className={mode === "login" ? "active" : ""} type="button" onClick={() => setMode("login")}>Войти</button>
        </div>
        <form className="onboarding-form" onSubmit={submit}>
          {mode === "register" && (
            <label className="field">
              <span>Как к вам обращаться</span>
              <input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                required
                maxLength={100}
                autoComplete="name"
                placeholder="Екатерина"
              />
            </label>
          )}
          <label className="field">
            <span>Электронная почта</span>
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              autoComplete="email"
              placeholder="name@example.com"
            />
          </label>
          <label className="field">
            <span>Пароль</span>
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={mode === "register" ? 10 : 1}
              maxLength={128}
              type="password"
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              placeholder={mode === "register" ? "Не менее 10 символов" : "Ваш пароль"}
            />
          </label>
          <button className="button button-mint" disabled={pending} type="submit">
            {pending
              ? (mode === "register" ? "Создаём пространство…" : "Входим…")
              : (mode === "register" ? "Начать наблюдение" : "Войти в профиль")}
          </button>
          {error && <p className="form-error" role="alert">{error}</p>}
        </form>
        <p className="privacy-note">Фотографии доступны только после входа в профиль.</p>
      </section>
    </main>
  );
}
