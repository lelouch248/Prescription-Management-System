import { FormEvent, ReactNode, useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronRight,
  FileUp,
  LockKeyhole,
  Mic,
  Plus,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { api, jsonBody, setCsrf, toLocalInput } from "./api";
import { AIStatus, AnyRecord } from "./types";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand ${compact ? "brand-compact" : ""}`}>
      <span className="brand-mark">H</span>
      <span>
        <strong>HealthVault</strong>
        <small>LOCAL</small>
      </span>
    </div>
  );
}

export function Button({
  children,
  variant = "primary",
  icon,
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  icon?: ReactNode;
}) {
  return (
    <button className={`button button-${variant} ${className}`} {...props}>
      {icon}
      {children}
    </button>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon}
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "good" | "warning" | "critical" | "info";
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) =>
      event.key === "Escape" && onClose();
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div
        className={`modal ${wide ? "modal-wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <header>
          <h2 id="modal-title">{title}</h2>
          <button className="icon-button" onClick={onClose} aria-label="Close">
            <X size={20} />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}

export function SetupScreen({
  ai,
  onReady,
}: {
  ai: AIStatus;
  onReady: () => void;
}) {
  const [step, setStep] = useState(0);
  const [password, setPassword] = useState("");
  const [profileName, setProfileName] = useState("");
  const [destination, setDestination] = useState("");
  const [backupPassword, setBackupPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const steps = [
    "Welcome",
    "Create vault",
    "Data location",
    "Backup",
    "Local AI",
    "Ready",
  ];

  async function createVault(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<any>(
        "/setup",
        jsonBody({ password, profile_name: profileName }),
      );
      setCsrf(result.csrf_token);
      setStep(2);
    } catch (caught: any) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  async function configureBackup(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (destination)
        await api(
          "/backups/destinations",
          jsonBody({
            name: "Primary backup",
            path: destination,
            role: "primary",
            enabled: true,
          }),
        );
      if (backupPassword) {
        const form = new FormData();
        form.set("app_password", password);
        form.set("backup_password", backupPassword);
        await api("/backups/credential", { method: "POST", body: form });
        await api(
          "/backups/create",
          jsonBody({ password: backupPassword, kind: "manual" }),
        );
      }
      setStep(4);
    } catch (caught: any) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page setup-page">
      <section className="setup-shell">
        <div className="setup-aside">
          <Brand />
          <div className="setup-progress">
            {steps.map((label, index) => (
              <div
                className={`setup-step ${index === step ? "active" : ""} ${index < step ? "done" : ""}`}
                key={label}
              >
                <span>{index < step ? <Check size={15} /> : index + 1}</span>
                {label}
              </div>
            ))}
          </div>
          <p className="privacy-note">
            <ShieldCheck size={17} /> Nothing is sent to a cloud service.
          </p>
        </div>
        <div className="setup-content">
          {error && (
            <div className="alert alert-critical">
              <AlertTriangle size={18} />
              {error}
            </div>
          )}
          {step === 0 && (
            <div className="setup-panel">
              <p className="eyebrow">WELCOME</p>
              <h1>
                Your family’s medical history,
                <br />
                kept in your hands.
              </h1>
              <p>
                HealthVault Local keeps structured records and original
                documents on this computer. Backup is part of setup because
                recovery matters more than convenience.
              </p>
              <Button onClick={() => setStep(1)}>
                Create my local vault <ChevronRight size={18} />
              </Button>
            </div>
          )}
          {step === 1 && (
            <form className="setup-panel form-stack" onSubmit={createVault}>
              <p className="eyebrow">STEP 1 OF 5</p>
              <h1>Create and lock your vault</h1>
              <label>
                Your first health profile
                <input
                  required
                  maxLength={200}
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                  placeholder="Your name"
                  autoFocus
                />
              </label>
              <label>
                Application password
                <input
                  required
                  type="password"
                  minLength={10}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 10 characters"
                />
              </label>
              <p className="field-help">
                This password cannot be recovered. Keep a secure offline copy.
              </p>
              <Button disabled={busy}>
                {busy ? "Creating…" : "Create vault"}
              </Button>
            </form>
          )}
          {step === 2 && (
            <div className="setup-panel">
              <p className="eyebrow">STEP 2 OF 5</p>
              <h1>Your data stays separate from the application</h1>
              <div className="data-location-card">
                <ShieldCheck />
                <div>
                  <strong>Local data directory</strong>
                  <code>data/</code>
                  <p>
                    Database, originals, voice notes, exports, and recovery
                    files live here and are excluded from Git.
                  </p>
                </div>
              </div>
              <p>
                You can change this location before startup with{" "}
                <code>HEALTHVAULT_DATA_DIR</code>. For long-term safety, use
                normal filesystem backup destinations rather than a
                vendor-specific integration.
              </p>
              <Button onClick={() => setStep(3)}>
                Configure backup <ChevronRight size={18} />
              </Button>
            </div>
          )}
          {step === 3 && (
            <form className="setup-panel form-stack" onSubmit={configureBackup}>
              <p className="eyebrow">STEP 3 OF 5 · IMPORTANT</p>
              <h1>Make the first recoverable copy</h1>
              <label>
                Backup folder path
                <input
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  placeholder="D:\HealthVault Backups or a synced folder"
                />
              </label>
              <label>
                Backup password
                <input
                  type="password"
                  minLength={12}
                  value={backupPassword}
                  onChange={(e) => setBackupPassword(e.target.value)}
                  placeholder="At least 12 characters"
                />
              </label>
              <p className="field-help">
                Backups use AES-256-GCM. The password is not stored inside the
                archive and cannot be recovered. Add a second destination later.
              </p>
              <Button
                disabled={busy || !destination || backupPassword.length < 12}
              >
                {busy
                  ? "Creating encrypted backup…"
                  : "Save and test first backup"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setStep(4)}>
                I understand the risk — configure later
              </Button>
            </form>
          )}
          {step === 4 && (
            <div className="setup-panel">
              <p className="eyebrow">STEP 4 OF 5 · OPTIONAL</p>
              <h1>Local AI is optional by design</h1>
              <div
                className={`capability-card ${ai.available ? "available" : ""}`}
              >
                <Sparkles />
                <div>
                  <strong>
                    {ai.available
                      ? `Ready · ${ai.selected_model || "Ollama"}`
                      : "Not installed or not running"}
                  </strong>
                  <p>
                    {ai.available
                      ? "Record-grounded organization and extraction are available."
                      : "Install Ollama later. Records, search, backup, OCR, and reminders continue to work without it."}
                  </p>
                </div>
                <Badge tone={ai.available ? "good" : "neutral"}>
                  {ai.available ? "Available" : "Optional"}
                </Badge>
              </div>
              <Button onClick={() => setStep(5)}>
                Continue <ChevronRight size={18} />
              </Button>
            </div>
          )}
          {step === 5 && (
            <div className="setup-panel">
              <div className="success-orb">
                <Check />
              </div>
              <p className="eyebrow">READY</p>
              <h1>Your local vault is ready.</h1>
              <p>
                Add records manually or start with an existing prescription,
                document, appointment, voice note, or health note. Anything
                extracted by OCR or AI stays unverified until you confirm it.
              </p>
              <Button onClick={onReady}>Open HealthVault</Button>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

export function LockScreen({ onUnlock }: { onUnlock: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<any>("/auth/login", jsonBody({ password }));
      setCsrf(result.csrf_token);
      onUnlock();
    } catch (caught: any) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-page">
      <section className="lock-card">
        <Brand />
        <div className="lock-icon">
          <LockKeyhole />
        </div>
        <p className="eyebrow">VAULT LOCKED</p>
        <h1>Welcome back</h1>
        <p>Your records remain on this computer.</p>
        <form onSubmit={submit}>
          <label>
            Application password
            <input
              autoFocus
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && <div className="form-error">{error}</div>}
          <Button disabled={busy} className="full-width">
            {busy ? "Unlocking…" : "Unlock vault"}
          </Button>
        </form>
        <small>Sessions lock automatically after inactivity.</small>
      </section>
    </main>
  );
}

const ADD_TYPES = [
  "Health note",
  "Prescription",
  "Doctor visit",
  "Medicine",
  "Appointment",
  "Document",
  "Voice note",
  "Measurement",
  "Family profile",
] as const;
export type AddType = (typeof ADD_TYPES)[number];

export function QuickAdd({
  initialType,
  onClose,
  onCreated,
}: {
  initialType?: AddType;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [type, setType] = useState<AddType | undefined>(initialType);
  const [profiles, setProfiles] = useState<AnyRecord[]>([]);
  const [providers, setProviders] = useState<AnyRecord[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([
      api<AnyRecord[]>("/profiles"),
      api<AnyRecord[]>("/providers"),
    ]).then(([p, d]) => {
      setProfiles(p);
      setProviders(d);
    });
  }, []);
  if (!type)
    return (
      <Modal title="Add to HealthVault" onClose={onClose}>
        <div className="add-grid">
          {ADD_TYPES.map((item) => (
            <button
              key={item}
              onClick={() => setType(item)}
              className="add-choice"
            >
              {item === "Voice note" ? (
                <Mic />
              ) : item === "Document" ? (
                <FileUp />
              ) : (
                <Plus />
              )}
              <span>{item}</span>
              <ChevronRight size={18} />
            </button>
          ))}
        </div>
      </Modal>
    );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const value = (name: string) => String(form.get(name) || "");
    try {
      const profileId = value("profile_id");
      if (type === "Health note")
        await api(
          "/notes",
          jsonBody({
            profile_id: profileId,
            title: value("title") || null,
            content: value("content"),
            occurred_at: new Date().toISOString(),
          }),
        );
      if (type === "Family profile")
        await api(
          "/profiles",
          jsonBody({
            name: value("name"),
            date_of_birth: value("date_of_birth") || null,
            blood_group: value("blood_group") || null,
            allergies: value("allergies") || null,
            chronic_conditions: value("chronic_conditions") || null,
            emergency_information: null,
            notes: null,
            color: value("color") || "#27786d",
          }),
        );
      if (type === "Doctor visit")
        await api(
          "/visits",
          jsonBody({
            profile_id: profileId,
            provider_id: value("provider_id") || null,
            visit_date: new Date(value("visit_date")).toISOString(),
            reason: value("reason") || null,
            symptoms: value("symptoms") || null,
            clinical_impression: value("clinical_impression") || null,
            diagnosis_text: value("diagnosis_text") || null,
            follow_up_date: value("follow_up_date")
              ? new Date(value("follow_up_date")).toISOString()
              : null,
            summary: value("summary") || null,
            notes: value("notes") || null,
            appointment_id: null,
          }),
        );
      if (type === "Prescription")
        await api(
          "/prescriptions",
          jsonBody({
            profile_id: profileId,
            provider_id: value("provider_id") || null,
            visit_id: null,
            document_id: null,
            prescription_date: value("prescription_date"),
            status: "verified",
            diagnosis_text: value("diagnosis_text") || null,
            notes: value("notes") || null,
          }),
        );
      if (type === "Appointment")
        await api(
          "/appointments",
          jsonBody({
            profile_id: profileId,
            provider_id: value("provider_id") || null,
            starts_at: new Date(value("starts_at")).toISOString(),
            purpose: value("purpose") || null,
            location: value("location") || null,
            preparation_notes: value("preparation_notes") || null,
            documents_to_carry: value("documents_to_carry") || null,
            reminder_minutes: Number(value("reminder_minutes") || 1440),
            status: "scheduled",
            post_visit_notes: null,
          }),
        );
      if (type === "Measurement")
        await api(
          "/observations",
          jsonBody({
            profile_id: profileId,
            observed_at: new Date(value("observed_at")).toISOString(),
            kind: value("kind"),
            value: Number(value("measurement_value")),
            unit: value("unit"),
            secondary_value: value("secondary_value")
              ? Number(value("secondary_value"))
              : null,
            notes: value("notes") || null,
          }),
        );
      if (type === "Medicine") {
        const medication: any = await api(
          "/medications",
          jsonBody({
            generic_name: value("generic_name") || null,
            brand_name: value("brand_name") || null,
            strength: value("strength") || null,
            form: value("form") || null,
            manufacturer: null,
            notes: null,
          }),
        );
        await api(
          "/prescribed-medications",
          jsonBody({
            prescription_id: null,
            profile_id: profileId,
            medication_id: medication.id,
            dosage: value("dosage") || null,
            frequency: value("frequency") || null,
            timing: value("timing") || null,
            duration: value("duration") || null,
            start_date: value("start_date") || null,
            end_date: value("end_date") || null,
            food_relation: value("food_relation") || null,
            instructions: value("instructions") || null,
            as_needed: form.get("as_needed") === "on",
            verification_status: "verified",
            tracking_status: "active",
            schedule: {
              times: value("times")
                .split(",")
                .map((v) => v.trim())
                .filter(Boolean),
            },
          }),
        );
      }
      if (type === "Document") {
        const upload = new FormData();
        upload.set("file", form.get("file")!);
        upload.set("profile_id", profileId);
        upload.set("category", value("category"));
        upload.set("document_date", value("document_date"));
        upload.set("title", value("title"));
        await api("/documents", { method: "POST", body: upload });
      }
      if (type === "Voice note") {
        const upload = new FormData();
        upload.set("file", form.get("file")!);
        upload.set("profile_id", profileId);
        upload.set("occurred_at", new Date().toISOString());
        await api("/voice-notes", { method: "POST", body: upload });
      }
      onCreated();
      onClose();
    } catch (caught: any) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  const profile = type !== "Family profile" && (
    <label>
      Family member
      <select name="profile_id" required defaultValue="">
        <option value="" disabled>
          Select profile
        </option>
        {profiles.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </select>
    </label>
  );
  const provider = (
    <label>
      Doctor / provider
      <select name="provider_id" defaultValue="">
        <option value="">Not linked</option>
        {providers.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
            {item.specialty ? ` · ${item.specialty}` : ""}
          </option>
        ))}
      </select>
    </label>
  );
  return (
    <Modal title={`Add ${type.toLowerCase()}`} onClose={onClose}>
      <form className="form-stack modal-form" onSubmit={submit}>
        {profile}
        {type === "Health note" && (
          <>
            <label>
              Short title
              <input name="title" placeholder="Optional" />
            </label>
            <label>
              Note
              <textarea
                name="content"
                required
                autoFocus
                placeholder="Fever started today…"
              />
            </label>
          </>
        )}
        {type === "Family profile" && (
          <>
            <label>
              Name
              <input name="name" required autoFocus />
            </label>
            <div className="form-row">
              <label>
                Date of birth
                <input name="date_of_birth" type="date" />
              </label>
              <label>
                Blood group
                <input name="blood_group" placeholder="e.g. O+" />
              </label>
            </div>
            <label>
              Known allergies
              <textarea name="allergies" />
            </label>
            <label>
              Chronic conditions
              <textarea name="chronic_conditions" />
            </label>
            <label>
              Profile color
              <input name="color" type="color" defaultValue="#27786d" />
            </label>
          </>
        )}
        {type === "Doctor visit" && (
          <>
            {provider}
            <label>
              Visit date & time
              <input
                name="visit_date"
                type="datetime-local"
                defaultValue={toLocalInput()}
                required
              />
            </label>
            <label>
              Reason for visit
              <input name="reason" required />
            </label>
            <label>
              Symptoms
              <textarea name="symptoms" />
            </label>
            <label>
              Diagnosis / impression as written
              <textarea name="diagnosis_text" />
            </label>
            <label>
              Follow-up date
              <input name="follow_up_date" type="datetime-local" />
            </label>
            <label>
              Summary and notes
              <textarea name="summary" />
            </label>
          </>
        )}
        {type === "Prescription" && (
          <>
            {provider}
            <label>
              Prescription date
              <input
                name="prescription_date"
                type="date"
                defaultValue={new Date().toISOString().slice(0, 10)}
                required
              />
            </label>
            <label>
              Diagnosis as written
              <textarea name="diagnosis_text" />
            </label>
            <label>
              Notes
              <textarea name="notes" />
            </label>
            <div className="safety-inline">
              <ShieldCheck size={17} /> Manual entries are marked verified by
              you. Link original evidence from Documents.
            </div>
          </>
        )}
        {type === "Appointment" && (
          <>
            {provider}
            <label>
              Date & time
              <input
                name="starts_at"
                type="datetime-local"
                defaultValue={toLocalInput(new Date(Date.now() + 86400000))}
                required
              />
            </label>
            <label>
              Purpose
              <input name="purpose" required />
            </label>
            <label>
              Location
              <input name="location" />
            </label>
            <label>
              Preparation notes
              <textarea name="preparation_notes" />
            </label>
            <label>
              Documents to carry
              <textarea name="documents_to_carry" />
            </label>
            <label>
              Remind me (minutes before)
              <input
                name="reminder_minutes"
                type="number"
                min="0"
                defaultValue="1440"
              />
            </label>
          </>
        )}
        {type === "Measurement" && (
          <>
            <label>
              Measured at
              <input
                name="observed_at"
                type="datetime-local"
                defaultValue={toLocalInput()}
                required
              />
            </label>
            <div className="form-row">
              <label>
                Measurement
                <select name="kind">
                  <option>Weight</option>
                  <option>Blood pressure</option>
                  <option>Blood glucose</option>
                  <option>Temperature</option>
                  <option>Pulse</option>
                  <option>SpO2</option>
                  <option>Other</option>
                </select>
              </label>
              <label>
                Value
                <input
                  name="measurement_value"
                  type="number"
                  step="any"
                  required
                />
              </label>
            </div>
            <div className="form-row">
              <label>
                Second value
                <input
                  name="secondary_value"
                  type="number"
                  step="any"
                  placeholder="Diastolic"
                />
              </label>
              <label>
                Unit
                <input name="unit" required placeholder="kg, mmHg, mg/dL…" />
              </label>
            </div>
            <label>
              Notes
              <textarea name="notes" />
            </label>
          </>
        )}
        {type === "Medicine" && (
          <>
            <div className="form-row">
              <label>
                Generic name
                <input name="generic_name" />
              </label>
              <label>
                Brand name
                <input name="brand_name" />
              </label>
            </div>
            <div className="form-row">
              <label>
                Strength
                <input name="strength" placeholder="500 mg" />
              </label>
              <label>
                Form
                <input name="form" placeholder="Tablet" />
              </label>
            </div>
            <div className="form-row">
              <label>
                Dose
                <input name="dosage" placeholder="1 tablet" />
              </label>
              <label>
                Frequency
                <input name="frequency" placeholder="Twice daily" />
              </label>
            </div>
            <div className="form-row">
              <label>
                Start date
                <input name="start_date" type="date" />
              </label>
              <label>
                End date
                <input name="end_date" type="date" />
              </label>
            </div>
            <label>
              Times, comma-separated
              <input name="times" placeholder="08:00, 20:00" />
            </label>
            <label>
              Food timing
              <select name="food_relation">
                <option value="">Not recorded</option>
                <option>Before food</option>
                <option>After food</option>
                <option>With food</option>
                <option>Bedtime</option>
              </select>
            </label>
            <label>
              Instructions
              <textarea name="instructions" />
            </label>
            <label className="check-label">
              <input name="as_needed" type="checkbox" /> Take as needed
            </label>
          </>
        )}
        {type === "Document" && (
          <>
            <label>
              Original file
              <input
                name="file"
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.heic,.heif,application/pdf,image/*"
                capture="environment"
                required
              />
            </label>
            <div className="form-row">
              <label>
                Category
                <select name="category">
                  <option value="prescription">Prescription</option>
                  <option value="lab_report">Lab report</option>
                  <option value="scan">Scan</option>
                  <option value="discharge_summary">Discharge summary</option>
                  <option value="invoice">Invoice</option>
                  <option value="insurance">Insurance</option>
                  <option value="referral">Referral</option>
                  <option value="vaccination">Vaccination</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <label>
                Document date
                <input name="document_date" type="date" />
              </label>
            </div>
            <label>
              Title
              <input name="title" />
            </label>
            <div className="safety-inline">
              <ShieldCheck size={17} /> The original bytes are preserved.
              Derivatives and OCR are stored separately.
            </div>
          </>
        )}
        {type === "Voice note" && (
          <>
            <label>
              Record or choose audio
              <input
                name="file"
                type="file"
                accept="audio/*"
                capture
                required
              />
            </label>
            <div className="safety-inline">
              <Mic size={17} /> The original recording is stored locally.
              Transcription and extracted details require review.
            </div>
          </>
        )}
        {error && <div className="form-error">{error}</div>}
        <div className="modal-actions">
          <Button
            type="button"
            variant="ghost"
            onClick={() => setType(undefined)}
          >
            Back
          </Button>
          <Button disabled={busy}>
            {busy ? "Saving…" : `Save ${type.toLowerCase()}`}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
