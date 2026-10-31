/* Buscador: panel exacto en memoria (como ILIKE) y panel por significado en Chroma. */

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

function idiomasElegidos() {
  return [...document.querySelectorAll(".chk-idioma:checked")].map((c) => c.value);
}

async function leer(url, opciones) {
  const r = await fetch(url, opciones);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || "No se pudo completar la operación.");
  return data;
}

function aviso(texto) {
  const el = $("#aviso");
  el.hidden = !texto;
  el.textContent = texto || "";
}

async function actualizarEstado() {
  try {
    const e = await leer("/api/estado");
    const chip = $("#chip-conexion");
    $("#txt-modelo").textContent = e.modelo || "";
    if (e.conectado) {
      chip.textContent = "● Conectado a Chroma";
      chip.className = "chip ok";
      $("#txt-registros").textContent = e.registros
        ? `${e.registros} registros`
        : "0 registros · pulsa Cargar datos";
      aviso(e.error || "");
    } else {
      chip.textContent = "● Sin conexión";
      chip.className = "chip mal";
      $("#txt-registros").textContent = "sin registros";
      aviso(e.error || "No se pudo conectar con Chroma.");
    }
  } catch (err) {
    $("#chip-conexion").textContent = "● Sin conexión";
    $("#chip-conexion").className = "chip mal";
    aviso(err.message);
  }
}

function fila(r, conSimilitud) {
  const sim = conSimilitud ? `
    <div class="sim">
      <span class="barra"><i style="width:${Number(r.similitud) || 0}%"></i></span>
      <b>${esc(r.similitud)}%</b>
    </div>` : "";
  return `<li class="item">
    <div class="item-top">
      <span class="idioma lang-${esc(r.idioma)}">${esc((r.idioma || "").toUpperCase())}</span>
      <span class="texto">${esc(r.texto)}</span>
      <span class="categoria">${esc(r.categoria)}</span>
    </div>
    ${sim}
  </li>`;
}

function pintar(data, q) {
  $("#sql").textContent = `WHERE texto ILIKE '%${q}%'`;
  $("#lista-exacta").innerHTML = data.exacta.length
    ? data.exacta.map((r) => fila(r, false)).join("")
    : `<li class="vacio">Sin resultados</li>`;

  const signo = $("#lista-significado");
  if (data.error) signo.innerHTML = `<li class="error">${esc(data.error)}</li>`;
  else if (!idiomasElegidos().length) signo.innerHTML = `<li class="vacio">Elige al menos un idioma</li>`;
  else if (!data.significado.length) signo.innerHTML = `<li class="vacio">Sin resultados</li>`;
  else signo.innerHTML = data.significado.map((r) => fila(r, true)).join("");
}

async function buscar() {
  const q = $("#q").value.trim();
  if (!q) return;
  $("#btn-buscar").disabled = true;
  try {
    const idiomas = idiomasElegidos().join(",");
    const data = await leer(`/api/buscar?q=${encodeURIComponent(q)}&n=8&idiomas=${idiomas}`);
    pintar(data, q);
    aviso(data.error || "");
  } catch (err) {
    aviso(err.message);
  } finally {
    $("#btn-buscar").disabled = false;
  }
}

async function operacion(url, boton, texto) {
  const original = boton.textContent;
  boton.disabled = true;
  boton.textContent = texto;
  try {
    await leer(url, { method: "POST" });
    await actualizarEstado();
    if ($("#q").value.trim()) await buscar();
  } catch (err) {
    aviso(err.message);
  } finally {
    boton.disabled = false;
    boton.textContent = original;
  }
}

$("#form-buscar").onsubmit = (e) => { e.preventDefault(); buscar(); };
$("#q").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    buscar();
  }
});

document.querySelectorAll(".ejemplo").forEach((b) => {
  b.onclick = () => { $("#q").value = b.textContent.trim(); buscar(); };
});

document.querySelectorAll(".chk-idioma").forEach((c) => {
  c.onchange = () => { if ($("#q").value.trim()) buscar(); };
});

$("#btn-cargar").onclick = () => operacion("/api/cargar", $("#btn-cargar"), "Cargando…");

$("#btn-reiniciar").onclick = () => {
  if (!confirm("Se borra la colección y se vuelve a cargar. ¿Continuar?")) return;
  operacion("/api/reiniciar", $("#btn-reiniciar"), "Reiniciando…");
};

actualizarEstado();
