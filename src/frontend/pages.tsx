import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Archive,
  ArrowDownToLine,
  CalendarDays,
  Check,
  ChevronRight,
  Clock3,
  DatabaseBackup,
  Download,
  FileCheck2,
  FileText,
  HeartPulse,
  ListFilter,
  Maximize2,
  Pill,
  Plus,
  RefreshCw,
  RotateCw,
  Search,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  TestTube2,
  Upload,
  UsersRound,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { api, displayDate, jsonBody } from "./api";
import { Badge, Button, EmptyState, Modal } from "./components";
import { AIStatus, AnyRecord, BackupHealth, DashboardData } from "./types";

function useLoad<T>(path: string, refresh = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<T>(path)
      .then((value) => active && setData(value))
      .catch((caught) => active && setError(caught.message));
    return () => {
      active = false;
    };
  }, [path, refresh]);
  return { data, error };
}

function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action}
    </header>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return message ? (
    <div className="alert alert-critical">
      <AlertCircle size={18} />
      {message}
    </div>
  ) : null;
}
function SkeletonCards() {
  return (
    <div className="skeleton-grid">
      <div />
      <div />
      <div />
    </div>
  );
}
function initials(name = "?") {
  return name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function DashboardPage({
  onAdd,
  navigate,
}: {
  onAdd: () => void;
  navigate: (route: string) => void;
}) {
  const [refresh, setRefresh] = useState(0);
  const { data, error } = useLoad<DashboardData>("/dashboard", refresh);
  async function reminderAction(id: string, action: "complete" | "snooze") {
    await api(
      `/reminders/${id}/${action}${action === "snooze" ? "?minutes=10" : ""}`,
      { method: "POST" },
    );
    setRefresh((value) => value + 1);
  }
  if (!data)
    return (
      <>
        <PageHeader eyebrow="OVERVIEW" title="Today" />
        <ErrorBanner message={error} />
        <SkeletonCards />
      </>
    );
  const todayReminders = data.reminders.filter(
    (item) => new Date(item.due_at) <= new Date(Date.now() + 86400000),
  );
  return (
    <>
      <PageHeader
        eyebrow={new Intl.DateTimeFormat(undefined, {
          weekday: "long",
          month: "long",
          day: "numeric",
        })
          .format(new Date())
          .toUpperCase()}
        title="Good to see you."
        description="Here’s what needs attention across your family."
        action={
          <Button icon={<Plus size={18} />} onClick={onAdd}>
            Add record
          </Button>
        }
      />
      <section className="dashboard-hero-grid">
        <button
          className={`safety-card safety-${data.backup.label.toLowerCase()}`}
          onClick={() => navigate("backup")}
        >
          <div
            className="safety-ring"
            style={
              {
                "--score": `${data.backup.score * 3.6}deg`,
              } as React.CSSProperties
            }
          >
            <span>{data.backup.score}</span>
          </div>
          <div>
            <p className="eyebrow">DATA SAFETY</p>
            <h2>{data.backup.label}</h2>
            <p>
              {data.backup.warnings[0] || "Encrypted, recent, and recoverable."}
            </p>
          </div>
          <ChevronRight />
        </button>
        <div className="today-card">
          <div className="card-heading">
            <span className="icon-disc">
              <Clock3 />
            </span>
            <div>
              <p className="eyebrow">TODAY</p>
              <h2>
                {todayReminders.length
                  ? `${todayReminders.length} items due`
                  : "Nothing urgent"}
              </h2>
            </div>
          </div>
          {todayReminders.length ? (
            <div className="mini-list">
              {todayReminders.slice(0, 3).map((item) => (
                <div key={item.id}>
                  <span className={`dot dot-${item.kind}`} />
                  <div>
                    <strong>{item.title}</strong>
                    <small>{displayDate(item.due_at, true)}</small>
                  </div>
                  <button
                    className="mini-action"
                    onClick={() => reminderAction(item.id, "complete")}
                    aria-label={`Complete ${item.title}`}
                  >
                    <Check size={15} />
                  </button>
                  <button
                    className="mini-action"
                    onClick={() => reminderAction(item.id, "snooze")}
                    aria-label={`Snooze ${item.title}`}
                  >
                    <Clock3 size={15} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="calm-copy">
              No medicines, appointments, or follow-ups are currently due.
            </p>
          )}
          <button className="text-link" onClick={() => navigate("timeline")}>
            View family timeline <ChevronRight size={15} />
          </button>
        </div>
      </section>
      <section className="section-block">
        <div className="section-title">
          <div>
            <p className="eyebrow">FAMILY</p>
            <h2>Health profiles</h2>
          </div>
          <button className="text-link" onClick={() => navigate("family")}>
            View all <ChevronRight size={15} />
          </button>
        </div>
        {data.profiles.length ? (
          <div className="profile-strip">
            {data.profiles.map((profile) => (
              <button
                className="profile-chip-card"
                key={profile.id}
                onClick={() => navigate(`family:${profile.id}`)}
              >
                <span className="avatar" style={{ background: profile.color }}>
                  {initials(profile.name)}
                </span>
                <span>
                  <strong>{profile.name}</strong>
                  <small>
                    {profile.allergies
                      ? "Allergies recorded"
                      : "No allergies recorded"}
                  </small>
                </span>
                <ChevronRight size={17} />
              </button>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No profiles yet"
            description="Add a family member to begin."
          />
        )}
      </section>
      <div className="two-column-sections">
        <section className="section-block">
          <div className="section-title">
            <div>
              <p className="eyebrow">UPCOMING</p>
              <h2>Appointments & follow-ups</h2>
            </div>
          </div>
          {data.appointments.length || data.follow_ups.length ? (
            <div className="timeline-list compact">
              {data.appointments.slice(0, 4).map((item) => (
                <div className="timeline-row" key={item.id}>
                  <div className="date-tile">
                    <strong>{new Date(item.starts_at).getDate()}</strong>
                    <small>
                      {new Intl.DateTimeFormat(undefined, {
                        month: "short",
                      }).format(new Date(item.starts_at))}
                    </small>
                  </div>
                  <span className="timeline-line" />
                  <div>
                    <Badge tone="info">Appointment</Badge>
                    <h3>{item.purpose || "Medical appointment"}</h3>
                    <p>
                      {displayDate(item.starts_at, true)}
                      {item.location ? ` · ${item.location}` : ""}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<CalendarDays />}
              title="No upcoming appointments"
              description="Add one and export it to your phone calendar."
            />
          )}
        </section>
        <section className="section-block">
          <div className="section-title">
            <div>
              <p className="eyebrow">RECENT</p>
              <h2>Latest activity</h2>
            </div>
          </div>
          {data.recent.length ? (
            <div className="activity-list">
              {data.recent.slice(0, 6).map((item) => (
                <div key={`${item.kind}-${item.id}`}>
                  <span className="activity-icon">
                    {item.kind === "Document" ? (
                      <FileText />
                    ) : item.kind === "Visit" ? (
                      <Stethoscope />
                    ) : item.kind === "Prescription" ? (
                      <Pill />
                    ) : (
                      <HeartPulse />
                    )}
                  </span>
                  <div>
                    <strong>
                      {item.title || item.reason || item.content || item.kind}
                    </strong>
                    <small>
                      {item.kind} · {displayDate(item.created_at)}
                    </small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No activity yet"
              description="Your newest records will appear here."
            />
          )}
        </section>
      </div>
    </>
  );
}

export function ProfilesPage({
  initialId,
  onAdd,
}: {
  initialId?: string;
  onAdd: () => void;
}) {
  const { data: profiles, error } = useLoad<AnyRecord[]>("/profiles");
  const [selected, setSelected] = useState(initialId || "");
  useEffect(() => {
    if (initialId) setSelected(initialId);
  }, [initialId]);
  if (!profiles)
    return (
      <>
        <PageHeader title="Family" />
        <ErrorBanner message={error} />
        <SkeletonCards />
      </>
    );
  const profile = profiles.find((item) => item.id === selected);
  if (profile)
    return <ProfileDetail profile={profile} onBack={() => setSelected("")} />;
  return (
    <>
      <PageHeader
        eyebrow="FAMILY PROFILES"
        title="Everyone’s history, clearly separated."
        description="Each record belongs to one person and can be moved or linked without losing its UUID."
        action={
          <Button icon={<Plus size={18} />} onClick={onAdd}>
            Add family member
          </Button>
        }
      />
      {profiles.length ? (
        <div className="profile-grid">
          {profiles.map((item) => (
            <button
              className="profile-card"
              key={item.id}
              onClick={() => setSelected(item.id)}
            >
              <span
                className="avatar avatar-large"
                style={{ background: item.color }}
              >
                {initials(item.name)}
              </span>
              <div>
                <h2>{item.name}</h2>
                <p>
                  {item.date_of_birth
                    ? `Born ${displayDate(item.date_of_birth)}`
                    : "Date of birth not recorded"}
                </p>
              </div>
              <div className="profile-facts">
                <span>
                  <small>Blood group</small>
                  <strong>{item.blood_group || "—"}</strong>
                </span>
                <span>
                  <small>Allergies</small>
                  <strong>{item.allergies || "None recorded"}</strong>
                </span>
                <span>
                  <small>Conditions</small>
                  <strong>{item.chronic_conditions || "None recorded"}</strong>
                </span>
              </div>
              <span className="open-label">
                Open full history <ChevronRight size={16} />
              </span>
            </button>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<UsersRound />}
          title="Add your first family profile"
          description="Profiles keep every person’s records and timeline distinct."
          action={<Button onClick={onAdd}>Add profile</Button>}
        />
      )}
    </>
  );
}

function ProfileDetail({
  profile,
  onBack,
}: {
  profile: AnyRecord;
  onBack: () => void;
}) {
  const { data: timeline, error } = useLoad<AnyRecord[]>(
    `/timeline/${profile.id}`,
  );
  return (
    <>
      <button className="back-link" onClick={onBack}>
        ← All family profiles
      </button>
      <PageHeader
        eyebrow="HEALTH PROFILE"
        title={profile.name}
        description={[
          profile.blood_group && `Blood ${profile.blood_group}`,
          profile.date_of_birth && displayDate(profile.date_of_birth),
        ]
          .filter(Boolean)
          .join(" · ")}
        action={
          <a
            className="button button-secondary"
            href={`/api/profiles/${profile.id}/doctor-summary`}
            download
          >
            Prepare doctor summary <Download size={17} />
          </a>
        }
      />
      <div className="profile-banner">
        <span
          className="avatar avatar-xl"
          style={{ background: profile.color }}
        >
          {initials(profile.name)}
        </span>
        <div className="profile-banner-facts">
          <span>
            <small>Known allergies</small>
            <strong>{profile.allergies || "Not recorded"}</strong>
          </span>
          <span>
            <small>Chronic conditions</small>
            <strong>{profile.chronic_conditions || "Not recorded"}</strong>
          </span>
          <span>
            <small>Emergency information</small>
            <strong>{profile.emergency_information || "Not recorded"}</strong>
          </span>
        </div>
      </div>
      <section className="section-block">
        <div className="section-title">
          <div>
            <p className="eyebrow">COMPLETE HISTORY</p>
            <h2>Timeline</h2>
          </div>
        </div>
        <ErrorBanner message={error} />
        {timeline?.length ? (
          <Timeline records={timeline} />
        ) : (
          <EmptyState
            icon={<Clock3 />}
            title="No history yet"
            description="Visits, prescriptions, medicines, notes, reports, and measurements will be combined here."
          />
        )}
      </section>
    </>
  );
}

function Timeline({ records }: { records: AnyRecord[] }) {
  return (
    <div className="timeline-list">
      {records.map((item) => (
        <div className="timeline-row" key={`${item.kind}-${item.id}`}>
          <div className="date-tile">
            <strong>{new Date(item.event_date).getDate()}</strong>
            <small>
              {new Intl.DateTimeFormat(undefined, { month: "short" }).format(
                new Date(item.event_date),
              )}
            </small>
          </div>
          <span className="timeline-line" />
          <div>
            <Badge
              tone={
                item.kind === "prescription"
                  ? "warning"
                  : item.kind === "visit"
                    ? "info"
                    : item.kind === "measurement"
                      ? "good"
                      : "neutral"
              }
            >
              {String(item.kind).replace("_", " ")}
            </Badge>
            <h3>
              {item.title ||
                item.reason ||
                item.purpose ||
                item.diagnosis_text ||
                item.content ||
                item.original_filename ||
                item.kind}
            </h3>
            <p>
              {item.summary ||
                item.symptoms ||
                item.notes ||
                item.category ||
                displayDate(item.event_date, true)}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

export function TimelinePage() {
  const { data: profiles } = useLoad<AnyRecord[]>("/profiles");
  const [profileId, setProfileId] = useState("");
  useEffect(() => {
    if (!profileId && profiles?.length) setProfileId(profiles[0].id);
  }, [profiles, profileId]);
  const { data: records, error } = useLoad<AnyRecord[]>(
    profileId ? `/timeline/${profileId}` : "/timeline/none",
  );
  return (
    <>
      <PageHeader
        eyebrow="CHRONOLOGY"
        title="Family timeline"
        description="Visits, documents, medicine, appointments, measurements, and notes in one sequence."
        action={
          <select
            className="header-select"
            value={profileId}
            onChange={(e) => setProfileId(e.target.value)}
          >
            {profiles?.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        }
      />
      <ErrorBanner message={error} />
      {records?.length ? (
        <Timeline records={records} />
      ) : (
        <EmptyState
          icon={<Clock3 />}
          title="Nothing on this timeline yet"
          description="Choose a profile or add a health record."
        />
      )}
    </>
  );
}

const RECORD_CONFIG: Record<
  string,
  {
    title: string;
    eyebrow: string;
    icon: ReactNode;
    endpoint: string;
    addLabel: string;
  }
> = {
  visits: {
    title: "Doctor visits",
    eyebrow: "CONSULTATIONS",
    icon: <Stethoscope />,
    endpoint: "/visits",
    addLabel: "Doctor visit",
  },
  prescriptions: {
    title: "Prescriptions",
    eyebrow: "PRESCRIBED CARE",
    icon: <FileCheck2 />,
    endpoint: "/prescriptions",
    addLabel: "Prescription",
  },
  notes: {
    title: "Health notes",
    eyebrow: "QUICK NOTES",
    icon: <HeartPulse />,
    endpoint: "/notes",
    addLabel: "Health note",
  },
};

export function RecordsPage({
  kind,
  onAdd,
}: {
  kind: "visits" | "prescriptions" | "notes";
  onAdd: () => void;
}) {
  const config = RECORD_CONFIG[kind];
  const { data, error } = useLoad<AnyRecord[]>(config.endpoint);
  return (
    <>
      <PageHeader
        eyebrow={config.eyebrow}
        title={config.title}
        description={
          kind === "prescriptions"
            ? "Original evidence and verified structured details remain distinct."
            : "Searchable, timestamped, and linked to the right family member."
        }
        action={
          <Button icon={<Plus size={18} />} onClick={onAdd}>
            Add {config.addLabel.toLowerCase()}
          </Button>
        }
      />
      <ErrorBanner message={error} />
      {data?.length ? (
        <div className="record-grid">
          {data.map((item) => (
            <article className="record-card" key={item.id}>
              <div className="record-icon">{config.icon}</div>
              <div className="record-main">
                <div className="record-meta">
                  <Badge
                    tone={item.status === "unverified" ? "warning" : "neutral"}
                  >
                    {item.status || kind.slice(0, -1)}
                  </Badge>
                  <span>
                    {displayDate(
                      item.visit_date ||
                        item.prescription_date ||
                        item.occurred_at,
                      Boolean(item.visit_date || item.occurred_at),
                    )}
                  </span>
                </div>
                <h2>
                  {item.reason ||
                    item.diagnosis_text ||
                    item.title ||
                    item.content?.slice(0, 90) ||
                    "Untitled record"}
                </h2>
                <p>
                  {item.summary ||
                    item.symptoms ||
                    item.notes ||
                    item.content ||
                    "No additional notes."}
                </p>
              </div>
              <button className="icon-button" aria-label="Open record">
                <ChevronRight />
              </button>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={config.icon}
          title={`No ${config.title.toLowerCase()} yet`}
          description={`Use Add to create the first ${config.addLabel.toLowerCase()}.`}
          action={
            <Button onClick={onAdd}>Add {config.addLabel.toLowerCase()}</Button>
          }
        />
      )}
    </>
  );
}

export function MedicinesPage({ onAdd }: { onAdd: () => void }) {
  const { data: prescribed, error } = useLoad<AnyRecord[]>(
    "/prescribed-medications",
  );
  const { data: medicines } = useLoad<AnyRecord[]>("/medications");
  const { data: profiles } = useLoad<AnyRecord[]>("/profiles");
  const medMap = useMemo(
    () => Object.fromEntries((medicines || []).map((item) => [item.id, item])),
    [medicines],
  );
  const profileMap = useMemo(
    () => Object.fromEntries((profiles || []).map((item) => [item.id, item])),
    [profiles],
  );
  async function markDose(item: AnyRecord, status: "taken" | "skipped") {
    await api(
      "/doses",
      jsonBody({
        prescribed_medication_id: item.id,
        scheduled_at: new Date().toISOString(),
        status,
        note: null,
      }),
    );
  }
  const groups = {
    Active:
      prescribed?.filter((item) => item.tracking_status === "active") || [],
    Completed:
      prescribed?.filter((item) => item.tracking_status === "completed") || [],
    Past:
      prescribed?.filter((item) => item.tracking_status === "stopped") || [],
  };
  return (
    <>
      <PageHeader
        eyebrow="MEDICINES"
        title="Medication, without losing history."
        description="Tracking can stop; prescriptions and recorded doses remain unchanged."
        action={
          <Button icon={<Plus size={18} />} onClick={onAdd}>
            Add medicine
          </Button>
        }
      />
      <ErrorBanner message={error} />
      {Object.entries(groups).map(([label, items]) => (
        <section className="section-block" key={label}>
          <div className="section-title">
            <div>
              <p className="eyebrow">{label.toUpperCase()}</p>
              <h2>
                {items.length} {items.length === 1 ? "medicine" : "medicines"}
              </h2>
            </div>
          </div>
          {items.length ? (
            <div className="medicine-grid">
              {items.map((item) => {
                const med = medMap[item.medication_id] || {};
                return (
                  <article className="medicine-card" key={item.id}>
                    <div className="medicine-top">
                      <span className="pill-symbol">
                        <Pill />
                      </span>
                      <div>
                        <Badge
                          tone={
                            item.verification_status === "verified"
                              ? "good"
                              : "warning"
                          }
                        >
                          {item.verification_status}
                        </Badge>
                        <h2>
                          {med.brand_name ||
                            med.generic_name ||
                            "Unknown medicine"}
                        </h2>
                        <p>
                          {[med.generic_name, med.strength, med.form]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                      </div>
                    </div>
                    <div className="dose-facts">
                      <span>
                        <small>Dose</small>
                        <strong>{item.dosage || "Not recorded"}</strong>
                      </span>
                      <span>
                        <small>Frequency</small>
                        <strong>{item.frequency || "Not recorded"}</strong>
                      </span>
                      <span>
                        <small>Timing</small>
                        <strong>
                          {item.timing || item.food_relation || "Not recorded"}
                        </strong>
                      </span>
                    </div>
                    <p className="medicine-owner">
                      For{" "}
                      {profileMap[item.profile_id]?.name || "Unknown profile"} ·{" "}
                      {item.start_date
                        ? displayDate(item.start_date)
                        : "start not recorded"}
                    </p>
                    {label === "Active" && (
                      <div className="medicine-actions">
                        <Button
                          variant="secondary"
                          onClick={() => markDose(item, "taken")}
                          icon={<Check size={16} />}
                        >
                          Taken
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() => markDose(item, "skipped")}
                        >
                          Skip
                        </Button>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          ) : (
            <p className="calm-copy">No {label.toLowerCase()} medicines.</p>
          )}
        </section>
      ))}
    </>
  );
}

export function AppointmentsPage({ onAdd }: { onAdd: () => void }) {
  const { data, error } = useLoad<AnyRecord[]>("/appointments");
  const [view, setView] = useState<"list" | "calendar">("list");
  const current = new Date();
  const first = new Date(current.getFullYear(), current.getMonth(), 1);
  const days = new Date(
    current.getFullYear(),
    current.getMonth() + 1,
    0,
  ).getDate();
  const cells = [
    ...Array(first.getDay()).fill(null),
    ...Array.from({ length: days }, (_, index) => index + 1),
  ];
  return (
    <>
      <PageHeader
        eyebrow="APPOINTMENTS"
        title="Plan visits and follow through."
        description="Export standard calendar events for durable phone reminders."
        action={
          <div className="header-actions">
            <a
              href="/api/appointments.ics"
              className="button button-secondary"
              download
            >
              <ArrowDownToLine size={17} /> Export .ics
            </a>
            <Button icon={<Plus size={18} />} onClick={onAdd}>
              Add appointment
            </Button>
          </div>
        }
      />
      <div className="segmented">
        <button
          className={view === "list" ? "active" : ""}
          onClick={() => setView("list")}
        >
          <ListFilter />
          List
        </button>
        <button
          className={view === "calendar" ? "active" : ""}
          onClick={() => setView("calendar")}
        >
          <CalendarDays />
          Calendar
        </button>
      </div>
      <ErrorBanner message={error} />
      {view === "calendar" ? (
        <div className="calendar-card">
          <div className="calendar-heading">
            <h2>
              {new Intl.DateTimeFormat(undefined, {
                month: "long",
                year: "numeric",
              }).format(current)}
            </h2>
          </div>
          <div className="calendar-weekdays">
            {"Sun Mon Tue Wed Thu Fri Sat".split(" ").map((day) => (
              <span key={day}>{day}</span>
            ))}
          </div>
          <div className="calendar-grid">
            {cells.map((day, index) => (
              <div
                className={`${day === current.getDate() ? "today" : ""}`}
                key={index}
              >
                {day && (
                  <>
                    <strong>{day}</strong>
                    {data
                      ?.filter((item) => {
                        const value = new Date(item.starts_at);
                        return (
                          value.getDate() === day &&
                          value.getMonth() === current.getMonth()
                        );
                      })
                      .map((item) => (
                        <span
                          className="calendar-event"
                          title={item.purpose}
                          key={item.id}
                        >
                          {item.purpose || "Appointment"}
                        </span>
                      ))}
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : data?.length ? (
        <div className="appointment-list">
          {data.map((item) => (
            <article key={item.id}>
              <div className="appointment-date">
                <strong>{new Date(item.starts_at).getDate()}</strong>
                <span>
                  {new Intl.DateTimeFormat(undefined, {
                    month: "short",
                  }).format(new Date(item.starts_at))}
                </span>
                <small>
                  {new Intl.DateTimeFormat(undefined, {
                    timeStyle: "short",
                  }).format(new Date(item.starts_at))}
                </small>
              </div>
              <div>
                <Badge
                  tone={
                    item.status === "scheduled"
                      ? "info"
                      : item.status === "completed"
                        ? "good"
                        : "neutral"
                  }
                >
                  {item.status}
                </Badge>
                <h2>{item.purpose || "Medical appointment"}</h2>
                <p>{item.location || "Location not recorded"}</p>
                <small>
                  {item.preparation_notes || "No preparation notes"}
                </small>
              </div>
              {item.status === "completed" && (
                <Button
                  variant="secondary"
                  onClick={() =>
                    api(`/appointments/${item.id}/create-visit`, {
                      method: "POST",
                    })
                  }
                >
                  Create visit record
                </Button>
              )}
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<CalendarDays />}
          title="No appointments yet"
          description="Plan an appointment, set a reminder, and export it to your phone."
          action={<Button onClick={onAdd}>Add appointment</Button>}
        />
      )}
    </>
  );
}

export function DocumentsPage({ onAdd }: { onAdd: () => void }) {
  const [refresh, setRefresh] = useState(0);
  const { data, error } = useLoad<AnyRecord[]>("/documents", refresh);
  const [viewer, setViewer] = useState<AnyRecord | null>(null);
  async function ocr(item: AnyRecord) {
    try {
      await api(`/documents/${item.id}/ocr`, { method: "POST" });
      setRefresh((value) => value + 1);
    } catch (caught: any) {
      window.alert(caught.message);
    }
  }
  return (
    <>
      <PageHeader
        eyebrow="ORIGINAL EVIDENCE"
        title="Documents"
        description="Originals are immutable, content-hashed, and stored outside SQLite."
        action={
          <Button icon={<Upload size={18} />} onClick={onAdd}>
            Upload document
          </Button>
        }
      />
      <ErrorBanner message={error} />
      {data?.length ? (
        <div className="document-grid">
          {data.map((item) => (
            <article className="document-card" key={item.id}>
              <button
                className="document-preview"
                onClick={() => setViewer(item)}
              >
                {item.thumbnail_path ? (
                  <img src={`/api/documents/${item.id}/thumbnail`} alt="" />
                ) : (
                  <span>
                    <FileText />
                    <small>
                      {item.mime_type === "application/pdf" ? "PDF" : "FILE"}
                    </small>
                  </span>
                )}
              </button>
              <div className="document-info">
                <Badge>{String(item.category).replaceAll("_", " ")}</Badge>
                <h2>{item.title || item.original_filename}</h2>
                <p>
                  {displayDate(item.document_date || item.created_at)} ·{" "}
                  {(item.size_bytes / 1048576).toFixed(1)} MB
                </p>
                <div className="document-status">
                  <span className={`status-dot status-${item.ocr_status}`} />{" "}
                  OCR {String(item.ocr_status).replaceAll("_", " ")}
                </div>
              </div>
              <div className="document-actions">
                <button
                  className="icon-button"
                  onClick={() => setViewer(item)}
                  aria-label="View"
                >
                  <Maximize2 />
                </button>
                <a
                  className="icon-button"
                  href={`/api/documents/${item.id}/content?download=true`}
                  aria-label="Download"
                >
                  <Download />
                </a>
                {item.ocr_status === "not_started" && (
                  <button
                    className="icon-button"
                    onClick={() => ocr(item)}
                    aria-label="Run OCR"
                  >
                    <RefreshCw />
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<FileText />}
          title="No documents yet"
          description="Upload a prescription photo, PDF, report, scan, or invoice. Exact duplicates are detected automatically."
          action={<Button onClick={onAdd}>Upload first document</Button>}
        />
      )}
      {viewer && (
        <DocumentViewer document={viewer} onClose={() => setViewer(null)} />
      )}
    </>
  );
}

function DocumentViewer({
  document: item,
  onClose,
}: {
  document: AnyRecord;
  onClose: () => void;
}) {
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const image = item.mime_type.startsWith("image/");
  return (
    <Modal title={item.title || item.original_filename} onClose={onClose} wide>
      <div className="viewer-toolbar">
        <Button
          variant="ghost"
          onClick={() => setZoom(Math.max(0.5, zoom - 0.25))}
          icon={<ZoomOut />}
        >
          Zoom out
        </Button>
        <span>{Math.round(zoom * 100)}%</span>
        <Button
          variant="ghost"
          onClick={() => setZoom(Math.min(3, zoom + 0.25))}
          icon={<ZoomIn />}
        >
          Zoom in
        </Button>
        {image && (
          <Button
            variant="ghost"
            onClick={() => setRotation((value) => value + 90)}
            icon={<RotateCw />}
          >
            Rotate
          </Button>
        )}
        <a
          className="button button-secondary"
          href={`/api/documents/${item.id}/content?download=true`}
        >
          <Download size={16} /> Original
        </a>
      </div>
      <div className="viewer-stage">
        {image ? (
          <img
            src={`/api/documents/${item.id}/content`}
            style={{ transform: `scale(${zoom}) rotate(${rotation}deg)` }}
            alt={item.title || item.original_filename}
          />
        ) : (
          <iframe
            src={`/api/documents/${item.id}/content`}
            title={item.title || item.original_filename}
          />
        )}
      </div>
      {(item.corrected_ocr_text || item.original_ocr_text) && (
        <details className="ocr-panel">
          <summary>OCR text & evidence</summary>
          <pre>{item.corrected_ocr_text || item.original_ocr_text}</pre>
        </details>
      )}
    </Modal>
  );
}

export function SearchPage() {
  const [query, setQuery] = useState("");
  const [profile, setProfile] = useState("");
  const [type, setType] = useState("");
  const [results, setResults] = useState<AnyRecord[]>([]);
  const [searched, setSearched] = useState(false);
  const { data: profiles } = useLoad<AnyRecord[]>("/profiles");
  async function submit(event: FormEvent) {
    event.preventDefault();
    const params = new URLSearchParams({ q: query });
    if (profile) params.set("profile_id", profile);
    if (type) params.set("entity_type", type);
    setResults(await api(`/search?${params}`));
    setSearched(true);
  }
  return (
    <>
      <PageHeader
        eyebrow="FULL-TEXT SEARCH"
        title="Find the thread in the history."
        description="Search doctors, medicines, diagnoses, symptoms, notes, documents, and preserved OCR."
      />
      <form className="search-bar" onSubmit={submit}>
        <Search />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          required
          placeholder="Try ‘knee pain’, a medicine, doctor, or test…"
          autoFocus
        />
        <Button>Search</Button>
      </form>
      <div className="filter-bar">
        <select value={profile} onChange={(e) => setProfile(e.target.value)}>
          <option value="">All family members</option>
          {profiles?.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All record types</option>
          <option value="visits">Visits</option>
          <option value="prescriptions">Prescriptions</option>
          <option value="medications">Medicines</option>
          <option value="documents">Documents</option>
          <option value="notes">Notes</option>
        </select>
      </div>
      {results.length ? (
        <div className="search-results">
          {results.map((item) => (
            <article key={`${item.entity_type}-${item.entity_id}`}>
              <span className="search-type">
                {String(item.entity_type).replace("_", " ")}
              </span>
              <div>
                <h2>{item.title}</h2>
                <p>
                  {String(item.snippet)
                    .replaceAll("<mark>", "")
                    .replaceAll("</mark>", "")}
                </p>
                <small>{displayDate(item.event_date)}</small>
              </div>
              <ChevronRight />
            </article>
          ))}
        </div>
      ) : searched ? (
        <EmptyState
          icon={<Search />}
          title="No supporting records found"
          description="Try fewer words or remove a filter. HealthVault does not guess missing information."
        />
      ) : null}
    </>
  );
}

export function BackupPage() {
  const [refresh, setRefresh] = useState(0);
  const { data, error } = useLoad<BackupHealth>("/backups", refresh);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [showDestination, setShowDestination] = useState(false);
  const [showRestore, setShowRestore] = useState(false);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy("backup");
    setMessage("");
    try {
      const backupPassword = String(form.get("password") || "");
      const appPassword = String(form.get("app_password") || "");
      if (appPassword) {
        const credential = new FormData();
        credential.set("app_password", appPassword);
        credential.set("backup_password", backupPassword);
        await api("/backups/credential", { method: "POST", body: credential });
      }
      await api(
        "/backups/create",
        jsonBody({ password: backupPassword, kind: "manual" }),
      );
      setMessage(
        `Encrypted backup completed.${appPassword ? " Automatic daily backup is enabled while HealthVault is running and unlocked." : ""}`,
      );
      setRefresh((v) => v + 1);
    } catch (caught: any) {
      setMessage(caught.message);
    } finally {
      setBusy("");
    }
  }
  async function verify(event: FormEvent<HTMLFormElement>, test = false) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(test ? "test" : "verify");
    setMessage("");
    try {
      const result: any = await api(
        `/backups/${test ? "test-restore" : "verify"}`,
        jsonBody({ path: form.get("path"), password: form.get("password") }),
      );
      setMessage(
        test
          ? `Test restore passed. ${result.profile_count} profile(s) opened successfully.`
          : "Backup archive, manifest, database, and checksums verified.",
      );
      setRefresh((v) => v + 1);
    } catch (caught: any) {
      setMessage(caught.message);
    } finally {
      setBusy("");
    }
  }
  async function destination(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api(
      "/backups/destinations",
      jsonBody({
        name: form.get("name"),
        path: form.get("path"),
        role: form.get("role"),
        enabled: true,
      }),
    );
    setShowDestination(false);
    setRefresh((v) => v + 1);
  }
  async function restore(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (form.get("confirm") !== "on") return;
    setBusy("restore");
    setMessage("");
    try {
      const result: any = await api(
        "/backups/restore",
        jsonBody({ path: form.get("path"), password: form.get("password") }),
      );
      setMessage(
        `Restore completed after creating emergency snapshot ${result.emergency_backup}. Restart HealthVault and verify the restored records.`,
      );
      setShowRestore(false);
      setRefresh((v) => v + 1);
    } catch (caught: any) {
      setMessage(caught.message);
    } finally {
      setBusy("");
    }
  }
  return (
    <>
      <PageHeader
        eyebrow="BACKUP & RECOVERY"
        title="Know that recovery will work."
        description="A backup is healthy only after its contents and database have been verified."
        action={
          <Button
            icon={<Plus size={18} />}
            onClick={() => setShowDestination(true)}
          >
            Add destination
          </Button>
        }
      />
      <ErrorBanner message={error} />
      {data && (
        <>
          <section
            className={`backup-health-card backup-${data.label.toLowerCase()}`}
          >
            <div className="backup-score">
              <strong>{data.score}</strong>
              <span>/100</span>
            </div>
            <div>
              <p className="eyebrow">DATA SAFETY</p>
              <h2>{data.label}</h2>
              <p>
                {data.warnings[0] ||
                  "Recent encrypted backup with verified recovery."}
              </p>
              <div className="backup-checks">
                <span className={data.last_successful ? "pass" : "fail"}>
                  <Check /> Last backup{" "}
                  {data.last_successful
                    ? displayDate(data.last_successful.completed_at, true)
                    : "missing"}
                </span>
                <span className={data.last_verified ? "pass" : "fail"}>
                  <Check /> Restore evidence{" "}
                  {data.last_verified
                    ? displayDate(data.last_verified.verified_at)
                    : "missing"}
                </span>
                <span
                  className={data.destinations.length > 1 ? "pass" : "warn"}
                >
                  <Check /> {data.destinations.length} external destination(s)
                </span>
              </div>
            </div>
            <DatabaseBackup />
          </section>
          {message && (
            <div
              className={`alert ${message.toLowerCase().includes("failed") || message.toLowerCase().includes("wrong") ? "alert-critical" : "alert-success"}`}
            >
              {message}
            </div>
          )}
          <div className="backup-grid">
            <section className="section-block">
              <p className="eyebrow">CREATE</p>
              <h2>Encrypted backup</h2>
              <p>
                Includes a consistent SQLite snapshot, originals, voice notes,
                schema versions, manifest, and SHA-256 checksums.
              </p>
              <form className="form-stack" onSubmit={create}>
                <label>
                  Backup password
                  <input
                    name="password"
                    type="password"
                    minLength={12}
                    required
                  />
                </label>
                <label>
                  Application password (optional)
                  <input name="app_password" type="password" />
                  <span className="field-help">
                    Enter it to enable automatic daily/weekly/monthly backups
                    while the app is running and unlocked.
                  </span>
                </label>
                <Button
                  disabled={busy === "backup"}
                  icon={<DatabaseBackup size={17} />}
                >
                  {busy === "backup" ? "Backing up…" : "Back up now"}
                </Button>
              </form>
            </section>
            <section className="section-block">
              <p className="eyebrow">VERIFY OR TEST</p>
              <h2>Prove recoverability</h2>
              <p>
                Test restore opens the archive in a temporary location without
                touching current data.
              </p>
              <form
                className="form-stack"
                onSubmit={(event) => verify(event, false)}
              >
                <label>
                  Backup file path
                  <input
                    name="path"
                    required
                    placeholder="…\healthvault_backup_….hvault"
                  />
                </label>
                <label>
                  Backup password
                  <input name="password" type="password" required />
                </label>
                <div className="button-row">
                  <Button
                    variant="secondary"
                    disabled={Boolean(busy)}
                    icon={<FileCheck2 size={17} />}
                  >
                    {busy === "verify" ? "Verifying…" : "Verify backup"}
                  </Button>
                  <Button
                    type="button"
                    disabled={Boolean(busy)}
                    onClick={(event) => {
                      const form = event.currentTarget.closest("form");
                      if (form)
                        verify(
                          { preventDefault() {}, currentTarget: form } as any,
                          true,
                        );
                    }}
                    icon={<TestTube2 size={17} />}
                  >
                    {busy === "test" ? "Testing…" : "Test restore"}
                  </Button>
                </div>
              </form>
            </section>
          </div>
          <section className="section-block">
            <div className="section-title">
              <div>
                <p className="eyebrow">DESTINATIONS</p>
                <h2>Independent copies</h2>
              </div>
            </div>
            {data.destinations.length ? (
              <div className="destination-list">
                {data.destinations.map((item) => (
                  <div key={item.id}>
                    <span className="destination-icon">
                      <DatabaseBackup />
                    </span>
                    <div>
                      <strong>{item.name}</strong>
                      <code>{item.path}</code>
                    </div>
                    <Badge
                      tone={
                        item.last_error
                          ? "critical"
                          : item.last_success_at
                            ? "good"
                            : "warning"
                      }
                    >
                      {item.last_error
                        ? "Failed"
                        : item.last_success_at
                          ? "Healthy"
                          : "Not tested"}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<DatabaseBackup />}
                title="Only the local recovery folder exists"
                description="Add an external drive, NAS folder, or synced filesystem folder."
              />
            )}
          </section>
          <section className="danger-zone">
            <Archive />
            <div>
              <h2>Full restore</h2>
              <p>
                Restore validates in staging and always creates an emergency
                encrypted snapshot before replacing current data.
              </p>
            </div>
            <Button variant="danger" onClick={() => setShowRestore(true)}>
              Open restore wizard
            </Button>
          </section>
        </>
      )}
      {showDestination && (
        <Modal
          title="Add backup destination"
          onClose={() => setShowDestination(false)}
        >
          <form className="form-stack modal-form" onSubmit={destination}>
            <label>
              Name
              <input name="name" required placeholder="External drive" />
            </label>
            <label>
              Folder path
              <input
                name="path"
                required
                placeholder="E:\HealthVault Backups"
              />
            </label>
            <label>
              Role
              <select name="role">
                <option value="primary">Primary</option>
                <option value="secondary">Secondary</option>
                <option value="archive">Archive</option>
              </select>
            </label>
            <Button>Save destination</Button>
          </form>
        </Modal>
      )}
      {showRestore && (
        <Modal
          title="Restore existing vault"
          onClose={() => setShowRestore(false)}
        >
          <form className="form-stack modal-form" onSubmit={restore}>
            <div className="alert alert-critical">
              <AlertCircle size={18} />
              Verify and test-restore this archive first. Current data will be
              replaced only after an emergency encrypted snapshot succeeds.
            </div>
            <label>
              Backup file path
              <input
                name="path"
                required
                placeholder={"D:\\Backups\\healthvault_backup_….hvault"}
              />
            </label>
            <label>
              Backup password
              <input name="password" type="password" required />
            </label>
            <label className="check-label">
              <input name="confirm" type="checkbox" required />I understand that
              current records will be replaced after the safety snapshot.
            </label>
            <div className="modal-actions">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setShowRestore(false)}
              >
                Cancel
              </Button>
              <Button variant="danger" disabled={busy === "restore"}>
                {busy === "restore"
                  ? "Restoring safely…"
                  : "Create snapshot and restore"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}

export function AssistantPage({ ai }: { ai: AIStatus }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const { data: profiles } = useLoad<AnyRecord[]>("/profiles");
  const [profile, setProfile] = useState("");
  async function ask(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      setAnswer(
        await api(
          "/ai/query",
          jsonBody({ question, profile_id: profile || null }),
        ),
      );
    } catch (caught: any) {
      setAnswer({ answer: caught.message, citations: [] });
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader
        eyebrow="PRIVATE LOCAL AI"
        title="Ask your records, not the internet."
        description="Answers are grounded in stored evidence and link back to supporting UUIDs."
      />
      <div className={`ai-status ${ai.available ? "available" : ""}`}>
        <span>
          <Sparkles />
        </span>
        <div>
          <strong>
            {ai.available
              ? `${ai.selected_model || "Local model"} is ready`
              : "Local AI is unavailable"}
          </strong>
          <p>
            {ai.available
              ? "Queries stay on this computer through Ollama."
              : "Start Ollama and install a model. The rest of HealthVault remains fully usable."}
          </p>
        </div>
        <Badge tone={ai.available ? "good" : "neutral"}>
          {ai.available ? "Local only" : "Gracefully disabled"}
        </Badge>
      </div>
      <form className="assistant-composer" onSubmit={ask}>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          required
          placeholder="When was Dad’s last cardiology appointment?"
        />
        <div>
          <select value={profile} onChange={(e) => setProfile(e.target.value)}>
            <option value="">Search all family profiles</option>
            {profiles?.map((item) => (
              <option value={item.id} key={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <Button
            disabled={busy || !ai.available}
            icon={<Sparkles size={17} />}
          >
            {busy ? "Reviewing records…" : "Ask records"}
          </Button>
        </div>
      </form>
      {answer && (
        <section className="assistant-answer">
          <p className="eyebrow">ANSWER FROM YOUR RECORDS</p>
          <div className="answer-copy">{answer.answer}</div>
          {answer.citations?.length ? (
            <div className="citations">
              <strong>Supporting records</strong>
              {answer.citations.map((item: AnyRecord) => (
                <div key={item.entity_id}>
                  <Badge>{item.entity_type}</Badge>
                  <code>{item.entity_id}</code>
                  <span>{item.title}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="no-evidence">
              No supporting record links were returned. Do not rely on this
              answer for medical decisions.
            </p>
          )}
        </section>
      )}
    </>
  );
}

export function SettingsPage({
  ai,
  theme,
  setTheme,
}: {
  ai: AIStatus;
  theme: string;
  setTheme: (value: string) => void;
}) {
  const [test, setTest] = useState("");
  return (
    <>
      <PageHeader
        eyebrow="SETTINGS"
        title="Local system settings"
        description="Core health records never require internet access or telemetry."
      />
      <div className="settings-grid">
        <section className="section-block">
          <div className="settings-heading">
            <span>
              <Sparkles />
            </span>
            <div>
              <h2>Local AI</h2>
              <p>Ollama-compatible provider</p>
            </div>
          </div>
          <dl>
            <div>
              <dt>Status</dt>
              <dd>
                <Badge tone={ai.available ? "good" : "neutral"}>
                  {ai.available ? "Available" : "Unavailable"}
                </Badge>
              </dd>
            </div>
            <div>
              <dt>Selected model</dt>
              <dd>{ai.selected_model || "None"}</dd>
            </div>
            <div>
              <dt>Privacy mode</dt>
              <dd>Local only</dd>
            </div>
          </dl>
          <Button
            variant="secondary"
            onClick={async () => {
              const result: any = await api("/ai/test", { method: "POST" });
              setTest(result.test);
            }}
            icon={<RefreshCw size={16} />}
          >
            Test AI
          </Button>
          {test && <p className="field-help">Test result: {test}</p>}
        </section>
        <section className="section-block">
          <div className="settings-heading">
            <span>
              <ShieldCheck />
            </span>
            <div>
              <h2>Appearance</h2>
              <p>Comfortable across devices</p>
            </div>
          </div>
          <label>
            Color theme
            <select value={theme} onChange={(e) => setTheme(e.target.value)}>
              <option value="system">Use system setting</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </label>
          <p className="field-help">
            Keyboard focus, high contrast, and large touch targets are enabled
            in every mode.
          </p>
        </section>
        <section className="section-block">
          <div className="settings-heading">
            <span>
              <DatabaseBackup />
            </span>
            <div>
              <h2>System versions</h2>
              <p>Compatibility identifiers</p>
            </div>
          </div>
          <dl>
            <div>
              <dt>Application</dt>
              <dd>0.1.0</dd>
            </div>
            <div>
              <dt>Database schema</dt>
              <dd>1</dd>
            </div>
            <div>
              <dt>Export schema</dt>
              <dd>1</dd>
            </div>
            <div>
              <dt>Backup format</dt>
              <dd>1</dd>
            </div>
          </dl>
        </section>
        <section className="section-block">
          <div className="settings-heading">
            <span>
              <ShieldCheck />
            </span>
            <div>
              <h2>Privacy</h2>
              <p>No telemetry</p>
            </div>
          </div>
          <ul className="plain-list">
            <li>
              <Check /> No analytics or tracking
            </li>
            <li>
              <Check /> Strict same-site session cookies
            </li>
            <li>
              <Check /> Originals never modified
            </li>
            <li>
              <Check /> External AI disabled by design
            </li>
          </ul>
        </section>
      </div>
    </>
  );
}
