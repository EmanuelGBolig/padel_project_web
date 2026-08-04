// Placas para redes: genera el QR y exporta la placa a PNG 1080×1920 (html2canvas,
// scale 3 sobre un nodo base de 360px).
//
// Clave: la imagen se PRE-GENERA al cargar y se cachea, así al tocar "Compartir"
// llamamos a navigator.share() dentro del gesto del usuario (si no, se pierde la
// "activación" mientras html2canvas trabaja y el selector de redes no abre).
(function () {
  'use strict';

  var qrEl = document.getElementById('qr');
  var shareUrl = (qrEl && qrEl.getAttribute('data-url')) || 'https://todopadel.club';

  // --- QR real ---
  if (qrEl && typeof qrcode === 'function') {
    try {
      var qr = qrcode(0, 'M');
      qr.addData(shareUrl);
      qr.make();
      qrEl.innerHTML = qr.createImgTag(3, 0);
    } catch (e) { /* sin QR no rompe la placa */ }
  }

  var placa = document.getElementById('placa');
  var btnShare = document.getElementById('btn-share');
  var btnDownload = document.getElementById('btn-download');

  var cachedFile = null;     // File listo para compartir/descargar
  var building = null;       // promesa en curso

  function _render() {
    if (typeof html2canvas !== 'function') {
      return Promise.reject(new Error('No se cargó el generador de imagen. Revisá tu conexión y recargá.'));
    }
    var w = placa.offsetWidth || 360;
    var h = placa.offsetHeight || 640;
    return html2canvas(placa, {
      scale: 3, backgroundColor: '#15191E', logging: false,
      width: w, height: h, windowWidth: w, windowHeight: h, imageTimeout: 8000,
    }).then(function (canvas) {
      return new Promise(function (resolve, reject) {
        try {
          canvas.toBlob(function (b) {
            b ? resolve(new File([b], 'todopadel-placa.png', { type: 'image/png' }))
              : reject(new Error('No se pudo crear el PNG.'));
          }, 'image/png');
        } catch (e) { reject(e); }
      });
    });
  }

  function buildFile() {
    if (cachedFile) return Promise.resolve(cachedFile);
    if (building) return building;
    building = _render().then(function (file) {
      cachedFile = file;
      building = null;
      return file;
    }).catch(function (e) {
      building = null;
      throw e;
    });
    return building;
  }

  function descargar(file) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(file);
    a.download = 'todopadel-placa.png';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
  }

  function puedeCompartirArchivo(file) {
    return !!(navigator.canShare && navigator.canShare({ files: [file] }));
  }

  var esMobile = (navigator.maxTouchPoints || 0) > 0
    || /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || '');

  // Pre-generar apenas cargue todo (imágenes incluidas), para tener el File listo.
  window.addEventListener('load', function () {
    setTimeout(function () { buildFile().catch(function () {}); }, 300);
  });

  // --- COMPARTIR ---
  if (btnShare) {
    btnShare.addEventListener('click', function () {
      // En desktop no tiene sentido "compartir a IG": descargamos el PNG.
      if (!esMobile) {
        var t = btnShare.textContent;
        btnShare.disabled = true; btnShare.textContent = 'Generando…';
        buildFile().then(descargar).catch(function (e) {
          alert('No se pudo generar la imagen.\n' + (e && e.message ? e.message : e));
        }).then(function () { btnShare.disabled = false; btnShare.textContent = t; });
        return;
      }
      // 1) Si ya está listo, compartir YA (dentro del gesto) -> abre el selector.
      if (cachedFile && puedeCompartirArchivo(cachedFile)) {
        navigator.share({ files: [cachedFile], title: 'TodoPadel' })
          .catch(function (e) { if (!e || e.name !== 'AbortError') descargar(cachedFile); });
        return;
      }
      // 2) Si no está listo, generar y después decidir.
      var txt = btnShare.textContent;
      btnShare.disabled = true; btnShare.textContent = 'Generando…';
      buildFile().then(function (file) {
        if (puedeCompartirArchivo(file)) {
          return navigator.share({ files: [file], title: 'TodoPadel' })
            .catch(function (e) { if (!e || e.name !== 'AbortError') descargar(file); });
        }
        // El navegador no comparte archivos (típico en desktop): descargar el PNG.
        descargar(file);
      }).catch(function (e) {
        alert('No se pudo generar la imagen.\n' + (e && e.message ? e.message : e));
      }).then(function () {
        btnShare.disabled = false; btnShare.textContent = txt;
      });
    });
  }

  // --- DESCARGAR (siempre baja el PNG) ---
  if (btnDownload) {
    btnDownload.addEventListener('click', function () {
      var txt = btnDownload.textContent;
      btnDownload.disabled = true; btnDownload.textContent = 'Generando…';
      buildFile().then(descargar).catch(function (e) {
        alert('No se pudo generar la imagen.\n' + (e && e.message ? e.message : e));
      }).then(function () {
        btnDownload.disabled = false; btnDownload.textContent = txt;
      });
    });
  }
})();
