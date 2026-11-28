import { Plant, PlantAlert } from "./api";

const titles: Record<PlantAlert["alert_code"], string> = {
  humidity_too_low: "Низкая влажность",
  humidity_too_high: "Высокая влажность",
  temperature_too_low: "Низкая температура",
  temperature_too_high: "Высокая температура",
};

type Props = {
  alerts: PlantAlert[];
  plants: Plant[];
  loading: boolean;
  error: string | null;
  pending: string | null;
  onRead: (id: string) => void;
  onRetry: () => void;
};

export function AlertList({ alerts, plants, loading, error, pending, onRead, onRetry }: Props) {
  return (
    <main className="empty-stage alerts-stage">
      <section className="create-plant-panel">
        <h1>Уведомления</h1>
        {error && <p role="alert">{error} <button onClick={onRetry}>Повторить</button></p>}
        {loading && <p role="status">Загружаем уведомления…</p>}
        {!error && !loading && !alerts.length && <p>Уведомлений пока нет.</p>}
        <ul className="alert-list">
          {alerts.map((alert) => (
            <li key={alert.id}>
              <strong>{titles[alert.alert_code]}</strong>
              <span>{plants.find((plant) => plant.id === alert.plant_id)?.nickname ?? "Растение"} · {alert.severity === "critical" ? "Критично" : "Предупреждение"}</span>
              <time dateTime={alert.occurred_at}>{new Date(alert.occurred_at).toLocaleString("ru-RU")}</time>
              {alert.acknowledged_at ? <span>Прочитано</span> : (
                <button className="button" disabled={loading || pending !== null} onClick={() => onRead(alert.id)}>
                  {pending === alert.id ? "Сохраняем…" : "Отметить прочитанным"}
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
