import { useEffect, useState } from "react";

import {
  Assessment,
  Dynamics,
  Identification,
  Plant,
  PlantHistory,
  SpeciesCandidate,
  assessObservation,
  confirmSpecies,
  createCareEvent,
  createObservation,
  createPlant,
  identifyObservation,
  listPlants,
  loadDynamics,
  loadHistory,
  registerUser,
} from "./api";
import { CreatePlant } from "./CreatePlant";
import { LeafMark } from "./icons";
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

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    listPlants(token)
      .then((items) => {
        setPlants(items);
        const current = items.some((item) => item.id === selectedId) ? selectedId : items[0]?.id ?? null;
        setSelectedId(current);
        if (current) localStorage.setItem(PLANT_KEY, current);
        setShowCreatePlant(items.length === 0);
        setError(null);
      })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Не удалось загрузить растения"))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    if (!token || !selectedId) {
      setHistory(null);
      return;
    }
    setLoading(true);
    loadHistory(token, selectedId)
      .then((nextHistory) => {
        setHistory(nextHistory);
        setAssessment(restoredAssessment(nextHistory));
        setIdentification(null);
        setDynamics(null);
        setError(null);
      })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Не удалось загрузить историю"))
      .finally(() => setLoading(false));
  }, [token, selectedId]);

  async function register(displayName: string, email: string) {
    setPending(true);
    setError(null);
    try {
      const result = await registerUser(displayName, email);
      localStorage.setItem(TOKEN_KEY, result.access_token);
      setToken(result.access_token);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Не удалось создать профиль");
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
      setError(requestError instanceof Error ? requestError.message : "Не удалось добавить растение");
    } finally {
      setPending(false);
    }
  }

  function selectPlant(plantId: string) {
    setSelectedId(plantId);
    localStorage.setItem(PLANT_KEY, plantId);
    setShowCreatePlant(false);
  }

  async function addObservation(formData: FormData) {
    if (!token || !selectedId || !history) return;
    setPending(true);
    setError(null);
    try {
      const observation = await createObservation(token, selectedId, formData);
      const [nextIdentification, nextAssessment] = await Promise.all([
        identifyObservation(token, selectedId, observation.id),
        assessObservation(token, selectedId, observation.id),
      ]);
      setIdentification(nextIdentification);
      setAssessment(nextAssessment);
      if (history.observations[0]) {
        const nextDynamics = await loadDynamics(token, selectedId, observation.id, history.observations[0].id);
        setDynamics(nextDynamics);
      }
      const nextHistory = await loadHistory(token, selectedId);
      setHistory(nextHistory);
      setPlants((items) => items.map((item) => item.id === selectedId ? nextHistory.plant : item));
      setShowObservation(false);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Не удалось обработать наблюдение");
    } finally {
      setPending(false);
    }
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
      setError(requestError instanceof Error ? requestError.message : "Не удалось подтвердить вид");
    } finally {
      setConfirming(false);
    }
  }

  async function addCare(actionType: string, notes: string) {
    if (!token || !selectedId) return;
    setCarePending(true);
    try {
      await createCareEvent(token, selectedId, actionType, notes);
      setHistory(await loadHistory(token, selectedId));
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Не удалось сохранить действие");
    } finally {
      setCarePending(false);
    }
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PLANT_KEY);
    setToken(null);
    setPlants([]);
    setSelectedId(null);
    setHistory(null);
    setAssessment(null);
    setError(null);
  }

  if (!token) return <Onboarding pending={pending} error={error} onRegister={register} />;

  return (
    <div className="app-shell">
      <Sidebar
        plants={plants}
        selectedId={selectedId}
        onSelect={selectPlant}
        onAddPlant={() => setShowCreatePlant(true)}
        onAddObservation={() => selectedId && setShowObservation(true)}
        onLogout={logout}
      />
      {loading && !history && !showCreatePlant ? (
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
        />
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
      <MobileNav onAddPlant={() => setShowCreatePlant(true)} onAddObservation={() => selectedId && setShowObservation(true)} />
    </div>
  );
}
