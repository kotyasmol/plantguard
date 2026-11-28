import { FormEvent, useState } from "react";

import { Assessment, Dynamics, PlantHistory } from "./api";
import { AssessmentPanel } from "./AssessmentPanel";
import { CameraIcon, DropletIcon, PlusIcon, ThermometerIcon } from "./icons";
import { Timeline } from "./Timeline";
import type { ReactNode } from "react";

type Props = {
  children?: ReactNode;
  history: PlantHistory;
  assessment: Assessment | null;
  dynamics: Dynamics | null;
  identification: Parameters<typeof AssessmentPanel>[0]["identification"];
  confirming: boolean;
  carePending: boolean;
  onAddObservation: () => void;
  onConfirm: Parameters<typeof AssessmentPanel>[0]["onConfirm"];
  onCare: (actionType: string, notes: string) => Promise<void>;
};

const trendCopy = {
  improving: "Есть улучшение",
  stable: "Без заметных изменений",
  worsening: "Есть ухудшение",
  unknown: "Недостаточно данных",
};

export function PlantWorkspace({
  children,
  history,
  assessment,
  dynamics,
  identification,
  confirming,
  carePending,
  onAddObservation,
  onConfirm,
  onCare,
}: Props) {
  const latest = history.observations[0];
  const [careType, setCareType] = useState("watered");
  const [careNotes, setCareNotes] = useState("");

  async function submitCare(event: FormEvent) {
    event.preventDefault();
    await onCare(careType, careNotes);
    setCareNotes("");
  }

  return (
    <main className={`workspace ${latest?.photos[0] ? "has-plant-photo" : ""}`} style={
      latest?.photos[0] ? { "--plant-photo": `url("${latest.photos[0].read_url}")` } as React.CSSProperties : undefined
    }>
      <header className="workspace-topbar">
        <span className="mobile-brand">PlantGuard</span>
        <button className="button button-mint add-observation" type="button" onClick={onAddObservation}>
          <PlusIcon /> Новое наблюдение
        </button>
      </header>

      <section className="plant-hero">
        <div className="plant-title">
          <p className="section-label">Ваше растение</p>
          <h1>{history.plant.nickname}</h1>
          <p className="species-line">
            {history.plant.species_scientific_name || "Вид ещё не подтверждён"}
            {history.plant.species_status === "confirmed" && <span>подтверждён</span>}
          </p>
        </div>
        {!latest && (
          <button className="first-observation" type="button" onClick={onAddObservation}>
            <CameraIcon /><span><strong>Добавьте первый снимок</strong><small>Определим вид и сохраним состояние</small></span>
          </button>
        )}
      </section>

      <div className="workspace-grid">
        <div className="workspace-main">
          <AssessmentPanel
            assessment={assessment}
            identification={identification}
            speciesConfirmed={history.plant.species_status === "confirmed"}
            confirming={confirming}
            onConfirm={onConfirm}
          />
          <div className="environment-strip">
            <div><DropletIcon /><span><strong>{latest?.humidity_pct ?? "—"}{latest?.humidity_pct != null && "%"}</strong> влажность</span></div>
            <div><ThermometerIcon /><span><strong>{latest?.temperature_c ?? "—"}{latest?.temperature_c != null && "°"}</strong> температура</span></div>
            {dynamics && <div className={`trend trend-${dynamics.trend}`}><span><strong>Динамика</strong>{trendCopy[dynamics.trend]}</span></div>}
          </div>
          {children}
          <Timeline observations={history.observations} careEvents={history.care_events} />
        </div>

        <aside className="care-panel">
          <div><p className="section-label">Действие</p><h2>Отметить уход</h2></div>
          <form onSubmit={submitCare}>
            <label className="field">
              <span>Что сделали</span>
              <select value={careType} onChange={(event) => setCareType(event.target.value)}>
                <option value="watered">Полив</option>
                <option value="fertilized">Подкормка</option>
                <option value="repotted">Пересадка</option>
                <option value="moved">Смена места</option>
                <option value="pruned">Обрезка</option>
                <option value="treated">Обработка</option>
                <option value="other">Другое</option>
              </select>
            </label>
            <label className="field">
              <span>Комментарий</span>
              <textarea rows={3} value={careNotes} onChange={(event) => setCareNotes(event.target.value)} placeholder="Например, полив 250 мл" />
            </label>
            <button className="button button-outline" type="submit" disabled={carePending}>
              {carePending ? "Сохраняем…" : "Добавить в историю"}
            </button>
          </form>
        </aside>
      </div>
    </main>
  );
}
