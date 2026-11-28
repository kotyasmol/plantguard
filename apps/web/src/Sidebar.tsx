import type { ReactNode } from "react";
import { Plant } from "./api";
import { CameraIcon, HomeIcon, LeafMark, LogoutIcon, PlantIcon, PlusIcon } from "./icons";

type Props = {
  children?: ReactNode;
  onHome?: () => void;
  alertsOpen?: boolean;
  plants: Plant[];
  selectedId: string | null;
  onSelect: (plantId: string) => void;
  onAddPlant: () => void;
  onAddObservation: () => void;
  onLogout: () => void;
};

export function Sidebar({ plants, selectedId, onSelect, onAddPlant, onAddObservation, onLogout, children, onHome, alertsOpen }: Props) {
  return (
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="PlantGuard">
        <LeafMark />
        <span>PlantGuard</span>
      </a>
      <nav className="primary-nav" aria-label="Основная навигация">
        <button className={alertsOpen ? "nav-item" : "nav-item active"} type="button" onClick={onHome}>
          <HomeIcon /> <span>Главная</span>
        </button>
        <button className="nav-item" type="button" onClick={onAddObservation} disabled={!selectedId}>
          <CameraIcon /> <span>Наблюдение</span>
        </button>
        {children}
      </nav>
      <div className="plant-nav">
        <div className="nav-label">
          <span>Мои растения</span>
          <button type="button" onClick={onAddPlant} aria-label="Добавить растение"><PlusIcon /></button>
        </div>
        {plants.map((plant) => (
          <button
            key={plant.id}
            className={`plant-nav-item ${plant.id === selectedId ? "selected" : ""}`}
            type="button"
            onClick={() => onSelect(plant.id)}
          >
            <PlantIcon />
            <span>{plant.nickname}</span>
          </button>
        ))}
      </div>
      <button className="nav-item logout" type="button" onClick={onLogout}>
        <LogoutIcon /> <span>Выйти</span>
      </button>
    </aside>
  );
}

export function MobileNav({ onAddObservation, onAddPlant, children, onHome, alertsOpen }: Pick<Props, "onAddObservation" | "onAddPlant" | "children" | "onHome" | "alertsOpen">) {
  return (
    <nav className="mobile-nav" aria-label="Мобильная навигация">
      <button className={alertsOpen ? "" : "active"} type="button" onClick={onHome}><HomeIcon /><span>Главная</span></button>
      <button type="button" onClick={onAddPlant}><PlantIcon /><span>Растения</span></button>
      <button type="button" onClick={onAddObservation}><CameraIcon /><span>Снимок</span></button>
      {children}
    </nav>
  );
}
