// Re-mounts on every navigation, so each section slides in gently when it
// opens from the wallet (the animation is switched off for reduced motion).
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
