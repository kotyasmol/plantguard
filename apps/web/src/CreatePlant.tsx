import { FormEvent, useState } from "react";

import { LeafMark, PlusIcon } from "./icons";

type Props = {
  hasPlants: boolean;
  pending: boolean;
  error: string | null;
  onCreate: (nickname: string) => Promise<void>;
  onCancel: () => void;
};

export function CreatePlant({ hasPlants, pending, error, onCreate, onCancel }: Props) {
  const [nickname, setNickname] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    await onCreate(nickname.trim());
  }

  return (
    <main className="empty-stage">
      <section className="create-plant-panel">
        <div className="empty-mark"><LeafMark /></div>
        <p className="section-label">{hasPlants ? "Новое растение" : "Первое растение"}</p>
        <h1>{hasPlants ? "Добавьте ещё одно растение" : "Начнём с вашей зелёной коллекции"}</h1>
        <p>Дайте растению привычное имя. Вид можно определить по первой фотографии.</p>
        <form onSubmit={submit}>
          <label className="field">
            <span>Название растения</span>
            <input
              autoFocus
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
              required
              maxLength={100}
              placeholder="Например, Монстера у окна"
            />
          </label>
          <div className="form-actions">
            {hasPlants && <button className="button button-ghost" type="button" onClick={onCancel}>Отмена</button>}
            <button className="button button-mint" disabled={pending} type="submit">
              <PlusIcon /> {pending ? "Добавляем…" : "Добавить растение"}
            </button>
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
        </form>
      </section>
    </main>
  );
}
