import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-16 border-t border-border/60">
      <div className="mx-auto max-w-5xl px-4 py-8 text-xs text-muted-foreground">
        <p className="leading-relaxed">
          regrag retrieves and summarises text from publicly published SEBI
          circulars and RBI master directions.{" "}
          <span className="font-medium text-foreground">
            This is regulatory information, not legal advice.
          </span>{" "}
          Always consult primary sources before acting on a regulation.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1">
          <Link
            href="https://www.sebi.gov.in/"
            className="hover:text-foreground"
            target="_blank"
            rel="noreferrer noopener"
          >
            sebi.gov.in
          </Link>
          <Link
            href="https://www.rbi.org.in/"
            className="hover:text-foreground"
            target="_blank"
            rel="noreferrer noopener"
          >
            rbi.org.in
          </Link>
          <span aria-hidden>·</span>
          <span>MIT License · v0.1.0</span>
        </div>
      </div>
    </footer>
  );
}
