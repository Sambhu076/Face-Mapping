import { useEffect, useState, useRef } from "react";
import { createPortal } from "react-dom";
import {
  createEvent,
  deleteAllPhotos,
  deleteEvent,
  deletePhoto,
  fetchAdminDashboard,
  fetchAdminEvent,
  fetchIndexingProgress,
  fetchPublicEvent,
  getSession,
  login,
  logout,
  searchPublicEvent,
  updateEvent,
  uploadEventPhotos,
  cancelTasks,
} from "./api";

function useAsync(loader, deps = []) {
  const [state, setState] = useState({ loading: true, error: "", data: null });

  useEffect(() => {
    let active = true;
    setState({ loading: true, error: "", data: null });
    loader()
      .then((data) => {
        if (active) {
          setState({ loading: false, error: "", data });
        }
      })
      .catch((error) => {
        if (active) {
          setState({ loading: false, error: error.message, data: null });
        }
      });
    return () => {
      active = false;
    };
  }, deps);

  return state;
}

function Header({ session, onLogout }) {
  return (
    <header className="app-hero">
      <div>
        <p className="kicker">Hola Amigos</p>
        <h1>Studio Face Finder</h1>
        <p className="subtitle">
          Hastala Vista Amigos
        </p>
      </div>
      <nav className="nav-row">
        <a href="/">Home</a>
        {session?.isStaff ? <a href="/dashboard/admin">Admin Dashboard</a> : null}
        {session?.authenticated ? (
          <button className="ghost-button" onClick={onLogout}>Logout</button>
        ) : (
          <a href="/login">Admin Login</a>
        )}
      </nav>
    </header>
  );
}

function Layout({ session, onLogout, children }) {
  return (
    <div className="app-shell">
      <Header session={session} onLogout={onLogout} />
      {children}
    </div>
  );
}

function ConfirmModal({ open, title, description, confirmLabel, busy, onCancel, onConfirm }) {
  if (!open) {
    return null;
  }

  return createPortal(
    <div className="confirm-modal">
      <div className="confirm-modal__backdrop" onClick={busy ? undefined : onCancel} />
      <div className="confirm-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title">
        <p className="kicker">Please Confirm</p>
        <h3 id="confirm-modal-title">{title}</h3>
        <p className="copy">{description}</p>
        <div className="confirm-modal__actions">
          <button className="ghost-button" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className="danger-button" onClick={onConfirm} disabled={busy}>
            {busy ? "Deleting..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

function BinIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9 3h6l1 2h4v2H4V5h4l1-2Zm-1 6h2v8H8V9Zm6 0h2v8h-2V9ZM6 9h2v10h8V9h2v12H6V9Z" fill="currentColor" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M11 4h2v8.17l2.59-2.58L17 11l-5 5-5-5 1.41-1.41L11 12.17V4Zm-6 14h14v2H5v-2Z" fill="currentColor" />
    </svg>
  );
}

function cssVars(styleText) {
  return (styleText || "")
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean)
    .reduce((accumulator, entry) => {
      const [key, value] = entry.split(":");
      if (key && value) {
        accumulator[key.trim()] = value.trim();
      }
      return accumulator;
    }, {});
}

function LandingPage() {
  return (
    <section className="panel hero-panel">
      <div>
        <p className="kicker">QR-Based Event Access</p>
        <h2>Open event dashboards, upload a face image, and retrieve matching photos faster.</h2>
        <p className="copy">
          Guests can use the event link directly. Studio admins can manage events, indexing, uploads, and archive cleanup from the dashboard.
        </p>
      </div>
      <div className="card-grid">
        <article className="mini-card">
          <h3>Admin Workflow</h3>
          <p>Create events, upload archives, inspect detected faces, and share QR access.</p>
          <a className="primary-link" href="/login">Go to Admin Login</a>
        </article>
        <article className="mini-card">
          <h3>Guest Workflow</h3>
          <p>Use the event-specific link from the QR code, upload a face image, and download matched photos.</p>
        </article>
      </div>
    </section>
  );
}

function LoginPage({ onAuthenticated }) {
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const session = await login(form);
      onAuthenticated(session);
      window.location.href = session.isStaff ? "/dashboard/admin/" : "/";
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel narrow-panel">
      <p className="kicker">Admin Access</p>
      <h2>Sign in to manage events and archive indexing.</h2>
      <form className="stack-form" onSubmit={handleSubmit}>
        <label>
          Username
          <input
            value={form.username}
            onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={form.password}
            onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
          />
        </label>
        <button disabled={loading}>{loading ? "Signing In..." : "Sign In"}</button>
        {error ? <p className="error-text">{error}</p> : null}
      </form>
    </section>
  );
}

function UserDashboardPage() {
  return (
    <section className="panel hero-panel">
      <div>
        <p className="kicker">User Dashboard</p>
        <h2>Open your event-specific dashboard to search for matched photos.</h2>
        <p className="copy">
          User access is event-specific. Scan the QR code or open the event link shared by the studio, then upload a clear face image to retrieve your matched photos.
        </p>
      </div>
      <div className="card-grid">
        <article className="mini-card">
          <h3>Scan the Event QR</h3>
          <p>Each QR code opens one event-only dashboard, so your search stays limited to that archive.</p>
        </article>
        <article className="mini-card">
          <h3>Use the Shared Event Link</h3>
          <p>If the studio sent you a direct event URL, open it to upload your face image and view matches.</p>
        </article>
      </div>
    </section>
  );
}

function AdminDashboardPage() {
  const { loading, error, data } = useAsync(fetchAdminDashboard, []);
  const [form, setForm] = useState({ name: "", eventDate: "" });
  const [busy, setBusy] = useState(false);
  const canCreateEvent = form.name.trim() !== "" && form.eventDate.trim() !== "";

  if (loading) return <section className="panel">Loading admin dashboard...</section>;
  if (error) return <section className="panel error-text">{error}</section>;

  async function handleCreate(event) {
    event.preventDefault();
    if (!canCreateEvent) {
      return;
    }
    setBusy(true);
    try {
      await createEvent(form);
      window.location.reload();
    } catch (err) {
      alert(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-grid">
      <section className="panel">
        <p className="kicker">Studio Overview</p>
        <h2>Manage events, archive stats, and admin workflows.</h2>
        <div className="stats-grid">
          <div className="stat-box"><strong>{data.events.length}</strong><span>Events</span></div>
          <div className="stat-box"><strong>{data.photoCount}</strong><span>Photos</span></div>
          <div className="stat-box"><strong>{data.faceCount}</strong><span>Faces</span></div>
        </div>
      </section>
      <section className="panel">
        <p className="kicker">Create Event</p>
        <form className="stack-form" onSubmit={handleCreate}>
          <label>
            Event Name
            <input required value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} />
          </label>
          <label>
            Event Date
            <input required type="date" value={form.eventDate} onChange={(event) => setForm((current) => ({ ...current, eventDate: event.target.value }))} />
          </label>
          <button disabled={busy || !canCreateEvent}>{busy ? "Creating..." : "Create Event"}</button>
        </form>
      </section>
      <section className="panel full-span">
        <p className="kicker">Events</p>
        <div className="list-grid">
          {data.events.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
      </section>
    </div>
  );
}

function EventCard({ event }) {
  const [edit, setEdit] = useState({ name: event.name, eventDate: event.eventDate || "" });
  const [saving, setSaving] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const hasChanges =
    edit.name.trim() !== (event.name || "").trim() ||
    (edit.eventDate || "") !== (event.eventDate || "");

  async function handleSave(submitEvent) {
    submitEvent.preventDefault();
    if (!hasChanges) return;
    setSaving(true);
    await updateEvent(event.id, edit);
    window.location.reload();
  }

  async function handleDelete() {
    setDeleting(true);
    await deleteEvent(event.id);
    window.location.reload();
  }

  return (
    <article className="mini-card">
      <h3>{event.name}</h3>
      <p>{event.photoCount} photos · {event.faceCount} faces</p>
      <div className="action-stack" style={{ marginBottom: "1rem" }}>
        <a className="primary-link action-link" href={`/dashboard/admin/events/${event.id}`}>Admin Dashboard</a>
        <a className="primary-link action-link" href={`/events/${event.slug || "event"}/${event.accessKey}/`}>Public Gallery</a>
      </div>
      <form className="stack-form compact-stack" onSubmit={handleSave}>
        <label>
          Rename Event
          <input value={edit.name} onChange={(event) => setEdit((current) => ({ ...current, name: event.target.value }))} />
        </label>
        <label>
          Event Date
          <input type="date" value={edit.eventDate} onChange={(event) => setEdit((current) => ({ ...current, eventDate: event.target.value }))} />
        </label>
        <button className="ghost-button" type="submit" disabled={!hasChanges || saving}>
          {saving ? "Saving..." : "Save Changes"}
        </button>
      </form>
      <button className="danger-button" onClick={() => setShowDeleteConfirm(true)}>Delete Event</button>
      <ConfirmModal
        open={showDeleteConfirm}
        title={`Delete ${event.name}?`}
        description="This will permanently remove the event and its uploaded archive. This action cannot be undone."
        confirmLabel="Delete Event"
        busy={deleting}
        onCancel={() => setShowDeleteConfirm(false)}
        onConfirm={handleDelete}
      />
    </article>
  );
}

function AdminEventPage({ eventId }) {
  const [reloadTrigger, setReloadTrigger] = useState(0);
  const { loading, error, data } = useAsync(() => fetchAdminEvent(eventId), [eventId, reloadTrigger]);
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [showArchive, setShowArchive] = useState(false);
  const [showFaces, setShowFaces] = useState(false);
  const [progress, setProgress] = useState({ total: 0, completed: 0, processing: false });
  const [uploadPercent, setUploadPercent] = useState(0);
  const [localPhotos, setLocalPhotos] = useState([]);
  const [uploadIndex, setUploadIndex] = useState(0);
  const xhrRef = useRef(null);

  const [photoToDelete, setPhotoToDelete] = useState(null);
  const [showDeleteAllConfirm, setShowDeleteAllConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [localPhotoCount, setLocalPhotoCount] = useState(0);
  const [localFaceCount, setLocalFaceCount] = useState(0);
  const [pendingTaskIds, setPendingTaskIds] = useState([]);

  useEffect(() => {
    if (data) {
      setLocalPhotos(data.photos || []);
      setLocalPhotoCount(data.photoCount || 0);
      setLocalFaceCount(data.faceCount || 0);
    }
  }, [data]);

  useEffect(() => {
    let interval;
    if (progress.processing || busy) {
      interval = setInterval(async () => {
        try {
          const res = await fetchIndexingProgress(eventId);
          if (res.ok) {
            setProgress((prevProgress) => {
              if (prevProgress.processing && !res.progress.processing && !busy) {
                setReloadTrigger((t) => t + 1);
              }
              return res.progress;
            });
          }
        } catch (err) {
          console.error("Failed to fetch progress", err);
        }
      }, 2500);
    }
    return () => clearInterval(interval);
  }, [eventId, busy]);

  useEffect(() => {
    fetchIndexingProgress(eventId).then(res => {
      if (res.ok) setProgress(res.progress);
    }).catch(() => { });
  }, [eventId]);

  if (loading) return <section className="panel">Loading event dashboard...</section>;
  if (error) return <section className="panel error-text">{error}</section>;

  async function handleUpload(event) {
    event.preventDefault();
    if (!files.length) return;
    setBusy(true);
    setUploadPercent(0);
    setUploadIndex(0);
    setPendingTaskIds([]);

    try {
      for (let i = 0; i < files.length; i++) {
        setUploadIndex(i + 1);
        const res = await uploadEventPhotos(
          eventId,
          [files[i]],
          (percent) => {
            const overall = Math.round(((i + percent / 100) / files.length) * 100);
            setUploadPercent(overall);
          },
          { onXhr: (xhr) => { xhrRef.current = xhr; } }
        );

        if (res.ok && res.photos) {
          setLocalPhotos((prev) => [...res.photos, ...prev]);
          setLocalPhotoCount(prev => prev + res.photos.length);
          const addedFaces = res.photos.reduce((sum, p) => sum + (p.faceCount || 0), 0);
          setLocalFaceCount(prev => prev + addedFaces);
          setShowArchive(true);
          if (res.taskId) {
            setPendingTaskIds(prev => [...prev, res.taskId]);
          }
        }
      }
      setFiles([]);
      setPendingTaskIds([]);
      const res = await fetchIndexingProgress(eventId);
      if (res.ok) setProgress(res.progress);
    } catch (err) {
      if (err.message !== "Upload cancelled.") {
        alert(err.message);
      }
    } finally {
      setBusy(false);
      xhrRef.current = null;
      setTimeout(() => {
        setUploadPercent(0);
        setUploadIndex(0);
      }, 2000);
    }
  }

  function handleCancelUpload() {
    if (xhrRef.current) {
      xhrRef.current.abort();
    }
    if (pendingTaskIds.length > 0) {
      cancelTasks(eventId, pendingTaskIds);
    }
    setPendingTaskIds([]);
  }

  async function confirmDeletePhoto() {
    if (!photoToDelete) return;
    setDeleting(true);
    try {
      await deletePhoto(eventId, photoToDelete.id);
      setLocalPhotos(prev => prev.filter(p => p.id !== photoToDelete.id));
      setLocalPhotoCount(prev => prev - 1);
      setLocalFaceCount(prev => prev - (photoToDelete.faceCount || 0));
      setPhotoToDelete(null);
    } catch (err) {
      alert(err.message);
    } finally {
      setDeleting(false);
    }
  }

  async function confirmDeleteAll() {
    setDeleting(true);
    try {
      await deleteAllPhotos(eventId);
      setLocalPhotos([]);
      setLocalPhotoCount(0);
      setLocalFaceCount(0);
      setShowDeleteAllConfirm(false);
    } catch (err) {
      alert(err.message);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="page-grid">
      <section className="panel">
        <p className="kicker">Event Dashboard</p>
        <h2>{data.event.name}</h2>
        <div className="stats-grid">
          <div className="stat-box"><strong>{localPhotoCount}</strong><span>Photos</span></div>
          <div className="stat-box">
            <strong>{localFaceCount}</strong><span>Faces</span>
            {localFaceCount > 0 && (
              <button className={showFaces ? "ghost-button" : "primary-link"} style={{ marginTop: "0.8rem", width: "100%", padding: "0.5rem", fontSize: "0.9rem" }} onClick={() => setShowFaces(!showFaces)}>
                {showFaces ? "Hide Faces" : "View Faces"}
              </button>
            )}
          </div>
        </div>
        {showFaces && data.uniqueFaces?.length > 0 && (
          <div className="unique-faces-section" style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid var(--border-color)" }}>
            <h3>Recognized Persons</h3>
            <div className="face-preview-grid">
              {data.uniqueFaces.map((face) => (
                <article key={face.id} className="face-preview-tile">
                  <div className="face-preview-thumb" style={cssVars(face.preview_style)}>
                    <img src={face.imageUrl} alt={`Person ${face.person_id}`} />
                  </div>
                  <div className="face-preview-copy">
                    {face.person_id && <span>Person: <span title={face.person_id}>{face.person_id.substring(0, 8)}...</span></span>}
                  </div>
                </article>
              ))}
            </div>
          </div>
        )}
      </section>
      <section className="panel">
        <p className="kicker">QR Access</p>
        <p className="copy" style={{ wordBreak: "break-all" }}>
          Share Link: <strong>{`${window.location.origin}/events/${data.event.slug}/${data.event.accessKey}/`}</strong>
        </p>
        <div className="card-grid">
          <img className="qr-image" src={data.qrImageUrl} alt="Event QR" />
          <a className="primary-link" href={data.qrDownloadUrl}>Download QR</a>
        </div>
      </section>
      <section className="panel">
        <p className="kicker">Bulk Upload</p>
        <form className="stack-form" onSubmit={handleUpload}>
          <label>
            Select Photos
            <input type="file" multiple onChange={(event) => setFiles(Array.from(event.target.files || []))} />
          </label>
          <button disabled={busy || progress.processing}>{busy ? `Uploading ${uploadIndex}/${files.length}...` : progress.processing ? "Indexing In Progress..." : "Upload Photos"}</button>
          {busy && (
            <button type="button" className="danger-button ghost-button" onClick={handleCancelUpload}>
              Cancel Upload
            </button>
          )}
        </form>

        {busy && uploadPercent > 0 && (
          <div className="upload-progress" style={{ marginTop: "1.5rem" }}>
            <div className="upload-progress-header" style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
              <strong>Upload Progress ({uploadIndex} / {files.length})</strong>
              <span>{uploadPercent}%</span>
            </div>
            <div className="upload-progress-track" style={{ background: "rgba(255,255,255,0.1)", borderRadius: "999px", height: "8px", overflow: "hidden" }}>
              <div
                className="upload-progress-bar"
                style={{
                  background: "linear-gradient(135deg, #3b82f6, #60a5fa)",
                  height: "100%",
                  width: `${uploadPercent}%`,
                  transition: "width 0.2s ease"
                }}
              />
            </div>
          </div>
        )}

        {progress.processing && (
          <div className="upload-progress" style={{ marginTop: "1.5rem" }}>
            <div className="upload-progress-header" style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
              <strong>AI Face Indexing Progress</strong>
              <span>{progress.completed} / {progress.total} Photos</span>
            </div>
            <div className="upload-progress-track" style={{ background: "rgba(255,255,255,0.1)", borderRadius: "999px", height: "8px", overflow: "hidden" }}>
              <div
                className="upload-progress-bar"
                style={{
                  background: "linear-gradient(135deg, #2dd4bf, #10b981)",
                  height: "100%",
                  width: `${progress.total > 0 ? (progress.completed / progress.total) * 100 : 0}%`,
                  transition: "width 0.3s ease"
                }}
              />
            </div>
            <p className="kicker" style={{ marginTop: "0.5rem", fontSize: "0.7rem" }}>GPU Acceleration Enabled</p>
          </div>
        )}
      </section>
      <section className="panel full-span">
        <div className="section-row">
          <div>
            <p className="kicker">Uploaded Archive</p>
            <h3>{localPhotos.length} uploaded photos</h3>
          </div>
          <div className="action-stack">
            <button className="ghost-button" onClick={() => setShowArchive((current) => !current)}>
              {showArchive ? "Hide Uploaded Photos" : "View Uploaded Photos"}
            </button>
            <button className="danger-button" onClick={() => setShowDeleteAllConfirm(true)}>Delete All Photos</button>
          </div>
        </div>
        <p className="copy">The uploaded archive is displayed as photos are successfully transferred.</p>

        <ConfirmModal
          open={showDeleteAllConfirm}
          title="Delete All Photos?"
          description="This will permanently remove all photos in this event archive. This action cannot be undone."
          confirmLabel="Delete All"
          busy={deleting}
          onCancel={() => setShowDeleteAllConfirm(false)}
          onConfirm={confirmDeleteAll}
        />

        <ConfirmModal
          open={!!photoToDelete}
          title={`Delete ${photoToDelete?.title}?`}
          description="This will permanently remove this photo from the event archive."
          confirmLabel="Delete Photo"
          busy={deleting}
          onCancel={() => setPhotoToDelete(null)}
          onConfirm={confirmDeletePhoto}
        />

        {showArchive ? (
          <div className="archive-dropdown">
            <div className="archive-dropdown__header">
              <div>
                <p className="kicker">Uploaded Photos</p>
                <h3>{data.event.name}</h3>
              </div>
            </div>
            <div className="card-grid">
              {localPhotos.map((photo) => (
                <article key={photo.id} className="mini-card">
                  <div className="image-action-card">
                    <img className="card-image" src={photo.imageUrl} alt={photo.title} />
                    <div className="image-action-overlay">
                      <a
                        className="image-icon-button"
                        href={`/downloads/photo/${photo.id}/`}
                        aria-label={`Download ${photo.title}`}
                        title="Download photo"
                      >
                        <DownloadIcon />
                      </a>
                      <button
                        className="image-icon-button image-icon-button--danger"
                        onClick={() => setPhotoToDelete(photo)}
                        aria-label={`Delete ${photo.title}`}
                        title="Delete photo"
                      >
                        <BinIcon />
                      </button>
                    </div>
                  </div>
                  <h3>{photo.title}</h3>
                  <p>{photo.faceCount} indexed faces</p>
                  <details>
                    <summary>Recognized Faces</summary>
                    <div className="face-preview-grid">
                      {(photo.faces || []).map((face) => (
                        <article key={face.id} className="face-preview-tile">
                          <div className="face-preview-thumb" style={cssVars(face.preview_style)}>
                            <img src={photo.imageUrl} alt={`Face ${face.face_index} from ${photo.title}`} />
                          </div>
                          <div className="face-preview-copy">
                            <strong>Face {face.face_index}</strong>
                            {face.person_id && <span>Person: <span title={face.person_id}>{face.person_id.substring(0, 8)}...</span></span>}
                            <span>Confidence {Number(face.detection_score).toFixed(3)}</span>
                          </div>
                        </article>
                      ))}
                    </div>
                  </details>
                </article>
              ))}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function PublicEventPage({ slug, accessKey }) {
  const { loading, error, data } = useAsync(() => fetchPublicEvent(slug, accessKey), [slug, accessKey]);
  const [form, setForm] = useState({ username: "", file: null });
  const [busy, setBusy] = useState(false);
  const [matches, setMatches] = useState(null);

  useEffect(() => {
    if (data?.matches) {
      setMatches(data.matches);
    }
    if (data?.searchUsername) {
      setForm((current) => ({ ...current, username: data.searchUsername }));
    }
  }, [data]);

  if (loading) return <section className="panel">Loading event access...</section>;
  if (error) return <section className="panel error-text">{error}</section>;

  async function handleSearch(event) {
    event.preventDefault();
    if (!form.file) return;
    setBusy(true);
    try {
      const response = await searchPublicEvent(slug, accessKey, form);
      setMatches(response.matches);
    } catch (err) {
      alert(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-grid">
      <section className="panel full-span">
        <p className="kicker">User Dashboard</p>
        <h2>{data.event.name}</h2>
        <p className="copy">
          Upload a clear face image to search only within this event and retrieve your matched photos.
        </p>
      </section>
      <section className="panel">
        <p className="kicker">Find Your Photos</p>
        <form className="stack-form" onSubmit={handleSearch}>
          <label>
            Username
            <input value={form.username} onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))} />
          </label>
          <label>
            Face Image
            <input type="file" onChange={(event) => setForm((current) => ({ ...current, file: event.target.files?.[0] || null }))} />
          </label>
          <button disabled={busy}>{busy ? "Searching Engine..." : "Find My Photos"}</button>
        </form>
        <div className="action-stack">
          <a className="primary-link action-link" href="/downloads/matches/">Download Matched ZIP</a>
        </div>
      </section>
      <section className="panel full-span">
        <p className="kicker">Matched Photos</p>
        {matches && matches.length === 0 ? (
          <div className="empty-state">No matching photos found in this event.</div>
        ) : (
          <div className="card-grid">
            {(matches || []).map((match) => (
              <article key={match.photoId} className="mini-card">
                <img className="card-image" src={match.imageUrl} alt={match.title} />
                <h3>{match.title}</h3>
                <p>{match.eventName}</p>
                <p>Similarity: {Number(match.score).toFixed(3)}</p>
                <div className="action-stack">
                  <a className="primary-link action-link" href={match.downloadUrl}>Download Photo</a>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function NotFoundPage() {
  return (
    <section className="panel">
      <p className="kicker">Not Found</p>
      <h2>This route is not mapped in the React frontend yet.</h2>
      <a className="primary-link" href="/">Back Home</a>
    </section>
  );
}

export default function App() {
  const [session, setSession] = useState(null);
  const [loadingSession, setLoadingSession] = useState(true);

  useEffect(() => {
    getSession()
      .then(setSession)
      .catch(() => { })
      .finally(() => setLoadingSession(false));
  }, []);

  async function handleLogout() {
    setLoadingSession(true);
    const nextSession = await logout();
    setSession(nextSession);
    setLoadingSession(false);
    window.location.href = "/";
  }

  // Routing logic
  let page = null;
  const path = window.location.pathname;
  const authenticated = !!session?.authenticated;
  const isStaff = !!session?.isStaff;

  const adminEventMatch = path.match(/^\/dashboard\/admin\/events\/(\d+)\/?$/);
  const publicEventMatch =
    path.match(/^\/dashboard\/user\/events\/([^/]+)\/([^/]+)\/?$/) ||
    path.match(/^\/events\/([^/]+)\/([^/]+)\/?$/);

  if (loadingSession) {
    page = <section className="panel">Checking session...</section>;
  } else {
    // Determine page based on path and auth status
    if (path === "/login/" || path === "/login" || path === "/register/" || path === "/register") {
      page = <LoginPage onAuthenticated={setSession} />;
    } else if (path === "/dashboard/user/" || path === "/dashboard/user") {
      page = <UserDashboardPage />;
    } else if (adminEventMatch) {
      if (isStaff) {
        page = <AdminEventPage eventId={adminEventMatch[1]} />;
      } else {
        page = <LoginPage onAuthenticated={setSession} />;
      }
    } else if (path.startsWith("/dashboard/admin/") || path === "/dashboard/admin" || path.startsWith("/admin/") || path === "/admin" || path === "/dashboard/" || path === "/dashboard") {
      if (isStaff) {
        page = <AdminDashboardPage />;
      } else {
        page = <LoginPage onAuthenticated={setSession} />;
      }
    } else if (publicEventMatch) {
      page = <PublicEventPage slug={publicEventMatch[1]} accessKey={publicEventMatch[2]} />;
    } else if (path === "/" || path === "") {
      if (isStaff) {
        page = <AdminDashboardPage />;
      } else {
        page = <LandingPage />;
      }
    } else {
      page = <NotFoundPage />;
    }
  }

  return <Layout session={session} onLogout={handleLogout}>{page}</Layout>;
}
