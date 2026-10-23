import { Loader2, AlertTriangle, ArrowUpRight } from "lucide-react";
import { type ReactNode } from "react";
import { Link } from "react-router-dom";
export function Loading() {
  return (
    <div className="empty">
      <Loader2 className="spin" /> Loading workspace data…
    </div>
  );
}
export function ErrorBox({ error }: { error: unknown }) {
  return error ? (
    <div role="alert" className="error">
      <AlertTriangle size={17} />
      {error instanceof Error ? error.message : String(error)}
    </div>
  ) : null;
}
export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function SectionHeading({
  title,
  link,
  to,
}: {
  title: string;
  link?: string;
  to?: string;
}) {
  return (
    <div className="section-heading">
      <h2>{title}</h2>
      {link && (
        <Link to={to ?? "/"}>
          {link}
          <ArrowUpRight size={14} />
        </Link>
      )}
    </div>
  );
}
export function Badge({ children }: { children: ReactNode }) {
  return <span className="badge">{children}</span>;
}
