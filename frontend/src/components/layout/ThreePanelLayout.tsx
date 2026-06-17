import type { ReactNode } from "react";

type Props = {
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
};

export function ThreePanelLayout({ left, center, right }: Props) {
  return (
    <main className="three-panel">
      <aside className="left-panel">{left}</aside>
      <section className="center-panel">{center}</section>
      <aside className="right-panel">{right}</aside>
    </main>
  );
}
