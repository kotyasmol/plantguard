import { ChangeEvent, FormEvent, useEffect, useState } from "react";

import { CameraIcon } from "./icons";

type Props = {
  plantName: string;
  pending: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (formData: FormData) => Promise<void>;
};

export function ObservationComposer({ plantName, pending, error, onClose, onSubmit }: Props) {
  const [photo, setPhoto] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  function changePhoto(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    if (preview) URL.revokeObjectURL(preview);
    setPhoto(selected);
    setPreview(selected ? URL.createObjectURL(selected) : null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!photo) return;
    const formData = new FormData(event.currentTarget);
    for (const field of ["humidity_pct", "temperature_c"]) {
      if (formData.get(field) === "") formData.delete(field);
    }
    await onSubmit(formData);
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !pending) onClose();
    }}>
      <section className="observation-modal" role="dialog" aria-modal="true" aria-labelledby="observation-title">
        <header className="modal-header">
          <div>
            <p className="section-label">{plantName}</p>
            <h2 id="observation-title">Новое наблюдение</h2>
          </div>
          <button className="close-button" type="button" onClick={onClose} disabled={pending} aria-label="Закрыть">×</button>
        </header>
        <form className="observation-form" onSubmit={submit}>
          <label className={`photo-drop ${preview ? "with-photo" : ""}`}>
            <input type="file" name="photo" accept="image/jpeg,image/png,image/webp" onChange={changePhoto} required />
            {preview ? <img src={preview} alt="Предпросмотр растения" /> : (
              <span><CameraIcon /><strong>Добавьте фотографию листа</strong><small>JPEG, PNG или WebP до 10 МБ</small></span>
            )}
          </label>
          <label className="field field-wide">
            <span>Что изменилось?</span>
            <textarea name="description" rows={4} placeholder="Например: край листа пожелтел около недели назад" />
          </label>
          <div className="field-row">
            <label className="field">
              <span>Влажность, %</span>
              <input name="humidity_pct" type="number" min="0" max="100" inputMode="decimal" placeholder="52" />
            </label>
            <label className="field">
              <span>Температура, °C</span>
              <input name="temperature_c" type="number" min="-50" max="70" step="0.1" inputMode="decimal" placeholder="23" />
            </label>
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="modal-actions">
            <button className="button button-ghost" type="button" onClick={onClose} disabled={pending}>Отмена</button>
            <button className="button button-mint" type="submit" disabled={pending || !photo}>
              {pending ? "Анализируем…" : "Сохранить и оценить"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
