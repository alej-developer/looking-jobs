const STATUSES = [
  ["PENDING", "Guardada"],
  ["DRAFT", "Borrador"],
  ["APPLIED", "Enviada"],
  ["INTERVIEW", "Entrevista"],
  ["OFFER", "Oferta"],
  ["REJECTED", "Rechazada"],
  ["SKIPPED", "Descartada"],
  ["FAILED", "Fallida"],
];

const loginView = document.querySelector("#login-view");
const boardView = document.querySelector("#board-view");
const profileView = document.querySelector("#profile-view");
const offerList = document.querySelector("#offer-list");
const detail = document.querySelector("#detail");
const loginError = document.querySelector("#login-error");
const logoutButton = document.querySelector("#nav-logout");

let selectedId = null;

function safeUrl(value) {
  try {
    const parsed = new URL(value);
    if (parsed.protocol === "https:" || parsed.protocol === "http:") {
      return parsed.href;
    }
  } catch (_error) {
    return "";
  }
  return "";
}

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

async function api(path, options) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (response.status === 401) {
    showLogin();
    throw new Error("auth");
  }
  return response;
}

function showLogin() {
  loginView.hidden = false;
  boardView.hidden = true;
  profileView.hidden = true;
  logoutButton.hidden = true;
}

function showBoard() {
  loginView.hidden = true;
  boardView.hidden = false;
  profileView.hidden = true;
  logoutButton.hidden = false;
  document.querySelector("#nav-board").classList.add("is-active");
  document.querySelector("#nav-profile").classList.remove("is-active");
}

function showProfile() {
  loginView.hidden = true;
  boardView.hidden = true;
  profileView.hidden = false;
  logoutButton.hidden = false;
  document.querySelector("#nav-profile").classList.add("is-active");
  document.querySelector("#nav-board").classList.remove("is-active");
}

async function loadOffers() {
  const status = document.querySelector("#status-filter").value;
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const response = await api(`/api/offers${query}`);
  const data = await response.json();
  offerList.replaceChildren();
  data.items.forEach((offer) => {
    const item = el("li");
    const button = el("button", "", "offer");
    button.type = "button";
    button.append(el("strong", offer.job_title));
    const meta = [offer.company_name, offer.location, offer.status].filter(Boolean).join(" · ");
    button.append(el("span", meta));
    button.addEventListener("click", () => openOffer(offer.id));
    item.append(button);
    offerList.append(item);
  });
  if (!data.items.length) {
    offerList.append(el("li", "No hay ofertas con ese filtro.", "muted"));
  }
}

function statusSelect(current) {
  const select = document.createElement("select");
  STATUSES.forEach(([value, label]) => {
    const option = el("option", label);
    option.value = value;
    if (value === current) option.selected = true;
    select.append(option);
  });
  return select;
}

async function openOffer(id) {
  selectedId = id;
  const response = await api(`/api/offers/${id}`);
  const offer = await response.json();
  renderDetail(offer);
}

function renderDetail(offer) {
  detail.replaceChildren();
  const head = el("div", "", "detail-head");
  head.append(el("h2", offer.job_title));
  if (offer.fit_score !== null && offer.fit_score !== undefined) {
    head.append(el("span", `${offer.fit_score}/100`, "score"));
  }
  detail.append(head);
  detail.append(el("p", `${offer.company_name} · ${offer.ats_type || "ATS"} · ${offer.location || "sin ubicación"}`, "muted"));

  const link = safeUrl(offer.url);
  if (link) {
    const anchor = el("a", "Abrir oferta en la empresa");
    anchor.href = link;
    anchor.target = "_blank";
    anchor.rel = "noreferrer noopener";
    detail.append(anchor);
  }

  detail.append(el("h3", "Descripción"));
  detail.append(el("p", offer.description || "Sin descripción guardada."));
  detail.append(el("h3", "Encaje"));
  detail.append(el("p", offer.fit_summary || "Todavía no analizada."));
  detail.append(el("h3", "Huecos"));
  detail.append(el("p", offer.gap_notes || "Sin huecos calculados."));

  const draftLabel = el("label", "Borrador editable");
  const draft = document.createElement("textarea");
  draft.value = offer.draft_body || "";
  draftLabel.append(draft);
  detail.append(draftLabel);

  const statusLabel = el("label", "Estado");
  const select = statusSelect(offer.status);
  statusLabel.append(select);
  detail.append(statusLabel);

  const actions = el("div", "", "row");
  const analyze = el("button", "Analizar encaje");
  analyze.type = "button";
  analyze.addEventListener("click", () => analyzeOffer(offer.id));
  const save = el("button", "Guardar revisión");
  save.type = "button";
  save.addEventListener("click", () => saveOffer(offer.id, select.value, draft.value));
  actions.append(analyze, save);
  detail.append(actions);

  const check = el("div", "", "checklist");
  check.append(el("strong", "Antes de enviar en la web de la empresa"));
  check.append(el("p", "El borrador cita solo evidencias del perfil. El envío lo haces tú en la página original."));
  check.append(el("p", "Comprueba que el CV que subes es el que quieres para este rol."));
  detail.append(check);
}

async function analyzeOffer(id) {
  const response = await api(`/api/offers/${id}/analyze`, { method: "POST" });
  if (!response.ok) return;
  renderDetail(await response.json());
  await loadOffers();
}

async function saveOffer(id, status, draftBody) {
  const response = await api(`/api/offers/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status, draft_body: draftBody }),
  });
  if (!response.ok) return;
  renderDetail(await response.json());
  await loadOffers();
}

function field(form, name, label, value, multiline) {
  const wrap = el("label", label);
  const input = document.createElement(multiline ? "textarea" : "input");
  input.name = name;
  input.value = value || "";
  wrap.append(input);
  form.append(wrap);
  return input;
}

async function loadProfile() {
  const response = await api("/api/profile");
  const profile = await response.json();
  const form = document.querySelector("#profile-form");
  form.replaceChildren();
  field(form, "full_name", "Nombre", profile.full_name);
  field(form, "email", "Email", profile.email);
  field(form, "phone", "Teléfono", profile.phone);
  field(form, "origin_sector", "Sector de origen", profile.origin_sector);
  field(form, "origin_role", "Rol de origen", profile.origin_role);
  field(form, "origin_years", "Años", profile.origin_years ?? "");
  field(form, "origin_highlights", "Logros que puedes demostrar", profile.origin_highlights, true);
  field(form, "target_roles", "Roles objetivo", profile.target_roles, true);
  field(form, "target_sectors", "Sectores objetivo", profile.target_sectors);
  field(form, "constraints_text", "Restricciones", profile.constraints_text, true);
  field(form, "why_change", "Por qué cambias de sector", (profile.anchors || {}).why_change, true);
  field(form, "what_you_bring", "Qué aportas sin experiencia directa", (profile.anchors || {}).what_you_bring, true);
  const bridge = (profile.bridge && profile.bridge[0]) || { skill: "", evidence: "" };
  field(form, "bridge_skill", "Habilidad puente", bridge.skill);
  field(form, "bridge_evidence", "Evidencia de esa habilidad", bridge.evidence, true);
  const save = el("button", "Guardar perfil");
  save.type = "submit";
  form.append(save);
  const note = el("p", "", "error");
  note.id = "profile-note";
  form.append(note);
}

document.querySelector("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.textContent = "";
  const token = document.querySelector("#token").value;
  const response = await fetch("/api/auth/login", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  document.querySelector("#token").value = "";
  if (!response.ok) {
    loginError.textContent = "No se pudo abrir la sesión.";
    return;
  }
  showBoard();
  await loadOffers();
});

document.querySelector("#nav-board").addEventListener("click", async () => {
  showBoard();
  await loadOffers();
  if (selectedId) await openOffer(selectedId);
});

document.querySelector("#nav-profile").addEventListener("click", async () => {
  showProfile();
  await loadProfile();
});

logoutButton.addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  showLogin();
});

document.querySelector("#status-filter").addEventListener("change", () => {
  loadOffers().catch(() => {});
});

document.querySelector("#profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const years = String(data.get("origin_years") || "").trim();
  const skill = String(data.get("bridge_skill") || "").trim();
  const evidence = String(data.get("bridge_evidence") || "").trim();
  const payload = {
    full_name: data.get("full_name") || "",
    email: data.get("email") || "",
    phone: data.get("phone") || "",
    origin_sector: data.get("origin_sector") || "",
    origin_role: data.get("origin_role") || "",
    origin_years: years ? Number(years) : null,
    origin_highlights: data.get("origin_highlights") || "",
    target_roles: data.get("target_roles") || "",
    target_sectors: data.get("target_sectors") || "",
    constraints_text: data.get("constraints_text") || "",
    anchors: {
      why_change: data.get("why_change") || "",
      what_you_bring: data.get("what_you_bring") || "",
    },
    bridge: skill && evidence ? [{ skill, evidence }] : [],
    proof: [],
  };
  const response = await api("/api/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  const note = document.querySelector("#profile-note");
  note.textContent = response.ok ? "Perfil guardado." : "No se pudo guardar el perfil.";
});

api("/api/me").then(() => {
  showBoard();
  return loadOffers();
}).catch(() => {
  showLogin();
});
