import { FormEvent, useEffect, useState } from "react";
import { CareSchedule, loadCareSchedule, saveCareIntervals } from "./api";

type Props = {
  token: string;
  plantId: string;
  eventCount: number;
  pending: boolean;
  onCare: (action: string, notes: string) => Promise<void>;
};

export function CareReminders({ token, plantId, eventCount, pending, onCare }: Props) {
  const [schedule, setSchedule] = useState<CareSchedule | null>(null);
  const [revision, setRevision] = useState(0);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [now, setNow] = useState(Date.now);

  useEffect(() => {
    let active = true;
    setError("");
    loadCareSchedule(token, plantId).then((result) => {
      if (active) setSchedule(result);
    }).catch(() => {
      if (active) setError("Не удалось загрузить расписание.");
    });
    return () => { active = false; };
  }, [token, plantId, eventCount, revision]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const days = (name: string) => data.get(name) ? Number(data.get(name)) : null;
    setSaving(true);
    setError("");
    try {
      const updated = await saveCareIntervals(token, plantId, {
        watering_days: days("watering"), feeding_days: days("feeding"),
      });
      setSchedule(updated);
      setEditing(false);
      setRevision((value) => value + 1);
    } catch {
      setError("Не удалось сохранить интервалы.");
    } finally {
      setSaving(false);
    }
  }

  function reminder(title: string, action: string, days: number | null, due: string | null) {
    if (!days) return null;
    const water = action === "watered";
    return <li>
      <strong>{title}</strong>
      <span>{due ? <>
        {Date.parse(due) <= now ? (water ? "Пора полить" : "Пора подкормить") : "Следующий срок"}
        {" · "}<time dateTime={due}>{new Date(due).toLocaleString("ru-RU")}</time>
      </> : "Отметьте первый уход для расчёта срока."}</span>
      <button type="button" className="button button-outline" disabled={pending || saving}
        onClick={() => onCare(action, "")}>{water ? "Полито" : "Подкормлено"}</button>
    </li>;
  }

  return <section className="reading-panel care-reminders" aria-label="Расписание ухода">
    <h2>Расписание ухода</h2>
    {error && <p role="alert">{error} {!editing && <button onClick={() => setRevision((v) => v + 1)}>Повторить</button>}</p>}
    {schedule ? <>
      <ul className="alert-list">
        {reminder("Полив", "watered", schedule.watering_days, schedule.watering_due_at)}
        {reminder("Подкормка", "fertilized", schedule.feeding_days, schedule.feeding_due_at)}
      </ul>
      {editing ? <form onSubmit={save}>
        <label className="field">Полив, дней<input name="watering" type="number" min="1" max="365" step="1" defaultValue={schedule.watering_days ?? ""} /></label>
        <label className="field">Подкормка, дней<input name="feeding" type="number" min="1" max="365" step="1" defaultValue={schedule.feeding_days ?? ""} /></label>
        <small>Оставьте поле пустым, чтобы отключить напоминание.</small>
        <button className="button button-mint" disabled={saving}>Сохранить интервалы</button>
        <button type="button" disabled={saving} onClick={() => { setEditing(false); setError(""); }}>Отмена</button>
      </form> : <button type="button" className="button button-outline" onClick={() => setEditing(true)}>Настроить интервалы</button>}
    </> : !error && <p>Загрузка расписания…</p>}
  </section>;
}
