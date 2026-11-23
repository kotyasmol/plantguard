import { Plant } from "./api";
import { CameraIcon, HomeIcon, LeafMark, LogoutIcon, PlantIcon, PlusIcon } from "./icons";

type Props = {
  plants: Plant[];
  selectedId: string | null;
  onSelect: (plantId: string) => void;
  onAddPlant: () => void;
  onAddObservation: () => void;
  onLogout: () => void;
};

export function Sidebar({ plants, selectedId, onSelect, onAddPlant, onAddObservation, onLogout }: Props) {
  return (
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="PlantGuard">
        <LeafMark />
        <span>PlantGuard</span>
      </a>
      <nav className="primary-nav" aria-label="Основная навигация">
        <button className="nav-item active" type="button">
          <HomeIcon /> <span>Главная</span>
        </button>
        <button className="nav-item" type="button" onClick={onAddObservation} disabled={!selectedId}>
          <CameraIcon /> <span>Наблюдение</span>
        </button>
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

export function MobileNav({ onAddObservation, onAddPlant }: Pick<Props, "onAddObservation" | "onAddPlant">) {
  return (
    <nav className="mobile-nav" aria-label="Мобильная навигация">
      <button className="active" type="button"><HomeIcon /><span>Главная</span></button>
      <button type="button" onClick={onAddPlant}><PlantIcon /><span>Растения</span></button>
      <button type="button" onClick={onAddObservation}><CameraIcon /><span>Снимок</span></button>
    </nav>
  );
}
