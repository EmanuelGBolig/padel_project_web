// Placas para redes: genera el QR y exporta la placa a PNG 1080×1920 (html2canvas,
// scale 3 sobre un nodo base de 360px). Compartir nativo en mobile (Web Share API)
// con fallback a descarga. Robusto: si algo falla, resetea el botón y avisa.
(function () {
  'use strict';

  // --- QR real apuntando a la URL del torneo / app ---
  var qrEl = document.getElementById('qr');
  if (qrEl && typeof qrcode === 'function') {
    var url = qrEl.getAttribute('data-url') || 'https://todopadel.club';
    try {
      var qr = qrcode(0, 'M');
      qr.addData(url);
      qr.make();
      qrEl.innerHTML = qr.createImgTag(3, 0);
    } catch (e) { /* sin QR no rompe la placa */ }
  }

  var placa = document.getElementById('placa');
  var btnShare = document.getElementById('btn-share');
  var btnDownload = document.getElementById('btn-download');

  function exportarBlob() {
    if (typeof html2canvas !== 'function') {
      return Promise.reject(new Error('No se cargó el generador de imagen. Revisá tu conexión y recargá la página.'));
    }
    var w = placa.offsetWidth || 360;
    var h = placa.offsetHeight || 640;
    return html2canvas(placa, {
      scale: 3,                 // 360px * 3 = 1080px -> 1080×1920
      backgroundColor: '#15191E',
      // Sin useCORS: las imágenes (logo, QR) son del mismo origen; forzar crossorigin
      // las hacía fallar y colgaba la captura ~15s.
      logging: false,
      width: w, height: h, windowWidth: w, windowHeight: h,
      imageTimeout: 8000,
    }).then(function (canvas) {
      return new Promise(function (resolve, reject) {
        try {
          canvas.toBlob(function (b) {
            b ? resolve(b) : reject(new Error('No se pudo crear el PNG.'));
          }, 'image/png');
        } catch (e) { reject(e); }
      });
    });
  }

  function descargar(blob) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'todopadel-placa.png';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
  }

  function conEstado(btn, fn) {
    if (!btn) return;
    btn.addEventListener('click', function () {
      var txt = btn.textContent;
      btn.disabled = true;
      btn.textContent = 'Generando…';
      Promise.resolve()
        .then(fn)
        .catch(function (e) {
          alert('No se pudo generar la imagen.\n' + (e && e.message ? e.message : e));
        })
        .then(function () {
          btn.disabled = false;
          btn.textContent = txt;
        });
    });
  }

  conEstado(btnShare, function () {
    return exportarBlob().then(function (blob) {
      var file = new File([blob], 'todopadel-placa.png', { type: 'image/png' });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        return navigator.share({ files: [file], title: 'TodoPadel' }).catch(function (e) {
          if (e && e.name === 'AbortError') return;   // el usuario canceló
          descargar(blob);                            // cualquier otro error -> descarga
        });
      }
      descargar(blob);                                // desktop / sin Web Share -> descarga
    });
  });

  conEstado(btnDownload, function () {
    return exportarBlob().then(descargar);
  });
})();
