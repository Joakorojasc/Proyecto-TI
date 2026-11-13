// Deja la casilla de términos bloqueada hasta que la persona abre el PDF.
// El servidor vuelve a comprobarlo: la marca la deja la propia petición del
// documento, así que esto no se puede saltar editando el HTML.
(function () {
    "use strict";

    var formulario = document.querySelector("form[data-exige-terminos]");
    if (!formulario) {
        return;
    }

    var casilla = formulario.querySelector("input[name='acepta_terminos']");
    var enlace = formulario.querySelector("[data-abre-terminos]");
    if (!casilla || !enlace) {
        return;
    }

    var aviso = document.createElement("span");
    aviso.className = "terminos-aviso";
    aviso.setAttribute("role", "status");
    aviso.textContent = "Abre el documento para poder aceptarlo.";
    enlace.parentNode.appendChild(aviso);

    function habilitar() {
        casilla.disabled = false;
        aviso.remove();
    }

    if (formulario.hasAttribute("data-terminos-abiertos")) {
        habilitar();
        return;
    }

    casilla.checked = false;
    casilla.disabled = true;

    enlace.addEventListener("click", function () {
        // La pestaña nueva ya pide el documento. Lo pedimos también desde acá
        // porque hay navegadores que abren el PDF en un visor aparte y la
        // sesión de esa petición no vuelve al portal.
        fetch(enlace.href, { credentials: "same-origin", cache: "no-store" })
            .then(habilitar)
            .catch(habilitar);
    });
})();
