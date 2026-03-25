async function request(path, options = {}, retryState = { attemptedCsrfRefresh: false }) {
  const response = await fetch(path, {
    credentials: "include",
    ...options,
    headers: {
      ...(options.headers || {}),
    },
  });

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  const looksLikeCsrfFailure =
    response.status === 403 &&
    typeof data === "string" &&
    data.toLowerCase().includes("csrf");

  if (
    looksLikeCsrfFailure &&
    !retryState.attemptedCsrfRefresh
  ) {
    await fetch("/api/session/", {
      credentials: "include",
    });
    return request(path, options, { attemptedCsrfRefresh: true });
  }

  if (!response.ok) {
    const message =
      typeof data === "object" && data?.error
        ? data.error
        : `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  return data;
}

function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export function getSession() {
  return request("/api/session/");
}

export function login(payload) {
  const body = new URLSearchParams(payload);
  return request("/api/auth/login/", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "X-CSRFToken": getCsrfToken(),
    },
    body,
  });
}

export function logout() {
  return request("/api/auth/logout/", {
    method: "POST",
    headers: {
      "X-CSRFToken": getCsrfToken(),
    },
  });
}

export function fetchAdminDashboard() {
  return request("/api/admin/dashboard/");
}

export function createEvent(payload) {
  const body = new URLSearchParams({
    "event-name": payload.name,
    "event-event_date": payload.eventDate || "",
  });
  return request("/api/admin/events/", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "X-CSRFToken": getCsrfToken(),
    },
    body,
  });
}

export function updateEvent(eventId, payload) {
  const body = new URLSearchParams({
    [`rename-${eventId}-name`]: payload.name,
    [`rename-${eventId}-event_date`]: payload.eventDate || "",
  });
  return request(`/api/admin/events/${eventId}/update/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "X-CSRFToken": getCsrfToken(),
    },
    body,
  });
}

export function deleteEvent(eventId) {
  return request(`/api/admin/events/${eventId}/delete/`, {
    method: "POST",
    headers: {
      "X-CSRFToken": getCsrfToken(),
    },
  });
}

export function fetchAdminEvent(eventId) {
  return request(`/api/admin/events/${eventId}/`);
}

export function uploadEventPhotos(eventId, files, onUploadProgress, options = {}) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    files.forEach((file) => formData.append("photos", file));

    const xhr = new XMLHttpRequest();
    if (options.onXhr) {
      options.onXhr(xhr);
    }
    xhr.open("POST", `/api/admin/events/${eventId}/upload/`, true);
    xhr.withCredentials = true;
    xhr.setRequestHeader("X-CSRFToken", getCsrfToken());

    if (onUploadProgress) {
      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          onUploadProgress(percent);
        }
      });
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText);
          resolve(data);
        } catch (e) {
          resolve(xhr.responseText);
        }
      } else {
        let message = `Upload failed with status ${xhr.status}`;
        try {
          const data = JSON.parse(xhr.responseText);
          if (data.error) message = data.error;
        } catch (e) { }
        reject(new Error(message));
      }
    };

    xhr.onerror = () => reject(new Error("Network error during upload."));
    xhr.onabort = () => reject(new Error("Upload cancelled."));

    xhr.send(formData);
  });
}

export function deletePhoto(eventId, photoId) {
  return request(`/api/admin/events/${eventId}/photos/${photoId}/delete/`, {
    method: "POST",
    headers: {
      "X-CSRFToken": getCsrfToken(),
    },
  });
}

export function deleteAllPhotos(eventId) {
  return request(`/api/admin/events/${eventId}/photos/delete-all/`, {
    method: "POST",
    headers: {
      "X-CSRFToken": getCsrfToken(),
    },
  });
}

export function fetchPublicEvent(slug, accessKey) {
  return request(`/api/events/${slug}/${accessKey}/`);
}

export function searchPublicEvent(slug, accessKey, payload) {
  const formData = new FormData();
  formData.append("username", payload.username);
  formData.append("query_image", payload.file);
  return request(`/api/events/${slug}/${accessKey}/search/`, {
    method: "POST",
    headers: {
      "X-CSRFToken": getCsrfToken(),
    },
    body: formData,
  });
}

export function fetchIndexingProgress(eventId) {
  return request(`/api/admin/events/${eventId}/indexing-progress/`);
}

export function cancelTasks(eventId, taskIds) {
  return request(`/api/admin/events/${eventId}/cancel-tasks/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
    },
    body: JSON.stringify({ taskIds }),
  });
}
