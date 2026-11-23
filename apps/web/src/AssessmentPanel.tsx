import { Assessment, Identification, SpeciesCandidate } from "./api";
import { LeafMark, WarningIcon } from "./icons";

const riskCopy = {
  unknown: "Нужно больше данных",
  low: "Состояние стабильное",
  medium: "Нужно внимание",
  high: "Требуется проверка",
};

type Props = {
  assessment: Assessment | null;
  identification: Identification | null;
  speciesConfirmed: boolean;
  confirming: boolean;
  onConfirm: (candidate: SpeciesCandidate) => Promise<void>;
};

export function AssessmentPanel({ assessment, identification, speciesConfirmed, confirming, onConfirm }: Props) {
  if (!assessment) {
    return (
      <section className="assessment-panel assessment-empty">
        <LeafMark />
        <div>
          <p className="section-label">Состояние</p>
          <h2>Добавьте наблюдение</h2>
          <p>Фотография и описание помогут оценить видимые изменения.</p>
        </div>
      </section>
    );
  }
  const candidates = identification?.candidates ?? [];
  const topCandidate = candidates[0];
  const providerLabel = identification?.model_version.startsWith("plantnet")
    ? "широкий каталог"
    : "локальная модель";
  return (
    <section className={`assessment-panel risk-${assessment.risk_level}`}>
      <div className="assessment-heading">
        <div>
          <p className="section-label">Состояние</p>
          <span className="risk-tag"><WarningIcon />{riskCopy[assessment.risk_level]}</span>
        </div>
        {topCandidate && <span className="confidence">{Math.round(topCandidate.confidence * 100)}%</span>}
      </div>
      <p className="assessment-copy">{assessment.explanation}</p>
      {assessment.recommended_actions.length > 0 && (
        <div className="next-action">
          <LeafMark />
          <div><span>Что сделать сейчас</span><strong>{assessment.recommended_actions[0]}</strong></div>
        </div>
      )}
      {topCandidate && !speciesConfirmed && (
        <div className="species-suggestions">
          <div className="species-suggestions-heading">
            <div><span>Возможные виды</span><strong>Выберите правильное растение</strong></div>
            <small>{providerLabel}</small>
          </div>
          <ol>
            {candidates.map((candidate) => (
              <li key={candidate.species_code}>
                <div>
                  <span>{Math.round(candidate.confidence * 100)}%</span>
                  <p><strong>{candidate.common_name}</strong><small>{candidate.scientific_name}</small></p>
                </div>
                <button className="button button-outline" type="button" disabled={confirming} onClick={() => onConfirm(candidate)}>
                  {confirming ? "Сохраняем…" : "Это оно"}
                </button>
              </li>
            ))}
          </ol>
        </div>
      )}
      <p className="assessment-disclaimer">Предварительная оценка, не диагноз специалиста</p>
    </section>
  );
}
