// TP-17.3 — Vista previa en vivo de la estructura del torneo en el alta.
// Escucha cambios de cupos / tipo / forzar-3 / equipos-por-zona y consulta el
// endpoint (fuente de verdad única: torneos.formats.describir_estructura) para
// repintar el panel. Mejora progresiva: sin JS, el panel ya viene renderizado
// server-side con los cupos iniciales.
(function () {
  'use strict';

  var form = document.querySelector('form[data-preview-url]');
  var panel = document.getElementById('preview-estructura');
  if (!form || !panel) return;

  var url = form.getAttribute('data-preview-url');
  var elCupos = document.getElementById('id_cupos_totales');
  var elTipo = document.getElementById('id_tipo_torneo');
  var elForzar = document.getElementById('id_forzar_grupos_de_3');
  var elEpg = document.getElementById('id_equipos_por_grupo');
  var elBtnOrg = document.getElementById('btn-usar-org');

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function render(data) {
    var warn = data.nivel === 'warn';
    panel.className =
      'rounded-2xl p-4 md:p-5 border ' +
      (warn ? 'border-error/40 bg-error/10' : 'border-primary/35 bg-primary/10');

    var top = panel.querySelector('.uppercase') || panel.firstElementChild;
    if (top) {
      top.className =
        'flex items-center gap-2 text-xs uppercase tracking-wide font-bold mb-2 ' +
        (warn ? 'text-error' : 'text-primary');
    }

    var title = document.getElementById('pv-title');
    if (title) title.textContent = data.titulo;

    var flow = document.getElementById('pv-flow');
    if (flow) {
      var parts = [];
      (data.flujo || []).forEach(function (paso, i) {
        if (i > 0) parts.push('<span class="text-primary font-black">&rarr;</span>');
        parts.push(
          '<span class="badge badge-lg bg-base-100 dark:bg-base-300 border-base-300">' +
            esc(paso) +
            '</span>'
        );
      });
      flow.innerHTML = parts.join('');
    }

    var zonas = document.getElementById('pv-zonas');
    if (zonas) {
      zonas.innerHTML = (data.zonas || [])
        .map(function (z) {
          return (
            '<span class="text-xs px-2 py-0.5 rounded-md bg-base-100 dark:bg-base-300 border border-base-300">Zona ' +
            esc(z[0]) +
            ': ' +
            esc(z[1]) +
            '</span>'
          );
        })
        .join('');
    }

    var note = document.getElementById('pv-note');
    if (note) note.textContent = data.mensaje || '';
  }

  function actualizar() {
    var n = elCupos ? elCupos.value : '';
    var tipo = elTipo ? elTipo.value : 'G';
    var forzar3 = elForzar && elForzar.checked ? '1' : '0';
    var epg = elEpg ? elEpg.value : '3';
    var qs =
      '?n=' + encodeURIComponent(n) +
      '&tipo=' + encodeURIComponent(tipo) +
      '&forzar3=' + forzar3 +
      '&epg=' + encodeURIComponent(epg);

    fetch(url + qs, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { if (data) render(data); })
      .catch(function () { /* sin red: queda el render server-side */ });
  }

  var timer = null;
  function debounced() {
    clearTimeout(timer);
    timer = setTimeout(actualizar, 220);
  }

  [elCupos, elEpg].forEach(function (el) {
    if (el) el.addEventListener('input', debounced);
  });
  [elTipo, elForzar].forEach(function (el) {
    if (el) el.addEventListener('change', actualizar);
  });

  // TP-17.4 — botón "usar datos de mi organización"
  if (elBtnOrg) {
    elBtnOrg.addEventListener('click', function () {
      var map = {
        id_sede_nombre: elBtnOrg.getAttribute('data-sede'),
        id_ciudad: elBtnOrg.getAttribute('data-ciudad'),
        id_sede_direccion: elBtnOrg.getAttribute('data-direccion'),
      };
      Object.keys(map).forEach(function (id) {
        var el = document.getElementById(id);
        if (el && map[id]) el.value = map[id];
      });
      var note = document.getElementById('org-note');
      if (note) note.classList.remove('hidden');
    });
  }
})();
