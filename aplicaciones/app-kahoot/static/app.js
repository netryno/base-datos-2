/* Interfaz del quiz: ingreso (nombre + rol), panel del Profesor y pantalla del Jugador.
   El navegador nunca habla con Redis: usa fetch para comandos y EventSource (SSE) para recibir
   los eventos que el backend reenvía desde Redis Pub/Sub. El servidor manda tiempo y puntaje. */

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const OPCIONES = ["a", "b", "c", "d"];

// Identifica a esta pestaña (valor guardado en publisher:lock o como player_id).
// crypto.randomUUID solo existe en contextos seguros (https / localhost); por http://IP-local se usa el fallback.
const nuevoId = () => (crypto.randomUUID ? crypto.randomUUID()
  : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}-${Math.random().toString(36).slice(2, 10)}`);
const sesion = JSON.parse(sessionStorage.sesion || "null") || { id: nuevoId(), rol: null, nombre: "" };
const guardarSesion = () => (sessionStorage.sesion = JSON.stringify(sesion));
guardarSesion();

let CFG = { question_duration: 25, result_reveal_seconds: 2, top_n: 10, heartbeat_interval: 5, publisher_lock_ttl: 15, min_name_length: 2, max_name_length: 20 };
let estado = null;          // última instantánea de la partida (se actualiza con los eventos)
let espectador = false;
let offsetReloj = 0;        // servidor - cliente (ms); el servidor es la fuente de verdad del tiempo
let fuente = null;          // EventSource
let gameIdConectado = null;
let sseActivo = false;
let sondeoPartida = null;
let esperaSse = null;

async function api(url, { method = "GET", body } = {}) {
  const r = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json", "X-Session-Id": sesion.id },
    body: body && JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(data.error || `Error ${r.status}`), { status: r.status, data });
  return data;
}

/* Terminal estilo redis-cli bajo el widget. */
function terminal(id, comando, ...respuestas) {
  const t = $(id);
  if (!t) return;
  const bloque = document.createElement("div");
  bloque.innerHTML = (comando ? `<span class="prompt">&gt;</span> ${esc(comando)}` : "")
                   + respuestas.map((r) => `<span class="resp">${esc(r)}</span>`).join("");
  t.append(bloque);
  while (t.children.length > 10) t.firstChild.remove();
  t.scrollTop = t.scrollHeight;
}
const terminalComandos = (id, comandos) => (comandos || []).forEach(([c, r]) => terminal(id, c, r));

function alternarConsola(btnId, termId) {
  const btn = $(btnId);
  const term = $(termId);
  if (!btn || !term) return;
  btn.onclick = () => {
    const abrir = term.hidden;
    term.hidden = !abrir;
    btn.setAttribute("aria-expanded", String(abrir));
    btn.classList.toggle("activo", abrir);
    if (abrir) term.scrollTop = term.scrollHeight;
  };
}

let confettiPartida = null;

/** Confeti breve centrado en los puestos del podio (canvas local, sin dependencias). */
/** Confeti suave sobre un contenedor (acierto en revelación). */
function confettiSuave(contenedor) {
  if (!contenedor) return;
  contenedor.querySelector(".revelacion-canvas")?.remove();
  const canvas = document.createElement("canvas");
  canvas.className = "confetti-canvas revelacion-canvas";
  const ancho = contenedor.clientWidth;
  const alto = Math.max(contenedor.clientHeight, 160);
  canvas.width = ancho;
  canvas.height = alto;
  contenedor.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  const colores = ["#22c55e", "#eab308", "#3b82f6", "#a855f7", "#14b8a6"];
  const piezas = [];
  for (let i = 0; i < 55; i++) {
    piezas.push({
      x: ancho * (0.2 + Math.random() * 0.6),
      y: alto * 0.35,
      vx: (Math.random() - 0.5) * 7,
      vy: -Math.random() * 9 - 2,
      w: 4 + Math.random() * 4,
      h: 2 + Math.random() * 3,
      rot: Math.random() * Math.PI,
      vr: (Math.random() - 0.5) * 0.2,
      color: colores[(Math.random() * colores.length) | 0],
      vida: 0.7 + Math.random() * 0.3,
    });
  }
  let fotograma = 0;
  const dibujar = () => {
    fotograma += 1;
    ctx.clearRect(0, 0, ancho, alto);
    let quedan = false;
    for (const p of piezas) {
      p.vy += 0.18;
      p.x += p.vx;
      p.y += p.vy;
      p.vida -= 0.014;
      if (p.vida <= 0) continue;
      quedan = true;
      ctx.save();
      ctx.globalAlpha = Math.min(1, p.vida * 1.3);
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      p.rot += p.vr;
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    }
    if (fotograma < 120 && quedan) requestAnimationFrame(dibujar);
    else canvas.remove();
  };
  requestAnimationFrame(dibujar);
}

let revelacionActiva = null;

function confettiPodio(podioId, seccionId) {
  const podio = $(podioId);
  const seccion = $(seccionId);
  if (!podio || !seccion || !podio.querySelector(".puesto")) return;
  seccion.querySelector(".confetti-canvas")?.remove();
  const canvas = document.createElement("canvas");
  canvas.className = "confetti-canvas";
  const ancho = seccion.clientWidth;
  const alto = Math.max(seccion.clientHeight, 280);
  canvas.width = ancho;
  canvas.height = alto;
  seccion.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  const base = seccion.getBoundingClientRect();
  const colores = ["#eab308", "#22c55e", "#3b82f6", "#ec4899", "#f97316", "#a855f7", "#ef4444", "#fff"];
  const piezas = [];
  podio.querySelectorAll(".puesto").forEach((el) => {
    const r = el.getBoundingClientRect();
    const cx = r.left - base.left + r.width / 2;
    const cy = r.top - base.top + r.height * 0.35;
    for (let i = 0; i < 40; i++) {
      piezas.push({
        x: cx + (Math.random() - 0.5) * r.width * 0.5,
        y: cy,
        vx: (Math.random() - 0.5) * 9,
        vy: -Math.random() * 11 - 3,
        w: 5 + Math.random() * 6,
        h: 3 + Math.random() * 4,
        rot: Math.random() * Math.PI,
        vr: (Math.random() - 0.5) * 0.25,
        color: colores[(Math.random() * colores.length) | 0],
        vida: 0.85 + Math.random() * 0.15,
      });
    }
  });
  let fotograma = 0;
  const dibujar = () => {
    fotograma += 1;
    ctx.clearRect(0, 0, ancho, alto);
    let quedan = false;
    for (const p of piezas) {
      p.vy += 0.22;
      p.vx *= 0.99;
      p.x += p.vx;
      p.y += p.vy;
      p.vida -= 0.011;
      if (p.vida <= 0) continue;
      quedan = true;
      ctx.save();
      ctx.globalAlpha = Math.min(1, p.vida * 1.2);
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      p.rot += p.vr;
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    }
    if (fotograma < 200 && quedan) requestAnimationFrame(dibujar);
    else canvas.remove();
  };
  requestAnimationFrame(dibujar);
}

function celebrarPodio() {
  if (!estado || estado.status !== "GAME_OVER" || estado.cancelled || !estado.podium?.length) return;
  if (confettiPartida === estado.game_id) return;
  confettiPartida = estado.game_id;
  const podio = sesion.rol === "profesor" ? "#prof-podio" : "#jug-podio";
  const sec = sesion.rol === "profesor" ? "#prof-final" : "#jug-final";
  setTimeout(() => confettiPodio(podio, sec), 180);
}

/* ====================================================== Componentes compartidos */

const COLORES = ["#f97316", "#22c55e", "#3b82f6", "#a855f7", "#ec4899", "#14b8a6", "#eab308", "#ef4444", "#6366f1", "#84cc16"];
const FORMAS = [
  "",                                                                                              // 0 silueta simple
  "<circle cx='32' cy='10' r='5'/>",                                                               // 1 moño
  "<path d='M19 21 Q32 4 45 21 Z'/><rect x='15' y='20' width='34' height='4' rx='2'/>",           // 2 gorra
  "<path d='M19 24 C18 8 46 8 45 24 L48 46 L16 46 Z'/>",                                           // 3 cabello largo
  "<path d='M21 17 L25 5 L29 14 L32 2 L35 14 L39 5 L43 17 Z'/>",                                   // 4 puntas
  "<circle cx='27' cy='25' r='3.5' class='bg'/><circle cx='37' cy='25' r='3.5' class='bg'/><rect x='30' y='24' width='4' height='1.5' class='bg'/>", // 5 lentes
  "<path d='M21 27 Q32 46 43 27 Z'/>",                                                             // 6 barba
  "<circle cx='32' cy='22' r='17'/>",                                                              // 7 afro
];
function avatar(a, clase = "") {
  const color = COLORES[(a?.color ?? 0) % COLORES.length];
  const forma = FORMAS[(a?.shape ?? 0) % FORMAS.length];
  return `<svg class="avatar ${clase}" viewBox="0 0 64 64" style="--c:${color}">
    <circle cx="32" cy="32" r="32" fill="${color}"/>
    <g fill="#0f172a"><circle cx="32" cy="24" r="11"/><path d="M12 60 C12 45 20 40 32 40 C44 40 52 45 52 60 Z"/>${forma}</g>
  </svg>`;
}

function htmlJugadores(jugadores, meId) {
  if (!jugadores?.length) return `<p class="vacio">Aún no hay jugadores. Comparte la dirección de la app.</p>`;
  return jugadores.map((j) => `
    <div class="jugador ${j.player_id === meId ? "yo" : ""}" title="${esc(j.name)}">
      ${avatar(j.avatar)}<span>${esc(j.name)}</span>
    </div>`).join("");
}

function htmlEnunciado(q) {
  const texto = typeof q === "string" ? q : q?.text;
  const bloque = typeof q === "object" ? q?.code_block : null;
  let html = `<h3 class="texto-pregunta">${esc(texto)}</h3>`;
  if (bloque?.content) {
    const lang = bloque.language
      ? `<span class="codigo-lang">${esc(bloque.language)}</span>`
      : "";
    html += `<div class="bloque-codigo-wrap">${lang}<pre class="bloque-codigo"><code>${esc(bloque.content)}</code></pre></div>`;
  }
  return html;
}

function htmlOpciones(opciones, { correcta = null, conteos = null, elegida = null, clicable = false, confirmarPendiente = false } = {}) {
  const total = conteos ? Object.values(conteos).reduce((a, b) => a + b, 0) : 0;
  return OPCIONES.map((o) => {
    const clases = ["opcion", `op-${o}`];
    if (correcta) clases.push(o === correcta ? "correcta" : "incorrecta");
    if (elegida === o) clases.push("elegida");
    const pct = total ? Math.round((conteos[o] || 0) * 100 / total) : 0;
    const capa = elegida === o && confirmarPendiente ? `
      <div class="opcion-cap">
        <p>¿Confirmar esta respuesta?</p>
        <div class="opcion-cap-acciones">
          <button type="button" class="btn btn-si btn-cap" data-confirm="si" data-op="${o}">Confirmar</button>
          <button type="button" class="btn btn-no btn-cap" data-confirm="no" data-op="${o}">Cancelar</button>
        </div>
      </div>` : "";
    const tag = clicable && !capa ? "button" : "div";
    return `<${tag} class="${clases.join(" ")}" data-op="${o}" ${tag === "button" ? "type='button'" : ""}>
      <b>${o.toUpperCase()}</b><span>${esc(opciones[o])}</span>
      ${conteos ? `<small>${conteos[o] || 0} · ${pct}%</small><i style="width:${pct}%"></i>` : ""}
      ${capa}
    </${tag}>`;
  }).join("");
}

function htmlRanking(ranking, meId) {
  if (!ranking?.length) return `<li class="vacio">Sin jugadores.</li>`;
  return ranking.map((r) => `
    <li class="${r.player_id === meId ? "yo" : ""} pos-${r.pos}">
      <span class="pos">${r.pos}</span>${avatar(r.avatar, "mini")}
      <span class="nombre">${esc(r.name)}</span>
      <small>${r.total_time.toFixed(1)} s</small>
      <b>${r.score} pts</b>
    </li>`).join("");
}

function htmlPodio(podio, meId) {
  if (!podio?.length) return `<p class="vacio">Partida cancelada: no hay podio.</p>`;
  const orden = [podio[1], podio[0], podio[2]].filter(Boolean);
  return orden.map((p) => `
    <div class="puesto puesto-${p.pos} ${p.player_id === meId ? "yo" : ""}">
      <span class="medalla">${["🥇", "🥈", "🥉"][p.pos - 1]}</span>
      ${avatar(p.avatar, "grande")}
      <strong>${esc(p.name)}</strong>
      <b>${p.score} pts</b>
      <i>${p.pos}.°</i>
    </div>`).join("");
}

/* Lista de los puestos 4.° a 10.° (o todos si la partida fue cancelada). Se oculta si no hay nadie más. */
function pintarResto(id, st, meId) {
  const resto = (st.ranking || []).slice(st.cancelled ? 0 : 3);
  $(id).hidden = resto.length === 0;
  $(id).innerHTML = htmlRanking(resto, meId);
}

/* Temporizador: el cliente solo renderiza la cuenta regresiva a partir del deadline del servidor. */
let relojTimer = null;

function detenerTemporizador() {
  clearInterval(relojTimer);
  relojTimer = null;
}

function iniciarTemporizador(deadline, duracion, idBarra, idSegundos, alTerminar) {
  detenerTemporizador();
  const pintar = () => {
    if (estado?.status !== "QUESTION_STARTED") { detenerTemporizador(); return; }
    const bar = $(idBarra);
    const seg = $(idSegundos);
    if (!bar || !seg) { detenerTemporizador(); return; }
    const restante = Math.max(0, deadline - (Date.now() + offsetReloj));
    seg.textContent = Math.ceil(restante / 1000);
    bar.style.width = `${(restante / (duracion * 1000)) * 100}%`;
    bar.classList.toggle("urgente", restante < 3000);
    if (restante <= 0) {
      detenerTemporizador();
      if (estado?.status === "QUESTION_STARTED") alTerminar?.();
    }
  };
  pintar();
  relojTimer = setInterval(pintar, 100);
}
const ahoraServidor = () => Date.now() + offsetReloj;

/* ====================================================== Ingreso */

async function cargarConfig() {
  CFG = await api("/api/config");
  $("#inp-nombre").maxLength = CFG.max_name_length;
  document.querySelectorAll(".top-n").forEach((e) => (e.textContent = CFG.top_n));
}

async function actualizarEstadoLock() {
  try {
    const { ocupado, ttl, nombre } = await api("/api/session/publisher");
    const e = $("#estado-lock");
    e.textContent = ocupado ? `ocupado por ${nombre} · expira en ${ttl} s si no hay latido` : "disponible";
    e.classList.toggle("ocupado", ocupado);
    const { game } = await api("/api/games/current");
    $("#estado-sala").textContent = !game ? "sin sala abierta todavía"
      : game.status === "LOBBY" ? `sala abierta: «${game.title}» · ${game.players.length} en espera`
      : game.status === "GAME_OVER" ? "partida terminada · esperando una nueva"
      : `partida en curso (${game.idx + 1}/${game.total_questions}) · entrarías como espectador`;
  } catch (e) {
    $("#estado-lock").textContent = e.data?.degraded ? "Redis no disponible" : "sin conexión";
  }
}
let sondeoLock = null;

function mensajeIngreso(texto) {
  const m = $("#msg-ingreso");
  m.hidden = !texto;
  m.textContent = texto || "";
}

async function elegirRol(rol) {
  const nombre = $("#inp-nombre").value.trim().replace(/\s+/g, " ");
  if (nombre.length < CFG.min_name_length || nombre.length > CFG.max_name_length) {
    mensajeIngreso(`Escribe tu nombre (entre ${CFG.min_name_length} y ${CFG.max_name_length} caracteres).`);
    $("#inp-nombre").focus();
    return;
  }
  sesion.nombre = nombre;
  try {
    if (rol === "profesor") {
      const r = await api("/api/session/claim-publisher", { method: "POST", body: { name: nombre } });
      terminalComandos("#term-prof", r.comandos);
    }
  } catch (e) {
    mensajeIngreso(e.message);
    terminalComandos("#term-prof", e.data?.comandos);
    return;
  }
  sesion.rol = rol;
  guardarSesion();
  entrar();
}

function entrar() {
  clearInterval(sondeoLock);
  mensajeIngreso("");
  document.body.dataset.rol = sesion.rol;
  $("#chip-rol").textContent = `${sesion.rol} · ${sesion.nombre}`;
  $("#vista-profesor").hidden = sesion.rol !== "profesor";
  $("#vista-jugador").hidden = sesion.rol !== "jugador";
  $("#pantalla-ingreso").hidden = true;
  sesion.rol === "profesor" ? iniciarProfesor() : iniciarJugador();
}

/* ====================================================== SSE (Redis SUBSCRIBE -> navegador) */

function detenerSondeoPartida() {
  clearInterval(sondeoPartida);
  sondeoPartida = null;
}

function firmaEstado(snap) {
  if (!snap) return "";
  const d = snap.question?.deadline ?? 0;
  return `${snap.status}:${snap.idx ?? -1}:${d}:${snap.players?.length ?? 0}:${snap.answers_count ?? 0}`;
}

function iniciarSondeoPartida(gameId) {
  const forzado = CFG.state_poll_interval > 0;
  const cada = forzado ? CFG.state_poll_interval : 2;
  if (sondeoPartida) return;
  let ultima = firmaEstado(estado);
  $("#chip-conexion").textContent = "● sondeo HTTP (SSE bloqueado por proxy/túnel)";
  sondeoPartida = setInterval(async () => {
    try {
      const snap = gameId
        ? await api(`/api/games/${gameId}/state`)
        : (await api("/api/games/current")).game;
      if (!snap) return;
      const f = firmaEstado(snap);
      if (f !== ultima) { ultima = f; aplicarInstantanea(snap); }
      else if (snap.server_now) offsetReloj = snap.server_now - Date.now();
    } catch { /* conexión puntual */ }
  }, cada * 1000);
}

function programarFallbackSondeo(gameId) {
  clearTimeout(esperaSse);
  const pollCfg = CFG.state_poll_interval;
  if (pollCfg === 0 && !gameId && sesion.rol !== "profesor") {
    esperaSse = setTimeout(() => { if (!sseActivo) iniciarSondeoPartida(null); }, 3500);
    return;
  }
  const ms = pollCfg > 0 ? 500 : 3500;
  esperaSse = setTimeout(() => { if (!sseActivo) iniciarSondeoPartida(gameId); }, ms);
}

function conectarEventos(gameId) {
  if (fuente && gameIdConectado === gameId && sseActivo && !sondeoPartida) return;
  fuente?.close();
  detenerSondeoPartida();
  sseActivo = false;
  gameIdConectado = gameId;
  programarFallbackSondeo(gameId);
  const term = sesion.rol === "profesor" ? "#term-prof" : "#term-jug";
  const url = `/api/events?role=${sesion.rol}&session_id=${sesion.id}${gameId ? `&game_id=${gameId}` : ""}`;
  fuente = new EventSource(url);
  fuente.onopen = () => {
  if (sseActivo) $("#chip-conexion").textContent = gameId ? `● suscrito a game:${gameId.slice(-6)}:events` : "● suscrito a games:events";
  };
  fuente.onerror = () => { if (!sseActivo) return; $("#chip-conexion").textContent = "● reconectando…"; if (!sondeoPartida) iniciarSondeoPartida(gameId); };
  fuente.addEventListener("subscribed", (e) => {
    sseActivo = true;
    clearTimeout(esperaSse);
    detenerSondeoPartida();
    $("#chip-conexion").textContent = gameId ? `● suscrito a game:${gameId.slice(-6)}:events` : "● suscrito a games:events";
    const { canales } = JSON.parse(e.data);
    terminal(term, `SUBSCRIBE ${canales.join(" ")}`, ...canales.map((c, i) => `${i + 1}) "${c}"`));
  });
  fuente.addEventListener("state_snapshot", (e) => {
    aplicarInstantanea(JSON.parse(e.data));
  });
  const tipos = ["session_reset", "game_created", "player_joined", "player_left", "lobby_cleared", "game_started", "question_started", "answer_received",
                 "question_closed", "ranking_shown", "game_over", "game_cancelled"];
  tipos.forEach((tipo) => fuente.addEventListener(tipo, (e) => {
    const msg = JSON.parse(e.data);
    if (msg.ts) offsetReloj = msg.ts - Date.now();
    if (tipo !== "answer_received") terminal(term, null, '1) "message"', `2) "${tipo}"`, `3) ${e.data.slice(0, 110)}${e.data.length > 110 ? "…" : ""}`);
    aplicarEvento(tipo, msg);
  }));
}

let partidaDescartada = null;   // el Profesor pulsó "Nueva partida" sobre esta partida terminada

function aplicarInstantanea(snap) {
  if (snap.server_now) offsetReloj = snap.server_now - Date.now();
  if (sesion.rol === "profesor" && snap.status === "GAME_OVER" && snap.game_id === partidaDescartada) {
    estado = null; render(); return;
  }
  estado = snap;
  if (sesion.rol === "jugador") espectador = !snap.me && snap.status !== "LOBBY";
  render();
}

function aplicarEvento(tipo, msg) {
  const { game_id, payload } = msg;
  if (tipo === "session_reset") {
    fuente?.close();
    gameIdConectado = null;
    if (sesion.rol === "profesor") {
      partidaDescartada = null;
      estado = null;
      conectarEventos(null);
      render();
      return;
    }
    if (sesion.rol === "jugador") {
      estado = null;
      espectador = false;
      sesion.rol = null;
      guardarSesion();
      delete document.body.dataset.rol;
      $("#vista-jugador").hidden = true;
      $("#vista-profesor").hidden = true;
      $("#pantalla-ingreso").hidden = false;
      mensajeIngreso("La sesión se reinició desde el profesor. Vuelve a elegir «Jugador» cuando haya una sala.");
      $("#inp-nombre").value = sesion.nombre || "";
      actualizarEstadoLock();
      clearInterval(sondeoLock);
      sondeoLock = setInterval(actualizarEstadoLock, 5000);
      conectarEventos(null);
    }
    return;
  }
  if (tipo === "game_created") {
    if (sesion.rol === "profesor") refrescarEstado(game_id);
    else unirseComoJugador(game_id);
    return;
  }
  if (!estado || estado.game_id !== game_id) return;
  switch (tipo) {
    case "player_joined":
      if (Array.isArray(payload.players) && payload.players.length) {
        estado.players = [...payload.players].sort((a, b) => a.order - b.order);
      } else if (!estado.players.some((p) => p.player_id === payload.player_id)) {
        estado.players.push({ player_id: payload.player_id, name: payload.name, avatar: payload.avatar, order: payload.order });
      }
      break;
    case "player_left":
      if (Array.isArray(payload.players)) {
        estado.players = [...payload.players].sort((a, b) => a.order - b.order);
      } else {
        estado.players = estado.players.filter((p) => p.player_id !== payload.player_id);
      }
      break;
    case "lobby_cleared":
      estado.players = Array.isArray(payload.players) ? payload.players : [];
      break;
    case "game_started":
      estado.started_at = Date.now();
      break;
    case "question_started":
      estado.status = "QUESTION_STARTED";
      estado.idx = payload.idx;
      estado.question = payload;
      estado.answers_count = 0;
      estado.answers_confirmed = 0;
      estado.last = null;
      revelacionActiva = null;
      if (estado.me) { estado.me.answer = null; estado.me.answer_confirmed = false; }
      break;
    case "answer_received":
      if (payload.idx === estado.idx) { estado.answers_count = payload.count; estado.answers_confirmed = payload.confirmed_count; }
      break;
    case "question_closed":
      detenerTemporizador();
      estado.status = "QUESTION_CLOSED";
      estado.last = payload;
      revelacionActiva = `${game_id}:${payload.idx ?? estado.idx}`;
      if (sesion.rol === "jugador" && estado.me) refrescarEstado(game_id);
      break;
    case "ranking_shown":
      detenerTemporizador();
      estado.status = "RANKING_SHOWN";
      estado.ranking = payload.top10;
      estado.is_last = payload.is_last;
      if (sesion.rol === "jugador" && estado.me) refrescarEstado(game_id);   // mi puntaje/posición desde el servidor
      break;
    case "game_over":
      estado.status = "GAME_OVER";
      estado.podium = payload.podium;
      estado.ranking = payload.ranking;
      if (sesion.rol === "jugador" && estado.me) refrescarEstado(game_id);
      break;
    case "game_cancelled":
      estado.status = "GAME_OVER";
      estado.cancelled = true;
      estado.podium = [];
      break;
  }
  render();
}

async function refrescarEstado(gameId) {
  try {
    const snap = await api(`/api/games/${gameId}/state`);
    aplicarInstantanea(snap);
    conectarEventos(gameId);
  } catch (e) {
    if (e.status === 404) { estado = null; render(); }
  }
}

function render() {
  sesion.rol === "profesor" ? renderProfesor() : renderJugador();
}

/* ====================================================== Profesor */

let categorias = [];
let preguntasBanco = [];

async function iniciarProfesor() {
  $("#chip-lock").hidden = false;
  iniciarLatido();
  await cargarCategorias();
  await cargarPreguntasBanco();
  const { game } = await api("/api/games/current");
  if (game) aplicarInstantanea(game);
  else render();
  conectarEventos(game?.game_id || null);
}

/* --- Lock: heartbeat cada HEARTBEAT_INTERVAL s; si se pierde, se vuelve al ingreso --- */
function iniciarLatido() {
  let ttl = CFG.publisher_lock_ttl;
  setInterval(() => { $("#lock-ttl").textContent = Math.max(--ttl, 0); }, 1000);
  setInterval(async () => {
    try {
      const r = await api("/api/session/heartbeat", { method: "POST" });
      ttl = r.ttl;
      if (!r.ok) perderLock();
    } catch (e) {
      $("#chip-conexion").textContent = e.data?.degraded ? "● Redis no disponible" : "● sin conexión";
    }
  }, CFG.heartbeat_interval * 1000);
  // Al cerrar la pestaña se libera el lock (si no, expira solo por TTL).
  window.addEventListener("pagehide", () =>
    navigator.sendBeacon("/api/session/release-publisher", new Blob([JSON.stringify({ session_id: sesion.id })], { type: "application/json" })));
}

function perderLock() {
  alert("Se perdió el lock de Profesor (expiró el TTL o lo tomó otra persona).");
  sesion.rol = null; guardarSesion(); location.reload();
}

async function accionProfesor(fn) {
  try {
    const r = await fn();
    terminalComandos("#term-prof", r.comandos);
    if (r.game) { aplicarInstantanea(r.game); conectarEventos(r.game.game_id); }
    return r;
  } catch (e) {
    if (e.data?.lost_lock) return perderLock();
    alert(e.message);
  }
}

/* --- Banco de preguntas --- */
async function cargarCategorias() {
  categorias = await api("/api/categories");
  const pintar = (sel, vacio) => {
    const previo = sel.value;
    sel.innerHTML = categorias.length
      ? categorias.map((c) => `<option value="${c.id}">${esc(c.name)} (${c.questions})</option>`).join("")
      : `<option value="">${vacio}</option>`;
    if ([...sel.options].some((o) => o.value === previo)) sel.value = previo;
  };
  pintar($("#sel-cat-banco"), "Crea una categoría primero");
  pintar($("#sel-cat-partida"), "Sin categorías");
  pintarSubconjunto();
}

async function cargarPreguntasBanco() {
  const cid = $("#sel-cat-banco").value;
  preguntasBanco = cid ? await api(`/api/questions?category_id=${cid}`) : [];
  $("#lista-preguntas").innerHTML = preguntasBanco.length
    ? preguntasBanco.map((q) => `
      <li>
        <div class="q-texto">${esc(q.text)}${q.code_block?.content ? " <em class='q-tag'>code</em>" : ""}</div>
        <small class="q-meta">${q.duration_seconds ? `${q.duration_seconds} s` : `defecto ${CFG.question_duration} s`}</small>
        <div class="q-opciones">${OPCIONES.map((o) => `<span class="${o === q.correct ? "ok" : ""}"><b>${o.toUpperCase()}</b> ${esc(q.options[o])}</span>`).join("")}</div>
        <button class="btn btn-mini" data-borrar="${q.id}" title="Eliminar">✕</button>
      </li>`).join("")
    : `<li class="vacio">${cid ? "Esta categoría no tiene preguntas todavía." : "Crea una categoría y añade preguntas."}</li>`;
}

async function pintarSubconjunto() {
  const cid = $("#sel-cat-partida").value;
  const ul = $("#lista-subconjunto");
  if (!cid) { ul.innerHTML = ""; return; }
  const qs = await api(`/api/questions?category_id=${cid}`).catch(() => []);
  ul.innerHTML = qs.length
    ? qs.map((q) => `<li><label><input type="checkbox" value="${q.id}" checked> ${esc(q.text)}</label></li>`).join("")
    : `<li class="vacio">Sin preguntas en esta categoría.</li>`;
}

$("#form-categoria").onsubmit = async (e) => {
  e.preventDefault();
  await accionProfesor(async () => {
    const c = await api("/api/categories", { method: "POST", body: { name: $("#inp-categoria").value } });
    $("#inp-categoria").value = "";
    terminal("#term-prof", `db.categories.insert_one({name: "${c.name}"})`, `ObjectId('${c.id}')`);
    await cargarCategorias();
    $("#sel-cat-banco").value = c.id;
    await cargarPreguntasBanco();
    return {};
  });
};

$("#btn-borrar-categoria").onclick = async () => {
  const cid = $("#sel-cat-banco").value;
  if (!cid || !confirm("¿Eliminar esta categoría? Solo se permite si no tiene preguntas.")) return;
  await accionProfesor(async () => {
    await api(`/api/categories/${cid}`, { method: "DELETE" });
    await cargarCategorias(); await cargarPreguntasBanco();
    return {};
  });
};

$("#sel-cat-banco").onchange = cargarPreguntasBanco;
$("#sel-cat-partida").onchange = pintarSubconjunto;

$("#form-pregunta").onsubmit = async (e) => {
  e.preventDefault();
  const cid = $("#sel-cat-banco").value;
  if (!cid) return alert("Crea una categoría primero.");
  const correcta = document.querySelector("input[name=correcta]:checked")?.value;
  const codigo = $("#inp-codigo").value.trim();
  const lang = $("#inp-codigo-lang").value.trim();
  const tiempo = $("#inp-tiempo-pregunta").value.trim();
  const body = {
    category_id: cid, text: $("#inp-texto").value, correct: correcta,
    options: Object.fromEntries(OPCIONES.map((o) => [o, $(`#inp-op-${o}`).value])),
  };
  if (tiempo) body.duration_seconds = tiempo;
  if (codigo) body.code_block = lang ? { content: codigo, language: lang } : { content: codigo };
  await accionProfesor(async () => {
    const q = await api("/api/questions", { method: "POST", body });
    terminal("#term-prof", `db.questions.insert_one({text: "${q.text.slice(0, 30)}…", correct: "${q.correct}"})`, `ObjectId('${q.id}')`);
    $("#form-pregunta").reset();
    $("#inp-texto").focus();
    await cargarCategorias(); await cargarPreguntasBanco();
    return {};
  });
};

$("#lista-preguntas").onclick = async (e) => {
  const id = e.target.dataset.borrar;
  if (!id || !confirm("¿Eliminar esta pregunta?")) return;
  await accionProfesor(async () => {
    await api(`/api/questions/${id}`, { method: "DELETE" });
    await cargarCategorias(); await cargarPreguntasBanco();
    return {};
  });
};

/* --- Control de la partida --- */
$("#form-partida").onsubmit = async (e) => {
  e.preventDefault();
  const marcadas = [...document.querySelectorAll("#lista-subconjunto input:checked")].map((i) => i.value);
  const todas = document.querySelectorAll("#lista-subconjunto input").length;
  const usarSubconjunto = marcadas.length > 0 && marcadas.length < todas;
  const rawCant = $("#inp-cantidad-preguntas").value.trim();
  let question_count = null;
  if (!usarSubconjunto && rawCant !== "" && rawCant !== "0") {
    question_count = parseInt(rawCant, 10);
    if (!Number.isInteger(question_count) || question_count < 1) {
      alert("Indica un número entero mayor que 0, o deja vacío/0 para usar todas las preguntas.");
      return;
    }
  }
  await accionProfesor(() => api("/api/games", { method: "POST", body: {
    category_id: $("#sel-cat-partida").value,
    question_ids: usarSubconjunto ? marcadas : null,
    question_count: usarSubconjunto ? null : question_count,
  } }));
};
$("#btn-lanzar").onclick = () => accionProfesor(() => api(`/api/games/${estado.game_id}/start`, { method: "POST" }));
$("#btn-siguiente").onclick = () => accionProfesor(() => api(`/api/games/${estado.game_id}/next`, { method: "POST" }));
$("#btn-cancelar-lobby").onclick = () => cancelarPartida();
$("#btn-vaciar-sala").onclick = () => {
  if (confirm("¿Vaciar la sala? Se quitarán todos de la lista y tendrán que volver a unirse con su nombre.")) {
    accionProfesor(() => api(`/api/games/${estado.game_id}/clear-lobby`, { method: "POST" }));
  }
};
document.querySelectorAll(".btn-cancelar").forEach((b) => (b.onclick = cancelarPartida));
function cancelarPartida() {
  if (confirm("¿Cancelar la partida? Todos volverán a la vista inicial.")) {
    accionProfesor(() => api(`/api/games/${estado.game_id}/cancel`, { method: "POST" }));
  }
}
$("#btn-nueva").onclick = () => { partidaDescartada = estado?.game_id; estado = null; render(); cargarCategorias(); };

$("#btn-reiniciar-sesion").onclick = () => {
  if (!confirm("¿Reiniciar la sesión? Se elimina la partida en Redis, todos los jugadores vuelven a la pantalla inicial y deberás crear una sala nueva.")) return;
  accionProfesor(async () => {
    const r = await api("/api/games/reset", { method: "POST" });
    partidaDescartada = null;
    estado = null;
    conectarEventos(null);
    render();
    return r;
  });
};

const ETIQUETAS = { LOBBY: "Sala abierta", QUESTION_STARTED: "Pregunta abierta", QUESTION_CLOSED: "Resultado",
                    RANKING_SHOWN: "Ranking", GAME_OVER: "Finalizada" };

function renderProfesor() {
  const s = estado?.status ?? null;
  const mostrar = (id, cond) => ($(id).hidden = !cond);
  mostrar("#prof-crear", !estado);
  mostrar("#prof-lobby", s === "LOBBY");
  mostrar("#prof-pregunta", s === "QUESTION_STARTED");
  mostrar("#prof-revelacion", s === "QUESTION_CLOSED");
  mostrar("#prof-ranking", s === "RANKING_SHOWN");
  mostrar("#prof-final", s === "GAME_OVER");
  $("#prof-estado-chip").textContent = estado ? ETIQUETAS[s] : "Sin partida";
  $("#prof-estado-chip").dataset.estado = s || "";
  if ($("#prof-partida-ayuda-tecnica")) $("#prof-partida-ayuda-tecnica").hidden = s === "QUESTION_STARTED";
  if (!estado) {
    /* Sin partida: ocultar secciones dejó el DOM con datos viejos; vaciar para no ver jugadores/ranking anteriores. */
    $("#prof-jugadores").innerHTML = "";
    $("#prof-lobby-n").textContent = "0";
    $("#prof-rank-lista").innerHTML = "";
    $("#prof-podio").innerHTML = "";
    $("#prof-final-lista").innerHTML = "";
    $("#prof-opciones").innerHTML = "";
    $("#prof-enunciado").innerHTML = "";
    $("#prof-rev-enunciado").innerHTML = "";
    $("#prof-rev-opciones").innerHTML = "";
    $("#prof-partida-ayuda-tecnica").hidden = false;
    return;
  }

  if (s === "LOBBY") {
    $("#prof-lobby-titulo").textContent = estado.title;
    $("#prof-lobby-detalle").textContent = `${estado.total_questions} preguntas · tiempo por pregunta (defecto ${CFG.question_duration} s)`;
    $("#prof-lobby-n").textContent = estado.players.length;
    $("#prof-jugadores").innerHTML = htmlJugadores(estado.players);
    $("#btn-lanzar").disabled = estado.players.length === 0;
  }
  if (s === "QUESTION_STARTED") {
    const q = estado.question;
    $("#prof-progreso").textContent = `Pregunta ${q.idx + 1} de ${estado.total_questions}`;
    const pend = estado.answers_count - (estado.answers_confirmed || 0);
    $("#prof-conteo").textContent = `${estado.answers_count} / ${estado.players.length} respondieron · ${estado.answers_confirmed || 0} confirmadas${pend ? ` · ${pend} pendientes` : ""}`;
    $("#prof-enunciado").innerHTML = htmlEnunciado(q);
    $("#prof-opciones").innerHTML = htmlOpciones(q.options);
    const clave = `${estado.game_id}:${q.idx}`;
    if ($("#prof-pregunta").dataset.clave !== clave) {
      $("#prof-pregunta").dataset.clave = clave;
      iniciarTemporizador(q.deadline, q.duration, "#prof-barra", "#prof-segundos");
    }
  }
  if (s === "QUESTION_CLOSED") {
    const q = estado.question;
    const l = estado.last;
    const correcta = l?.correct;
    $("#prof-rev-enunciado").innerHTML = htmlEnunciado(q);
    $("#prof-rev-opciones").innerHTML = htmlOpciones(q.options, { correcta, conteos: l?.counts });
    $("#prof-rev-msg").textContent = correcta
      ? `Respuesta correcta: «${correcta.toUpperCase()}» · mostrando ranking en unos segundos…`
      : "";
  }
  if (s === "RANKING_SHOWN") {
    const q = estado.question, l = estado.last;
    $("#prof-rank-progreso").textContent = `Ronda ${q.idx + 1} de ${estado.total_questions}`;
    $("#prof-rank-conteo").textContent = l ? `${l.answered} / ${l.players_count} respondieron` : "";
    $("#prof-rank-lista").innerHTML = htmlRanking(estado.ranking);
    const ultima = estado.idx + 1 >= estado.total_questions;
    $("#btn-siguiente").textContent = ultima ? "Ver podio 🏆" : "Siguiente pregunta ▶";
    $("#btn-siguiente").disabled = false;
  }
  if (s === "GAME_OVER") {
    $("#prof-final-titulo").textContent = estado.cancelled ? `${estado.title} · cancelada` : `${estado.title} · ¡Podio!`;
    $("#prof-final-detalle").textContent = `${estado.category.name} · ${estado.players.length} jugadores · guardado en MongoDB (games)`;
    $("#prof-podio").innerHTML = htmlPodio(estado.podium);
    pintarResto("#prof-final-lista", estado);
    celebrarPodio();
  }
}

/* ====================================================== Jugador */

function bloquearCopiaJugador() {
  const vista = $("#vista-jugador");
  if (!vista || vista.dataset.antirobo) return;
  vista.dataset.antirobo = "1";
  const freno = (e) => {
    if (e.target.closest(".terminal, .btn-terminal")) return;
    e.preventDefault();
  };
  vista.addEventListener("copy", freno);
  vista.addEventListener("cut", freno);
  vista.addEventListener("contextmenu", freno);
}

async function iniciarJugador() {
  bloquearCopiaJugador();
  $("#jug-avatar").innerHTML = "";
  let game = null;
  try { ({ game } = await api("/api/games/current")); } catch (e) { /* sin Redis: se muestra espera */ }
  if (!game) { estado = null; render(); conectarEventos(null); return; }
  if (game.me) { aplicarInstantanea(game); conectarEventos(game.game_id); return; }     // reconexión
  if (game.status === "LOBBY") return unirseComoJugador(game.game_id);
  espectador = game.status !== "GAME_OVER";                                               // llegó tarde
  aplicarInstantanea(game);
  conectarEventos(game.game_id);
}

async function unirseComoJugador(gameId) {
  try {
    const r = await api(`/api/games/${gameId}/join`, { method: "POST", body: { name: sesion.nombre } });
    espectador = false;
    terminal("#term-jug", `HSET game:${gameId.slice(-6)}:players ${sesion.id.slice(0, 8)}… {name:"${sesion.nombre}"}`, "(integer) 1");
    aplicarInstantanea(r.game);
    conectarEventos(gameId);
  } catch (e) {
    if (e.data?.duplicate) {                       // nombre tomado: volver al ingreso con el aviso
      fuente?.close();
      sesion.rol = null; guardarSesion();
      delete document.body.dataset.rol;
      $("#vista-jugador").hidden = true;
      mensajeIngreso(e.message);
      sondeoLock = setInterval(actualizarEstadoLock, 5000);
      return;
    }
    if (e.data?.spectator || e.status === 409) {   // ya empezó: espectador
      espectador = true;
      await refrescarEstado(gameId);
      return;
    }
    alert(e.message);
  }
}

// Si el jugador cierra la pestaña estando en el LOBBY, sale de la sala (durante la partida se conserva para reconectar).
window.addEventListener("pagehide", () => {
  if (sesion.rol === "jugador" && estado?.status === "LOBBY" && estado.me) {
    navigator.sendBeacon(`/api/games/${estado.game_id}/leave`, new Blob([JSON.stringify({ session_id: sesion.id })], { type: "application/json" }));
  }
});

/* Respuesta en dos pasos: tocar una opción la deja *pendiente* (se puede cambiar o retirar con "No");
   "Sí" la confirma y bloquea. Si el tiempo acaba con una pendiente, el servidor la cuenta igual. */
let respuestaEnVuelo = 0;
const CAP_ANTI_TOQUE_MS = 450;

function activarCapaConfirmacion() {
  document.querySelectorAll("#jug-opciones .opcion-cap").forEach((cap) => {
    cap.classList.add("cap-sin-clic");
    window.setTimeout(() => cap.classList.remove("cap-sin-clic"), CAP_ANTI_TOQUE_MS);
  });
}
function actualizarRespuestaLocal(opcion, confirmar) {
  if (!estado?.me) return;
  if (opcion === null) {
    estado.me.answer = null;
    estado.me.answer_confirmed = false;
  } else {
    estado.me.answer = opcion;
    estado.me.answer_confirmed = !!confirmar;
  }
  render();
}

async function enviarRespuesta(opcion, confirmar = false) {
  if (!estado?.question || !estado.me || estado.me.answer_confirmed) return;
  if (ahoraServidor() > estado.question.deadline) return;
  const idx = estado.question.idx;
  const antes = { answer: estado.me.answer, confirmed: estado.me.answer_confirmed };
  actualizarRespuestaLocal(opcion, confirmar);

  const vuelo = ++respuestaEnVuelo;
  try {
    const r = await api(`/api/games/${estado.game_id}/answer`, { method: "POST", body: { idx, option: opcion, confirm: confirmar } });
    if (vuelo !== respuestaEnVuelo) return;
    estado.me.answer = r.option;
    estado.me.answer_confirmed = confirmar && !!r.confirmed;
    const cmd = opcion === null ? `HDEL game:…:answers:${idx} ${sesion.id.slice(0, 8)}…`
      : `HSET game:…:answers:${idx} ${sesion.id.slice(0, 8)}… {option:"${opcion}", confirmed:${confirmar}}`;
    terminal("#term-jug", cmd, opcion === null ? "(integer) 1" : "(integer) 0");
    render();
  } catch (e) {
    if (vuelo !== respuestaEnVuelo) return;
    if (e.data?.already) {
      estado.me.answer = opcion;
      estado.me.answer_confirmed = true;
    } else {
      estado.me.answer = antes.answer;
      estado.me.answer_confirmed = antes.confirmed;
      $("#jug-estado-respuesta").textContent = e.message;
      $("#jug-estado-respuesta").className = "estado-respuesta error";
    }
    terminal("#term-jug", `HSET game:…:answers:${idx} …`, `(error) ${e.message}`);
    render();
  }
}
$("#jug-opciones").onclick = (e) => {
  const capBtn = e.target.closest("[data-confirm]");
  if (capBtn) {
    const capa = capBtn.closest(".opcion-cap");
    if (capa?.classList.contains("cap-sin-clic")) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    if (capBtn.dataset.confirm === "si") enviarRespuesta(capBtn.dataset.op, true);
    else enviarRespuesta(null, false);
    return;
  }
  if (e.target.closest(".opcion-cap")) return;
  const b = e.target.closest("button.opcion[data-op]");
  if (b && !b.disabled) enviarRespuesta(b.dataset.op, false);
};

function renderJugador() {
  const s = estado?.status ?? null;
  const me = estado?.me || null;
  const mostrar = (id, cond) => ($(id).hidden = !cond);
  mostrar("#jug-espera", !estado);
  mostrar("#jug-lobby", s === "LOBBY");
  mostrar("#jug-pregunta", s === "QUESTION_STARTED");
  mostrar("#jug-revelacion", s === "QUESTION_CLOSED");
  mostrar("#jug-ranking", s === "RANKING_SHOWN");
  mostrar("#jug-final", s === "GAME_OVER");
  mostrar("#jug-espectador", espectador && !!estado && s !== "GAME_OVER");
  $("#jug-avatar").innerHTML = me ? avatar(me.avatar) : "";
  $("#jug-estado-chip").textContent = estado ? ETIQUETAS[s] : "";
  $("#jug-estado-chip").dataset.estado = s || "";

  if (!estado) {
    $("#jug-titulo").textContent = "Sala de juego";
    $("#jug-subtitulo").textContent = `Hola ${sesion.nombre}. Esperando a que el Profesor abra una sala…`;
    $("#jug-subtitulo").hidden = false;
    $("#jug-jugadores").innerHTML = "";
    $("#jug-lobby-n").textContent = "0";
    $("#jug-rank-lista").innerHTML = "";
    $("#jug-final-lista").innerHTML = "";
    $("#jug-podio").innerHTML = "";
    $("#jug-opciones").innerHTML = "";
    $("#jug-estado-respuesta").textContent = "";
    return;
  }
  $("#jug-titulo").textContent = estado.title;
  $("#jug-subtitulo").textContent = `${estado.category.name} · ${estado.total_questions} preguntas · ${me ? `juegas como ${me.name}` : "espectador"}`;
  $("#jug-subtitulo").hidden = s === "QUESTION_STARTED";

  if (s === "LOBBY") {
    $("#jug-lobby-n").textContent = estado.players.length;
    $("#jug-jugadores").innerHTML = htmlJugadores(estado.players, sesion.id);
  }
  if (s === "QUESTION_STARTED") {
    const q = estado.question;
    $("#jug-progreso").textContent = `Pregunta ${q.idx + 1} de ${estado.total_questions}`;
    $("#jug-mi-puntaje").textContent = me ? `${me.score} pts` : "";
    $("#jug-enunciado").innerHTML = htmlEnunciado(q);
    const elegida = me?.answer || null;
    const confirmada = !!me?.answer_confirmed;
    const cerrada = ahoraServidor() > q.deadline;
    const bloqueado = !me || confirmada || cerrada;
    const pendiente = !!elegida && !confirmada && !cerrada;
    $("#jug-opciones").innerHTML = htmlOpciones(q.options, { elegida, clicable: !bloqueado, confirmarPendiente: pendiente });
    if (pendiente) activarCapaConfirmacion();
    if (bloqueado) document.querySelectorAll("#jug-opciones .opcion").forEach((b) => (b.disabled = true));

    const est = $("#jug-estado-respuesta");
    const letra = elegida ? elegida.toUpperCase() : "";
    if (!me) { est.textContent = "Solo miras: no estás inscrito en esta partida."; est.className = "estado-respuesta"; }
    else if (confirmada) { est.textContent = `✔ Respuesta «${letra}» confirmada. Ya no se puede cambiar.`; est.className = "estado-respuesta ok"; }
    else if (cerrada && elegida) { est.textContent = `⏱ Tiempo agotado: se registró tu selección «${letra}».`; est.className = "estado-respuesta ok"; }
    else if (cerrada) { est.textContent = "⏱ Tiempo agotado sin respuesta."; est.className = "estado-respuesta error"; }
    else if (elegida) { est.textContent = "Confirma en el recuadro elegido o toca otra opción para cambiar."; est.className = "estado-respuesta"; }
    else { est.textContent = "Elige una opción antes de que acabe el tiempo."; est.className = "estado-respuesta"; }

    const clave = `${estado.game_id}:${q.idx}`;
    if ($("#jug-pregunta").dataset.clave !== clave) {
      $("#jug-pregunta").dataset.clave = clave;
      iniciarTemporizador(q.deadline, q.duration, "#jug-barra", "#jug-segundos", () => render());
    }
  }
  if (s === "QUESTION_CLOSED") {
    const l = estado.last;
    const correcta = l?.correct;
    const mi = me?.answer;
    const acerto = mi && correcta && mi === correcta;
    const banner = $("#jug-rev-banner");
    banner.hidden = false;
    banner.classList.remove("acierto", "fallo");
    banner.classList.add(acerto ? "acierto" : "fallo");
    $("#jug-rev-icono").textContent = acerto ? "🎉" : "✗";
    $("#jug-rev-titulo").textContent = acerto ? "¡Correcto!" : "Incorrecto";
    if (!mi) {
      $("#jug-rev-detalle").textContent = correcta
        ? `No respondiste. La respuesta era «${correcta.toUpperCase()}».`
        : "No respondiste a esta pregunta.";
    } else if (acerto) {
      const pts = me?.last_points;
      $("#jug-rev-detalle").textContent = pts != null ? `+${pts} pts` : `Elegiste «${mi.toUpperCase()}».`;
    } else {
      $("#jug-rev-detalle").textContent = correcta
        ? `Tu respuesta: «${mi.toUpperCase()}» · correcta: «${correcta.toUpperCase()}».`
        : `Tu respuesta fue «${mi.toUpperCase()}».`;
    }
    const claveRev = `${estado.game_id}:${estado.idx}`;
    if (revelacionActiva === claveRev && acerto) {
      setTimeout(() => confettiSuave($("#jug-revelacion")), 60);
    }
  }
  if (s === "RANKING_SHOWN") {
    $("#jug-rev-banner").hidden = true;
    $("#jug-rank-lista").innerHTML = htmlRanking(estado.ranking, sesion.id);
    $("#jug-mi-posicion").textContent = me?.position ? `Tu puesto: ${me.position}.° · ${me.score} pts` : "";
    const ultima = estado.idx + 1 >= estado.total_questions;
    $("#jug-rank-ayuda").textContent = ultima ? "Última pregunta: el Profesor mostrará el podio." : "Esperando a que el Profesor lance la siguiente pregunta…";
  }
  if (s === "GAME_OVER") {
    $("#jug-final-titulo").textContent = estado.cancelled ? "Partida cancelada" : "🏆 ¡Partida terminada!";
    $("#jug-final-detalle").textContent = me?.position ? `Terminaste en el puesto ${me.position}.° con ${me.score} pts` : espectador ? "Entrarás en la próxima partida." : "";
    $("#jug-podio").innerHTML = htmlPodio(estado.podium, sesion.id);
    pintarResto("#jug-final-lista", estado, sesion.id);
    celebrarPodio();
  }
}

/* ====================================================== Arranque */

(async function arrancar() {
  await cargarConfig().catch(() => {});
  alternarConsola("#toggle-term-prof", "#term-prof");
  alternarConsola("#toggle-term-jug", "#term-jug");
  document.querySelectorAll(".rol-opcion").forEach((b) => { b.onclick = () => elegirRol(b.dataset.rol); });
  $("#inp-nombre").value = sesion.nombre || "";
  $("#inp-nombre").onkeydown = (e) => { if (e.key === "Enter") elegirRol("jugador"); };

  $("#btn-salir").onclick = async () => {
    if (sesion.rol === "profesor") await api("/api/session/release-publisher", { method: "POST" }).catch(() => {});
    if (sesion.rol === "jugador" && estado?.status === "LOBBY") await api(`/api/games/${estado.game_id}/leave`, { method: "POST" }).catch(() => {});
    sesion.rol = null; guardarSesion(); location.reload();
  };

  if (sesion.rol === "profesor") {                 // recarga de la pestaña del Profesor: el lock es reentrante
    try {
      const r = await api("/api/session/claim-publisher", { method: "POST", body: { name: sesion.nombre } });
      terminalComandos("#term-prof", r.comandos);
      return entrar();
    } catch (e) { sesion.rol = null; guardarSesion(); mensajeIngreso(e.message); }
  } else if (sesion.rol === "jugador") {
    return entrar();
  }
  actualizarEstadoLock();
  sondeoLock = setInterval(actualizarEstadoLock, 5000);
})();
