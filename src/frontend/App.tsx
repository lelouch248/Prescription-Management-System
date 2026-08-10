import { useEffect, useState } from "react";
import {
  Bell,
  CalendarDays,
  ChevronLeft,
  ClipboardList,
  Clock3,
  DatabaseBackup,
  FileText,
  HeartPulse,
  Menu,
  Mic,
  Moon,
  Pill,
  Plus,
  Search,
  Settings,
  Sparkles,
  Stethoscope,
  Sun,
  UsersRound,
  X,
} from "lucide-react";
import { api, setCsrf } from "./api";
import {
  AddType,
  Brand,
  Button,
  LockScreen,
  QuickAdd,
  SetupScreen,
} from "./components";
import {
  AppointmentsPage,
  AssistantPage,
  BackupPage,
  DashboardPage,
  DocumentsPage,
  MedicinesPage,
  ProfilesPage,
  RecordsPage,
  SearchPage,
  SettingsPage,
  TimelinePage,
} from "./pages";
import { Status } from "./types";

type Mode = "loading" | "setup" | "locked" | "ready";

const NAV = [
  ["dashboard", "Dashboard", HeartPulse],
  ["family", "Family", UsersRound],
  ["timeline", "Timeline", Clock3],
  ["prescriptions", "Prescriptions", ClipboardList],
  ["visits", "Visits", Stethoscope],
  ["medicines", "Medicines", Pill],
  ["appointments", "Appointments", CalendarDays],
  ["documents", "Documents", FileText],
  ["notes", "Notes", ClipboardList],
  ["assistant", "Assistant", Sparkles],
  ["search", "Search", Search],
  ["backup", "Backup & Recovery", DatabaseBackup],
  ["settings", "Settings", Settings],
] as const;

const ADD_FOR_ROUTE: Record<string, AddType> = {
  family: "Family profile",
  prescriptions: "Prescription",
  visits: "Doctor visit",
  medicines: "Medicine",
  appointments: "Appointment",
  documents: "Document",
  notes: "Health note",
};

export default function App() {
  const [mode, setMode] = useState<Mode>("loading");
  const [status, setStatus] = useState<Status | null>(null);
  const [route, setRoute] = useState(
    () => location.hash.slice(1) || "dashboard",
  );
  const [add, setAdd] = useState<AddType | "choose" | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [theme, setThemeState] = useState(
    () => localStorage.getItem("healthvault-theme") || "system",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("healthvault-theme", theme);
  }, [theme]);
  useEffect(() => {
    api<Status>("/status")
      .then(async (value) => {
        setStatus(value);
        if (!value.configured) {
          setMode("setup");
          return;
        }
        try {
          const user = await api<any>("/auth/me");
          setCsrf(user.csrf_token);
          setMode("ready");
        } catch {
          setMode("locked");
        }
      })
      .catch(() => setMode("locked"));
  }, []);
  useEffect(() => {
    const handler = () => setRoute(location.hash.slice(1) || "dashboard");
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);

  function navigate(next: string) {
    location.hash = next;
    setRoute(next);
  }
  function changed() {
    setRefresh((value) => value + 1);
  }
  if (mode === "loading" || !status)
    return (
      <div className="boot-screen">
        <Brand />
        <div className="boot-line" />
        <p>Opening your local vault…</p>
      </div>
    );
  if (mode === "setup")
    return (
      <SetupScreen
        ai={status.ai}
        onReady={() => {
          setMode("ready");
          changed();
        }}
      />
    );
  if (mode === "locked")
    return <LockScreen onUnlock={() => setMode("ready")} />;
  return (
    <Shell
      route={route}
      navigate={navigate}
      onAdd={(type) => setAdd(type)}
      onLock={() => setMode("locked")}
      status={status}
      theme={theme}
      setTheme={setThemeState}
      refresh={refresh}
    >
      <RouteView
        route={route}
        status={status}
        navigate={navigate}
        onAdd={(type) => setAdd(type)}
        theme={theme}
        setTheme={setThemeState}
      />
      {add && (
        <QuickAdd
          initialType={add === "choose" ? undefined : add}
          onClose={() => setAdd(null)}
          onCreated={changed}
        />
      )}
    </Shell>
  );
}

function RouteView({
  route,
  status,
  navigate,
  onAdd,
  theme,
  setTheme,
}: {
  route: string;
  status: Status;
  navigate: (route: string) => void;
  onAdd: (type: AddType | "choose") => void;
  theme: string;
  setTheme: (value: string) => void;
}) {
  const [base, id] = route.split(":");
  if (base === "dashboard")
    return <DashboardPage onAdd={() => onAdd("choose")} navigate={navigate} />;
  if (base === "family")
    return (
      <ProfilesPage initialId={id} onAdd={() => onAdd("Family profile")} />
    );
  if (base === "timeline") return <TimelinePage />;
  if (base === "visits" || base === "prescriptions" || base === "notes")
    return <RecordsPage kind={base} onAdd={() => onAdd(ADD_FOR_ROUTE[base])} />;
  if (base === "medicines")
    return <MedicinesPage onAdd={() => onAdd("Medicine")} />;
  if (base === "appointments")
    return <AppointmentsPage onAdd={() => onAdd("Appointment")} />;
  if (base === "documents")
    return <DocumentsPage onAdd={() => onAdd("Document")} />;
  if (base === "assistant") return <AssistantPage ai={status.ai} />;
  if (base === "search") return <SearchPage />;
  if (base === "backup") return <BackupPage />;
  if (base === "settings")
    return <SettingsPage ai={status.ai} theme={theme} setTheme={setTheme} />;
  return <DashboardPage onAdd={() => onAdd("choose")} navigate={navigate} />;
}

function Shell({
  route,
  navigate,
  onAdd,
  onLock,
  status,
  theme,
  setTheme,
  children,
  refresh,
}: {
  route: string;
  navigate: (value: string) => void;
  onAdd: (type: AddType | "choose") => void;
  onLock: () => void;
  status: Status;
  theme: string;
  setTheme: (value: string) => void;
  refresh: number;
  children: React.ReactNode;
}) {
  const [menu, setMenu] = useState(false);
  const base = route.split(":")[0];

  useEffect(() => {
    if (!("Notification" in window) || Notification.permission !== "granted")
      return;
    const check = async () => {
      try {
        const reminders = await api<any[]>("/reminders");
        const notified = new Set(
          JSON.parse(localStorage.getItem("healthvault-notified") || "[]"),
        );
        reminders
          .filter(
            (item) =>
              item.status === "pending" && new Date(item.due_at) <= new Date(),
          )
          .forEach((item) => {
            if (!notified.has(item.id)) {
              new Notification(item.title, {
                body: "HealthVault Local reminder",
              });
              notified.add(item.id);
            }
          });
        localStorage.setItem(
          "healthvault-notified",
          JSON.stringify([...notified].slice(-200)),
        );
      } catch {
        /* session may have locked */
      }
    };
    check();
    const timer = window.setInterval(check, 60000);
    return () => window.clearInterval(timer);
  }, []);

  async function notifications() {
    if ("Notification" in window) await Notification.requestPermission();
  }
  async function logout() {
    await api("/auth/logout", { method: "POST" });
    onLock();
  }
  return (
    <div className="app-shell">
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <div className="sidebar-top">
          <Brand compact />
          <button
            className="close-menu"
            onClick={() => setMenu(false)}
            aria-label="Close menu"
          >
            <X />
          </button>
        </div>
        <Button
          className="sidebar-add"
          icon={<Plus />}
          onClick={() => {
            onAdd("choose");
            setMenu(false);
          }}
        >
          Add
        </Button>
        <button
          className="voice-add"
          onClick={() => {
            onAdd("Voice note");
            setMenu(false);
          }}
        >
          <Mic /> Add voice note
        </button>
        <nav>
          {NAV.map(([key, label, Icon]) => (
            <button
              key={key}
              className={base === key ? "active" : ""}
              onClick={() => {
                navigate(key);
                setMenu(false);
              }}
            >
              <Icon />
              <span>{label}</span>
              {key === "assistant" && !status.ai.available && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button onClick={notifications}>
            <Bell />
            <span>Enable alerts</span>
          </button>
          <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? <Sun /> : <Moon />}
            <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
          </button>
          <button onClick={logout}>
            <ChevronLeft />
            <span>Lock vault</span>
          </button>
          <small>Local · v{status.version}</small>
        </div>
      </aside>
      {menu && (
        <button
          className="menu-scrim"
          onClick={() => setMenu(false)}
          aria-label="Close navigation"
        />
      )}
      <header className="mobile-header">
        <button
          className="icon-button"
          onClick={() => setMenu(true)}
          aria-label="Open menu"
        >
          <Menu />
        </button>
        <Brand compact />
        <button
          className="icon-button"
          onClick={() => onAdd("choose")}
          aria-label="Add record"
        >
          <Plus />
        </button>
      </header>
      <main className="main-content" key={`${route}-${refresh}`}>
        {children}
      </main>
      <nav className="mobile-nav">
        {[
          ["dashboard", "Today", HeartPulse],
          ["family", "Family", UsersRound],
          ["add", "Add", Plus],
          ["appointments", "Calendar", CalendarDays],
          ["search", "Search", Search],
        ].map(([key, label, Icon]: any) => (
          <button
            key={key}
            className={base === key ? "active" : ""}
            onClick={() => (key === "add" ? onAdd("choose") : navigate(key))}
          >
            <Icon />
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
