import { useEffect, useMemo, useState } from "react";

import { CareEvent, Observation, Photo } from "./api";
import { CameraIcon, CareIcon, DropletIcon } from "./icons";

type Entry = {
  id: string;
  kind: "observation" | "care";
  date: string;
  title: string;
  detail: string;
  sortDate: string;
  observation?: Observation;
};

type ArchivedPhoto = {
  photo: Photo;
  observation: Observation;
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

function formatFullDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(value));
}

function formatPhotoCount(count: number) {
  const category = new Intl.PluralRules("ru-RU").select(count);
  const noun = category === "one" ? "снимок" : category === "few" ? "снимка" : "снимков";
  return `${count} ${noun}`;
}

export function Timeline({ observations, careEvents }: { observations: Observation[]; careEvents: CareEvent[] }) {
  const photos = useMemo<ArchivedPhoto[]>(() => observations
    .flatMap((observation) => observation.photos.map((photo) => ({ photo, observation })))
    .sort((a, b) => a.observation.observed_at.localeCompare(b.observation.observed_at)), [observations]);
  const [selectedPhotoIndex, setSelectedPhotoIndex] = useState<number | null>(null);
  const selectedPhoto = selectedPhotoIndex == null ? null : photos[selectedPhotoIndex];

  useEffect(() => {
    if (selectedPhotoIndex != null && selectedPhotoIndex >= photos.length) setSelectedPhotoIndex(null);
  }, [photos.length, selectedPhotoIndex]);

  useEffect(() => {
    if (selectedPhotoIndex == null) return undefined;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setSelectedPhotoIndex(null);
      if (event.key === "ArrowLeft") setSelectedPhotoIndex((current) => current == null ? null : Math.max(0, current - 1));
      if (event.key === "ArrowRight") setSelectedPhotoIndex((current) => current == null ? null : Math.min(photos.length - 1, current + 1));
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [photos.length, selectedPhotoIndex]);

  function openPhoto(photoId: string) {
    const index = photos.findIndex(({ photo }) => photo.id === photoId);
    if (index >= 0) setSelectedPhotoIndex(index);
  }

  const entries: Entry[] = [
    ...observations.map((item) => ({
      id: item.id,
      kind: "observation" as const,
      date: formatDate(item.observed_at),
      title: "Наблюдение",
      detail: item.description || "Фотография состояния растения",
      sortDate: item.observed_at,
      observation: item,
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
    <>
      {photos.length > 0 && (
        <section className="photo-journal" aria-labelledby="photo-journal-title">
          <div className="section-heading">
            <div><p className="section-label">Фотопрогресс</p><h2 id="photo-journal-title">Архив снимков</h2></div>
            <span>{formatPhotoCount(photos.length)}</span>
          </div>
          <p className="photo-journal-copy">Снимки расположены от первого наблюдения к последнему.</p>
          <div className="photo-progress-rail" aria-label="Снимки растения по датам">
            {photos.map(({ photo, observation }, index) => (
              <button
                className="photo-progress-item"
                key={photo.id}
                type="button"
                onClick={() => setSelectedPhotoIndex(index)}
                aria-label={`Открыть снимок от ${formatFullDate(observation.observed_at)}`}
              >
                <img src={photo.read_url} alt="" loading="lazy" decoding="async" />
                <span>{formatDate(observation.observed_at)}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="timeline-section">
        <div className="section-heading"><div><p className="section-label">Хронология</p><h2>История растения</h2></div><span>{entries.length} событий</span></div>
        {entries.length === 0 ? <p className="timeline-empty">История появится после первого наблюдения.</p> : (
          <ol className="timeline">
            {entries.map((entry) => {
              const photo = entry.observation?.photos[0];
              return (
                <li key={`${entry.kind}-${entry.id}`} className={photo ? "has-photo" : undefined}>
                  <span className="timeline-icon">{entry.kind === "observation" ? <CameraIcon /> : entry.title === "Полив" ? <DropletIcon /> : <CareIcon />}</span>
                  <time>{entry.date}</time>
                  <div className="timeline-entry-copy"><strong>{entry.title}</strong><p>{entry.detail}</p></div>
                  {photo && (
                    <button
                      className="timeline-photo"
                      type="button"
                      onClick={() => openPhoto(photo.id)}
                      aria-label={`Открыть фото наблюдения от ${formatFullDate(entry.sortDate)}`}
                    >
                      <img src={photo.read_url} alt="" loading="lazy" decoding="async" />
                      {entry.observation && entry.observation.photos.length > 1 && <span>+{entry.observation.photos.length - 1}</span>}
                    </button>
                  )}
                </li>
              );
            })}
          </ol>
        )}
      </section>

      {selectedPhoto && selectedPhotoIndex != null && (
        <div className="photo-viewer-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.currentTarget === event.target) setSelectedPhotoIndex(null);
        }}>
          <section className="photo-viewer" role="dialog" aria-modal="true" aria-labelledby="photo-viewer-title">
            <header className="photo-viewer-header">
              <div>
                <p className="section-label">Снимок {selectedPhotoIndex + 1} из {photos.length}</p>
                <h2 id="photo-viewer-title">{formatFullDate(selectedPhoto.observation.observed_at)}</h2>
              </div>
              <button className="close-button" type="button" onClick={() => setSelectedPhotoIndex(null)} aria-label="Закрыть просмотр">×</button>
            </header>
            <div className="photo-viewer-content">
              <div className="photo-viewer-image-wrap">
                <img src={selectedPhoto.photo.read_url} alt={`Состояние растения ${formatFullDate(selectedPhoto.observation.observed_at)}`} />
                {photos.length > 1 && (
                  <div className="photo-viewer-navigation">
                    <button type="button" onClick={() => setSelectedPhotoIndex(selectedPhotoIndex - 1)} disabled={selectedPhotoIndex === 0} aria-label="Предыдущий снимок">←</button>
                    <span>{selectedPhotoIndex + 1} / {photos.length}</span>
                    <button type="button" onClick={() => setSelectedPhotoIndex(selectedPhotoIndex + 1)} disabled={selectedPhotoIndex === photos.length - 1} aria-label="Следующий снимок">→</button>
                  </div>
                )}
              </div>
              <aside className="photo-viewer-details">
                <div><span>Наблюдение</span><p>{selectedPhoto.observation.description || "Без комментария"}</p></div>
                <dl>
                  <div><dt>Влажность</dt><dd>{selectedPhoto.observation.humidity_pct == null ? "—" : `${selectedPhoto.observation.humidity_pct}%`}</dd></div>
                  <div><dt>Температура</dt><dd>{selectedPhoto.observation.temperature_c == null ? "—" : `${selectedPhoto.observation.temperature_c}°C`}</dd></div>
                </dl>
              </aside>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
