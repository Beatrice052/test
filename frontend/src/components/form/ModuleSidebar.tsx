import type { FormModule } from "../../api/types";

type Props = {
  modules: FormModule[];
  activeModule: string;
  onSelect: (moduleId: string) => void;
};

export function ModuleSidebar({ modules, activeModule, onSelect }: Props) {
  return (
    <nav className="module-tabs" aria-label="Form modules">
      {modules.map((module) => (
        <button
          key={module.id}
          type="button"
          className={module.id === activeModule ? "active" : ""}
          onClick={() => onSelect(module.id)}
        >
          <span>{module.title}</span>
          <strong>{module.complete} / {module.total}</strong>
        </button>
      ))}
    </nav>
  );
}
