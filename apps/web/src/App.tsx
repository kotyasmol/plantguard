import { useEffect, useRef, useState } from "react";
import { AlertList } from "./AlertList";
import { CareReminders } from "./CareReminders";
import { EnvironmentPanel } from "./EnvironmentPanel";

import {
  Assessment,
  ApiError,
  Dynamics,
  Identification,
  Plant,
  PlantHistory,
  PlantAlert,
  listAlerts,
  acknowledgeAlert,
  SpeciesCandidate,
  assessObservation,
  confirmSpecies,
  createCareEvent,
  createObservation,
  createPlant,
  identifyObservation,
  listPlants,
  loginUser,
  loadDynamics,
  loadHistory,
  registerUser,
} from "./api";
import { CreatePlant } from "./CreatePlant";
import { LeafMark, WarningIcon } from "./icons";
import { ObservationComposer } from "./ObservationComposer";
import { Onboarding } from "./Onboarding";
import { PlantWorkspace } from "./PlantWorkspace";
import { MobileNav, Sidebar } from "./Sidebar";

const TOKEN_KEY = "plantguard_access_token";
const PLANT_KEY = "plantguard_selected_plant";

function restoredAssessment(history: PlantHistory): Assessment | null {
  const stored = history.assessments[0];
  if (!stored?.explanation) return null;
  return {
    assessment_id: stored.id,
    observation_id: stored.observation_id,
    status: stored.status,
    risk_level: stored.risk_level,
    requires_species_confirmation: history.plant.species_status !== "confirmed",
    requires_more_data: stored.status === "needs_review",
    conflicting_evidence: false,
    missing_inputs: [],
    evidence: stored.finding_code ? [{
      code: stored.finding_code,
      confidence: stored.finding_confidence ?? 0,
      source: "stored",
    }] : [],
    recommended_actions: [],
    explanation: stored.explanation,
    explanation_source: "stored",
    policy_version: "stored",
    model_version: stored.model_version ?? "stored",
  };
}

export function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [plants, setPlants] = useState<Plant[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(() => localStorage.getItem(PLANT_KEY));
  const [history, setHistory] = useState<PlantHistory | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [identification, setIdentification] = useState<Identification | null>(null);
  const [dynamics, setDynamics] = useState<Dynamics | null>(null);
  const [loading, setLoading] = useState(Boolean(token));
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreatePlant, setShowCreatePlant] = useState(false);
  const [showObservation, setShowObservation] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [carePending, setCarePending] = useState(false);
  const [alerts, setAlerts] = useState<PlantAlert[]>([]);
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertsError, setAlertsError] = useState<string | null>(null);
  const [readingAlert, setReadingAlert] = useState<string | null>(null);
  const [alertsRevision, refreshAlerts] = useState(0);
  const currentSession = useRef(token);

  useEffect(() => {
    currentSession.current = token;
    if (!token) return;
    let active = true;
    setAlertsLoading(true);
    setAlertsError(null);
    listAlerts(token).then((items) => {
      if (active) setAlerts(items);
    }).catch((reason) => {
      if (!active) return;
      if (reason instanceof ApiError && reason.status === 401) handleRequestError(reason, "");
      else setAlertsError("Не удалось загрузить уведомления.");
    }).finally(() => {
      if (active) setAlertsLoading(false);
    });
    return () => { active = false; };
  }, [token, alertsRevision]);

  async function markAlertRead(id: string) {
    if (!token) return;
    setReadingAlert(id);
    setAlertsError(null);
    try {
      const updated = await acknowledgeAlert(token, id);
      if (currentSession.current === token) {
        setAlerts((items) => items.map((item) => item.id === id ? updated : item));
        refreshAlerts((value) => value + 1);
      }
    } catch (reason) {
      if (currentSession.current !== token) return;
      if (reason instanceof ApiError && reason.status === 401) handleRequestError(reason, "");
      else setAlertsError("Не удалось отметить уведомление прочитанным.");
    } finally {
      if (currentSession.current === token) setReadingAlert(null);
    }
  }

  function handleRequestError(requestError: unknown, fallback: string) {
    if (requestError instanceof ApiError && requestError.status === 401) {
      logout();
      setError("Сессия истекла. Войдите в профиль ещё раз.");
      return;
    }
    setError(requestError instanceof Error ? requestError.message : fallback);
  }

  useEffect(() => {
    if (!token) return;
    let active = true;
    setLoading(true);
    listPlants(token)
      .then((items) => {
        if (!active) return;
        setPlants(items);
        const current = items.some((item) => item.id === selectedId) ? selectedId : items[0]?.id ?? null;
        setSelectedId(current);
        if (current) localStorage.setItem(PLANT_KEY, current);
        setShowCreatePlant(items.length === 0);
        setError(null);
      })
      .catch((requestError) => {
        if (active) handleRequestError(requestError, "Не удалось загрузить растения");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [token]);

  useEffect(() => {
    if (!token || !selectedId) {
      setHistory(null);
      return;
    }
    let active = true;
    setLoading(true);
    loadHistory(token, selectedId)
      .then((nextHistory) => {
        if (!active) return;
        setHistory(nextHistory);
        setAssessment(restoredAssessment(nextHistory));
        setIdentification(null);
        setDynamics(null);
        setError(null);
      })
      .catch((requestError) => {
        if (active) handleRequestError(requestError, "Не удалось загрузить историю");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [token, selectedId]);

  function saveSession(accessToken: string) {
    localStorage.setItem(TOKEN_KEY, accessToken);
    setToken(accessToken);
  }

  async function register(displayName: string, email: string, password: string) {
    setPending(true);
    setError(null);
    try {
      const result = await registerUser(displayName, email, password);
      saveSession(result.access_token);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Не удалось создать профиль");
    } finally {
      setPending(false);
    }
  }

  async function login(email: string, password: string) {
    setPending(true);
    setError(null);
    try {
      const result = await loginUser(email, password);
      saveSession(result.access_token);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Не удалось войти");
    } finally {
      setPending(false);
    }
  }

  async function addPlant(nickname: string) {
    if (!token) return;
    setPending(true);
    setError(null);
    try {
      const plant = await createPlant(token, nickname);
      setPlants((items) => [plant, ...items]);
      setSelectedId(plant.id);
      localStorage.setItem(PLANT_KEY, plant.id);
      setShowCreatePlant(false);
    } catch (requestError) {
      handleRequestError(requestError, "Не удалось добавить растение");
    } finally {
      setPending(false);
    }
  }

  function selectPlant(plantId: string) {
    setAlertsOpen(false);
    setSelectedId(plantId);
    localStorage.setItem(PLANT_KEY, plantId);
    setShowCreatePlant(false);
  }

  async function addObservation(formData: FormData) {
    if (!token || !selectedId || !history) return;
    setPending(true);
    setError(null);
    let observation: Awaited<ReturnType<typeof createObservation>>;
    try {
      observation = await createObservation(token, selectedId, formData);
    } catch (requestError) {
      handleRequestError(requestError, "Не удалось сохранить наблюдение");
      setPending(false);
      return;
    }

    setShowObservation(false);
    const reference = history.observations[0];
    const [identificationResult, assessmentResult, dynamicsResult] = await Promise.allSettled([
      identifyObservation(token, selectedId, observation.id),
      assessObservation(token, selectedId, observation.id),
      reference
        ? loadDynamics(token, selectedId, observation.id, reference.id)
        : Promise.resolve<Dynamics | null>(null),
    ]);

    const rejectedResults = [identificationResult, assessmentResult, dynamicsResult]
      .filter((result): result is PromiseRejectedResult => result.status === "rejected");
    const authenticationError = rejectedResults
      .map((result) => result.reason)
      .find((reason) => reason instanceof ApiError && reason.status === 401);
    if (authenticationError) {
      handleRequestError(authenticationError, "Сессия истекла");
      setPending(false);
      return;
    }

    if (identificationResult.status === "fulfilled") setIdentification(identificationResult.value);
    else setIdentification(null);
    if (assessmentResult.status === "fulfilled") setAssessment(assessmentResult.value);
    if (dynamicsResult.status === "fulfilled") setDynamics(dynamicsResult.value);
    else setDynamics(null);

    const failures = rejectedResults
      .map((result) => result.reason instanceof Error ? result.reason.message : "ошибка анализа");

    try {
      const nextHistory = await loadHistory(token, selectedId);
      setHistory(nextHistory);
      setPlants((items) => items.map((item) => item.id === selectedId ? nextHistory.plant : item));
      if (assessmentResult.status === "rejected") setAssessment(restoredAssessment(nextHistory));
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        handleRequestError(requestError, "Сессия истекла");
        setPending(false);
        return;
      }
      failures.push(requestError instanceof Error ? requestError.message : "не удалось обновить историю");
    }
    setError(failures.length ? `Наблюдение сохранено, но часть анализа недоступна: ${failures.join("; ")}` : null);
    setPending(false);
  }

  async function confirm(candidate: SpeciesCandidate) {
    if (!token || !selectedId) return;
    setConfirming(true);
    try {
      const plant = await confirmSpecies(token, selectedId, candidate);
      setPlants((items) => items.map((item) => item.id === plant.id ? plant : item));
      setHistory((current) => current ? { ...current, plant } : current);
      setAssessment((current) => current ? { ...current, requires_species_confirmation: false } : current);
      setError(null);
    } catch (requestError) {
      handleRequestError(requestError, "Не удалось подтвердить вид");
    } finally {
      setConfirming(false);
    }
  }

  async function addCare(actionType: string, notes: string) {
    const plantId = history?.plant.id;
    if (!token || !plantId) return;
    setCarePending(true);
    try {
      await createCareEvent(token, plantId, actionType, notes);
      const updated = await loadHistory(token, plantId);
      setHistory((current) => current?.plant.id === plantId ? updated : current);
      setError(null);
    } catch (requestError) {
      handleRequestError(requestError, "Не удалось сохранить действие");
    } finally {
      setCarePending(false);
    }
  }

  function logout() {
    currentSession.current = null;
    setAlerts([]);
    setAlertsOpen(false);
    setAlertsError(null);
    setReadingAlert(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PLANT_KEY);
    setToken(null);
    setPlants([]);
    setSelectedId(null);
    setHistory(null);
    setAssessment(null);
    setError(null);
  }

  if (!token) return <Onboarding pending={pending} error={error} onRegister={register} onLogin={login} />;

  const unread = alerts.filter((item) => !item.acknowledged_at).length;
  const alertsButton = (
    <button className={alertsOpen ? "nav-item active" : "nav-item"} aria-pressed={alertsOpen}
      onClick={() => { setAlertsOpen(true); refreshAlerts((value) => value + 1); }}>
      <WarningIcon /><span>Уведомления{unread > 0 && <b className="alert-count"> {unread}</b>}</span>
    </button>
  );
  function openCreatePlant() { setAlertsOpen(false); setShowCreatePlant(true); }

  return (
    <div className="app-shell">
      <Sidebar
        plants={plants}
        selectedId={selectedId}
        onSelect={selectPlant}
        onAddPlant={openCreatePlant}
        onHome={() => setAlertsOpen(false)}
        alertsOpen={alertsOpen}
        onAddObservation={() => selectedId && setShowObservation(true)}
        onLogout={logout}
      >{alertsButton}</Sidebar>
      {alertsOpen ? (
        <AlertList alerts={alerts} plants={plants} loading={alertsLoading} error={alertsError}
          pending={readingAlert} onRead={markAlertRead} onRetry={() => refreshAlerts((value) => value + 1)} />
      ) : loading && !history && !showCreatePlant ? (
        <main className="loading-stage"><LeafMark /><span>Загружаем пространство…</span></main>
      ) : showCreatePlant || plants.length === 0 ? (
        <CreatePlant hasPlants={plants.length > 0} pending={pending} error={error} onCreate={addPlant} onCancel={() => setShowCreatePlant(false)} />
      ) : history ? (
        <PlantWorkspace
          history={history}
          assessment={assessment}
          dynamics={dynamics}
          identification={identification}
          confirming={confirming}
          carePending={carePending}
          onAddObservation={() => setShowObservation(true)}
          onConfirm={confirm}
          onCare={addCare}
        >
          <EnvironmentPanel key={history.plant.id} token={token} plantId={history.plant.id} />
          <CareReminders key={`care-${history.plant.id}`} token={token} plantId={history.plant.id}
            eventCount={history.care_events.length} pending={carePending} onCare={addCare} />
        </PlantWorkspace>
      ) : null}
      {error && history && !showObservation && <div className="global-error" role="alert">{error}<button onClick={() => setError(null)} aria-label="Закрыть">×</button></div>}
      {showObservation && history && (
        <ObservationComposer
          plantName={history.plant.nickname}
          pending={pending}
          error={error}
          onClose={() => { setShowObservation(false); setError(null); }}
          onSubmit={addObservation}
        />
      )}
      <MobileNav alertsOpen={alertsOpen} onHome={() => setAlertsOpen(false)} onAddPlant={openCreatePlant}
        onAddObservation={() => selectedId && setShowObservation(true)}>{alertsButton}</MobileNav>
    </div>
  );
}
