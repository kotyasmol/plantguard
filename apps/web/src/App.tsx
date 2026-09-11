import { ChangeEvent, FormEvent, useEffect, useState } from "react";

import { createObservation, ObservationCreated } from "./api";

type SubmitState =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "success"; result: ObservationCreated }
  | { kind: "error"; message: string };

export function App() {
  const [photo, setPhoto] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [submitState, setSubmitState] = useState<SubmitState>({ kind: "idle" });

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function handlePhotoChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedPhoto = event.target.files?.[0] ?? null;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPhoto(selectedPhoto);
    setPreviewUrl(selectedPhoto ? URL.createObjectURL(selectedPhoto) : null);
    setSubmitState({ kind: "idle" });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!photo) {
      setSubmitState({ kind: "error", message: "Добавь фотографию растения" });
      return;
    }

    const formData = new FormData(event.currentTarget);
    setSubmitState({ kind: "submitting" });

    try {
      const result = await createObservation(formData);
      setSubmitState({ kind: "success", result });
    } catch (error) {
      setSubmitState({
        kind: "error",
        message: error instanceof Error ? error.message : "Не удалось сохранить наблюдение",
      });
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="PlantGuard, главная">
          <span className="brand-mark" aria-hidden="true">P</span>
          <span>PlantGuard</span>
        </a>
        <span className="topbar-caption">Дневник здоровья растений</span>
      </header>

      <main className="page">
        <section className="intro" aria-labelledby="page-title">
          <p className="step">Первое наблюдение</p>
          <h1 id="page-title">Познакомимся с растением</h1>
          <p>
            Добавь фотографию и расскажи, что тебя беспокоит. После анализа можно будет
            подтвердить вид растения и сохранить его историю.
          </p>
        </section>

        <form className="observation-form" onSubmit={handleSubmit}>
          <fieldset>
            <legend>Фотография</legend>
            <label className={`photo-input ${previewUrl ? "has-photo" : ""}`}>
              <input
                type="file"
                name="photo"
                accept="image/jpeg,image/png,image/webp"
                onChange={handlePhotoChange}
              />
              {previewUrl ? (
                <img src={previewUrl} alt="Выбранное растение" />
              ) : (
                <span>
                  <strong>Выбрать снимок</strong>
                  <small>JPEG, PNG или WebP до 10 МБ</small>
                </span>
              )}
            </label>
          </fieldset>

          <fieldset>
            <legend>Наблюдение</legend>
            <label className="field field-wide">
              <span>Что изменилось или беспокоит?</span>
              <textarea
                name="description"
                rows={5}
                placeholder="Например: желтеют нижние листья, неделю назад пересадила…"
              />
            </label>

            <div className="field-row">
              <label className="field">
                <span>Влажность, %</span>
                <input name="humidity_pct" type="number" min="0" max="100" inputMode="decimal" />
              </label>
              <label className="field">
                <span>Температура, °C</span>
                <input
                  name="temperature_c"
                  type="number"
                  min="-50"
                  max="70"
                  step="0.1"
                  inputMode="decimal"
                />
              </label>
            </div>
          </fieldset>

          <button className="primary-action" type="submit" disabled={submitState.kind === "submitting"}>
            {submitState.kind === "submitting" ? "Сохраняем…" : "Создать наблюдение"}
          </button>

          <div className="feedback" aria-live="polite">
            {submitState.kind === "error" && <p className="error">{submitState.message}</p>}
            {submitState.kind === "success" && (
              <p className="success">{submitState.result.message}. Можно перейти к анализу.</p>
            )}
          </div>
        </form>
      </main>
    </div>
  );
}
