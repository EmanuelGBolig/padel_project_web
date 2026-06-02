// Placas para redes (TP-placas): genera el QR y exporta la placa a PNG 1080×1920
// (html2canvas, scale 3 sobre un nodo base de 360px). Compartir nativo en mobile
// (Web Share API nivel 2) con fallback a descarga en desktop.
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

  function nombreArchivo() {
    return 'todopadel-placa.png';
  }

  function exportarBlob() {
    return html2canvas(placa, {
      scale: 3,                 // 360px * 3 = 1080px de ancho -> 1080×1920
      backgroundColor: null,
      useCORS: true,
      logging: false,
    }).then(function (canvas) {
      return new Promise(function (resolve) {
        canvas.toBlob(function (b) { resolve(b); }, 'image/png');
      });
    });
  }

  function descargar(blob) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = nombreArchivo();
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
      Promise.resolve(fn())
        .catch(function () {})
        .then(function () {
          btn.disabled = false;
          btn.textContent = txt;
        });
    });
  }

  conEstado(btnShare, function () {
    return exportarBlob().then(function (blob) {
      if (!blob) return;
      var file = new File([blob], nombreArchivo(), { type: 'image/png' });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        return navigator.share({ files: [file], title: 'TodoPadel' }).catch(function (e) {
          if (e && e.name === 'AbortError') return;   // el usuario canceló
          descargar(blob);
        });
      }
      descargar(blob);
    });
  });

  conEstado(btnDownload, function () {
    return exportarBlob().then(function (blob) { if (blob) descargar(blob); });
  });
})();
