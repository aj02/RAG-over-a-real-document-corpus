"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Github, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { href: "/", label: "Ask" },
  { href: "/search", label: "Search" },
  { href: "/documents", label: "Docs" },
  { href: "/about", label: "About" },
] as const;

const REPO_URL = "https://github.com/aj02/sebi-rbi-rag";

export function Header() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-border/60 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <Link
          href="/"
          className="flex items-center gap-2 font-semibold tracking-tight"
        >
          <span className="grid h-6 w-6 place-items-center rounded-md bg-primary text-[11px] font-bold text-primary-foreground">
            r
          </span>
          <span>regrag</span>
          <span className="hidden text-xs font-normal text-muted-foreground sm:inline">
            / SEBI + RBI Q&amp;A
          </span>
        </Link>
        <nav className="flex items-center gap-1">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                pathname === link.href && "bg-accent text-foreground",
              )}
            >
              {link.label}
            </Link>
          ))}
          <ThemeToggle />
          <Button asChild variant="ghost" size="icon" aria-label="GitHub repo">
            <Link href={REPO_URL} target="_blank" rel="noreferrer noopener">
              <Github className="h-4 w-4" />
            </Link>
          </Button>
        </nav>
      </div>
    </header>
  );
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Toggle theme"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
    >
      {mounted && resolvedTheme === "dark" ? (
        <Sun className="h-4 w-4" />
      ) : (
        <Moon className="h-4 w-4" />
      )}
    </Button>
  );
}
