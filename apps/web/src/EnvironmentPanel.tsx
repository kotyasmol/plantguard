import { FormEvent, useEffect, useState } from "react";
import { addReading, EnvironmentReading, listReadings } from "./api";

type Metric = "temperature_c" | "humidity_pct";

function ReadingChart({ readings, metric }: { readings: EnvironmentReading[]; metric: Metric }) {
  const points = readings.flatMap((reading) => {
    const value = reading[metric];
    return value === null ? [] : [{ value, time: Date.parse(reading.occurred_at) }];
  }).reverse();
  if (!points.length) return <p>Для этого показателя пока нет измерений.</p>;

  const values = points.map((point) => point.value);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const first = points[0].time;
  const last = points[points.length - 1].time;
  const unit = metric === "temperature_c" ? "°C" : "%";
  const coordinates = points.map(({ time, value }) => ({
    x: last === first ? 150 : 5 + 290 * (time - first) / (last - first),
    y: high === low ? 35 : 65 - 60 * (value - low) / (high - low),
  }));
  return <figure className="reading-chart">
    <figcaption>Диапазон {low}–{high} {unit} · Последнее значение {values[values.length - 1]} {unit}</figcaption>
    <svg viewBox="0 0 300 70" role="img" aria-label={metric === "temperature_c" ? "График температуры" : "График влажности"}>
      <polyline fill="none" stroke="currentColor" strokeWidth="2" points={coordinates.map(({ x, y }) => `${x},${y}`).join(" ")} />
      {coordinates.map(({ x, y }, index) => <circle key={index} cx={x} cy={y} r="3" fill="currentColor">
        <title>{new Date(points[index].time).toLocaleString("ru-RU")} · {values[index]} {unit}</title>
      </circle>)}
    </svg>
    <div><time>{new Date(first).toLocaleString("ru-RU")}</time><time>{new Date(last).toLocaleString("ru-RU")}</time></div>
  </figure>;
}

export function EnvironmentPanel({ token, plantId }: { token: string; plantId: string }) {
  const [opened, setOpened] = useState(false);
  const [revision, setRevision] = useState(0);
  const [readings, setReadings] = useState<EnvironmentReading[]>([]);
  const [metric, setMetric] = useState<Metric>("temperature_c");
  const [temperature, setTemperature] = useState("");
  const [humidity, setHumidity] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    if (!opened) return;
    let active = true;
    setLoading(true);
    setLoadFailed(false);
    listReadings(token, plantId).then((items) => {
      if (active) setReadings(items);
    }).catch(() => {
      if (active) setLoadFailed(true);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [opened, token, plantId, revision]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!temperature && !humidity) {
      setMessage("Введите температуру или влажность.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const reading = await addReading(token, plantId, {
        temperature_c: temperature ? Number(temperature) : undefined,
        humidity_pct: humidity ? Number(humidity) : undefined,
      });
      setReadings((items) => [reading, ...items].slice(0, 30));
      setMetric(temperature ? "temperature_c" : "humidity_pct");
      setTemperature("");
      setHumidity("");
      setMessage("Показания сохранены.");
    } catch {
      setMessage("Не удалось сохранить показания. Попробуйте ещё раз.");
    } finally {
      setSaving(false);
    }
  }
  return <details className="reading-panel" onToggle={(event) => { if (event.currentTarget.open) setOpened(true); }}>
    <summary>Показания среды</summary>
    {opened && <>
      <form onSubmit={save}>
        <label className="field">Температура, °C<input type="number" min="-50" max="70" step="0.01" value={temperature} onChange={(e) => setTemperature(e.target.value)} /></label>
        <label className="field">Влажность, %<input type="number" min="0" max="100" step="0.01" value={humidity} onChange={(e) => setHumidity(e.target.value)} /></label>
        <button className="button button-outline" disabled={saving || loading}>Сохранить показания</button>
      </form>
      {message && <p role="status">{message}</p>}
      <label className="field">Показатель на графике<select value={metric} onChange={(e) => setMetric(e.target.value as Metric)}>
        <option value="temperature_c">Температура</option><option value="humidity_pct">Влажность</option>
      </select></label>
      {loading ? <p>Загрузка показаний…</p> : loadFailed ? <p role="alert">Не удалось загрузить историю. <button disabled={saving} onClick={() => setRevision((v) => v + 1)}>Повторить</button></p> : <ReadingChart readings={readings} metric={metric} />}
    </>}
  </details>;
}
