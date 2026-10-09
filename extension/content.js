const API = "http://127.0.0.1:8000";

function panel() {
  const root = document.createElement("aside");
  root.className = "lj-panel";
  const title = document.createElement("strong");
  title.textContent = "Looking Jobs";
  const note = document.createElement("p");
  note.textContent = "Rellena campos visibles. No pulsa Enviar.";
  const analyze = document.createElement("button");
  analyze.type = "button";
  analyze.textContent = "Analizar esta oferta";
  const fill = document.createElement("button");
  fill.type = "button";
  fill.textContent = "Rellenar datos basicos";
  const output = document.createElement("p");
  analyze.addEventListener("click", () => analyzePage(output));
  fill.addEventListener("click", () => fillBasics(output));
  root.append(title, note, analyze, fill, output);
  document.body.append(root);
}

function token() {
  return chrome.runtime.sendMessage({ type: "get-token" }).then((data) => data.token || "");
}

function pageText() {
  const heading = document.querySelector("h1");
  const title = heading ? heading.textContent.trim() : document.title;
  const body = document.body ? document.body.innerText.slice(0, 8000) : "";
  return { title, body };
}

async function analyzePage(output) {
  const key = await token();
  if (!key) {
    output.textContent = "Abre el icono de la extension y guarda el token.";
    return;
  }
  const { title, body } = pageText();
  const response = await fetch(`${API}/api/offers/import`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${key}`,
    },
    body: JSON.stringify({
      company_name: location.hostname,
      job_title: title || "Oferta",
      url: location.href,
      description: body,
    }),
  });
  if (!response.ok) {
    output.textContent = "No se pudo guardar la oferta en la API local.";
    return;
  }
  const created = await response.json();
  const analysis = await fetch(`${API}/api/offers/${created.id}/analyze`, {
    method: "POST",
    headers: { Authorization: `Bearer ${key}` },
  });
  if (!analysis.ok) {
    output.textContent = "La oferta se guardo, pero el analisis fallo.";
    return;
  }
  const data = await analysis.json();
  output.textContent = `Encaje ${data.fit_score}/100. Revisa el borrador en el dashboard.`;
}

function setIfEmpty(input, value) {
  if (!value || input.value) return;
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

async function fillBasics(output) {
  const key = await token();
  if (!key) {
    output.textContent = "Abre el icono de la extension y guarda el token.";
    return;
  }
  const response = await fetch(`${API}/api/profile`, {
    headers: { Authorization: `Bearer ${key}` },
  });
  if (!response.ok) {
    output.textContent = "No se pudo leer el perfil.";
    return;
  }
  const profile = await response.json();
  const fields = document.querySelectorAll("input, textarea");
  fields.forEach((input) => {
    const type = (input.getAttribute("type") || "").toLowerCase();
    if (type === "hidden" || type === "submit" || type === "button" || type === "file") {
      return;
    }
    const hint = [
      input.name,
      input.id,
      input.getAttribute("aria-label") || "",
      input.getAttribute("placeholder") || "",
    ].join(" ").toLowerCase();
    if (hint.includes("email") || type === "email") setIfEmpty(input, profile.email);
    else if (hint.includes("phone") || hint.includes("tel")) setIfEmpty(input, profile.phone);
    else if (hint.includes("name") || hint.includes("nombre")) setIfEmpty(input, profile.full_name);
  });
  output.textContent = "Campos basicos rellenados. Revisa antes de enviar.";
}

panel();
