import { CareEvent, Observation } from "./api";
import { CameraIcon, CareIcon, DropletIcon } from "./icons";

type Entry = {
  id: string;
  kind: "observation" | "care";
  date: string;
  title: string;
  detail: string;
  sortDate: string;
};

const careLabels: Record<string, string> = {
  watered: "Полив",
  fertilized: "Подкормка",
  repotted: "Пересадка",
  moved: "Смена места",
  pruned: "Обрезка",
  treated: "Обработка",
  other: "Уход",
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(new Date(value));
}

export function Timeline({ observations, careEvents }: { observations: Observation[]; careEvents: CareEvent[] }) {
  const entries: Entry[] = [
    ...observations.map((item) => ({
      id: item.id,
      kind: "observation" as const,
      date: formatDate(item.observed_at),
      title: "Наблюдение",
      detail: item.description || "Фотография состояния растения",
      sortDate: item.observed_at,
    })),
    ...careEvents.map((item) => ({
      id: item.id,
      kind: "care" as const,
      date: formatDate(item.performed_at),
      title: careLabels[item.action_type] ?? "Уход",
      detail: item.notes || "Действие отмечено в истории",
      sortDate: item.performed_at,
    })),
  ].sort((a, b) => b.sortDate.localeCompare(a.sortDate));

  return (
    <section className="timeline-section">
      <div className="section-heading"><div><p className="section-label">Хронология</p><h2>История растения</h2></div><span>{entries.length} событий</span></div>
      {entries.length === 0 ? <p className="timeline-empty">История появится после первого наблюдения.</p> : (
        <ol className="timeline">
          {entries.map((entry) => (
            <li key={`${entry.kind}-${entry.id}`}>
              <span className="timeline-icon">{entry.kind === "observation" ? <CameraIcon /> : entry.title === "Полив" ? <DropletIcon /> : <CareIcon />}</span>
              <time>{entry.date}</time>
              <div><strong>{entry.title}</strong><p>{entry.detail}</p></div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
