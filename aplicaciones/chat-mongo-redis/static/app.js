/* Interfaz: elección de rol + los tres widgets (caché, turnos, mapa). */

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

// Identifica a esta pestaña frente a Redis (valor que se guarda en lock:publicador).
const token = sessionStorage.token || (sessionStorage.token = crypto.randomUUID());

async function api(url, { method = "GET", body } = {}) {
  const r = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body && JSON.stringify(body) });
  return r.json();
}

/* Terminal bajo cada widget: imita la salida de redis-cli. */
function terminal(id, comando, ...respuestas) {
  const t = $(id);
  const bloque = document.createElement("div");
  bloque.innerHTML = (comando ? `<span class="prompt">&gt;</span> ${esc(comando)}` : "")
                   + respuestas.map((r) => `<span class="resp">${esc(r)}</span>`).join("");
  t.append(bloque);
  while (t.children.length > 8) t.firstChild.remove();
  t.scrollTop = t.scrollHeight;
}

/* ====================================================== Widget 1 · Caché */

let ttlCache = 0;
const historial = [];

async function iniciarCache() {
  const sel = $("#sel-asignatura");
  const asignaturas = await api("/api/asignaturas");

  if (!asignaturas.length) {
    sel.add(new Option("sin datos", "sin-datos"));
    sel.value = "sin-datos";
  } else {
    asignaturas.forEach((c) => sel.add(new Option(c)));
  }

  $("#btn-consultar").onclick = async () => {
    const r = await api(`/api/cache/${encodeURIComponent(sel.value)}`);
    r.comandos.forEach(([cmd, resp]) => terminal("#term-cache", cmd, resp));
    pintarResultado(r);
  };

  $("#btn-vaciar").onclick = async () => {
    const r = await api(`/api/cache/${sel.value}`, { method: "DELETE" });
    r.comandos.forEach(([cmd, resp]) => terminal("#term-cache", cmd, resp));
    ttlCache = 0;
  };

  setInterval(() => {
    if (ttlCache > 0) ttlCache--;
    $("#txt-ttl").textContent = ttlCache > 0
      ? `en Redis · expira en ${ttlCache} s`
      : historial.length ? "sin caché · la próxima consulta irá a MongoDB" : "";
  }, 1000);
}

function pintarResultado(r) {
  ttlCache = r.ttl;
  const badge = $("#badge-origen");
  badge.textContent = r.origen === "BD" ? "BD · MongoDB" : "CACHE · Redis";
  badge.className = `badge ${r.origen}`;
  $("#txt-ms").textContent = r.ms;

  const doc = $("#doc-cache");
  doc.hidden = false;
  doc.textContent = JSON.stringify(r.doc, null, 2);

  historial.unshift(r);
  historial.splice(6);
  const max = Math.max(...historial.map((h) => h.ms));
  $("#historial-cache").innerHTML = historial.map((h) => `
    <li class="${h.origen}">
      <span class="badge ${h.origen}">${h.origen}</span>
      <i style="width:${(h.ms / max) * 100}%"></i>
      <b>${h.ms} ms</b>
    </li>`).join("");
}

/* ====================================================== Rol: publicador / suscriptor */

async function actualizarEstadoLock() {
  const { ocupado, ttl } = await api("/api/publicador");
  const e = $("#estado-lock");
  e.textContent = ocupado ? `ocupado · el lock expira en ${ttl} s` : "disponible";
  e.classList.toggle("ocupado", ocupado);
}

async function elegirRol(rol) {
  if (rol === "publicador") {
    const r = await api("/api/publicador/entrar", { method: "POST", body: { token } });
    if (!r.ok) { $("#estado-lock").textContent = r.error; return; }
  }
  clearInterval(sondeoLock);
  document.body.dataset.rol = rol;
  $("#chip-rol").textContent = rol;
  rol === "publicador" ? iniciarPublicador() : iniciarSuscriptor();
  iniciarMapa(rol === "publicador");
}

/* --- Publicador: posee el lock, renueva su TTL y publica en los canales --- */

async function publicar(canal, mensaje, term) {
  const r = await api("/api/publicar", { method: "POST", body: { token, canal, mensaje } });
  terminal(term, r.comando ?? `PUBLISH ${canal}`, r.error ?? `(integer) ${r.oyentes}`);
  return r.error ? null : r;
}

function iniciarPublicador() {
  $("#chip-conexion").textContent = "● lock:publicador adquirido";
  terminal("#term-turnos", `SET lock:publicador "${token.slice(0, 8)}…" NX EX 30`, "OK");

  let ttl = 30;
  setInterval(() => { $("#lock-ttl").textContent = Math.max(--ttl, 0); }, 1000);
  setInterval(async () => {
    ({ ttl } = await api("/api/publicador/renovar", { method: "POST", body: { token } }));
    if (ttl < 0) { alert("Se perdió el lock de publicador."); location.reload(); }
  }, 10_000);

  $("#form-turno").onsubmit = async (e) => {
    e.preventDefault();
    const texto = $("#inp-turno").value.trim();
    const r = texto && await publicar("chat:sala1", texto, "#term-turnos");
    if (r) { mostrarTurno(texto, `${r.oyentes} oyente${r.oyentes === 1 ? "" : "s"}`); $("#inp-turno").value = ""; }
  };

  // Al cerrar la pestaña se libera el lock (si no, expira solo a los 30 s).
  window.addEventListener("pagehide", () =>
    navigator.sendBeacon("/api/publicador/salir", new Blob([JSON.stringify({ token })], { type: "application/json" })));
}

/* --- Suscriptor: recibe por SSE lo que el servidor escucha con SUBSCRIBE --- */

function iniciarSuscriptor() {
  const es = new EventSource("/api/suscribir");
  es.onopen = () => { $("#chip-conexion").textContent = "● suscrito a chat:sala1 y mapa:sala1"; };
  es.onerror = () => { $("#chip-conexion").textContent = "● reconectando…"; };

  terminal("#term-turnos", "SUBSCRIBE chat:sala1", '1) "subscribe"', '2) "chat:sala1"', "3) (integer) 1");
  terminal("#term-mapa", "SUBSCRIBE mapa:sala1", '1) "subscribe"', '2) "mapa:sala1"', "3) (integer) 1");

  es.addEventListener("chat:sala1", (e) => {
    terminal("#term-turnos", null, '1) "message"', '2) "chat:sala1"', `3) ${e.data}`);
    mostrarTurno(JSON.parse(e.data), new Date().toLocaleTimeString());
  });
  es.addEventListener("mapa:sala1", (e) => {
    terminal("#term-mapa", null, '1) "message"', '2) "mapa:sala1"', `3) ${e.data}`);
    moverMapa(JSON.parse(e.data));
  });
}

function mostrarTurno(texto, detalle) {
  $("#turno-actual").textContent = texto;
  const li = document.createElement("li");
  li.innerHTML = `<span>${esc(texto)}</span><small>${esc(detalle)}</small>`;
  const ul = $("#lista-turnos");
  ul.prepend(li);
  while (ul.children.length > 5) ul.lastChild.remove();
}

/* ====================================================== Widget 3 · Mapa */

let mapa, marcador;

function iniciarMapa(esPublicador) {
  mapa = L.map("mapa", {
    zoomControl: esPublicador, dragging: esPublicador, scrollWheelZoom: esPublicador,
    doubleClickZoom: esPublicador, touchZoom: esPublicador, keyboard: esPublicador, boxZoom: esPublicador,
  }).setView([-16.5, -68.13], 13);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap" }).addTo(mapa);
  marcador = L.marker(mapa.getCenter(), { draggable: esPublicador }).addTo(mapa);
  pintarCoords();

  $("#mapa-ayuda").textContent = esPublicador
    ? "Arrastra el marcador o mueve/haz zoom en el mapa: cada cambio se publica en mapa:sala1"
    : "El mapa y el marcador siguen al publicador";

  if (esPublicador) {
    // Se publica la vista (centro + zoom) y la posición del marcador en un solo mensaje.
    const publicarMapa = () => {
      pintarCoords();
      const c = mapa.getCenter(), m = marcador.getLatLng();
      publicar("mapa:sala1", {
        lat: +c.lat.toFixed(5), lng: +c.lng.toFixed(5), zoom: mapa.getZoom(),
        marcador: { lat: +m.lat.toFixed(5), lng: +m.lng.toFixed(5) },
      }, "#term-mapa");
    };
    mapa.on("moveend", publicarMapa);        // arrastrar el mapa o cambiar el zoom
    marcador.on("dragend", publicarMapa);    // soltar el marcador en otro lugar
  }
}

function moverMapa({ lat, lng, zoom, marcador: m }) {
  mapa.setView([lat, lng], zoom);
  marcador.setLatLng([m.lat, m.lng]);
  pintarCoords();
}

function pintarCoords() {
  const m = marcador.getLatLng();
  $("#txt-coords").textContent = `marcador ${m.lat.toFixed(5)}, ${m.lng.toFixed(5)} · zoom ${mapa.getZoom()}`;
}

/* ====================================================== Arranque */

iniciarCache();
actualizarEstadoLock();
const sondeoLock = setInterval(actualizarEstadoLock, 5000);

document.querySelectorAll(".rol-opcion").forEach((b) => { b.onclick = () => elegirRol(b.dataset.rol); });

$("#btn-salir").onclick = async () => {
  if (document.body.dataset.rol === "publicador") await api("/api/publicador/salir", { method: "POST", body: { token } });
  location.reload();
};
