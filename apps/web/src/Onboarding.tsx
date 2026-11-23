import { FormEvent, useState } from "react";

import { LeafMark } from "./icons";

type Props = {
  pending: boolean;
  error: string | null;
  onRegister: (displayName: string, email: string) => Promise<void>;
};

export function Onboarding({ pending, error, onRegister }: Props) {
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    await onRegister(displayName.trim(), email.trim());
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
          <h1>Понимайте свои растения</h1>
          <p>
            Сохраняйте наблюдения, распознавайте вид и получайте проверяемую оценку
            состояния по фотографии и описанию.
          </p>
        </div>
        <form className="onboarding-form" onSubmit={submit}>
          <label className="field">
            <span>Как к вам обращаться</span>
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              required
              maxLength={100}
              placeholder="Екатерина"
            />
          </label>
          <label className="field">
            <span>Электронная почта</span>
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              placeholder="name@example.com"
            />
          </label>
          <button className="button button-mint" disabled={pending} type="submit">
            {pending ? "Создаём пространство…" : "Начать наблюдение"}
          </button>
          {error && <p className="form-error" role="alert">{error}</p>}
        </form>
        <p className="privacy-note">Фотографии доступны только владельцу профиля.</p>
      </section>
    </main>
  );
}
